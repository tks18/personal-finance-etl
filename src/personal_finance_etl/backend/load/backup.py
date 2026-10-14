import os
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import duckdb
from filelock import FileLock, Timeout

from personal_finance_etl.backend.utils.helpers import get_temp_dir
from personal_finance_etl.backend.utils.logger import logger


class SnapshotOutcome(StrEnum):
    SNAPSHOT_STARTED = "SNAPSHOT_STARTED"
    SNAPSHOT_VALIDATED = "SNAPSHOT_VALIDATED"
    SNAPSHOT_PUBLISHED = "SNAPSHOT_PUBLISHED"
    SNAPSHOT_FAILED = "SNAPSHOT_FAILED"


class RestoreOutcome(StrEnum):
    RESTORE_VALIDATION_FAILED = "RESTORE_VALIDATION_FAILED"
    RESTORE_INSTALL_STARTED = "RESTORE_INSTALL_STARTED"
    RESTORE_SUCCEEDED = "RESTORE_SUCCEEDED"
    RESTORE_INSTALL_FAILED_ROLLED_BACK = "RESTORE_INSTALL_FAILED_ROLLED_BACK"
    RESTORE_STATE_UNCERTAIN = "RESTORE_STATE_UNCERTAIN"


class ActiveDatabaseState(StrEnum):
    PREVIOUS_PAIR_INTACT = "PREVIOUS_PAIR_INTACT"
    NEW_PAIR_INSTALLED = "NEW_PAIR_INSTALLED"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"


@dataclass
class SnapshotResult:
    outcome: SnapshotOutcome
    zip_path: str | None = None
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.outcome == SnapshotOutcome.SNAPSHOT_PUBLISHED and self.zip_path is not None

    def __bool__(self) -> bool:
        return self.is_success

    def __str__(self) -> str:
        return self.zip_path or self.error_message or self.outcome.value


@dataclass
class RestoreResult:
    outcome: RestoreOutcome
    active_database_state: ActiveDatabaseState
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return (
            self.outcome == RestoreOutcome.RESTORE_SUCCEEDED
            and self.active_database_state == ActiveDatabaseState.NEW_PAIR_INSTALLED
        )

    def __bool__(self) -> bool:
        return self.is_success


class SystemBackupManager:
    """Coordinate SQLite Control Plane and DuckDB state as one recovery unit."""

    def __init__(
        self,
        base_path: str,
        sqlite_db_name: str = "Raw_Documents.sqlite",
        duckdb_name: str = "Personal_Finance_DB.duckdb",
    ):
        self.base_path = base_path
        self.sqlite_path = os.path.join(base_path, sqlite_db_name)
        self.duckdb_path = os.path.join(base_path, duckdb_name)
        self.backup_dir = os.path.join(base_path, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

    @staticmethod
    def _checkpoint_duckdb(db_path: str) -> None:
        """Flush committed DuckDB state before a filesystem-level snapshot."""

        connection = duckdb.connect(db_path)
        try:
            connection.execute("CHECKPOINT")
        finally:
            connection.close()

    @staticmethod
    def _validate_sqlite(db_path: str) -> None:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError(f"Snapshot SQLite integrity check failed: {result!r}")
        finally:
            connection.close()

    @classmethod
    def _validate_duckdb(cls, db_path: str) -> None:
        """Open and checkpoint an extracted copy before production files are touched."""
        cls._checkpoint_duckdb(db_path)

    def create_snapshot(self) -> SnapshotResult:
        """Create an atomic archive of a checkpointed, coordinated database pair."""
        missing = [
            os.path.basename(path)
            for path in (self.sqlite_path, self.duckdb_path)
            if not os.path.isfile(path)
        ]
        if missing:
            msg = (
                "Cannot create coordinated snapshot. Missing required database(s): "
                + ", ".join(missing)
            )
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        temp_sqlite: str | None = None
        temp_zip: str | None = None
        try:
            with FileLock(lock_path, timeout=0):
                # Recheck after taking the production lock to avoid a check/use race.
                missing = [
                    os.path.basename(path)
                    for path in (self.sqlite_path, self.duckdb_path)
                    if not os.path.isfile(path)
                ]
                if missing:
                    msg = (
                        "Cannot create coordinated snapshot. Missing required database(s): "
                        + ", ".join(missing)
                    )
                    logger.error(msg)
                    return SnapshotResult(
                        outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg
                    )

                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                zip_filename = f"pf_etl_snapshot_{ts}.zip"
                zip_path = os.path.join(self.backup_dir, zip_filename)
                temp_zip = os.path.join(self.backup_dir, f".{zip_filename}.{uuid.uuid4().hex}.tmp")

                # A database file copy is only a sound boundary after DuckDB has
                # checkpointed its committed WAL state. If checkpoint fails, fail closed.
                self._checkpoint_duckdb(self.duckdb_path)

                temp_dir = get_temp_dir()
                os.makedirs(temp_dir, exist_ok=True)
                temp_sqlite = os.path.join(
                    temp_dir, f"snapshot_sqlite_{ts}_{uuid.uuid4().hex}.sqlite"
                )
                source = sqlite3.connect(self.sqlite_path, timeout=5)
                destination = sqlite3.connect(temp_sqlite, timeout=5)
                try:
                    source.backup(destination)
                    destination.commit()
                finally:
                    destination.close()
                    source.close()

                with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(temp_sqlite, os.path.basename(self.sqlite_path))
                    archive.write(self.duckdb_path, os.path.basename(self.duckdb_path))

                    # A WAL should normally be consumed by CHECKPOINT. If DuckDB
                    # leaves one, preserve it with its matching database file.
                    duckdb_wal = self.duckdb_path + ".wal"
                    if os.path.isfile(duckdb_wal):
                        archive.write(duckdb_wal, os.path.basename(duckdb_wal))

                with zipfile.ZipFile(temp_zip, "r") as archive:
                    bad_member = archive.testzip()
                    if bad_member is not None:
                        raise ValueError(f"Snapshot archive verification failed: {bad_member}")

                # Publish only a complete, CRC-verified archive.
                os.replace(temp_zip, zip_path)
                temp_zip = None
                logger.info(f"Coordinated snapshot created at {zip_path}")
                return SnapshotResult(
                    outcome=SnapshotOutcome.SNAPSHOT_PUBLISHED,
                    zip_path=zip_path,
                )
        except Timeout:
            msg = "Cannot create snapshot: Pipeline is currently running."
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)
        except Exception as e:
            msg = f"Failed to create coordinated snapshot: {e}"
            logger.error(msg)
            return SnapshotResult(outcome=SnapshotOutcome.SNAPSHOT_FAILED, error_message=msg)
        finally:
            for path in (temp_sqlite, temp_zip):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as cleanup_error:
                        logger.warning(
                            f"Could not remove temporary snapshot file {path}: {cleanup_error}"
                        )

    def restore_snapshot(self, zip_path: str) -> RestoreResult:
        """Restore the pair atomically, reporting outcome and active database state."""
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
                required_names = {
                    os.path.basename(self.sqlite_path),
                    os.path.basename(self.duckdb_path),
                }
                duckdb_wal_name = os.path.basename(self.duckdb_path) + ".wal"
                allowed_names = required_names | {duckdb_wal_name}

                # Validation phase
                try:
                    with zipfile.ZipFile(zip_path, "r") as archive:
                        members = [item for item in archive.infolist() if not item.is_dir()]
                        names = [item.filename.replace("\\", "/") for item in members]
                        member_names = set(names)

                        if len(names) != len(member_names):
                            raise ValueError(
                                "Invalid coordinated snapshot: duplicate archive members."
                            )

                        invalid_paths = {
                            name
                            for name in names
                            if name.startswith("/")
                            or "/" in name
                            or "\\" in name
                            or name in {"", ".", ".."}
                        }
                        if invalid_paths:
                            raise ValueError(
                                "Invalid coordinated snapshot path(s): "
                                + ", ".join(sorted(invalid_paths))
                            )

                        symlinks = [
                            item.filename
                            for item in members
                            if stat.S_ISLNK(item.external_attr >> 16)
                        ]
                        if symlinks:
                            raise ValueError(
                                "Invalid coordinated snapshot: symbolic links are not allowed."
                            )

                        missing = required_names - member_names
                        if missing:
                            raise ValueError(
                                "Invalid coordinated snapshot. Missing required database(s): "
                                + ", ".join(sorted(missing))
                            )

                        unexpected = member_names - allowed_names
                        if unexpected:
                            raise ValueError(
                                "Invalid coordinated snapshot. Unexpected file(s): "
                                + ", ".join(sorted(unexpected))
                            )

                        bad_member = archive.testzip()
                        if bad_member is not None:
                            raise ValueError(f"Snapshot archive is corrupt: {bad_member}")

                        archive.extractall(temp_extract_dir)

                    extracted_sqlite = os.path.join(
                        temp_extract_dir, os.path.basename(self.sqlite_path)
                    )
                    extracted_duckdb = os.path.join(
                        temp_extract_dir, os.path.basename(self.duckdb_path)
                    )

                    # Validate the extracted pair before moving any production file.
                    self._validate_sqlite(extracted_sqlite)
                    self._validate_duckdb(extracted_duckdb)
                except Exception as val_err:
                    msg = f"Snapshot validation failed: {val_err}"
                    logger.error(msg)
                    return RestoreResult(
                        outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                        active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                        error_message=msg,
                    )

                # Installation phase
                restore_names = [
                    os.path.basename(self.sqlite_path),
                    os.path.basename(self.duckdb_path),
                ]
                extracted_wal = os.path.join(temp_extract_dir, duckdb_wal_name)
                if os.path.isfile(extracted_wal):
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
                    # Preserve every member of the old recovery unit first.
                    for original_path in active_paths:
                        if not os.path.exists(original_path):
                            continue
                        backup_path = original_path + ".restore_bak"
                        if os.path.exists(backup_path):
                            os.remove(backup_path)
                        os.replace(original_path, backup_path)
                        backed_up_files.append((original_path, backup_path))

                    # Install the already validated new pair.
                    for name in restore_names:
                        src = os.path.join(temp_extract_dir, name)
                        dst = os.path.join(self.base_path, name)
                        shutil.move(src, dst)
                        installed_paths.append(dst)
                except Exception as install_err:
                    rollback_success = True
                    try:
                        for installed_path in reversed(installed_paths):
                            if os.path.exists(installed_path):
                                os.remove(installed_path)

                        for original_path, backup_path in reversed(backed_up_files):
                            if os.path.exists(backup_path):
                                if os.path.exists(original_path):
                                    os.remove(original_path)
                                os.replace(backup_path, original_path)
                    except Exception as rb_err:
                        rollback_success = False
                        logger.critical(
                            "RESTORE CRITICAL ERROR: Installation failed and rollback also failed: %s",
                            rb_err,
                        )

                    if rollback_success:
                        logger.warning(
                            "Restore installation failed; successfully rolled back to intact previous database pair: %s",
                            install_err,
                        )
                        return RestoreResult(
                            outcome=RestoreOutcome.RESTORE_INSTALL_FAILED_ROLLED_BACK,
                            active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                            error_message=str(install_err),
                        )
                    else:
                        logger.error(
                            "Restore installation failed and rollback could not be guaranteed; operator inspection required."
                        )
                        return RestoreResult(
                            outcome=RestoreOutcome.RESTORE_STATE_UNCERTAIN,
                            active_database_state=ActiveDatabaseState.INSPECTION_REQUIRED,
                            error_message=f"Installation failed ({install_err}); rollback failed. Inspection required.",
                        )

                # Installation is complete. Backup cleanup is non-transactional.
                for _, backup_path in backed_up_files:
                    try:
                        if os.path.exists(backup_path):
                            os.remove(backup_path)
                    except OSError as cleanup_error:
                        logger.warning(
                            f"Restored successfully but could not remove recovery file "
                            f"{backup_path}: {cleanup_error}"
                        )

                logger.info(f"Coordinated snapshot restored from {zip_path} to {self.base_path}")
                return RestoreResult(
                    outcome=RestoreOutcome.RESTORE_SUCCEEDED,
                    active_database_state=ActiveDatabaseState.NEW_PAIR_INSTALLED,
                )
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
