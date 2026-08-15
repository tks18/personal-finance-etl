META_DDL = """
-- Tracks every source file ever ingested into Bronze
CREATE TABLE IF NOT EXISTS meta.m_File_Registry (
    file_id         TEXT PRIMARY KEY,   -- deterministic: SHA-256(relative_path)
    file_name       TEXT NOT NULL,
    relative_path   TEXT NOT NULL UNIQUE,
    file_category   TEXT NOT NULL,      -- 'mf_holdings', 'stock_pl', 'sqlite_source', etc.
    file_hash       TEXT NOT NULL,      -- SHA-256 of file content
    file_size_bytes BIGINT,
    first_ingested  TIMESTAMP NOT NULL,
    last_ingested   TIMESTAMP NOT NULL,
    row_count       BIGINT
);

-- Tracks per-run metadata
CREATE TABLE IF NOT EXISTS meta.m_Run_Log (
    run_id          TEXT PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT,               -- 'running', 'success', 'failed'
    files_processed BIGINT,
    files_skipped   BIGINT,
    duration_sec    DOUBLE
);

-- ETL data quality
CREATE TABLE IF NOT EXISTS meta.m_Table_Row_Counts (
    run_id      TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    row_count   BIGINT,
    generated_at TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES meta.m_Run_Log(run_id)
);

-- Financial rules snapshot
CREATE TABLE IF NOT EXISTS meta.m_Financial_Rules (
    run_id       TEXT NOT NULL,
    Rule_Domain  TEXT NOT NULL,
    Rule_Type    TEXT NOT NULL,
    Target_Level TEXT NOT NULL,
    Target_ID    TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES meta.m_Run_Log(run_id)
);
-- Application settings snapshot
CREATE TABLE IF NOT EXISTS meta.m_Settings (
    run_id        TEXT NOT NULL,
    Setting_Group TEXT NOT NULL,
    Setting_Key   TEXT NOT NULL,
    Setting_Value TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES meta.m_Run_Log(run_id)
);
"""
