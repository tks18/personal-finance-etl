"""SQLite connection and transaction management for the durable control plane.

Owns
----
- SQLite connection lifecycle, WAL journal mode, and foreign key enforcement.
- Savepoint-based nested atomic transaction management (atomic() context manager).
- Schema bootstrap orchestration delegating DDL execution and validation to schema.py.
- SQLite transaction primitives (begin_transaction, commit, rollback).

Does not own
-------------
- Specific table payload reading/writing (owned by run_repository and artifact_repository).
- Schema DDL, migrations, and column definitions (owned by schema.py).
- DuckDB analytical warehouse connections (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from personal_finance_etl.infrastructure.control_plane.schema import (
    CURRENT_CONTROL_TABLES,
    RAW_DDL,
    REQUIRED_SCHEMA_COLUMNS,
    apply_schema_migrations,
    create_indexes,
    validate_schema,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["REQUIRED_SCHEMA_COLUMNS", "SQLiteManager"]

diagnostics = get_observability_diagnostics("personal_finance_etl.control_plane")


class SQLiteManager:
    """SQLite connection owner for the durable ETL control plane.

    Parameters
    ----------
    base_path : str
        Base directory containing the SQLite database.
    db_name : str, default="Raw_Documents.sqlite"
        Database file name.
    """

    SCHEMA_VERSION = 3

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite") -> None:
        self.db_path = os.path.join(base_path or ".", db_name)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Active SQLite connection handle.

        Raises
        ------
        RuntimeError
            If connection has not been opened.
        """
        if self._conn is None:
            raise RuntimeError("SQLiteManager connection not opened.")
        return self._conn

    def open(self) -> None:
        """Open the SQLite database and configure WAL pragmas and foreign keys."""
        if self._conn is not None:
            return
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        diagnostics.debug("SQLite Control Plane: Opening connection to %s", self.db_path)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None,
            )
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute("PRAGMA busy_timeout = 30000;")
            connection.execute("PRAGMA journal_mode = WAL;")
            connection.execute("PRAGMA synchronous = NORMAL;")
            connection.execute("PRAGMA cache_size = -64000;")
            connection.execute("PRAGMA mmap_size = 2147483648;")
            connection.execute("PRAGMA temp_store = MEMORY;")
            fk_check = connection.execute("PRAGMA foreign_keys;").fetchone()
            if fk_check is None or fk_check[0] != 1:
                raise RuntimeError("SQLite foreign-key enforcement could not be enabled.")
            self._conn = connection
        except Exception:
            if connection is not None:
                connection.close()
            raise
        diagnostics.debug("SQLite Control Plane: Configured WAL, busy timeout, and foreign keys")
        diagnostics.info("Control Plane DB connected at %s", self.db_path)

    def close(self) -> None:
        """Safely rollback uncommitted transactions and close the SQLite connection."""
        if self._conn is None:
            return
        try:
            if self._conn.in_transaction:
                diagnostics.warning(
                    "SQLite Control Plane: Rolling back open transaction during close."
                )
                self._conn.rollback()
            self._conn.close()
        finally:
            self._conn = None
        diagnostics.info("Control Plane DB connection closed.")

    @contextmanager
    def atomic(self) -> Generator[None]:
        """Atomic scope that works both standalone and nested in a pipeline transaction."""
        savepoint = f"cp_scope_{uuid.uuid4().hex}"
        self.conn.execute(f"SAVEPOINT {savepoint}")
        try:
            yield
            self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            try:
                self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            finally:
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise

    @property
    def is_open(self) -> bool:
        """Whether the SQLite connection is currently open."""
        return self._conn is not None

    def ensure_schema(self) -> None:
        """Create or migrate the schema to current version and validate shape."""
        if self.conn.in_transaction:
            raise RuntimeError("ensure_schema() must run outside an active SQLite transaction.")

        existing_tables = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        present_control_tables = existing_tables & CURRENT_CONTROL_TABLES
        if present_control_tables:
            apply_schema_migrations(self.conn, existing_tables)

        diagnostics.debug("SQLite Control Plane: Initializing current schema.")
        self.conn.executescript(RAW_DDL)
        create_indexes(self.conn)
        validate_schema(self.conn)

        violations = self.conn.execute("PRAGMA foreign_key_check").fetchmany(10)
        if violations:
            raise RuntimeError(
                "Control-plane database contains foreign-key violations; refusing to continue. "
                f"First violations: {violations!r}"
            )
        diagnostics.info(
            "SQLite Control Plane: Current schema ready (version %s).", self.SCHEMA_VERSION
        )

    def begin_transaction(self) -> None:
        """Begin an immediate SQLite transaction."""
        if self.conn.in_transaction:
            raise RuntimeError("A SQLite transaction is already active.")
        self.conn.execute("BEGIN IMMEDIATE;")
        diagnostics.debug("SQLite Control Plane: BEGIN IMMEDIATE")

    def commit(self) -> None:
        """Commit the active SQLite transaction."""
        self.conn.commit()
        diagnostics.info("Control Plane transaction committed.")

    def rollback(self) -> None:
        """Rollback the active SQLite transaction if one is open."""
        if self._conn is None or not self._conn.in_transaction:
            return
        try:
            self._conn.rollback()
            diagnostics.warning("Control Plane transaction rolled back.")
        except sqlite3.Error:
            diagnostics.exception("Failed to rollback SQLite control-plane transaction.")
            raise
