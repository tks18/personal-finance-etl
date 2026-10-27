"""Atomic restore and roll-back mechanics for coordinated database pairs.

Owns
----
- SnapshotRestorer: Atomically restores SQLite and DuckDB database pairs from a snapshot zip archive.
- Archive safety, member uniqueness, and path traversal validation.
- Rollback preservation guaranteeing the active database pair remains intact on failure.

Does not own
-------------
- Snapshot archive creation (owned by infrastructure.recovery.backup).
- Database integrity checks (owned by infrastructure.recovery.backup).
- Recovery workflow orchestration (owned by application.recovery).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile

import duckdb
from filelock import FileLock, Timeout

from personal_finance_etl.application.observability.diagnostics import get_observability_diagnostics
from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
)
from personal_finance_etl.infrastructure.filesystem.paths import get_temp_dir

diagnostics = get_observability_diagnostics("personal_finance_etl.recovery.restore")

__all__ = ["SnapshotRestorer"]


class SnapshotRestorer:
    """Coordinates atomic extraction, validation, and rollback-safe installation of snapshot archives.

    Parameters
    ----------
    base_path : str
        Directory containing the production database files.
    sqlite_path : str
        Full filesystem path to the production SQLite database file.
    duckdb_path : str
        Full filesystem path to the production DuckDB database file.
    """

    def __init__(
        self,
        base_path: str,
        sqlite_path: str,
        duckdb_path: str,
    ) -> None:
        self.base_path = base_path
        self.sqlite_path = sqlite_path
        self.duckdb_path = duckdb_path

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

    @staticmethod
    def _validate_duckdb(db_path: str) -> None:
        """Open and checkpoint an extracted copy before production files are touched.

        Parameters
        ----------
        db_path : str
            Filesystem path to the DuckDB file.
        """
        connection = duckdb.connect(db_path)
        try:
            connection.execute("CHECKPOINT")
        finally:
            connection.close()

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
            diagnostics.critical("RESTORE CRITICAL ERROR: Rollback failed: %s", rb_err)
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
                diagnostics.warning(
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
            diagnostics.error(msg)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )

        success, err_msg, rollback_success = self._install_restored_databases(temp_extract_dir)
        if not success:
            if rollback_success:
                diagnostics.warning(
                    "Restore installation failed; successfully rolled back to intact previous database pair: %s",
                    err_msg,
                )
                return RestoreResult(
                    outcome=RestoreOutcome.RESTORE_INSTALL_FAILED_ROLLED_BACK,
                    active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                    error_message=err_msg,
                )
            diagnostics.error(
                "Restore installation failed and rollback could not be guaranteed; operator inspection required."
            )
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_STATE_UNCERTAIN,
                active_database_state=ActiveDatabaseState.INSPECTION_REQUIRED,
                error_message=f"Installation failed ({err_msg}); rollback failed. Inspection required.",
            )

        diagnostics.info("Coordinated snapshot restored from %s to %s", zip_path, self.base_path)
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
            diagnostics.error(msg)
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
            diagnostics.error(msg)
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
            diagnostics.error("%s (%s)", msg, pe)
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=msg,
            )
        finally:
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
