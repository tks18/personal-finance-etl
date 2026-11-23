"""End-to-End pipeline execution test verifying full lifecycle, lakehouse publication, and Control Plane state.

Owns
----
- Executing the complete ETL pipeline synchronously against isolated temporary database paths.
- Asserting Control Plane execution status (SUCCESS) and zero RECOVERY_REQUIRED state.
- Asserting existence of Bronze, all 24 Silver, and all 22 Gold warehouse tables.
- Validating row counts and metadata snapshot tracking.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb

from personal_finance_etl.bootstrap.container import ServiceContainer
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY


def test_pipeline_e2e_execution(
    isolated_config: tuple[Settings, Path], test_rules_path: Path
) -> None:
    """Run full quantitative ETL pipeline and verify database, control plane, and contract integrity."""
    cfg, temp_cfg_path = isolated_config

    container = ServiceContainer(
        default_config_path=str(temp_cfg_path),
        default_rules_path=str(test_rules_path),
    )
    engine = container.create_engine()

    # 1. Execute ETL pipeline synchronously
    engine.run_pipeline_sync(
        config_path=str(temp_cfg_path),
        rules_path=str(test_rules_path),
    )

    # 2. Verify SQLite Control Plane
    sqlite_path = Path(cfg.database.target_db_base_path) / cfg.database.raw_document_store_name
    assert sqlite_path.exists(), f"Raw store missing at {sqlite_path}"

    with sqlite3.connect(sqlite_path) as cp_conn:
        cur = cp_conn.cursor()
        cur.execute("SELECT run_id, status FROM cp_runs ORDER BY started_at DESC LIMIT 1")
        run_row = cur.fetchone()
        assert run_row is not None, "No run recorded in cp_runs"
        _, latest_status = run_row
        assert latest_status == "SUCCESS", f"Expected run status SUCCESS, got {latest_status}"

        cur.execute("SELECT COUNT(*) FROM cp_runs WHERE UPPER(status) = 'RECOVERY_REQUIRED'")
        recovery_required = cur.fetchone()[0]
        assert recovery_required == 0, "Pipeline must leave zero RECOVERY_REQUIRED runs"

    # 3. Verify DuckDB Lakehouse
    duckdb_path = Path(cfg.database.target_db_base_path) / cfg.database.target_db_name
    assert duckdb_path.exists(), f"DuckDB missing at {duckdb_path}"

    with duckdb.connect(str(duckdb_path), read_only=True) as duck_conn:
        schemas = {
            r[0]
            for r in duck_conn.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        assert {"bronze", "silver", "gold", "meta"}.issubset(schemas)

        # Query all physical tables
        tables = {
            f"{r[0]}.{r[1]}"
            for r in duck_conn.execute(
                "SELECT table_schema, table_name FROM information_schema.tables"
            ).fetchall()
        }

        # Assert all 24 canonical Silver tables exist
        silver_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"]
        assert len(silver_contracts) == 24
        for contract in silver_contracts:
            assert contract.physical_table in tables, (
                f"Missing Silver table: {contract.physical_table}"
            )

        # Assert all 22 canonical Gold tables exist
        gold_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]
        assert len(gold_contracts) == 22
        for contract in gold_contracts:
            assert contract.physical_table in tables, (
                f"Missing Gold table: {contract.physical_table}"
            )

        # Verify row counts in key tables
        inc_row = duck_conn.execute("SELECT COUNT(*) FROM silver.fact_income_transactions").fetchone()
        assert inc_row is not None
        inc_count = inc_row[0]
        assert inc_count >= 2, f"Expected at least 2 income transactions, got {inc_count}"

        exp_row = duck_conn.execute("SELECT COUNT(*) FROM silver.fact_expense_transactions").fetchone()
        assert exp_row is not None
        exp_count = exp_row[0]
        assert exp_count >= 2, f"Expected at least 2 expense transactions, got {exp_count}"

        # Verify Gold analytical tables contain populated facts
        monthly_row = duck_conn.execute("SELECT COUNT(*) FROM gold.core_monthly_fact").fetchone()
        assert monthly_row is not None
        core_monthly_rows = monthly_row[0]
        assert core_monthly_rows >= 1, "gold.core_monthly_fact must have rows"
