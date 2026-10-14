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
