# pyright: reportPrivateUsage=false
"""Enterprise test suite for Wealth and FIRE capability composition and execution planning.

Owns
----
- Verification of household-only, wealth-enabled, and FIRE-enabled ExecutionPlans.
- Verification that ExecutionPlan correctly identifies required and produced Gold datasets (6 vs 8).
- Verification of CAPABILITY_COLUMN_INVENTORY queries via get_capability_columns for WEALTH and FIRE.
- Verification that WealthService presentation DAG conditionally generates tables based on active plan.
- Verification that PipelineExecutor conditionally emits PresentationKind.SKIP and skips simulation telemetry when FIRE is inactive.
- Verification that declarative sources.toml fixtures for household-only, household-wealth, and household-wealth-fire plan cleanly.

Does not own
-------------
- Pure numerical domain calculation kernels (owned by tests/domain/test_wealth_fire_source_gating.py).
- AST architectural boundary enforcement (owned by tests/architecture/test_boundaries.py).
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.application.pipeline import ETLOrchestrator
from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.application.wealth import WealthService
from personal_finance_etl.config.capabilities import CapabilitySelection
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.model import SourceConfig
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    get_capability_columns,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.observability import EventCode, PresentationKind
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


@pytest.fixture
def sample_domain_dfs() -> dict[str, pl.DataFrame]:
    """Provide minimal Silver/dimension tables for domain builder tests."""
    return {
        "df_f_opening_balances": pl.DataFrame(
            {
                "ZUTIME": [1672531199],
                "ZASSETUID": [1],
                "ZAMOUNTACCOUNT": [500000.0],
                "ZTXDATESTR": [date(2025, 1, 1)],
            }
        ),
        "df_d_calendar": pl.DataFrame(
            {
                "Date": [date(2025, 1, 1), date(2025, 1, 31)],
                "Year": [2025, 2025],
                "Month": [1, 1],
            }
        ),
        "df_d_macro_parameters": pl.DataFrame(
            {
                "FY_Start_Date": [date(2024, 4, 1)],
                "Inflation_Rate": [0.06],
            }
        ),
        "df_d_asset_subcategory": pl.DataFrame(
            {
                "UID": [1],
                "ASSET_CATEGORY": ["Bank Accounts"],
                "ASSET_SUBCATEGORY": ["Savings"],
                "Is_Liquid": [True],
                "is_non_cash_pnl": [False],
            }
        ),
        "df_d_investment_master": pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "CATEGORY_ID": [1],
            }
        ),
        "df_f_investment_analytics_isin": pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "Closing_Date": [date(2025, 1, 31)],
                "Total_Current_Value": [120000.0],
                "Total_Invested_Value": [100000.0],
                "Asset_PnL": [20000.0],
                "Forex_PnL": [0.0],
            }
        ),
        "df_f_investment_analytics_portfolio": pl.DataFrame(
            {
                "Closing_Date": [date(2025, 1, 31)],
                "Total_Current_Value": [120000.0],
                "Total_Invested_Value": [100000.0],
                "XIRR": [0.15],
                "Unrealized_PL": [20000.0],
                "Asset_PnL": [20000.0],
                "Forex_PnL": [0.0],
            }
        ),
        "df_f_investment_analytics_currency": pl.DataFrame(
            {
                "Closing_Date": [date(2025, 1, 31)],
                "CURRENCY_ID": ["USD"],
                "Total_Current_Value": [50000.0],
            }
        ),
    }


def test_wealth_fire_execution_plan_dependencies() -> None:
    """Verify transitive dependency expansion and Gold output sets across household, wealth, and FIRE plans."""
    planner = CapabilityPlanner()

    # 1. Household Core only
    plan_hh = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])
    assert plan_hh.active_capabilities == (CapabilityId.HOUSEHOLD_CORE,)
    assert set(plan_hh.active_gold_datasets) == {
        DatasetId.WEALTH_CORE_MONTHLY,
        DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN,
        DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN,
        DatasetId.WEALTH_BUDGET_VARIANCE,
        DatasetId.WEALTH_CASHFLOW_EFFICIENCY,
        DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY,
    }
    assert DatasetId.WEALTH_ASSET_BREAKDOWN not in plan_hh.active_gold_datasets
    assert DatasetId.FIRE_ANALYTICS not in plan_hh.active_gold_datasets

    # 2. Wealth requested (transitively pulls HOUSEHOLD_CORE)
    plan_wealth = planner.create_plan(requested_capabilities=[CapabilityId.WEALTH])
    assert plan_wealth.active_capabilities == (
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.WEALTH,
    )
    assert len(plan_wealth.active_gold_datasets) == 8
    assert DatasetId.WEALTH_ASSET_BREAKDOWN in plan_wealth.active_gold_datasets
    assert DatasetId.FIRE_ANALYTICS in plan_wealth.active_gold_datasets
    assert not plan_wealth.is_capability_active(CapabilityId.FIRE)

    # 3. FIRE requested (transitively pulls HOUSEHOLD_CORE and WEALTH)
    plan_fire = planner.create_plan(requested_capabilities=[CapabilityId.FIRE])
    assert plan_fire.active_capabilities == (
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.WEALTH,
        CapabilityId.FIRE,
    )
    # FIRE operates as column-level enrichment, so produced Gold count remains 8
    assert len(plan_fire.active_gold_datasets) == 8
    assert DatasetId.WEALTH_ASSET_BREAKDOWN in plan_fire.active_gold_datasets
    assert DatasetId.FIRE_ANALYTICS in plan_fire.active_gold_datasets


def test_wealth_fire_column_inventory_queries() -> None:
    """Verify that get_capability_columns correctly retrieves column attributions for WEALTH and FIRE."""
    wealth_monthly_cols = get_capability_columns(CapabilityId.WEALTH, DatasetId.WEALTH_CORE_MONTHLY)
    assert "Total_Assets_Market" in wealth_monthly_cols
    assert "Total_Net_Worth_Market" in wealth_monthly_cols
    assert "Opening_Balance_Asset_Market" in wealth_monthly_cols
    assert "Closing_Balance_Asset_Market" in wealth_monthly_cols
    assert "Asset_Market_Delta" in wealth_monthly_cols
    assert "Liquid_Assets_Market" in wealth_monthly_cols

    fire_cols = get_capability_columns(CapabilityId.FIRE, DatasetId.FIRE_ANALYTICS)
    assert "Months_To_FI_Conservative_P90" in fire_cols
    assert "Months_To_FI_Base_P50" in fire_cols
    assert "Months_To_FI_Aggressive_P10" in fire_cols
    assert "Probability_Of_Success_Pct" in fire_cols
    assert "Years_To_FI_P50" in fire_cols
    assert "Projected_FI_Date_P50" in fire_cols
    assert "Runway_Months_Stressed_P10" in fire_cols
    assert "Runway_Months_Base_P50" in fire_cols
    assert "Terminal_Wealth_Nominal_P50" in fire_cols
    assert "Target_FI_Total_Future_Nominal" in fire_cols
    assert "Savings_Rate_Required" in fire_cols


def test_wealth_service_orchestration_household_only(
    sample_domain_dfs: dict[str, pl.DataFrame],
    mock_rules: FinancialRules,
) -> None:
    """Verify that WealthService generates solely household marts and skips wealth/FIRE when household is alone."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])

    service = WealthService(rules=mock_rules, root_seed="test_hh_only", plan=plan)
    # Add minimal required tables for full run
    dfs = dict(sample_domain_dfs)
    dfs["df_f_transfer_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "AMOUNT_PROPER": pl.Float64,
        }
    )
    dfs["df_f_income_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "BASE_AMOUNT": pl.Float64,
            "CATEGORY_ID": pl.Int64,
            "Is_Active_Income": pl.Boolean,
            "Is_Dividend_Income": pl.Boolean,
            "Is_Interest_Income": pl.Boolean,
            "Is_Non_Cash_Income": pl.Boolean,
        }
    )
    dfs["df_f_expense_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "BASE_AMOUNT": pl.Float64,
            "CATEGORY_ID": pl.Int64,
            "Is_Core_Expense": pl.Boolean,
        }
    )

    results = service.run(dfs)

    # Core monthly totals and 5 household marts must be present
    assert "df_p_tf_wealth_monthly_totals" in results
    assert "df_p_tf_category_spend_analytics" in results
    assert "df_p_tf_income_streams_monthly" in results
    assert "df_p_tf_budget_forecast_monthly" in results
    assert "df_p_tf_monthly_cashflow_summary" in results
    assert "df_p_tf_cashflow_activity_summary" in results

    # Wealth and FIRE marts must be absent
    assert "df_p_tf_net_worth_monthly_summary" not in results
    assert "df_p_tf_wealth_risk_analytics" not in results
    assert "df_p_tf_wealth_risk_analytics_inputs" not in results
    assert "df_p_tf_investment_analytics" not in results


def test_wealth_service_orchestration_wealth_without_fire(
    sample_domain_dfs: dict[str, pl.DataFrame],
    mock_rules: FinancialRules,
) -> None:
    """Verify that WealthService generates wealth and deterministic FIRE marts when WEALTH is active without FIRE."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(requested_capabilities=[CapabilityId.WEALTH])

    service = WealthService(rules=mock_rules, root_seed="test_wealth_no_fire", plan=plan)
    dfs = dict(sample_domain_dfs)
    dfs["df_f_transfer_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "AMOUNT_PROPER": pl.Float64,
        }
    )
    dfs["df_f_income_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "BASE_AMOUNT": pl.Float64,
            "CATEGORY_ID": pl.Int64,
            "Is_Active_Income": pl.Boolean,
            "Is_Dividend_Income": pl.Boolean,
            "Is_Interest_Income": pl.Boolean,
            "Is_Non_Cash_Income": pl.Boolean,
        }
    )
    dfs["df_f_expense_transactions"] = pl.DataFrame(
        schema={
            "DATE": pl.Date,
            "ASSET_ID": pl.Int64,
            "BASE_AMOUNT": pl.Float64,
            "CATEGORY_ID": pl.Int64,
            "Is_Core_Expense": pl.Boolean,
        }
    )

    results = service.run(dfs)

    assert "df_p_tf_wealth_monthly_totals" in results
    assert "df_p_tf_net_worth_monthly_summary" in results
    assert "df_p_tf_wealth_risk_analytics" in results

    # Verify simulation columns in df_p_tf_wealth_risk_analytics are None
    df_fire = results["df_p_tf_wealth_risk_analytics"].collect()
    assert df_fire["Target_FI_Today"][0] is not None
    assert df_fire["Months_To_FI_Base_P50"][0] is None
    assert df_fire["Probability_Of_Success_Pct"][0] is None


def test_pipeline_executor_presentation_skipping_telemetry(
    mock_rules: FinancialRules,
) -> None:
    """Verify that PipelineExecutor emits SKIP events for inactive WEALTH and FIRE engines."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])

    mock_emitter = MagicMock(spec=ObservabilityEmitter)
    mock_db = MagicMock()
    mock_cp = MagicMock()
    mock_cp.runs.get_run_metadata.return_value = {"settings_snapshot_id": "snap_1"}

    executor = PipelineExecutor(
        cfg=Settings(),
        status_queue=MagicMock(),
        db_manager=mock_db,
        rules=mock_rules,
        emitter=mock_emitter,
        plan=plan,
    )
    executor.dfs = {}

    # Mock _run_presentation_engine
    executor._run_presentation_engine = MagicMock()  # type: ignore[method-assign]

    executor.run_engines(cp=mock_cp, run_id="run_test_skip")

    # Assert Wealth SKIP event
    mock_emitter.emit_event.assert_any_call(
        event_code=EventCode.WEALTH_ENGINE_START,
        message="Capability 'wealth' inactive in execution plan. Skipping Wealth Engine.",
        presentation_kind=PresentationKind.SKIP,
        stage=pytest.approx(
            executor.run_engines.__annotations__.get(
                "stage", mock_emitter.emit_event.call_args[1].get("stage")
            )
        ),
    )

    # Assert FIRE SKIP event
    mock_emitter.emit_event.assert_any_call(
        event_code=EventCode.FIRE_ENGINE_START,
        message="Capability 'fire' inactive in execution plan. Skipping FIRE simulation engine.",
        presentation_kind=PresentationKind.SKIP,
        stage=pytest.approx(
            executor.run_engines.__annotations__.get(
                "stage", mock_emitter.emit_event.call_args[1].get("stage")
            )
        ),
    )

    # Ensure presentation engine was still called because HOUSEHOLD_CORE is active
    executor._run_presentation_engine.assert_called_once_with(mock_cp, "run_test_skip")


def test_source_planner_with_declarative_fixtures() -> None:
    """Verify that SourcePlanner cleanly plans against household-only, household-wealth, and household-wealth-fire fixtures."""
    fixtures_dir = Path("tests/fixtures")
    cap_planner = CapabilityPlanner()

    # 1. Household only
    src_cfg_hh = SourceConfiguration.from_toml(fixtures_dir / "sources_household_only.toml")
    plan_hh = cap_planner.create_plan([CapabilityId.HOUSEHOLD_CORE])
    planner_hh = SourcePlanner(src_cfg_hh, plan_hh)
    compiled_hh = planner_hh.compile_plan()
    assert plan_hh.active_capabilities == (CapabilityId.HOUSEHOLD_CORE,)
    assert len(plan_hh.active_gold_datasets) == 6
    assert len(compiled_hh.dataset_plans) > 0

    # 2. Household + Wealth
    src_cfg_wealth = SourceConfiguration.from_toml(fixtures_dir / "sources_household_wealth.toml")
    plan_wealth = cap_planner.create_plan([CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH])
    planner_wealth = SourcePlanner(src_cfg_wealth, plan_wealth)
    compiled_wealth = planner_wealth.compile_plan()
    assert plan_wealth.active_capabilities == (
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.WEALTH,
    )
    assert len(plan_wealth.active_gold_datasets) == 8
    assert len(compiled_wealth.dataset_plans) > 0

    # 3. Household + Wealth + FIRE
    src_cfg_fire = SourceConfiguration.from_toml(
        fixtures_dir / "sources_household_wealth_fire.toml"
    )
    plan_fire = cap_planner.create_plan(
        [CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH, CapabilityId.FIRE]
    )
    planner_fire = SourcePlanner(src_cfg_fire, plan_fire)
    compiled_fire = planner_fire.compile_plan()
    assert plan_fire.active_capabilities == (
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.WEALTH,
        CapabilityId.FIRE,
    )
    assert len(plan_fire.active_gold_datasets) == 8
    assert len(compiled_fire.dataset_plans) > 0


def _setup_isolated_fixture_env(
    tmp_path: Path,
    fixture_filename: str,
) -> tuple[Settings, SourceConfiguration]:
    """Create an isolated test environment with the given fixture and required evidence.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    fixture_filename : str
        Name of fixture TOML in tests/fixtures/.

    Returns
    -------
    tuple[Settings, SourceConfiguration]
        Isolated Settings and SourceConfiguration with rewritten file paths.
    """
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    evidence_root = Path("tests/fixtures/evidence")
    shutil.copy(evidence_root / "household" / "SOURCE_DB.sqlite", inputs_dir / "SOURCE_DB.sqlite")
    shutil.copy(
        evidence_root / "reference" / "OPENING_BALANCE.csv", inputs_dir / "OPENING_BALANCE.csv"
    )

    fixture_path = Path("tests/fixtures") / fixture_filename
    base_cfg = SourceConfiguration.from_toml(fixture_path)

    updated_sources: list[SourceConfig] = []
    for s in base_cfg.sources:
        if str(s.source_id) == "household_db":
            updated_sources.append(
                s.model_copy(
                    update={"location": str(inputs_dir / "SOURCE_DB.sqlite").replace("\\", "/")}
                )
            )
        elif str(s.source_id) == "opening_balance_csv":
            updated_sources.append(
                s.model_copy(
                    update={"location": str(inputs_dir / "OPENING_BALANCE.csv").replace("\\", "/")}
                )
            )
        else:
            updated_sources.append(s)

    isolated_cfg = base_cfg.model_copy(update={"sources": tuple(updated_sources)})

    active_caps: tuple[CapabilityId, ...]
    if "household_only" in fixture_filename:
        active_caps = (CapabilityId.HOUSEHOLD_CORE,)
    elif "household_wealth_fire" in fixture_filename:
        active_caps = (CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH, CapabilityId.FIRE)
    elif "household_wealth" in fixture_filename:
        active_caps = (CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH)
    else:
        active_caps = tuple(CapabilityId)

    settings = Settings(
        TARGET_DB_BASE_PATH=str(outputs_dir),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        DISABLE_FILE_DISCOVERER=False,
        capabilities=CapabilitySelection(enabled=active_caps),
    )
    return settings, isolated_cfg


def test_end_to_end_household_only_fixture_analytical_assertions(
    tmp_path: Path,
    mock_rules: FinancialRules,
) -> None:
    """Verify end-to-end execution of sources_household_only.toml asserts DuckDB and SQLite outputs."""
    settings, cfg = _setup_isolated_fixture_env(tmp_path, "sources_household_only.toml")
    plan = CapabilityPlanner().create_plan(settings.capabilities.enabled)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=mock_rules,
        emitter=ObservabilityEmitter(),
        plan=plan,
        source_config=cfg,
    )
    orchestrator.run()

    # 1. DuckDB Warehouse Assertions
    db = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db.open()

    for mart in [
        "gold.wealth_cashflow_expense_breakdown",
        "gold.wealth_cashflow_income_breakdown",
        "gold.wealth_budget_variance",
        "gold.wealth_cashflow_efficiency",
        "gold.wealth_cashflow_activity_summary",
        "gold.wealth_core_monthly",
    ]:
        row_cnt = db.conn.query(f"SELECT COUNT(*) FROM {mart}").fetchone()
        assert row_cnt is not None and row_cnt[0] > 0, f"{mart} should be populated"

    core_fact = db.conn.query(
        """
        SELECT 
            Total_Income, Total_Expense, Net_Cashflow_Month, Total_Net_Worth
        FROM gold.wealth_core_monthly LIMIT 1
        """
    ).fetchone()
    assert core_fact is not None
    assert core_fact[0] is not None
    assert core_fact[1] is not None
    assert core_fact[2] is not None
    assert core_fact[3] is not None

    # Pruned columns are physically absent from table DDL
    fact_cols = {
        row[1] for row in db.conn.query("PRAGMA table_info('gold.wealth_core_monthly')").fetchall()
    }
    assert "Total_Assets_Market" not in fact_cols
    assert "Closing_Investment_Book_Value" not in fact_cols
    assert "Total_Foreign_Currency_Exposure" not in fact_cols

    # Disabled capability tables do NOT exist in DuckDB
    tables_in_gold = {
        row[0]
        for row in db.conn.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'gold'"
        ).fetchall()
    }
    assert "wealth_asset_breakdown" not in tables_in_gold
    assert "fire_analytics" not in tables_in_gold

    db.close()

    # 2. SQLite Control Plane Assertions
    cp_path = Path(settings.TARGET_DB_BASE_PATH) / settings.RAW_DOCUMENT_STORE_NAME
    conn = sqlite3.connect(cp_path)
    cur = conn.cursor()

    cur.execute("SELECT status FROM cp_runs WHERE status = 'SUCCESS'")
    run_rows = cur.fetchall()
    assert len(run_rows) >= 1

    cur.execute("SELECT COUNT(*) FROM cp_simulation_runs")
    sim_cnt = cur.fetchone()[0]
    assert sim_cnt == 0, "No simulation runs should be recorded when FIRE is inactive"

    conn.close()


def test_end_to_end_household_wealth_fixture_analytical_assertions(
    tmp_path: Path,
    mock_rules: FinancialRules,
) -> None:
    """Verify end-to-end execution of sources_household_wealth.toml asserts DuckDB and SQLite outputs."""
    settings, cfg = _setup_isolated_fixture_env(tmp_path, "sources_household_wealth.toml")
    plan = CapabilityPlanner().create_plan(settings.capabilities.enabled)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=mock_rules,
        emitter=ObservabilityEmitter(),
        plan=plan,
        source_config=cfg,
    )
    orchestrator.run()

    # 1. DuckDB Warehouse Assertions
    db = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db.open()

    wb_cnt = db.conn.query("SELECT COUNT(*) FROM gold.wealth_asset_breakdown").fetchone()
    assert wb_cnt is not None and wb_cnt[0] > 0

    core_fact = db.conn.query(
        """
        SELECT 
            Total_Net_Worth, Total_Net_Worth_Market, Total_Assets_Market
        FROM gold.wealth_core_monthly LIMIT 1
        """
    ).fetchone()
    assert core_fact is not None
    assert core_fact[0] is not None
    assert core_fact[1] is not None
    assert core_fact[2] is not None

    fact_cols = {
        row[1] for row in db.conn.query("PRAGMA table_info('gold.wealth_core_monthly')").fetchall()
    }
    assert "Closing_Investment_Book_Value" not in fact_cols
    assert "Total_Foreign_Currency_Exposure" not in fact_cols

    fire_cols = {
        row[1] for row in db.conn.query("PRAGMA table_info('gold.fire_analytics')").fetchall()
    }
    assert "Months_To_FI_Base_P50" not in fire_cols
    assert "Probability_Of_Success_Pct" not in fire_cols

    fire_row = db.conn.query(
        """
        SELECT 
            Target_FI_Today, Coast_FI_Today, Lean_FI_Today, FI_Gap, Runway_Months_Linear
        FROM gold.fire_analytics LIMIT 1
        """
    ).fetchone()
    assert fire_row is not None
    assert fire_row[0] is not None
    assert fire_row[1] is not None
    assert fire_row[2] is not None
    assert fire_row[3] is not None
    assert fire_row[4] is not None

    db.close()

    # 2. SQLite Control Plane Assertions
    cp_path = Path(settings.TARGET_DB_BASE_PATH) / settings.RAW_DOCUMENT_STORE_NAME
    conn = sqlite3.connect(cp_path)
    cur = conn.cursor()

    cur.execute("SELECT status FROM cp_runs WHERE status = 'SUCCESS'")
    assert len(cur.fetchall()) >= 1

    cur.execute("SELECT COUNT(*) FROM cp_simulation_runs")
    assert cur.fetchone()[0] == 0, "No simulation runs should be recorded when FIRE is inactive"

    conn.close()


def test_end_to_end_household_wealth_fire_fixture_analytical_assertions(
    tmp_path: Path,
    mock_rules: FinancialRules,
) -> None:
    """Verify end-to-end execution of sources_household_wealth_fire.toml asserts DuckDB and SQLite outputs."""
    settings, cfg = _setup_isolated_fixture_env(tmp_path, "sources_household_wealth_fire.toml")
    plan = CapabilityPlanner().create_plan(settings.capabilities.enabled)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=mock_rules,
        emitter=ObservabilityEmitter(),
        plan=plan,
        source_config=cfg,
    )
    orchestrator.run()

    # 1. DuckDB Warehouse Assertions
    db = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db.open()

    wb_cnt = db.conn.query("SELECT COUNT(*) FROM gold.wealth_asset_breakdown").fetchone()
    assert wb_cnt is not None and wb_cnt[0] > 0

    fire_row = db.conn.query(
        """
        SELECT 
            Target_FI_Today, Coast_FI_Today, Lean_FI_Today, FI_Gap,
            Months_To_FI_Base_P50, Probability_Of_Success_Pct, Years_To_FI_P50,
            Runway_Months_Base_P50, Terminal_Wealth_Nominal_P50, Target_FI_Total_Future_Nominal
        FROM gold.fire_analytics ORDER BY MONTH_START_DATE DESC LIMIT 1
        """
    ).fetchone()
    assert fire_row is not None
    assert fire_row[0] is not None
    assert fire_row[1] is not None
    assert fire_row[2] is not None
    assert fire_row[3] is not None
    assert fire_row[4] is not None
    assert fire_row[5] is not None
    assert fire_row[6] is not None
    assert fire_row[7] is not None
    assert fire_row[8] is not None
    assert fire_row[9] is not None

    db.close()

    # 2. SQLite Control Plane Assertions
    cp_path = Path(settings.TARGET_DB_BASE_PATH) / settings.RAW_DOCUMENT_STORE_NAME
    conn = sqlite3.connect(cp_path)
    cur = conn.cursor()

    cur.execute("SELECT status FROM cp_runs WHERE status = 'SUCCESS'")
    assert len(cur.fetchall()) >= 1

    cur.execute("SELECT iterations, status FROM cp_simulation_runs")
    sim_rows = cur.fetchall()
    assert len(sim_rows) == 1, "Exactly one simulation run should be logged when FIRE is active"
    assert sim_rows[0][0] == mock_rules.assumptions.monte_carlo.iterations
    assert sim_rows[0][1] == "SUCCESS"

    conn.close()
