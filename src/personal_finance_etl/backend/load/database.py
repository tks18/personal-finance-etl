import os

import duckdb
import psutil

from personal_finance_etl.backend.load.schema.gold import GOLD_DDL
from personal_finance_etl.backend.load.schema.meta import META_DDL
from personal_finance_etl.backend.load.schema.silver import SILVER_DDL


class DuckDBManager:
    """Owns the single persistent DuckDB file and its long-lived connection."""

    def __init__(self, base_path: str, db_name: str = "Personal_Finance_DB.duckdb"):
        self.base_path = base_path
        self.db_path = os.path.join(base_path, db_name)
        os.makedirs(base_path, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Returns the active connection. Raises if not opened."""
        if self._conn is None:
            raise RuntimeError("DuckDBManager.open() must be called before accessing conn.")
        return self._conn

    def open(self) -> duckdb.DuckDBPyConnection:
        """Opens the single long-lived connection. Called once at pipeline start."""
        if self._conn is not None:
            return self._conn
        self._conn = duckdb.connect(self.db_path)
        mem_gb = max(4, int(psutil.virtual_memory().total / (1024**3) * 0.75))
        self._conn.execute(f"PRAGMA memory_limit='{mem_gb}GB'")
        self._conn.execute("PRAGMA threads=4")
        return self._conn

    def close(self) -> None:
        """Checkpoints and closes the connection. Called once at pipeline end."""
        if self._conn is not None:
            try:
                self._conn.execute("VACUUM")
                self._conn.execute("CHECKPOINT")
            finally:
                self._conn.close()
                self._conn = None

    def ensure_schemas(self) -> None:
        """Creates bronze/silver/gold/meta schemas + all DDL tables if not exist.
        Uses the already-open connection."""
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS meta")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS silver")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
        self.conn.execute(META_DDL)
        self.conn.execute(SILVER_DDL)
        self.conn.execute(GOLD_DDL)
