import os
import shutil
import sqlite3
import zipfile
from datetime import datetime

from filelock import FileLock, Timeout

from personal_finance_etl.backend.utils.helpers import get_temp_dir
from personal_finance_etl.backend.utils.logger import logger


class SystemBackupManager:
    """
    Coordinates backups of both the SQLite Control Plane (Raw_Documents.sqlite)
    and the DuckDB Analytical Database (Personal_Finance_DB.duckdb) to ensure
    they are treated as one logical recovery unit.
    """

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

    def create_snapshot(self) -> str | None:
        """
        Creates a coordinated snapshot of both databases and zips them into a single archive.
        Returns the path to the backup zip file.
        """
        missing: list[str] = []
        if not os.path.exists(self.sqlite_path):
            missing.append(os.path.basename(self.sqlite_path))
        if not os.path.exists(self.duckdb_path):
            missing.append(os.path.basename(self.duckdb_path))

        if missing:
            logger.error(
                "Cannot create coordinated snapshot. Missing required database(s): "
                + ", ".join(missing)
            )
            return None

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        try:
            lock = FileLock(lock_path, timeout=0)
            with lock:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = f"pf_etl_snapshot_{ts}.zip"
                zip_path = os.path.join(self.backup_dir, zip_filename)

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    if os.path.exists(self.sqlite_path):
                        # Use tempfile to prevent orphaned files on crash
                        temp_sqlite = os.path.join(get_temp_dir(), f"temp_{ts}.sqlite")

                        try:
                            # Use sqlite3.backup to safely copy WAL into a single file
                            source = sqlite3.connect(self.sqlite_path)
                            dest = sqlite3.connect(temp_sqlite)
                            with source, dest:
                                source.backup(dest)
                            dest.close()
                            source.close()

                            zipf.write(temp_sqlite, os.path.basename(self.sqlite_path))
                        finally:
                            if os.path.exists(temp_sqlite):
                                os.remove(temp_sqlite)

                    if os.path.exists(self.duckdb_path):
                        zipf.write(self.duckdb_path, os.path.basename(self.duckdb_path))

                        # DuckDB doesn't have an online single-file backup API like SQLite.
                        # But since we hold the lock, it's safe to just backup the WAL file
                        # if it exists from a previous ungraceful shutdown.
                        duckdb_wal = self.duckdb_path + ".wal"
                        if os.path.exists(duckdb_wal):
                            zipf.write(duckdb_wal, os.path.basename(duckdb_wal))

                logger.info(f"Coordinated snapshot created at {zip_path}")
                return zip_path
        except Timeout:
            logger.error("Cannot create snapshot: Pipeline is currently running.")
            return None

    def restore_snapshot(self, zip_path: str) -> None:
        """
        Restores the coordinated SQLite + DuckDB snapshot as one recovery unit.
        The active pair is either fully replaced or fully rolled back.
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Backup file not found: {zip_path}")

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        try:
            lock = FileLock(lock_path, timeout=0)
            with lock:
                temp_extract_dir = os.path.join(get_temp_dir(), "snapshot_restore")
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                os.makedirs(temp_extract_dir, exist_ok=True)

                try:
                    required_names = {
                        os.path.basename(self.sqlite_path),
                        os.path.basename(self.duckdb_path),
                    }
                    duckdb_wal_name = os.path.basename(self.duckdb_path) + ".wal"
                    allowed_names = required_names | {duckdb_wal_name}

                    with zipfile.ZipFile(zip_path, "r") as zipf:
                        members = [info for info in zipf.infolist() if not info.is_dir()]
                        member_names = {info.filename.replace("\\", "/") for info in members}

                        # Coordinated snapshots are intentionally flat archives. Reject
                        # nested/absolute/traversal paths before extracting anything.
                        invalid_paths = {
                            name
                            for name in member_names
                            if name.startswith("/")
                            or name.startswith("../")
                            or "/../" in name
                            or "/" in name
                        }
                        if invalid_paths:
                            raise ValueError(
                                "Invalid coordinated snapshot path(s): "
                                + ", ".join(sorted(invalid_paths))
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

                        zipf.extractall(temp_extract_dir)

                    restore_names = [
                        os.path.basename(self.sqlite_path),
                        os.path.basename(self.duckdb_path),
                    ]
                    if duckdb_wal_name in member_names:
                        restore_names.append(duckdb_wal_name)

                    # Preserve the complete old recovery unit, including sidecars, so a
                    # failed restore can put the exact previous state back.
                    active_paths = [
                        self.sqlite_path,
                        self.sqlite_path + "-wal",
                        self.sqlite_path + "-shm",
                        self.duckdb_path,
                        self.duckdb_path + ".wal",
                    ]
                    backed_up_files: list[tuple[str, str]] = []

                    try:
                        for original_path in active_paths:
                            if not os.path.exists(original_path):
                                continue
                            backup_path = original_path + ".restore_bak"
                            if os.path.exists(backup_path):
                                os.remove(backup_path)
                            os.replace(original_path, backup_path)
                            backed_up_files.append((original_path, backup_path))

                        # Install only files belonging to this snapshot. SQLite snapshots
                        # are consolidated by sqlite3.backup(), so no SQLite sidecars are
                        # expected in the archive.
                        for name in restore_names:
                            src = os.path.join(temp_extract_dir, name)
                            dst = os.path.join(self.base_path, name)
                            os.replace(src, dst)

                        # Restore succeeded: discard the old recovery unit.
                        for _, backup_path in backed_up_files:
                            if os.path.exists(backup_path):
                                os.remove(backup_path)

                    except Exception:
                        # Remove every partially installed member of the new snapshot.
                        for name in restore_names:
                            dst = os.path.join(self.base_path, name)
                            if os.path.exists(dst):
                                os.remove(dst)

                        # Put the exact old recovery unit back, including WAL/SHM files.
                        for original_path, backup_path in reversed(backed_up_files):
                            if os.path.exists(backup_path):
                                os.replace(backup_path, original_path)
                        raise

                except PermissionError as pe:
                    raise PermissionError(
                        "Cannot restore snapshot: The database is currently being read by another program. "
                        "Please close all active dashboards or tools and try again."
                    ) from pe
                finally:
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)

                logger.info(f"Coordinated snapshot restored from {zip_path} to {self.base_path}")
        except Timeout as err:
            logger.error("Cannot restore snapshot: Pipeline is currently running.")
            raise RuntimeError("Cannot restore snapshot: Pipeline is currently running.") from err