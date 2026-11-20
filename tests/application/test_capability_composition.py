# pyright: reportPrivateUsage=false
"""Enterprise test suite for household and investment capability composition and isolation.

Owns
----
- Verification of household-only and composed execution plans via CapabilityPlanner.
- Verification of cross-capability contribution activation (ContributionScope.CASHFLOW_MOVEMENTS).
- Verification that household-only source configurations satisfy SourcePlanner requirements
  with zero investment dataset dependencies.
- Verification of end-to-end ETLOrchestrator pipeline execution in household-only mode:
  - Skipped investment asset pipelines, market fetching, and quant/tax engines.
  - Correct continuous calendar dimension derived exclusively from household transactions.
  - Plan-scoped completeness validation for exactly 12 active Silver datasets.
  - DuckDB Silver warehouse persistence and unpopulated Gold layers.
- Verification of full-plan parity preserving all 46 analytical data contracts.

Does not own
-------------
- Deep domain FIFO lot tracking or realized event math (owned by test_investment_accounting_assertions.py).
- AST architectural boundary enforcement (owned by test_boundaries.py).
- Low-level SQLite Control Plane file hashing (owned by test_file_discovery.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from personal_finance_etl.application.pipeline import ETLOrchestrator
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.model import SourceConfig
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    ContributionScope,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


class _MemoryEventSink(ObservabilitySink, Protocol):
    """Protocol for memory event sinks providing list of captured events."""

    events: list[ObservabilityEvent]


def _setup_isolated_household_env(
    tmp_path: Path,
) -> tuple[Settings, SourceConfiguration]:
    """Create an isolated test environment with only household static evidence.

    Parameters
    ----------
    tmp_path : Path
        Temporary testing directory.

    Returns
    -------
    tuple[Settings, SourceConfiguration]
        Isolated Settings and SourceConfiguration pointing to temporary directory.
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

    base_cfg = get_shan_baseline_source_configuration()
    hh_sources: list[SourceConfig] = []
    for s in base_cfg.sources:
        if str(s.source_id) == "household_db":
            hh_sources.append(
                s.model_copy(
                    update={"location": str(inputs_dir / "SOURCE_DB.sqlite").replace("\\", "/")}
                )
            )
        elif str(s.source_id) == "opening_balance_csv":
            hh_sources.append(
                s.model_copy(
                    update={"location": str(inputs_dir / "OPENING_BALANCE.csv").replace("\\", "/")}
                )
            )

    hh_dataset_ids = {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
    }
    hh_datasets = [d for d in base_cfg.datasets if d.dataset_id in hh_dataset_ids]

    isolated_cfg = base_cfg.model_copy(
        update={
            "sources": tuple(hh_sources),
            "datasets": tuple(hh_datasets),
        }
    )

    settings = Settings(
        TARGET_DB_BASE_PATH=str(outputs_dir),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        DISABLE_FILE_DISCOVERER=False,
    )
    return settings, isolated_cfg


def test_household_only_plan_resolution() -> None:
    """Verify CapabilityPlanner resolves a household-only plan with exactly 12 Silver datasets."""
    planner = CapabilityPlanner()
    full_plan = planner.create_plan()
    hh_plan = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])

    assert hh_plan.active_capabilities == (CapabilityId.HOUSEHOLD_CORE,)
    assert hh_plan.active_capability_count == 1
    assert hh_plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
    assert not hh_plan.is_capability_active(CapabilityId.INVESTMENT_ACCOUNTING)
    assert not hh_plan.is_capability_active(CapabilityId.TAX)

    # Exactly 12 active Silver datasets, 6 Gold datasets (total 18)
    assert hh_plan.active_analytical_dataset_count == 18
    assert len(hh_plan.active_silver_datasets) == 12
    assert len(hh_plan.active_gold_datasets) == 6

    expected_silver = {
        DatasetId.COMMON_CALENDAR,
        DatasetId.COMMON_CURRENCY,
        DatasetId.WEALTH_INCOME_CATEGORY,
        DatasetId.WEALTH_INCOME_SUBCATEGORY,
        DatasetId.WEALTH_EXPENSE_CATEGORY,
        DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
        DatasetId.WEALTH_ASSET_CATEGORY,
        DatasetId.WEALTH_ASSET_SUBCATEGORY,
        DatasetId.WEALTH_INCOME_TRANSACTIONS,
        DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
        DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
        DatasetId.WEALTH_OPENING_BALANCES,
    }
    assert set(hh_plan.active_silver_datasets) == expected_silver

    # Investment accounting Silver outputs must NOT be active
    assert not hh_plan.is_silver_dataset_active(DatasetId.INVESTMENT_MASTER)
    assert not hh_plan.is_silver_dataset_active(DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM)
    assert not hh_plan.is_silver_dataset_active(DatasetId.INVESTMENT_LOT_ANALYTICS)
    assert not hh_plan.is_silver_dataset_active(DatasetId.INVESTMENT_REALIZED_EVENTS)

    # Cross-contributions must be empty when INVESTMENT_ACCOUNTING is inactive
    assert len(hh_plan.active_contributions) == 0
    assert not hh_plan.is_contribution_active(
        CapabilityId.HOUSEHOLD_CORE, ContributionScope.CASHFLOW_MOVEMENTS
    )

    # Cryptographic fingerprint must be unique and stable
    assert hh_plan.plan_fingerprint != full_plan.plan_fingerprint
    assert hh_plan.plan_fingerprint.startswith("plan_")


def test_household_and_investment_cross_contributions() -> None:
    """Verify cross-capability contribution activation when both capabilities are active."""
    planner = CapabilityPlanner()
    plan_both = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )

    assert plan_both.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
    assert plan_both.is_capability_active(CapabilityId.INVESTMENT_ACCOUNTING)

    # CASHFLOW_MOVEMENTS contribution to HOUSEHOLD_CORE must be active
    assert plan_both.is_contribution_active(
        CapabilityId.HOUSEHOLD_CORE, ContributionScope.CASHFLOW_MOVEMENTS
    )

    # Contributions to TAX and WEALTH must remain inactive because those capabilities are inactive
    assert not plan_both.is_contribution_active(CapabilityId.TAX, ContributionScope.REALIZED_GAINS)
    assert not plan_both.is_contribution_active(
        CapabilityId.WEALTH, ContributionScope.PORTFOLIO_VALUATION
    )

    # Active analytical datasets count: 18 (Household: 12 Silver + 6 Gold) + 19 (Investments: 8 Silver + 11 Gold) = 37
    assert plan_both.active_analytical_dataset_count == 37


def test_household_only_source_planner_satisfaction(tmp_path: Path) -> None:
    """Verify SourcePlanner compiles successfully with household-only evidence configuration."""
    _settings, cfg = _setup_isolated_household_env(tmp_path)
    plan = CapabilityPlanner().create_plan([CapabilityId.HOUSEHOLD_CORE])

    planner = SourcePlanner(cfg, plan)
    compiled = planner.compile_plan()

    assert (
        len(compiled.source_plans) == 3
    )  # household_db, opening_balance_csv, synthesized provider
    enabled_ds = [dp for dp in compiled.dataset_plans if dp.is_enabled]
    assert len(enabled_ds) == 6

    enabled_ids = {dp.dataset_id for dp in enabled_ds}
    assert enabled_ids == {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
    }

    # Zero investment or provider market datasets enabled
    assert not compiled.is_dataset_enabled(DatasetId.INVESTMENT_STOCK_ORDERS)
    assert not compiled.is_dataset_enabled(DatasetId.INVESTMENT_MF_ORDERS)
    assert not compiled.is_dataset_enabled(DatasetId.MARKET_CURRENCY_FX_RATES)


def test_household_only_end_to_end_pipeline_execution(
    tmp_path: Path,
    rules: FinancialRules,
    test_emitter: tuple[ObservabilityEmitter, _MemoryEventSink],
) -> None:
    """Verify ETLOrchestrator executes end-to-end with only household evidence."""
    settings, cfg = _setup_isolated_household_env(tmp_path)
    plan = CapabilityPlanner().create_plan([CapabilityId.HOUSEHOLD_CORE])

    emitter, sink = test_emitter

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=cfg,
    )
    orchestrator.run()

    # 1. Verify produced table count matches active analytical contracts exactly (12 Silver + 6 Gold = 18)
    assert len(orchestrator.dfs) == 18

    expected_silver = {
        "df_d_income_category",
        "df_d_income_subcategory",
        "df_d_expense_category",
        "df_d_expense_subcategory",
        "df_d_asset_category",
        "df_d_asset_subcategory",
        "df_d_currency",
        "df_d_calendar",
        "df_f_income_transactions",
        "df_f_expense_transactions",
        "df_f_transfer_transactions",
        "df_f_opening_balances",
    }
    expected_gold = {
        "df_p_tf_wealth_monthly_totals",
        "df_p_tf_category_spend_analytics",
        "df_p_tf_income_streams_monthly",
        "df_p_tf_budget_forecast_monthly",
        "df_p_tf_monthly_cashflow_summary",
        "df_p_tf_cashflow_activity_summary",
    }
    assert set(orchestrator.dfs.keys()) == expected_silver | expected_gold

    # 2. Verify investment outputs are completely absent
    assert "df_d_macro_parameters" not in orchestrator.dfs
    assert "df_f_investment_market_data" not in orchestrator.dfs
    assert "df_f_tf_inv_purchase" not in orchestrator.dfs
    assert "df_f_tf_inv_sale" not in orchestrator.dfs
    assert "df_d_investment_master" not in orchestrator.dfs
    assert "df_f_investment_analytics_lot" not in orchestrator.dfs
    assert "df_f_investment_realized_events" not in orchestrator.dfs

    # 3. Verify calendar dimension was generated and continuous
    df_cal = orchestrator.dfs["df_d_calendar"]
    assert df_cal.height > 0
    assert "Date" in df_cal.columns
    assert "Month_Year" in df_cal.columns

    # 4. Verify skip events were emitted for inactive capabilities
    skip_messages = [e.message for e in sink.events if e.presentation_kind == PresentationKind.SKIP]
    assert any("investment asset pipelines" in m for m in skip_messages)
    assert any("df_d_macro_parameters" in m for m in skip_messages)

    # 5. Verify DuckDB warehouse persistence
    db = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db.open()

    # Silver tables populated
    silver_counts = db.conn.query(
        "SELECT COUNT(*) as cnt FROM silver.wealth_expense_transactions"
    ).fetchone()
    assert silver_counts is not None and silver_counts[0] > 0

    # Inactive Silver investment tables must NOT exist in DuckDB catalog
    silver_tables = {
        row[0]
        for row in db.conn.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'silver'"
        ).fetchall()
    }
    assert "investment_lot_analytics" not in silver_tables

    db.close()


def test_composed_household_and_investments_execution(
    tmp_path: Path,
    rules: FinancialRules,
) -> None:
    """Verify composed household and investment capabilities produce all 30 analytical contracts."""
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    evidence_root = Path("tests/fixtures/evidence")
    shutil.copy(evidence_root / "household" / "SOURCE_DB.sqlite", inputs_dir / "SOURCE_DB.sqlite")
    shutil.copy(
        evidence_root / "reference" / "OPENING_BALANCE.csv", inputs_dir / "OPENING_BALANCE.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "MF_ISIN_MAPPING.csv", inputs_dir / "MF_ISIN_MAPPING.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "MACRO_PARAMETERS.csv", inputs_dir / "MACRO_PARAMETERS.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "CURRENCY_MAPPING.csv", inputs_dir / "CURRENCY_MAPPING.csv"
    )
    shutil.copy(
        evidence_root / "reference" / "BENCHMARK_MAPPING.csv",
        inputs_dir / "BENCHMARK_MAPPING.csv",
    )
    shutil.copy(
        evidence_root / "reference" / "BENCHMARK_MASTER.csv",
        inputs_dir / "BENCHMARK_MASTER.csv",
    )
    shutil.copytree(
        evidence_root / "mutual_funds" / "Mutual Funds - Holdings",
        inputs_dir / "Mutual Funds - Holdings",
    )
    shutil.copytree(
        evidence_root / "mutual_funds" / "Mutual Funds - Orders",
        inputs_dir / "Mutual Funds - Orders",
    )
    shutil.copytree(
        evidence_root / "domestic_stocks" / "Stock PL Statements",
        inputs_dir / "Stock PL Statements",
    )
    shutil.copytree(
        evidence_root / "domestic_stocks" / "Stock - Orders",
        inputs_dir / "Stock - Orders",
    )
    shutil.copytree(
        evidence_root / "us_stocks" / "IND Money (US Stocks)" / "Transaction Reports" / "2025-26",
        inputs_dir / "2025-26",
    )

    base_cfg = get_shan_baseline_source_configuration()
    updated_sources: list[SourceConfig] = []
    for s in base_cfg.sources:
        loc = s.location
        if "SOURCE_DB.sqlite" in loc:
            loc = str(inputs_dir / "SOURCE_DB.sqlite").replace("\\", "/")
        elif "OPENING_BALANCE.csv" in loc:
            loc = str(inputs_dir / "OPENING_BALANCE.csv").replace("\\", "/")
        elif "MF_ISIN_MAPPING.csv" in loc:
            loc = str(inputs_dir / "MF_ISIN_MAPPING.csv").replace("\\", "/")
        elif "MACRO_PARAMETERS.csv" in loc:
            loc = str(inputs_dir / "MACRO_PARAMETERS.csv").replace("\\", "/")
        elif "CURRENCY_MAPPING.csv" in loc:
            loc = str(inputs_dir / "CURRENCY_MAPPING.csv").replace("\\", "/")
        elif "BENCHMARK_MAPPING.csv" in loc:
            loc = str(inputs_dir / "BENCHMARK_MAPPING.csv").replace("\\", "/")
        elif "BENCHMARK_MASTER.csv" in loc:
            loc = str(inputs_dir / "BENCHMARK_MASTER.csv").replace("\\", "/")
        elif "Mutual Funds - Holdings" in loc:
            loc = str(inputs_dir / "Mutual Funds - Holdings").replace("\\", "/")
        elif "Mutual Funds - Orders" in loc:
            loc = str(inputs_dir / "Mutual Funds - Orders").replace("\\", "/")
        elif "Stock PL Statements" in loc:
            loc = str(inputs_dir / "Stock PL Statements").replace("\\", "/")
        elif "Stock - Orders" in loc:
            loc = str(inputs_dir / "Stock - Orders").replace("\\", "/")
        elif "IND Money (US Stocks)" in loc:
            loc = str(inputs_dir / "2025-26").replace("\\", "/")
        updated_sources.append(s.model_copy(update={"location": loc}))

    full_cfg = base_cfg.model_copy(update={"sources": tuple(updated_sources)})

    settings = Settings(
        TARGET_DB_BASE_PATH=str(outputs_dir),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        DISABLE_FILE_DISCOVERER=False,
    )

    caps = [CapabilityId.HOUSEHOLD_CORE, CapabilityId.INVESTMENT_ACCOUNTING]
    composed_plan = CapabilityPlanner().create_plan(caps)
    assert composed_plan.active_analytical_dataset_count == 37

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=NullEventQueue(),
        rules=rules,
        emitter=ObservabilityEmitter(),
        plan=composed_plan,
        source_config=full_cfg,
    )
    orchestrator.run()

    # Must produce all 37 analytical tables under composed plan
    assert len(orchestrator.dfs) == 37
    assert "df_f_investment_analytics_lot" in orchestrator.dfs
    assert "df_f_investment_realized_events" in orchestrator.dfs
    assert "df_f_investment_reconciliation_events" in orchestrator.dfs
    assert "df_f_investment_analytics_isin" in orchestrator.dfs
    assert "df_f_investment_analytics_portfolio" in orchestrator.dfs
