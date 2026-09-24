import os
import sqlite3

from personal_finance_etl.backend.load.schema.control_plane import RAW_DDL
from personal_finance_etl.backend.utils.logger import logger


class SQLiteManager:
    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db_path = os.path.join(base_path, db_name)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("SQLiteManager connection not opened.")
        return self._conn

    def open(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA cache_size = -64000;")
        self._conn.execute("PRAGMA mmap_size = 2147483648;")
        self._conn.execute("PRAGMA temp_store = MEMORY;")
        logger.info(f"Control Plane DB connected at {self.db_path}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Control Plane DB connection closed.")

    def ensure_schema(self) -> None:
        self.conn.executescript(RAW_DDL)
        self.conn.commit()

    def begin_transaction(self) -> None:
        self.conn.execute("BEGIN TRANSACTION;")

    def commit(self) -> None:
        self.conn.commit()
        logger.info("Control Plane transaction committed.")

    def rollback(self) -> None:
        if not self._conn:
            return
        try:
            self._conn.rollback()
            logger.warning("Control Plane transaction rolled back.")
        except Exception as e:
            logger.error(f"Failed to rollback Control Plane transaction: {e}")
