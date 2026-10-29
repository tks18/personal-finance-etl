"""Declarative SQLite Control Plane DDL schemas and migration contracts.

Owns
----
- Declarative SQLite DDL definitions for the durable ETL control plane (cp_file_registry,
  cp_file_payloads, cp_settings_snapshots, cp_rules_snapshots, cp_runs, cp_run_failures,
  cp_artifact_run_events, cp_external_provider_requests, cp_run_sync_summaries, cp_simulation_runs).
- Required schema column manifests for schema validation.
- Schema migration statements and non-destructive column backfills.
- Control plane index definitions and creation.

Does not own
-------------
- SQLite connection management or savepoint execution (owned by infrastructure.control_plane.connection).
- DuckDB analytical warehouse DDL (owned by bronze.py, silver.py, gold.py, meta.py).
"""

from __future__ import annotations

import sqlite3

from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.control_plane.schema")

RAW_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cp_file_registry (
    file_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    file_category TEXT NOT NULL,
    file_type TEXT,
    file_hash TEXT NOT NULL,
    file_size_bytes BIGINT,
    sync_status TEXT DEFAULT 'PENDING_BRONZE',
    first_seen_run_id TEXT,
    first_seen_at TIMESTAMP NOT NULL,
    last_seen_run_id TEXT,
    last_seen_at TIMESTAMP NOT NULL,
    last_changed_run_id TEXT,
    last_changed_at TIMESTAMP,
    last_synced_run_id TEXT,
    last_synced_at TIMESTAMP,
    FOREIGN KEY(first_seen_run_id) REFERENCES cp_runs(run_id),
    FOREIGN KEY(last_seen_run_id) REFERENCES cp_runs(run_id),
    FOREIGN KEY(last_changed_run_id) REFERENCES cp_runs(run_id),
    FOREIGN KEY(last_synced_run_id) REFERENCES cp_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cp_file_payloads (
    file_id TEXT PRIMARY KEY,
    file_bytes BLOB,
    FOREIGN KEY(file_id) REFERENCES cp_file_registry(file_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cp_settings_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    canonical_payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS cp_rules_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    canonical_payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS cp_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status TEXT,
    commit_state TEXT NOT NULL DEFAULT 'NOT_STARTED',
    application_version TEXT,
    schema_version TEXT,
    settings_snapshot_id TEXT,
    rules_snapshot_id TEXT,
    execution_log BLOB,
    FOREIGN KEY(settings_snapshot_id) REFERENCES cp_settings_snapshots(snapshot_id),
    FOREIGN KEY(rules_snapshot_id) REFERENCES cp_rules_snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS cp_run_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    failed_isin TEXT,
    stage TEXT,
    error_type TEXT,
    error_message TEXT,
    traceback_log TEXT,
    failure_domain TEXT NOT NULL DEFAULT 'UNKNOWN',
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(run_id) REFERENCES cp_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cp_artifact_run_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TIMESTAMP NOT NULL,
    observed_path TEXT,
    content_hash TEXT,
    previous_status TEXT,
    new_status TEXT,
    event_reason TEXT,
    affected_table TEXT,
    detecting_run_id TEXT,
    replay_run_id TEXT,
    convergence_result TEXT,
    FOREIGN KEY(run_id) REFERENCES cp_runs(run_id),
    FOREIGN KEY(file_id) REFERENCES cp_file_registry(file_id)
);

CREATE TABLE IF NOT EXISTS cp_external_provider_requests (
    request_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    entity TEXT NOT NULL,
    requested_start DATE,
    requested_end DATE,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    failure_class TEXT,
    final_error TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(run_id) REFERENCES cp_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cp_run_sync_summaries (
    run_id TEXT PRIMARY KEY,
    actionable_count INTEGER NOT NULL,
    synced_count INTEGER NOT NULL,
    healed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    deferred_count INTEGER NOT NULL,
    sync_status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY(run_id) REFERENCES cp_runs(run_id)
);

CREATE TABLE IF NOT EXISTS cp_simulation_runs (
    simulation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    root_seed TEXT NOT NULL,
    iterations INTEGER,
    horizon INTEGER,
    input_as_of_date DATE,
    settings_snapshot_id TEXT,
    rules_snapshot_id TEXT,
    input_fingerprint TEXT,
    model_fingerprint TEXT,
    model_implementation_version TEXT,
    status TEXT,
    result_fingerprint TEXT,
    FOREIGN KEY(run_id) REFERENCES cp_runs(run_id),
    FOREIGN KEY(settings_snapshot_id) REFERENCES cp_settings_snapshots(snapshot_id),
    FOREIGN KEY(rules_snapshot_id) REFERENCES cp_rules_snapshots(snapshot_id)
);
"""

REQUIRED_SCHEMA_COLUMNS: dict[str, set[str]] = {
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

CURRENT_CONTROL_TABLES: set[str] = {
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

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_category_status ON cp_file_registry(file_category, sync_status)",
    "CREATE INDEX IF NOT EXISTS idx_cp_file_registry_status ON cp_file_registry(sync_status)",
    "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_file_time ON cp_artifact_run_events(file_id, event_at)",
    "CREATE INDEX IF NOT EXISTS idx_cp_artifact_events_run ON cp_artifact_run_events(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_cp_runs_status ON cp_runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_cp_runs_commit_state ON cp_runs(commit_state)",
    "CREATE INDEX IF NOT EXISTS idx_cp_run_failures_run ON cp_run_failures(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_cp_provider_requests_run ON cp_external_provider_requests(run_id)",
)


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create standard performance and foreign-key indexes on control plane tables.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    """
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)


def _migrate_runs(conn: sqlite3.Connection, existing_tables: set[str]) -> None:
    """Add commit_state column to cp_runs if missing.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    existing_tables : set[str]
        Existing table names in the database.
    """
    if "cp_runs" in existing_tables:
        cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(cp_runs)").fetchall()}
        if "commit_state" not in cols:
            diagnostics.info("SQLite Control Plane: Migrating cp_runs: adding commit_state column.")
            conn.execute(
                "ALTER TABLE cp_runs ADD COLUMN commit_state TEXT NOT NULL DEFAULT 'NOT_STARTED'"
            )


def _migrate_failures(conn: sqlite3.Connection, existing_tables: set[str]) -> None:
    """Add failure_domain column to cp_run_failures if missing.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    existing_tables : set[str]
        Existing table names in the database.
    """
    if "cp_run_failures" in existing_tables:
        cols = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(cp_run_failures)").fetchall()
        }
        if "failure_domain" not in cols:
            diagnostics.info(
                "SQLite Control Plane: Migrating cp_run_failures: adding failure_domain column."
            )
            conn.execute(
                "ALTER TABLE cp_run_failures ADD COLUMN failure_domain TEXT NOT NULL DEFAULT 'UNKNOWN'"
            )


def _migrate_events(conn: sqlite3.Connection, existing_tables: set[str]) -> None:
    """Add lineage and replay columns to cp_artifact_run_events if missing.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    existing_tables : set[str]
        Existing table names in the database.
    """
    if "cp_artifact_run_events" not in existing_tables:
        return
    cols = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(cp_artifact_run_events)").fetchall()
    }
    columns_to_add = [
        ("affected_table", "TEXT"),
        ("detecting_run_id", "TEXT"),
        ("replay_run_id", "TEXT"),
        ("convergence_result", "TEXT"),
    ]
    for col_name, col_type in columns_to_add:
        if col_name not in cols:
            conn.execute(f"ALTER TABLE cp_artifact_run_events ADD COLUMN {col_name} {col_type}")


def apply_schema_migrations(conn: sqlite3.Connection, existing_tables: set[str]) -> None:
    """Apply non-destructive schema migrations to existing control plane tables.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.
    existing_tables : set[str]
        Set of existing table names in the database.
    """
    _migrate_runs(conn, existing_tables)
    _migrate_failures(conn, existing_tables)
    _migrate_events(conn, existing_tables)


def validate_schema(conn: sqlite3.Connection) -> None:
    """Fail closed when an existing database is not on the current schema.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection.

    Raises
    ------
    RuntimeError
        If any table is missing required schema columns.
    """
    for table, required in REQUIRED_SCHEMA_COLUMNS.items():
        actual = {
            str(row[0])
            for row in conn.execute("SELECT name FROM pragma_table_info(?)", (table,)).fetchall()
        }
        missing = required - actual
        if missing:
            raise RuntimeError(
                f"Control-plane table {table!r} is not on the current schema; "
                f"missing columns: {sorted(missing)}. Run the project's explicit "
                "database migration procedure; automatic migrations are disabled."
            )
