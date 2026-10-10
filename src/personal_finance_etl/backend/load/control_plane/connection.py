from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from personal_finance_etl.backend.load.schema.control_plane import RAW_DDL
from personal_finance_etl.backend.utils.logger import logger


class SQLiteManager:
    """SQLite connection owner for the durable ETL control plane."""

    SCHEMA_VERSION = 2

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db_path = os.path.join(base_path or ".", db_name)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteManager connection not opened.")
        return self._conn

    def open(self) -> None:
        if self._conn is not None:
            return
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        logger.debug("[DATABASE:SQLITE] Opening connection to %s", self.db_path)
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
            if connection.execute("PRAGMA foreign_keys;").fetchone()[0] != 1:
                raise RuntimeError("SQLite foreign-key enforcement could not be enabled.")
            self._conn = connection
        except Exception:
            if connection is not None:
                connection.close()
            raise
        logger.debug("[DATABASE:SQLITE] Configured WAL, busy timeout, and foreign keys")
        logger.info("Control Plane DB connected at %s", self.db_path)

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            if self._conn.in_transaction:
                logger.warning("[DATABASE:SQLITE] Rolling back open transaction during close.")
                self._conn.rollback()
            self._conn.close()
        finally:
            self._conn = None
        logger.info("Control Plane DB connection closed.")

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
        """Create the current schema on a new database; never migrate existing data.

        Existing databases must be upgraded by the project's explicit migration
        workflow before this method is called. We validate their shape first so
        ``CREATE TABLE IF NOT EXISTS`` cannot disguise a stale or partial schema.
        """
        if self.conn.in_transaction:
            raise RuntimeError("ensure_schema() must run outside an active SQLite transaction.")

        existing_tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        current_tables = {
            "cp_settings_snapshots",
            "cp_rules_snapshots",
            "cp_runs",
            "cp_file_registry",
            "cp_file_payloads",
            "cp_run_failures",
            "cp_artifact_run_events",
            "cp_simulation_runs",
        }
        present_control_tables = existing_tables & current_tables
        if present_control_tables:
            missing_tables = current_tables - existing_tables
            if missing_tables:
                raise RuntimeError(
                    "Control-plane database does not match the current schema. "
                    f"Missing tables: {sorted(missing_tables)}. Run the project's "
                    "explicit database migration procedure; automatic migrations are disabled."
                )
            self._validate_current_schema()

        logger.debug("[DATABASE:SQLITE] Initializing current schema (no automatic migrations).")
        self.conn.executescript(RAW_DDL)
        self._create_indexes()

        violations = self.conn.execute("PRAGMA foreign_key_check").fetchmany(10)
        if violations:
            raise RuntimeError(
                "Control-plane database contains foreign-key violations; refusing to continue. "
                f"First violations: {violations!r}"
            )
        logger.info("[DATABASE:SQLITE] Current schema ready (version %s).", self.SCHEMA_VERSION)

    def _validate_current_schema(self) -> None:
        """Fail closed when an existing database is not already on the current schema."""
        required_columns: dict[str, set[str]] = {
            "cp_settings_snapshots": {
                "snapshot_id",
                "content_hash",
                "canonical_payload",
                "created_at",
            },
            "cp_rules_snapshots": {
                "snapshot_id",
                "content_hash",
                "canonical_payload",
                "created_at",
            },
            "cp_runs": {
                "run_id",
                "started_at",
                "finished_at",
                "status",
                "application_version",
                "schema_version",
                "settings_snapshot_id",
                "rules_snapshot_id",
                "execution_log",
            },
            "cp_file_registry": {
                "file_id",
                "file_name",
                "relative_path",
                "file_category",
                "file_type",
                "file_hash",
                "file_size_bytes",
                "sync_status",
                "first_seen_run_id",
                "first_seen_at",
                "last_seen_run_id",
                "last_seen_at",
                "last_changed_run_id",
                "last_changed_at",
                "last_synced_run_id",
                "last_synced_at",
            },
            "cp_file_payloads": {"file_id", "file_bytes"},
            "cp_run_failures": {
                "id",
                "run_id",
                "failed_isin",
                "stage",
                "error_type",
                "error_message",
                "traceback_log",
                "created_at",
            },
            "cp_artifact_run_events": {
                "event_id",
                "run_id",
                "file_id",
                "event_type",
                "event_at",
                "observed_path",
                "content_hash",
                "previous_status",
                "new_status",
                "event_reason",
            },
            "cp_simulation_runs": {
                "simulation_id",
                "run_id",
                "created_at",
                "root_seed",
                "iterations",
                "horizon",
                "input_as_of_date",
                "settings_snapshot_id",
                "rules_snapshot_id",
                "input_fingerprint",
                "model_fingerprint",
                "model_implementation_version",
                "status",
                "result_fingerprint",
            },
        }
        for table, required in required_columns.items():
            actual = {
                str(row[1]) for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            missing = required - actual
            if missing:
                raise RuntimeError(
                    f"Control-plane table {table!r} is not on the current schema; "
                    f"missing columns: {sorted(missing)}. Run the project's explicit "
                    "database migration procedure; automatic migrations are disabled."
                )

    def _create_indexes(self) -> None:
        statements = (
            "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_category_status ON cp_file_registry(file_category, sync_status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_status ON cp_file_registry(sync_status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_file_time ON cp_artifact_run_events(file_id, event_at)",
            "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_run ON cp_artifact_run_events(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_cp_runs_status ON cp_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_run_failures_run ON cp_run_failures(run_id)",
        )
        for statement in statements:
            self.conn.execute(statement)

    def begin_transaction(self) -> None:
        if self.conn.in_transaction:
            raise RuntimeError("A SQLite transaction is already active.")
        self.conn.execute("BEGIN IMMEDIATE;")
        logger.debug("[DATABASE:SQLITE] BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.commit()
        logger.info("Control Plane transaction committed.")

    def rollback(self) -> None:
        if self._conn is None or not self._conn.in_transaction:
            return
        try:
            self._conn.rollback()
            logger.warning("Control Plane transaction rolled back.")
        except sqlite3.Error:
            logger.exception("Failed to rollback SQLite control-plane transaction.")
            raise
