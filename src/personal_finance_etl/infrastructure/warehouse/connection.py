"""DuckDB analytical warehouse connection and schema management.

Owns
----
- Single persistent DuckDB database file lifecycle and long-lived connection handle.
- Memory and threading PRAGMA tuning for analytical queries.
- Schema creation (bronze, silver, gold, meta) and DDL initialization.
- Safe connection shutdown with VACUUM and CHECKPOINT maintenance.

Does not own
-------------
- SQLite control plane database connection (owned by infrastructure.control_plane.connection).
- Layer-specific table persistence logic (owned by bronze.py, silver.py, gold.py, meta.py).
"""

from __future__ import annotations

import os

import duckdb
import psutil

from personal_finance_etl.application.observability.diagnostics import get_observability_diagnostics
from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL
from personal_finance_etl.infrastructure.warehouse.schema.meta import META_DDL
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.connection")


class DuckDBManager:
    """Owns the single persistent DuckDB warehouse database and its connection handle.

    Parameters
    ----------
    base_path : str
        Base directory containing the DuckDB database file.
    db_name : str, default="Personal_Finance_DB.duckdb"
        Name of the database file.
    """

    def __init__(self, base_path: str, db_name: str = "Personal_Finance_DB.duckdb") -> None:
        self.base_path = base_path
        self.db_path = os.path.join(base_path, db_name)
        if base_path:
            os.makedirs(base_path, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Active DuckDB connection handle.

        Raises
        ------
        RuntimeError
            If open() has not been called.
        """
        if self._conn is None:
            raise RuntimeError("DuckDBManager.open() must be called before accessing conn.")
        return self._conn

    def open(self) -> duckdb.DuckDBPyConnection:
        """Open the long-lived DuckDB connection and tune PRAGMA parameters.

        Returns
        -------
        duckdb.DuckDBPyConnection
            Configured DuckDB connection instance.
        """
        if self._conn is not None:
            return self._conn
        diagnostics.debug("DuckDB Warehouse: Opening connection to %s", self.db_path)
        self._conn = duckdb.connect(self.db_path)
        mem_gb = max(4, int(psutil.virtual_memory().total / (1024**3) * 0.75))
        self._conn.execute(f"PRAGMA memory_limit='{mem_gb}GB'")  # nosec B608
        self._conn.execute("PRAGMA threads=4")
        diagnostics.debug(
            "DuckDB Warehouse: Connection configured: memory_limit=%dGB, threads=4", mem_gb
        )
        return self._conn

    def close(self) -> None:
        """Run checkpoint and vacuum, then close the connection."""
        if self._conn is not None:
            diagnostics.debug("DuckDB Warehouse: Commencing VACUUM and CHECKPOINT sequence...")
            try:
                self._conn.execute("VACUUM")
                self._conn.execute("CHECKPOINT")
                diagnostics.debug("DuckDB Warehouse: Checkpoint successful. Closing connection.")
            except duckdb.Error as e:
                diagnostics.warning("DuckDB Warehouse: Cleanup VACUUM/CHECKPOINT failed: %s", e)
            finally:
                self._conn.close()
                self._conn = None

    def ensure_schemas(self) -> None:
        """Create bronze, silver, gold, and meta schemas and initialize DDL tables."""
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS meta")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS silver")
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
        self.conn.execute(META_DDL)
        self.conn.execute(SILVER_DDL)
        self.conn.execute(GOLD_DDL)
