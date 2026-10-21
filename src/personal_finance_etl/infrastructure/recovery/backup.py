"""Atomic backup, snapshot, and restore mechanics for coordinated database pairs.

Owns
----
- SystemBackupManager implementation coordinating SQLite Control Plane and DuckDB state.
- Coordinated atomic snapshot archive generation (pf_etl_snapshot_*.zip).
- Atomic restore delegation to SnapshotRestorer.
- File-lock synchronization and checkpointing during backup.

Does not own
-------------
- Typed snapshot/restore outcome models (owned by contracts.recovery).
- Database connection lifecycle (owned by infrastructure.warehouse/control_plane).
- Detailed archive unpacking and rollback execution (owned by infrastructure.recovery.restore).
- Application-level recovery orchestration (owned by application.recovery).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
import zipfile
from datetime import datetime

import duckdb
from filelock import FileLock, Timeout

from personal_finance_etl.contracts.recovery import (
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.filesystem.paths import get_temp_dir
from personal_finance_etl.infrastructure.recovery.restore import SnapshotRestorer

logger = logging.getLogger("personal_finance_etl.recovery.backup")

__all__ = ["SnapshotRestorer", "SystemBackupManager"]


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
        return SnapshotRestorer(
            base_path=self.base_path,
            sqlite_path=self.sqlite_path,
            duckdb_path=self.duckdb_path,
        ).restore_snapshot(zip_path)
