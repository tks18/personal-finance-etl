import os
import zipfile
from datetime import datetime

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

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"pf_etl_snapshot_{ts}.zip"
        zip_path = os.path.join(self.backup_dir, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(self.sqlite_path):
                zipf.write(self.sqlite_path, os.path.basename(self.sqlite_path))
            if os.path.exists(self.duckdb_path):
                zipf.write(self.duckdb_path, os.path.basename(self.duckdb_path))

        logger.info(f"Coordinated snapshot created at {zip_path}")
        return zip_path

    def restore_snapshot(self, zip_path: str) -> None:
        """
        Restores both databases from a coordinated snapshot zip.
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Backup file not found: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zipf:
            zipf.extractall(self.base_path)

        logger.info(f"Coordinated snapshot restored from {zip_path} to {self.base_path}")
