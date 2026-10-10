META_DDL = """
-- Tracks the current source files present in Bronze
CREATE TABLE IF NOT EXISTS meta.m_File_Registry (
    file_id         TEXT PRIMARY KEY,   -- deterministic: SHA-256(relative_path)
    file_name       TEXT NOT NULL,
    relative_path   TEXT NOT NULL UNIQUE,
    file_category   TEXT NOT NULL,      -- 'mf_holdings', 'stock_pl', 'sqlite_source', etc.
    file_type       TEXT,               -- 'excel', 'csv', 'sqlite', 'parquet', 'virtual'
    file_hash       TEXT NOT NULL,      -- SHA-256 of file content
    file_size_bytes BIGINT,
    first_ingested  TIMESTAMP NOT NULL,
    last_ingested   TIMESTAMP NOT NULL,
    row_count       BIGINT
);

-- ETL data quality (Latest Run Only)
CREATE TABLE IF NOT EXISTS meta.m_Table_Row_Counts (
    schema_name TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    row_count   BIGINT,
    generated_at TIMESTAMP
);

-- Financial rules snapshot (Latest Run Only)
CREATE TABLE IF NOT EXISTS meta.m_Financial_Rules (
    Rule_Domain  TEXT NOT NULL,
    Rule_Type    TEXT NOT NULL,
    Target_Level TEXT NOT NULL,
    Target_ID    TEXT NOT NULL
);

-- Application settings snapshot (Latest Run Only)
CREATE TABLE IF NOT EXISTS meta.m_Settings (
    Setting_Group TEXT NOT NULL,
    Setting_Key   TEXT NOT NULL,
    Setting_Value TEXT NOT NULL
);

-- Contract Authority (Latest Run Only)
CREATE TABLE IF NOT EXISTS meta.m_Data_Contracts (
    contract_id       TEXT NOT NULL,
    layer             TEXT NOT NULL,
    physical_table    TEXT NOT NULL,
    domain            TEXT,
    grain             TEXT,
    producer          TEXT,
    is_full_replace   BOOLEAN,
    publication_order INTEGER
);

-- Latest simulation provenance mirror (Latest Run Only)
-- Mirrors the most recent successful cp_simulation_runs row from SQLite into DuckDB
-- so simulation fingerprints and model versions are queryable without cross-store joins.
CREATE TABLE IF NOT EXISTS meta.m_Latest_Simulation (
    simulation_id              TEXT NOT NULL,
    run_id                     TEXT NOT NULL,
    created_at                 TIMESTAMP NOT NULL,
    root_seed                  TEXT NOT NULL,
    iterations                 INTEGER,
    horizon                    INTEGER,
    model_implementation_version TEXT,
    model_fingerprint          TEXT,
    input_fingerprint          TEXT,
    result_fingerprint         TEXT,
    contract_registry_fingerprint TEXT,  -- SHA-256 of sorted DATA_CONTRACT_REGISTRY structural metadata
    settings_snapshot_id       TEXT,
    rules_snapshot_id          TEXT,
    status                     TEXT
);
"""
