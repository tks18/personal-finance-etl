"""Atomic backup, snapshot, and restore mechanics for coordinated database pairs.

Owns
----
- SystemBackupManager implementation coordinating SQLite Control Plane and DuckDB state.
- Coordinated atomic snapshot archive generation (pf_etl_snapshot_*.zip).
- Atomic restore and roll-back mechanisms preserving the active recovery unit.
- CRC validation and file-lock synchronization during backup/restore.

Does not own
-------------
- Typed snapshot/restore outcome models (owned by contracts.recovery).
- Database connection lifecycle (owned by infrastructure.warehouse/control_plane).
- Application-level recovery orchestration (owned by application.recovery).
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from datetime import datetime

import duckdb
from filelock import FileLock, Timeout

from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.filesystem.paths import get_temp_dir

logger = logging.getLogger("personal_finance_etl.recovery.backup")


class SystemBackupManager:
    """Coordinate SQLite Control Plane and DuckDB state as one recovery unit.

    Parameters
    ----------
    base_path : str
        Directory containing the production database files.
    sqlite_db_name : str, default="Raw_Documents.sqlite"
        Name of the SQLite control plane database file.
    duckdb_name : str, default="Personal_Finance_DB.duckdb"
        Name of the DuckDB analytical warehouse database file.
    """

    def __init__(
        self,
        base_path: str,
        sqlite_db_name: str = "Raw_Documents.sqlite",
        duckdb_name: str = "Personal_Finance_DB.duckdb",
    ) -> None:
        self.base_path = base_path
        self.sqlite_path = os.path.join(base_path, sqlite_db_name)
        self.duckdb_path = os.path.join(base_path, duckdb_name)
        self.backup_dir = os.path.join(base_path, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    @staticmethod
    def _checkpoint_duckdb(db_path: str) -> None:
        """Flush committed DuckDB state before a filesystem-level snapshot.

        Parameters
        ----------
        db_path : str
            Filesystem path to the DuckDB warehouse file.
        """
        connection = duckdb.connect(db_path)
        try:
            connection.execute("CHECKPOINT")
        finally:
            connection.close()

    @staticmethod
    def _validate_sqlite(db_path: str) -> None:
        """Verify structural integrity of an extracted SQLite database copy.

        Parameters
        ----------
        db_path : str
            Filesystem path to the SQLite file.

        Raises
        ------
        ValueError
            If SQLite integrity check returns any result other than 'ok'.
        """
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError(f"Snapshot SQLite integrity check failed: {result!r}")
        finally:
            connection.close()

    @classmethod
    def _validate_duckdb(cls, db_path: str) -> None:
        """Open and checkpoint an extracted copy before production files are touched.

        Parameters
        ----------
        db_path : str
            Filesystem path to the DuckDB file.
        """
        cls._checkpoint_duckdb(db_path)

    def _get_missing_databases(self) -> list[str]:
        """Return names of any required production databases missing from disk.

        Returns
        -------
        list[str]
            Basenames of missing required database files.
        """
        return [
            os.path.basename(path)
            for path in (self.sqlite_path, self.duckdb_path)
            if not os.path.isfile(path)
        ]

    def _create_sqlite_backup_copy(self, temp_sqlite_path: str) -> None:
        """Make an online backup copy of the SQLite control plane database.

        Parameters
        ----------
        temp_sqlite_path : str
            Target destination path for the temporary backup copy.
        """
        source = sqlite3.connect(self.sqlite_path, timeout=5)
        destination = sqlite3.connect(temp_sqlite_path, timeout=5)
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
            source.close()

    def _write_snapshot_archive(self, temp_zip: str, temp_sqlite: str) -> None:
        """Compress database files into the temporary snapshot archive and verify.

        Parameters
        ----------
        temp_zip : str
            Path to the temporary zip archive.
        temp_sqlite : str
            Path to the isolated SQLite copy.

        Raises
        ------
        ValueError
            If archive CRC verification fails.
        """
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_sqlite, os.path.basename(self.sqlite_path))
            archive.write(self.duckdb_path, os.path.basename(self.duckdb_path))

            duckdb_wal = self.duckdb_path + ".wal"
            if os.path.isfile(duckdb_wal):
                archive.write(duckdb_wal, os.path.basename(duckdb_wal))

        with zipfile.ZipFile(temp_zip, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"Snapshot archive verification failed: {bad_member}")

    def _execute_snapshot_under_lock(self) -> SnapshotResult:
        """Execute the coordinated snapshot workflow assuming pipeline lock is held.

        Returns
        -------
        SnapshotResult
            Result of the snapshot creation.
        """
        missing = self._get_missing_databases()
        if missing:
            msg = "Cannot create coordinated snapshot. Missing required database(s): " + ", ".join(
                missing
            )
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        zip_filename = f"pf_etl_snapshot_{ts}.zip"
        zip_path = os.path.join(self.backup_dir, zip_filename)
        temp_zip = os.path.join(self.backup_dir, f".{zip_filename}.{uuid.uuid4().hex}.tmp")
        temp_zip_to_clean: str | None = temp_zip

        self._checkpoint_duckdb(self.duckdb_path)

        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        temp_sqlite = os.path.join(temp_dir, f"snapshot_sqlite_{ts}_{uuid.uuid4().hex}.sqlite")

        try:
            self._create_sqlite_backup_copy(temp_sqlite)
            self._write_snapshot_archive(temp_zip, temp_sqlite)
            os.replace(temp_zip, zip_path)
            temp_zip_to_clean = None
            logger.info("Coordinated snapshot created at %s", zip_path)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_PUBLISHED, zip_path=zip_path)
        finally:
            for path in (temp_sqlite, temp_zip_to_clean):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as cleanup_error:
                        logger.warning(
                            "Could not remove temporary snapshot file %s: %s", path, cleanup_error
                        )

    def create_snapshot(self) -> SnapshotResult:
        """Create an atomic archive of a checkpointed, coordinated database pair.

        Returns
        -------
        SnapshotResult
            Outcome and path to the created zip archive.
        """
        missing = self._get_missing_databases()
        if missing:
            msg = "Cannot create coordinated snapshot. Missing required database(s): " + ", ".join(
                missing
            )
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        try:
            with FileLock(lock_path, timeout=0):
                return self._execute_snapshot_under_lock()
        except Timeout:
            msg = "Cannot create snapshot: Pipeline is currently running."
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)
        except Exception as e:
            msg = f"Failed to create coordinated snapshot: {e}"
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)

    @staticmethod
    def _validate_archive_members(
        members: list[zipfile.ZipInfo],
        required_names: set[str],
        allowed_names: set[str],
    ) -> None:
        """Validate safety, uniqueness, and completeness of zip archive members.

        Parameters
        ----------
        members : list[zipfile.ZipInfo]
            List of zip member metadata objects.
        required_names : set[str]
            Set of mandatory filenames expected in the archive.
        allowed_names : set[str]
            Set of all allowed filenames in the archive.

        Raises
        ------
        ValueError
            If validation checks fail.
        """
        names = [item.filename.replace("\\", "/") for item in members]
        member_names = set(names)

        if len(names) != len(member_names):
            raise ValueError("Invalid coordinated snapshot: duplicate archive members.")

        invalid_paths = {
            name
            for name in names
            if name.startswith("/") or "/" in name or "\\" in name or name in {"", ".", ".."}
        }
        if invalid_paths:
            raise ValueError(
                f"Invalid coordinated snapshot path(s): {', '.join(sorted(invalid_paths))}"
            )

        symlinks = [item.filename for item in members if stat.S_ISLNK(item.external_attr >> 16)]
        if symlinks:
            raise ValueError("Invalid coordinated snapshot: symbolic links are not allowed.")

        missing = required_names - member_names
        if missing:
            raise ValueError(
                f"Invalid coordinated snapshot. Missing required database(s): {', '.join(sorted(missing))}"
            )

        unexpected = member_names - allowed_names
        if unexpected:
            raise ValueError(
                f"Invalid coordinated snapshot. Unexpected file(s): {', '.join(sorted(unexpected))}"
            )

    def _validate_and_extract_archive(
        self,
        zip_path: str,
        temp_extract_dir: str,
    ) -> None:
        """Validate archive structure, member security, file integrity, and extract to temp directory.

        Parameters
        ----------
        zip_path : str
            Filesystem path to the zip archive.
        temp_extract_dir : str
            Destination directory for extracted databases.
        """
        required_names = {os.path.basename(self.sqlite_path), os.path.basename(self.duckdb_path)}
        duckdb_wal_name = os.path.basename(self.duckdb_path) + ".wal"
        allowed_names = required_names | {duckdb_wal_name}

        with zipfile.ZipFile(zip_path, "r") as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            self._validate_archive_members(members, required_names, allowed_names)

            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"Snapshot archive is corrupt: {bad_member}")

            archive.extractall(temp_extract_dir)

        extracted_sqlite = os.path.join(temp_extract_dir, os.path.basename(self.sqlite_path))
        extracted_duckdb = os.path.join(temp_extract_dir, os.path.basename(self.duckdb_path))

        self._validate_sqlite(extracted_sqlite)
        self._validate_duckdb(extracted_duckdb)

    @staticmethod
    def _backup_active_files(active_paths: list[str]) -> list[tuple[str, str]]:
        """Rename active files to .restore_bak copies for rollback protection.

        Parameters
        ----------
        active_paths : list[str]
            Active database file paths to back up.

        Returns
        -------
        list[tuple[str, str]]
            Pairs of (original_path, backup_path).
        """
        backed_up: list[tuple[str, str]] = []
        for original_path in active_paths:
            if not os.path.exists(original_path):
                continue
            backup_path = original_path + ".restore_bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.replace(original_path, backup_path)
            backed_up.append((original_path, backup_path))
        return backed_up

    @staticmethod
    def _rollback_active_files(
        backed_up_files: list[tuple[str, str]],
        installed_paths: list[str],
    ) -> bool:
        """Roll back partially installed files to intact previous states.

        Parameters
        ----------
        backed_up_files : list[tuple[str, str]]
            Original backup mappings.
        installed_paths : list[str]
            Files moved into production before failure.

        Returns
        -------
        bool
            True if rollback succeeded cleanly; False otherwise.
        """
        try:
            for installed_path in reversed(installed_paths):
                if os.path.exists(installed_path):
                    os.remove(installed_path)

            for original_path, backup_path in reversed(backed_up_files):
                if os.path.exists(backup_path):
                    if os.path.exists(original_path):
                        os.remove(original_path)
                    os.replace(backup_path, original_path)
            return True
        except Exception as rb_err:
            logger.critical("RESTORE CRITICAL ERROR: Rollback failed: %s", rb_err)
            return False

    @staticmethod
    def _cleanup_restore_backups(backed_up_files: list[tuple[str, str]]) -> None:
        """Remove .restore_bak temporary recovery copies after successful install.

        Parameters
        ----------
        backed_up_files : list[tuple[str, str]]
            Pairs of (original_path, backup_path).
        """
        for _, backup_path in backed_up_files:
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            except OSError as cleanup_error:
                logger.warning(
                    "Restored successfully but could not remove recovery file %s: %s",
                    backup_path,
                    cleanup_error,
                )

    def _install_restored_databases(
        self,
        temp_extract_dir: str,
    ) -> tuple[bool, str | None, bool]:
        """Atomically swap current databases with extracted backup files, with full rollback on failure.

        Parameters
        ----------
        temp_extract_dir : str
            Directory containing extracted validated database files.

        Returns
        -------
        tuple[bool, str | None, bool]
            (success, error_message, rollback_success).
        """
        duckdb_wal_name = os.path.basename(self.duckdb_path) + ".wal"
        restore_names = [os.path.basename(self.sqlite_path), os.path.basename(self.duckdb_path)]
        if os.path.isfile(os.path.join(temp_extract_dir, duckdb_wal_name)):
            restore_names.append(duckdb_wal_name)

        active_paths = [
            self.sqlite_path,
            self.sqlite_path + "-wal",
            self.sqlite_path + "-shm",
            self.duckdb_path,
            self.duckdb_path + ".wal",
        ]
        backed_up_files: list[tuple[str, str]] = []
        installed_paths: list[str] = []

        try:
            backed_up_files = self._backup_active_files(active_paths)
            for name in restore_names:
                src = os.path.join(temp_extract_dir, name)
                dst = os.path.join(self.base_path, name)
                shutil.move(src, dst)
                installed_paths.append(dst)
        except Exception as install_err:
            rollback_ok = self._rollback_active_files(backed_up_files, installed_paths)
            return False, str(install_err), rollback_ok

        self._cleanup_restore_backups(backed_up_files)
        return True, None, True

    def _execute_restore_under_lock(self, zip_path: str, temp_extract_dir: str) -> RestoreResult:
        """Perform validation and swap under active pipeline lock.

        Parameters
        ----------
        zip_path : str
            Filesystem path to the snapshot zip archive.
        temp_extract_dir : str
            Isolated extraction directory.

        Returns
        -------
        RestoreResult
            Detailed restore outcome and safety status.
        """
        try:
            self._validate_and_extract_archive(zip_path, temp_extract_dir)
        except Exception as val_err:
            msg = f"Snapshot validation failed: {val_err}"
            logger.error(msg)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )

        success, err_msg, rollback_success = self._install_restored_databases(temp_extract_dir)
        if not success:
            if rollback_success:
                logger.warning(
                    "Restore installation failed; successfully rolled back to intact previous database pair: %s",
                    err_msg,
                )
                return RestoreResult(
                    outcome=RestoreOutcome.RESTORE_INSTALL_FAILED_ROLLED_BACK,
                    active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                    error_message=err_msg,
                )
            logger.error(
                "Restore installation failed and rollback could not be guaranteed; operator inspection required."
            )
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_STATE_UNCERTAIN,
                active_database_state=ActiveDatabaseState.INSPECTION_REQUIRED,
                error_message=f"Installation failed ({err_msg}); rollback failed. Inspection required.",
            )

        logger.info("Coordinated snapshot restored from %s to %s", zip_path, self.base_path)
        return RestoreResult(
            outcome=RestoreOutcome.RESTORE_SUCCEEDED,
            active_database_state=ActiveDatabaseState.NEW_PAIR_INSTALLED,
        )

    def restore_snapshot(self, zip_path: str) -> RestoreResult:
        """Restore the database pair atomically, reporting outcome and active database state.

        Parameters
        ----------
        zip_path : str
            Filesystem path to the snapshot zip archive.

        Returns
        -------
        RestoreResult
            Detailed restore outcome and safety status.
        """
        if not os.path.isfile(zip_path):
            msg = f"Backup file not found: {zip_path}"
            logger.error(msg)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        temp_root = get_temp_dir()
        os.makedirs(temp_root, exist_ok=True)
        temp_extract_dir = tempfile.mkdtemp(prefix="snapshot_restore_", dir=temp_root)

        try:
            with FileLock(lock_path, timeout=0):
                return self._execute_restore_under_lock(zip_path, temp_extract_dir)
        except Timeout:
            msg = "Cannot restore snapshot: Pipeline is currently running."
            logger.error(msg)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )
        except PermissionError as pe:
            msg = (
                "Cannot restore snapshot: A database or backup file is currently in use. "
                "Close active dashboards or database tools and try again."
            )
            logger.error("%s (%s)", msg, pe)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )
        finally:
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
