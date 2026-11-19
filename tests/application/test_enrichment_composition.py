# pyright: reportPrivateUsage=false
"""Enterprise test suite for benchmark and foreign asset enrichment capability composition.

Owns
----
- Verification of domestic-only, benchmark-disabled, and foreign-enabled ExecutionPlans.
- Verification that ExecutionPlan.is_enrichment_required correctly identifies external market requirements.
- Verification of CAPABILITY_COLUMN_INVENTORY queries via get_capability_columns.
- Verification that domestic-only source configuration (sources_domestic_investments.toml)
  compiles cleanly via SourcePlanner with zero foreign/US evidence and zero benchmark files.
- Verification that TransformationDAG conditionally skips USStockPipeline and benchmark joins.
- Verification that market sync processes skip external fetching when enrichments are inactive.

Does not own
-------------
- Deep domain math or PyXIRR solver iterations (owned by test_enrichment_source_gating.py).
- AST architectural boundary enforcement (owned by test_boundaries.py).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.application.pipeline.transformer import TransformationDAG
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.contracts.capabilities import (
    CAPABILITY_COLUMN_INVENTORY,
    CapabilityId,
    ExternalEnrichmentId,
    get_capability_columns,
)
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter


def test_domestic_only_execution_plan_dependencies() -> None:
    """Verify that domestic-only investment accounting requires zero foreign or benchmark evidence."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )

    # 1. Active capabilities
    assert plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
    assert plan.is_capability_active(CapabilityId.INVESTMENT_ACCOUNTING)
    assert not plan.is_capability_active(CapabilityId.BENCHMARK_ENRICHMENT)
    assert not plan.is_capability_active(CapabilityId.FOREIGN_ASSET_ENRICHMENT)
    assert not plan.is_capability_active(CapabilityId.TAX)

    # 2. Required Bronze datasets must contain zero benchmark or foreign datasets
    assert DatasetId.INVESTMENT_BENCHMARK_MAPPING not in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_BENCHMARK_MASTER not in plan.required_bronze_datasets
    assert DatasetId.MARKET_BENCHMARK_HISTORY not in plan.required_bronze_datasets
    assert DatasetId.MARKET_CURRENCY_MAPPING not in plan.required_bronze_datasets
    assert DatasetId.MARKET_CURRENCY_FX_RATES not in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS not in plan.required_bronze_datasets
    assert DatasetId.MARKET_US_STOCK_PRICES not in plan.required_bronze_datasets

    # 3. Core domestic investment datasets must remain required
    assert DatasetId.INVESTMENT_MF_ISIN_MAPPING in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_MACRO_PARAMETERS in plan.required_bronze_datasets
    assert DatasetId.MARKET_MF_HOLDINGS in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_MF_ORDERS in plan.required_bronze_datasets
    assert DatasetId.MARKET_STOCK_HOLDINGS in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_STOCK_ORDERS in plan.required_bronze_datasets

    # 4. Zero external provider enrichments
    assert len(plan.required_external_enrichments) == 0
    assert not plan.is_enrichment_required(ExternalEnrichmentId.BENCHMARK_PRICES)
    assert not plan.is_enrichment_required(ExternalEnrichmentId.CURRENCY_FX_RATES)
    assert not plan.is_enrichment_required(ExternalEnrichmentId.US_STOCK_PRICES)


def test_benchmark_disabled_execution_plan_dependencies() -> None:
    """Verify that when benchmark is disabled but foreign is enabled, only FX/US enrichments are active."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
            CapabilityId.FOREIGN_ASSET_ENRICHMENT,
        ]
    )

    assert plan.is_capability_active(CapabilityId.FOREIGN_ASSET_ENRICHMENT)
    assert not plan.is_capability_active(CapabilityId.BENCHMARK_ENRICHMENT)

    # Benchmark requirements absent
    assert DatasetId.INVESTMENT_BENCHMARK_MAPPING not in plan.required_bronze_datasets
    assert DatasetId.MARKET_BENCHMARK_HISTORY not in plan.required_bronze_datasets
    assert not plan.is_enrichment_required(ExternalEnrichmentId.BENCHMARK_PRICES)

    # Foreign requirements active
    assert DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS in plan.required_bronze_datasets
    assert DatasetId.MARKET_CURRENCY_FX_RATES in plan.required_bronze_datasets
    assert plan.is_enrichment_required(ExternalEnrichmentId.CURRENCY_FX_RATES)
    assert plan.is_enrichment_required(ExternalEnrichmentId.US_STOCK_PRICES)


def test_foreign_enabled_execution_plan_dependencies() -> None:
    """Verify that full Shan plan requires all 3 external enrichments."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
            CapabilityId.BENCHMARK_ENRICHMENT,
            CapabilityId.FOREIGN_ASSET_ENRICHMENT,
            CapabilityId.TAX,
            CapabilityId.WEALTH,
            CapabilityId.FIRE,
        ]
    )

    assert plan.is_enrichment_required(ExternalEnrichmentId.BENCHMARK_PRICES)
    assert plan.is_enrichment_required(ExternalEnrichmentId.CURRENCY_FX_RATES)
    assert plan.is_enrichment_required(ExternalEnrichmentId.US_STOCK_PRICES)
    assert DatasetId.INVESTMENT_BENCHMARK_MAPPING in plan.required_bronze_datasets
    assert DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS in plan.required_bronze_datasets


def test_capability_column_inventory_queries() -> None:
    """Verify that get_capability_columns correctly partitions benchmark vs foreign columns."""
    bm_lot_cols = get_capability_columns(
        CapabilityId.BENCHMARK_ENRICHMENT, DatasetId.INVESTMENT_LOT_ANALYTICS
    )
    assert "BENCHMARK_ID" in bm_lot_cols
    assert "BM_Buy_Price" in bm_lot_cols
    assert "BM_XIRR" in bm_lot_cols
    assert "Active_Return" in bm_lot_cols
    assert "Lot_Alpha" in bm_lot_cols
    assert "Is_Lagging_Benchmark" in bm_lot_cols

    fx_lot_cols = get_capability_columns(
        CapabilityId.FOREIGN_ASSET_ENRICHMENT, DatasetId.INVESTMENT_LOT_ANALYTICS
    )
    assert "CURRENCY_ID" in fx_lot_cols
    assert "Buy_Value_Local" in fx_lot_cols
    assert "Forex_PnL" in fx_lot_cols
    assert "Forex_Contribution_Pct" in fx_lot_cols
    assert "XIRR_Local" in fx_lot_cols
    assert "FX_XIRR_Impact" in fx_lot_cols

    # Ensure zero overlap between benchmark-only and foreign-only analytical sets
    overlap = set(bm_lot_cols).intersection(set(fx_lot_cols))
    assert len(overlap) == 0

    # Verify Gold mart column mapping
    bm_isin_cols = get_capability_columns(
        CapabilityId.BENCHMARK_ENRICHMENT, DatasetId.INVESTMENT_BY_ISIN
    )
    assert "BM_XIRR" in bm_isin_cols
    assert "Active_Return" in bm_isin_cols

    fx_isin_cols = get_capability_columns(
        CapabilityId.FOREIGN_ASSET_ENRICHMENT, DatasetId.INVESTMENT_BY_ISIN
    )
    assert "Forex_PnL" in fx_isin_cols
    assert "XIRR_Local" in fx_isin_cols

    # Verify inventory is registered
    assert CapabilityId.BENCHMARK_ENRICHMENT in CAPABILITY_COLUMN_INVENTORY
    assert CapabilityId.FOREIGN_ASSET_ENRICHMENT in CAPABILITY_COLUMN_INVENTORY


def test_source_planner_satisfies_domestic_investments() -> None:
    """Verify that SourcePlanner compiles domestic-only source config with zero foreign/benchmark errors."""
    config = SourceConfiguration.from_toml("tests/fixtures/sources_domestic_investments.toml")
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )

    source_planner = SourcePlanner(config, plan)
    compiled = source_planner.compile_plan()

    assert len(compiled.source_plans) > 0
    assert len(compiled.dataset_plans) > 0

    # Assert no foreign or benchmark dataset plan is required or enabled
    for dp in compiled.dataset_plans:
        if dp.dataset_id in (
            DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            DatasetId.INVESTMENT_BENCHMARK_MASTER,
            DatasetId.MARKET_BENCHMARK_HISTORY,
            DatasetId.MARKET_CURRENCY_FX_RATES,
            DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
            DatasetId.MARKET_US_STOCK_PRICES,
        ):
            assert not dp.is_required
            assert not dp.is_enabled


def test_transformation_dag_skips_us_and_benchmark_when_disabled() -> None:
    """Verify TransformationDAG runs asset pipelines without USStockPipeline and without benchmark mapping."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )
    rules = FinancialRules.from_toml("tests/fixtures/financial_rules.toml")
    emitter = ObservabilityEmitter()

    # Construct minimal domestic dataset collection
    holdings_df = pl.DataFrame(
        {
            "Scheme Name": ["Aditya Birla Sun Life Frontline Equity Fund"],
            "AMC": ["Birla"],
            "Category": ["Equity"],
            "Sub-category": ["Large Cap"],
            "Folio No.": ["1018273"],
            "Source": ["CAS"],
            "Units": [100.0],
            "Invested Value": [4000.0],
            "Current Value": [5000.0],
            "Returns": [1000.0],
            "XIRR": [12.5],
            "Month Date": ["2024-03-31"],
            "artifact_id": ["art_01"],
        }
    )
    orders_df = pl.DataFrame(
        {
            "Month Date": ["2023-01-31"],
            "Scheme Name": ["Aditya Birla Sun Life Frontline Equity Fund"],
            "Transaction Type": ["Purchase"],
            "Units": [100.0],
            "NAV": [40.0],
            "Amount": [4000.0],
            "Date": ["2023-01-15"],
            "artifact_id": ["art_02"],
        }
    )
    isin_map_df = pl.DataFrame(
        {
            "INSTRUMENT_NAME": ["Aditya Birla Sun Life Frontline Equity Fund"],
            "ISIN": ["INF209K01157"],
        }
    )
    macro_df = pl.DataFrame(
        {
            "FY": ["2023-24"],
            "Equity_LTCG_Exemption": [100000.0],
        }
    )

    extracted = DatasetCollection(
        frames={
            DatasetId.MARKET_MF_HOLDINGS: holdings_df,
            DatasetId.INVESTMENT_MF_ORDERS: orders_df,
            DatasetId.INVESTMENT_MF_ISIN_MAPPING: isin_map_df,
            DatasetId.INVESTMENT_MACRO_PARAMETERS: macro_df,
        }
    )
    # Notice: ZERO US stock files, ZERO benchmark mapping files!

    subcat_lazy = pl.LazyFrame(
        {
            "UID": ["ASUB_01"],
            "ASSET_NAME": ["Mutual Funds"],
            "CATEGORY_SUB_NAME": ["Mutual Funds"],
            "ASSET_SUB_NAME": ["Mutual Funds"],
            "ASSET_SUB_ID": ["ASUB_01"],
            "CATEGORY_SUB_ID": ["CSUB_01"],
            "CURRENCY_ID": ["INR_INR"],
        }
    )

    dag = TransformationDAG(
        cfg=Settings(),
        status_queue=NullEventQueue(),
        rules=rules,
        emitter=emitter,
        plan=plan,
    )
    assets = dag._run_asset_pipelines(extracted, subcat_lazy)

    assert "df_f_investment_market_data" in assets
    assert "df_f_tf_inv_purchase" in assets
    assert "df_f_tf_inv_sale" in assets
    assert "df_d_investment_master" in assets

    master_df = assets["df_d_investment_master"].collect()
    assert "ISIN" in master_df.columns
    assert "BENCHMARK_ID" in master_df.columns
    # Benchmark ID must be null because BENCHMARK_ENRICHMENT is disabled
    assert master_df.select(pl.col("BENCHMARK_ID").drop_nulls()).height == 0
