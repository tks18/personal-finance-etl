# pyright: reportPrivateUsage=false
"""Integration tests verifying the Plan-Aware Analytical Warehouse.

Owns
----
- Testing dynamic DDL generation and physical column pruning in DuckDB.
- Testing catalog absence: tables belonging to disabled capabilities do NOT exist.
- Testing dynamic transitions across capability profiles (Full -> Household -> Full).
- Testing stale table cleanup: purging previously active managed tables when disabled.
- Testing strict protection of unknown/user-defined tables during transitions.
- Testing active contract catalog synchronization in meta.m_Data_Contracts.
- Testing column projection during DataFrame writes avoiding DuckDB BinderExceptions.

Does not own
-------------
- Low-level AST architectural boundaries (owned by tests/architecture/).
- Pure mathematical calculation kernels (owned by tests/domain/).
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from datetime import date

import polars as pl
import pytest

from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.config.capabilities import CapabilitySelection
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.gold import GoldLayer
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.schema.gold import generate_gold_ddl
from personal_finance_etl.infrastructure.warehouse.silver import SilverLayer


@pytest.fixture
def temp_warehouse() -> Iterator[tuple[DuckDBManager, str]]:
    """Provide an isolated DuckDB database manager in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DuckDBManager(base_path=tmpdir, db_name="test_plan_warehouse.duckdb")
        manager.open()
        yield manager, tmpdir
        manager.close()


def test_dynamic_ddl_pruning_columns(temp_warehouse: tuple[DuckDBManager, str]) -> None:
    """Verify that columns belonging strictly to disabled capabilities are physically omitted from DuckDB DDL."""
    manager, _ = temp_warehouse
    planner = CapabilityPlanner()

    # Plan with Domestic Investments only (no Benchmark, no Foreign FX, no Tax)
    domestic_plan = planner.create_plan(
        [CapabilityId.HOUSEHOLD_CORE, CapabilityId.INVESTMENT_ACCOUNTING]
    )

    manager.ensure_schemas(domestic_plan)

    # 1. Inspect gold.investment_by_isin columns via PRAGMA
    isin_cols = {
        row[1]
        for row in manager.conn.execute("PRAGMA table_info('gold.investment_by_isin')").fetchall()
    }
    # Base columns must exist
    assert "ISIN" in isin_cols
    assert "Total_Quantity" in isin_cols
    assert "Total_Current_Value" in isin_cols

    # Foreign FX columns must be physically omitted
    assert "Total_Current_Value_Local" not in isin_cols
    assert "Total_Invested_Value_Local" not in isin_cols
    assert "Forex_PnL" not in isin_cols
    assert "XIRR_Local" not in isin_cols

    # Benchmark enrichment columns must be physically omitted
    assert "BM_CAGR" not in isin_cols
    assert "BM_XIRR" not in isin_cols
    assert "Active_Return" not in isin_cols

    # Tax columns must be physically omitted
    assert "LTCG_Tax_If_Sold" not in isin_cols
    assert "STCG_Tax_If_Sold" not in isin_cols

    # 2. Inspect gold.wealth_core_monthly
    core_cols = {
        row[1]
        for row in manager.conn.execute("PRAGMA table_info('gold.wealth_core_monthly')").fetchall()
    }
    assert "MONTH_START_DATE" in core_cols
    assert "Total_Income" in core_cols
    assert "Total_Expense" in core_cols
    assert "Net_Cashflow_Month" in core_cols

    # Foreign FX columns in wealth_core_monthly must be physically omitted
    assert "Total_Foreign_Currency_Exposure" not in core_cols
    assert "Closing_Forex_PnL" not in core_cols
    assert "Foreign_Exposure_Pct" not in core_cols


def test_catalog_absence_for_disabled_capabilities(
    temp_warehouse: tuple[DuckDBManager, str],
) -> None:
    """Verify that tables for disabled capabilities do NOT exist in DuckDB catalog."""
    manager, _ = temp_warehouse
    planner = CapabilityPlanner()

    # Household-only plan
    hh_plan = planner.create_plan([CapabilityId.HOUSEHOLD_CORE])
    manager.ensure_schemas(hh_plan)

    existing_tables = {
        f"{r[0]}.{r[1]}"
        for r in manager.conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('silver', 'gold')"
        ).fetchall()
    }

    # Household core tables must exist
    assert "silver.common_calendar" in existing_tables
    assert "silver.wealth_income_transactions" in existing_tables
    assert "silver.wealth_expense_transactions" in existing_tables
    assert "gold.wealth_core_monthly" in existing_tables
    assert "gold.wealth_cashflow_activity_summary" in existing_tables

    # Investment, Tax, and Wealth tables must NOT exist
    assert "silver.investment_lot_analytics" not in existing_tables
    assert "silver.investment_realized_events" not in existing_tables
    assert "silver.tax_events" not in existing_tables
    assert "gold.investment_by_isin" not in existing_tables
    assert "gold.tax_year_summary" not in existing_tables
    assert "gold.wealth_asset_breakdown" not in existing_tables
    assert "gold.fire_analytics" not in existing_tables


def test_dynamic_capability_transitions_and_stale_table_cleanup(
    temp_warehouse: tuple[DuckDBManager, str],
) -> None:
    """Verify dynamic transitions across plans: Full -> Household -> Full.

    Asserts that:
    - Inactive managed tables are dropped when transitioning to Household.
    - Tables are recreated with full schemas when re-enabling Full.
    """
    manager, tmpdir = temp_warehouse
    planner = CapabilityPlanner()
    full_plan = planner.create_plan(list(CapabilityId))
    hh_plan = planner.create_plan([CapabilityId.HOUSEHOLD_CORE])

    settings = Settings(
        TARGET_DB_BASE_PATH=tmpdir,
        TARGET_DB_NAME="test_plan_warehouse.duckdb",
        capabilities=CapabilitySelection(enabled=tuple(CapabilityId)),
    )
    meta = MetaLayer(manager, settings)

    # 1. Run Full plan
    manager.ensure_schemas(full_plan)
    silver = SilverLayer(manager, emitter=ObservabilityEmitter())
    gold = GoldLayer(manager, emitter=ObservabilityEmitter())

    # Mock DataFrames for active datasets using their real contract_ids
    mock_dfs: dict[str, pl.DataFrame] = {
        "df_d_calendar": pl.DataFrame(
            {"Date": [date(2026, 1, 1)], "Year": [2026], "Month": [1], "artifact_id": ["art1"]}
        ),
        "df_f_investment_analytics_lot": pl.DataFrame(
            {
                "Lot_ID": ["lot1"],
                "ISIN": ["IN001"],
                "Closing_Date": [date(2026, 1, 1)],
                "Lot_Source_Type": ["PURCHASE"],
                "Quantity": [10.0],
                "artifact_id": ["art1"],
            }
        ),
        "df_f_investment_analytics_isin": pl.DataFrame(
            {
                "Closing_Date": [date(2026, 1, 1)],
                "ISIN": ["IN001"],
                "Total_Quantity": [10.0],
                "Total_Current_Value": [1000.0],
                "LTCG_Tax_If_Sold": [50.0],
                "BM_XIRR": [0.12],
                "Total_Current_Value_Local": [1000.0],
            }
        ),
        "df_p_tf_wealth_monthly_totals": pl.DataFrame(
            {
                "MONTH_START_DATE": [date(2026, 1, 1)],
                "Total_Income": [5000.0],
                "Total_Expense": [3000.0],
                "Net_Cashflow_Month": [2000.0],
            }
        ),
    }

    silver.load(mock_dfs, plan=full_plan)
    gold.load(mock_dfs, plan=full_plan)
    meta.load(mock_dfs, plan=full_plan)

    # Verify tables exist
    tables_step1 = {
        f"{r[0]}.{r[1]}"
        for r in manager.conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('silver', 'gold')"
        ).fetchall()
    }
    assert "silver.investment_lot_analytics" in tables_step1
    assert "gold.investment_by_isin" in tables_step1

    # 2. Transition to Household-only plan
    settings_hh = Settings(
        TARGET_DB_BASE_PATH=tmpdir,
        TARGET_DB_NAME="test_plan_warehouse.duckdb",
        capabilities=CapabilitySelection(enabled=(CapabilityId.HOUSEHOLD_CORE,)),
    )
    meta_hh = MetaLayer(manager, settings_hh)

    silver.load(mock_dfs, plan=hh_plan)
    gold.load(mock_dfs, plan=hh_plan)
    meta_hh.load(mock_dfs, plan=hh_plan)

    tables_step2 = {
        f"{r[0]}.{r[1]}"
        for r in manager.conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('silver', 'gold')"
        ).fetchall()
    }
    # Inactive managed tables must have been dropped
    assert "silver.investment_lot_analytics" not in tables_step2
    assert "gold.investment_by_isin" not in tables_step2
    assert "gold.wealth_core_monthly" in tables_step2

    # 3. Transition back to Full plan
    silver.load(mock_dfs, plan=full_plan)
    gold.load(mock_dfs, plan=full_plan)
    meta.load(mock_dfs, plan=full_plan)

    tables_step3 = {
        f"{r[0]}.{r[1]}"
        for r in manager.conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('silver', 'gold')"
        ).fetchall()
    }
    assert "silver.investment_lot_analytics" in tables_step3
    assert "gold.investment_by_isin" in tables_step3


def test_user_defined_tables_are_strictly_preserved(
    temp_warehouse: tuple[DuckDBManager, str],
) -> None:
    """Verify that unknown/user-defined custom tables are NEVER dropped during plan transitions."""
    manager, tmpdir = temp_warehouse
    planner = CapabilityPlanner()
    full_plan = planner.create_plan(list(CapabilityId))
    hh_plan = planner.create_plan([CapabilityId.HOUSEHOLD_CORE])

    manager.ensure_schemas(full_plan)

    # Create a user-defined table in silver and gold
    manager.conn.execute(
        "CREATE TABLE silver.user_manual_annotations (annotation_id VARCHAR, note TEXT)"
    )
    manager.conn.execute(
        "INSERT INTO silver.user_manual_annotations VALUES ('A1', 'User custom annotation')"
    )

    manager.conn.execute(
        "CREATE TABLE gold.bi_custom_dashboard_kpis (kpi_name VARCHAR, kpi_value DOUBLE)"
    )
    manager.conn.execute("INSERT INTO gold.bi_custom_dashboard_kpis VALUES ('custom_metric', 42.0)")

    settings = Settings(
        TARGET_DB_BASE_PATH=tmpdir,
        TARGET_DB_NAME="test_plan_warehouse.duckdb",
        capabilities=CapabilitySelection(enabled=(CapabilityId.HOUSEHOLD_CORE,)),
    )
    meta = MetaLayer(manager, settings)
    silver = SilverLayer(manager, emitter=ObservabilityEmitter())
    gold = GoldLayer(manager, emitter=ObservabilityEmitter())

    # Execute load under Household Only plan
    silver.load({}, plan=hh_plan)
    gold.load({}, plan=hh_plan)
    meta.load({}, plan=hh_plan)

    # Assert user tables still exist and data is intact!
    user_silver_cnt = manager.conn.execute(
        "SELECT COUNT(*) FROM silver.user_manual_annotations"
    ).fetchone()
    assert user_silver_cnt is not None and user_silver_cnt[0] == 1

    user_gold_cnt = manager.conn.execute(
        "SELECT COUNT(*) FROM gold.bi_custom_dashboard_kpis"
    ).fetchone()
    assert user_gold_cnt is not None and user_gold_cnt[0] == 1


def test_active_contract_catalog_synchronization(
    temp_warehouse: tuple[DuckDBManager, str],
) -> None:
    """Verify meta.m_Data_Contracts reflects only active contracts for the execution plan."""
    manager, tmpdir = temp_warehouse
    planner = CapabilityPlanner()
    hh_plan = planner.create_plan([CapabilityId.HOUSEHOLD_CORE])

    settings = Settings(
        TARGET_DB_BASE_PATH=tmpdir,
        TARGET_DB_NAME="test_plan_warehouse.duckdb",
        capabilities=CapabilitySelection(enabled=(CapabilityId.HOUSEHOLD_CORE,)),
    )
    meta = MetaLayer(manager, settings)
    manager.ensure_schemas(hh_plan)
    meta.load({}, plan=hh_plan)

    contracts_recorded = {
        row[0]
        for row in manager.conn.execute(
            "SELECT physical_table FROM meta.m_Data_Contracts"
        ).fetchall()
    }

    # Household tables are in meta catalog
    assert "silver.common_calendar" in contracts_recorded
    assert "gold.wealth_core_monthly" in contracts_recorded

    # Inactive capability tables are NOT in meta catalog
    assert "silver.investment_lot_analytics" not in contracts_recorded
    assert "gold.investment_by_isin" not in contracts_recorded
    assert "gold.wealth_asset_breakdown" not in contracts_recorded


def test_df_write_with_pruned_columns_no_binder_exception(
    temp_warehouse: tuple[DuckDBManager, str],
) -> None:
    """Verify that DataFrames with extra columns insert cleanly into pruned tables without DuckDB BinderException."""
    manager, _ = temp_warehouse
    planner = CapabilityPlanner()

    # Plan without Benchmark and without Tax
    plan = planner.create_plan([CapabilityId.HOUSEHOLD_CORE, CapabilityId.INVESTMENT_ACCOUNTING])
    gold = GoldLayer(manager, emitter=ObservabilityEmitter())

    # Generate pruned gold tables
    manager.conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
    manager.conn.execute(generate_gold_ddl(plan))

    # DataFrame that contains extra benchmark and tax columns that were pruned
    df_with_extra_cols = pl.DataFrame(
        {
            "Closing_Date": [date(2026, 1, 1)],
            "ISIN": ["IN001"],
            "Total_Quantity": [10.0],
            "Total_Current_Value": [1000.0],
            "BM_XIRR": [0.15],  # Pruned from DDL!
            "LTCG_Tax_If_Sold": [100.0],  # Pruned from DDL!
            "Extra_Unrelated_Column": [999],  # Completely arbitrary!
        }
    )

    # Must insert without _duckdb.BinderException
    inserted_rows = gold._write(df_with_extra_cols, "gold.investment_by_isin")
    assert inserted_rows == 1

    stored_row = manager.conn.execute(
        "SELECT ISIN, Total_Quantity, Total_Current_Value FROM gold.investment_by_isin"
    ).fetchone()
    assert stored_row == ("IN001", 10.0, 1000.0)
