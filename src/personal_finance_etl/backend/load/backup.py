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
        if not os.path.exists(self.sqlite_path) and not os.path.exists(self.duckdb_path):
            logger.warning("Neither SQLite nor DuckDB files found for backup.")
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
        Restores both databases from a coordinated snapshot zip safely,
        preventing stale sidecar conflicts.
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Backup file not found: {zip_path}")

        lock_path = os.path.join(self.base_path, "pipeline.lock")
        try:
            lock = FileLock(lock_path, timeout=0)
            with lock:
                temp_extract_dir = os.path.join(get_temp_dir(), "snapshot_restore")
                os.makedirs(temp_extract_dir, exist_ok=True)

                try:
                    with zipfile.ZipFile(zip_path, "r") as zipf:
                        zipf.extractall(temp_extract_dir)

                    target_items = os.listdir(temp_extract_dir)

                    # 1. Pre-flight check / Rename existing active databases to .bak
                    backed_up_files: list[tuple[str, str]] = []
                    try:
                        for item in target_items:
                            dst = os.path.join(self.base_path, item)
                            if os.path.exists(dst):
                                bak_path = dst + ".bak"
                                if os.path.exists(bak_path):
                                    os.remove(bak_path)
                                os.rename(dst, bak_path)
                                backed_up_files.append((bak_path, dst))

                        # Now remove stale sidecars since main files are successfully detached
                        sidecars = [
                            self.sqlite_path + "-wal",
                            self.sqlite_path + "-shm",
                            self.duckdb_path + ".wal",
                        ]
                        for sc in sidecars:
                            if os.path.exists(sc):
                                os.remove(sc)

                        # 2. Move new files into place
                        for item in target_items:
                            src = os.path.join(temp_extract_dir, item)
                            dst = os.path.join(self.base_path, item)
                            if os.path.isfile(src):
                                shutil.move(src, dst)

                        # 3. Clean up .bak files
                        for bak_path, _ in backed_up_files:
                            try:
                                os.remove(bak_path)
                            except OSError:
                                pass

                    except PermissionError as pe:
                        # Rollback
                        for bak_path, orig_path in backed_up_files:
                            if os.path.exists(bak_path):
                                os.rename(bak_path, orig_path)
                        raise PermissionError(
                            "Cannot restore snapshot: The database is currently being read by another program. "
                            "Please close all active dashboards or tools and try again."
                        ) from pe
                    except Exception as e:
                        # Rollback on other errors too
                        for bak_path, orig_path in backed_up_files:
                            if os.path.exists(bak_path) and not os.path.exists(orig_path):
                                os.rename(bak_path, orig_path)
                        raise e
                finally:
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)

                logger.info(f"Coordinated snapshot restored from {zip_path} to {self.base_path}")
        except Timeout as err:
            logger.error("Cannot restore snapshot: Pipeline is currently running.")
            raise RuntimeError("Cannot restore snapshot: Pipeline is currently running.") from err
