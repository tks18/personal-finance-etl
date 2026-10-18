"""SQLite connection and transaction management for the durable control plane.

Owns
----
- SQLite connection lifecycle, WAL journal mode, and foreign key enforcement.
- Savepoint-based nested atomic transaction management (atomic() context manager).
- Control plane schema initialization, migration (to SCHEMA_VERSION 3), and validation.
- SQLite transaction primitives (begin_transaction, commit, rollback).

Does not own
-------------
- Specific table payload reading/writing (owned by run_repository and artifact_repository).
- DuckDB analytical warehouse connections (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from personal_finance_etl.infrastructure.control_plane.schema import RAW_DDL

logger = logging.getLogger("personal_finance_etl.control_plane")


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
            fk_check = connection.execute("PRAGMA foreign_keys;").fetchone()
            if fk_check is None or fk_check[0] != 1:
                raise RuntimeError("SQLite foreign-key enforcement could not be enabled.")
            self._conn = connection
        except Exception:
            if connection is not None:
                connection.close()
            raise
        logger.debug("[DATABASE:SQLITE] Configured WAL, busy timeout, and foreign keys")
        logger.info("Control Plane DB connected at %s", self.db_path)

    def close(self) -> None:
        """Safely rollback uncommitted transactions and close the SQLite connection."""
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
        """Create or migrate the schema to current version and validate shape."""
        if self.conn.in_transaction:
            raise RuntimeError("ensure_schema() must run outside an active SQLite transaction.")

        existing_tables = {
            str(row[0])
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
            "cp_external_provider_requests",
            "cp_run_sync_summaries",
        }
        present_control_tables = existing_tables & current_tables
        if present_control_tables:
            self._migrate_schema(existing_tables)

        logger.debug("[DATABASE:SQLITE] Initializing current schema.")
        self.conn.executescript(RAW_DDL)
        self._create_indexes()
        self._validate_current_schema()

        violations = self.conn.execute("PRAGMA foreign_key_check").fetchmany(10)
        if violations:
            raise RuntimeError(
                "Control-plane database contains foreign-key violations; refusing to continue. "
                f"First violations: {violations!r}"
            )
        logger.info("[DATABASE:SQLITE] Current schema ready (version %s).", self.SCHEMA_VERSION)

    def _migrate_schema(self, existing_tables: set[str]) -> None:
        """Apply non-destructive schema migrations to existing control plane tables."""
        if "cp_runs" in existing_tables:
            cols = {
                str(row[1]) for row in self.conn.execute("PRAGMA table_info(cp_runs)").fetchall()
            }
            if "commit_state" not in cols:
                logger.info("[DATABASE:SQLITE] Migrating cp_runs: adding commit_state column.")
                self.conn.execute(
                    "ALTER TABLE cp_runs ADD COLUMN commit_state TEXT NOT NULL DEFAULT 'NOT_STARTED'"
                )

        if "cp_run_failures" in existing_tables:
            cols = {
                str(row[1])
                for row in self.conn.execute("PRAGMA table_info(cp_run_failures)").fetchall()
            }
            if "failure_domain" not in cols:
                logger.info(
                    "[DATABASE:SQLITE] Migrating cp_run_failures: adding failure_domain column."
                )
                self.conn.execute(
                    "ALTER TABLE cp_run_failures ADD COLUMN failure_domain TEXT NOT NULL DEFAULT 'UNKNOWN'"
                )

        if "cp_artifact_run_events" in existing_tables:
            cols = {
                str(row[1])
                for row in self.conn.execute("PRAGMA table_info(cp_artifact_run_events)").fetchall()
            }
            if "affected_table" not in cols:
                logger.info(
                    "[DATABASE:SQLITE] Migrating cp_artifact_run_events: adding lineage columns."
                )
                self.conn.execute(
                    "ALTER TABLE cp_artifact_run_events ADD COLUMN affected_table TEXT"
                )
            if "detecting_run_id" not in cols:
                self.conn.execute(
                    "ALTER TABLE cp_artifact_run_events ADD COLUMN detecting_run_id TEXT"
                )
            if "replay_run_id" not in cols:
                self.conn.execute(
                    "ALTER TABLE cp_artifact_run_events ADD COLUMN replay_run_id TEXT"
                )
            if "convergence_result" not in cols:
                self.conn.execute(
                    "ALTER TABLE cp_artifact_run_events ADD COLUMN convergence_result TEXT"
                )

    def _validate_current_schema(self) -> None:
        """Fail closed when an existing database is not on the current schema."""
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
                "commit_state",
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
                "failure_domain",
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
                "affected_table",
                "detecting_run_id",
                "replay_run_id",
                "convergence_result",
            },
            "cp_external_provider_requests": {
                "request_id",
                "run_id",
                "provider",
                "entity",
                "requested_start",
                "requested_end",
                "attempt_count",
                "status",
                "failure_class",
                "final_error",
                "created_at",
            },
            "cp_run_sync_summaries": {
                "run_id",
                "actionable_count",
                "synced_count",
                "healed_count",
                "failed_count",
                "deferred_count",
                "sync_status",
                "created_at",
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
                str(row[0])
                for row in self.conn.execute(
                    "SELECT name FROM pragma_table_info(?)", (table,)
                ).fetchall()
            }
            missing = required - actual
            if missing:
                raise RuntimeError(
                    f"Control-plane table {table!r} is not on the current schema; "
                    f"missing columns: {sorted(missing)}. Run the project's explicit "
                    "database migration procedure; automatic migrations are disabled."
                )

    def _create_indexes(self) -> None:
        """Create standard indexes on control plane tables."""
        statements = (
            "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_category_status ON cp_file_registry(file_category, sync_status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_status ON cp_file_registry(sync_status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_file_time ON cp_artifact_run_events(file_id, event_at)",
            "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_run ON cp_artifact_run_events(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_cp_runs_status ON cp_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_cp_runs_commit_state ON cp_runs(commit_state)",
            "CREATE INDEX IF NOT EXISTS idx_cp_run_failures_run ON cp_run_failures(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_cp_provider_requests_run ON cp_external_provider_requests(run_id)",
        )
        for statement in statements:
            self.conn.execute(statement)

    def begin_transaction(self) -> None:
        """Begin an immediate SQLite transaction."""
        if self.conn.in_transaction:
            raise RuntimeError("A SQLite transaction is already active.")
        self.conn.execute("BEGIN IMMEDIATE;")
        logger.debug("[DATABASE:SQLITE] BEGIN IMMEDIATE")

    def commit(self) -> None:
        """Commit the active SQLite transaction."""
        self.conn.commit()
        logger.info("Control Plane transaction committed.")

    def rollback(self) -> None:
        """Rollback the active SQLite transaction if one is open."""
        if self._conn is None or not self._conn.in_transaction:
            return
        try:
            self._conn.rollback()
            logger.warning("Control Plane transaction rolled back.")
        except sqlite3.Error:
            logger.exception("Failed to rollback SQLite control-plane transaction.")
            raise
