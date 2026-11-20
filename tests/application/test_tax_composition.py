# pyright: reportPrivateUsage=false
"""Enterprise test suite for tax capability composition and planning invariants.

Owns
----
- Verification of tax-enabled and tax-disabled ExecutionPlans.
- Verification that ExecutionPlan correctly identifies required and produced tax datasets.
- Verification of CAPABILITY_COLUMN_INVENTORY queries via get_capability_columns for CapabilityId.TAX.
- Verification that requesting TAX without required investment orders evidence fails in SourcePlanner.
- Verification that tax engine execution is conditionally bypassed with PresentationKind.SKIP when TAX is inactive.

Does not own
-------------
- Deep domain tax math, Section 112A grandfathering, or PyXIRR solver iterations (owned by test_tax_source_gating.py).
- AST architectural boundary enforcement (owned by test_boundaries.py).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    SourcePlanner,
    SourcePlanningError,
)
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector, SqliteSelector
from personal_finance_etl.contracts.capabilities import (
    CAPABILITY_COLUMN_INVENTORY,
    CapabilityId,
    get_capability_columns,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import EventCode, PresentationKind
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter


def test_tax_enabled_execution_plan_dependencies() -> None:
    """Verify that requesting TAX transitively activates HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(requested_capabilities=[CapabilityId.TAX])

    # 1. Transitive resolution
    assert plan.is_capability_active(CapabilityId.TAX)
    assert plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
    assert plan.is_capability_active(CapabilityId.INVESTMENT_ACCOUNTING)
    assert not plan.is_capability_active(CapabilityId.BENCHMARK_ENRICHMENT)
    assert not plan.is_capability_active(CapabilityId.FOREIGN_ASSET_ENRICHMENT)
    assert not plan.is_capability_active(CapabilityId.WEALTH)
    assert not plan.is_capability_active(CapabilityId.FIRE)

    # 2. Produced Silver datasets
    assert DatasetId.TAX_EVENTS in plan.active_silver_datasets
    assert DatasetId.INVESTMENT_REALIZED_EVENTS in plan.active_silver_datasets

    # 3. Produced Gold datasets
    assert DatasetId.TAX_YEAR_SUMMARY in plan.active_gold_datasets
    assert DatasetId.TAX_INCOME_BREAKDOWN in plan.active_gold_datasets
    assert DatasetId.TAX_RECONCILIATION in plan.active_gold_datasets


def test_tax_disabled_execution_plan_dependencies() -> None:
    """Verify that when TAX is disabled, tax marts and tables are absent from produced datasets."""
    planner = CapabilityPlanner()
    plan = planner.create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )

    assert not plan.is_capability_active(CapabilityId.TAX)
    assert DatasetId.TAX_EVENTS not in plan.active_silver_datasets
    assert DatasetId.TAX_YEAR_SUMMARY not in plan.active_gold_datasets
    assert DatasetId.TAX_INCOME_BREAKDOWN not in plan.active_gold_datasets
    assert DatasetId.TAX_RECONCILIATION not in plan.active_gold_datasets


def test_tax_column_inventory_queries() -> None:
    """Verify that get_capability_columns correctly identifies gated tax columns across marts."""
    lot_tax_cols = get_capability_columns(CapabilityId.TAX, DatasetId.INVESTMENT_LOT_ANALYTICS)
    assert "TAX_TYPE" in lot_tax_cols
    assert "TAX_SUBTYPE" in lot_tax_cols
    assert "Tax_Rate" in lot_tax_cols
    assert "LTCG_Threshold_Days" in lot_tax_cols
    assert "Days_To_LTCG" in lot_tax_cols
    assert "Unrealized_LTCG" in lot_tax_cols
    assert "Unrealized_STCG" in lot_tax_cols
    assert "Unrealized_Gain" in lot_tax_cols
    assert "Unrealized_LTCL" in lot_tax_cols
    assert "Unrealized_STCL" in lot_tax_cols
    assert "Unrealized_Loss" in lot_tax_cols
    assert "LTCG_Tax_If_Sold" in lot_tax_cols
    assert "STCG_Tax_If_Sold" in lot_tax_cols
    assert "After_Tax_PL" in lot_tax_cols
    assert "After_Tax_Close_Value" in lot_tax_cols
    assert "After_Tax_XIRR" in lot_tax_cols
    assert "FY" in lot_tax_cols
    assert "FY_Realized_LTCG" in lot_tax_cols
    assert "FY_Realized_STCG" in lot_tax_cols
    assert "FY_Realized_Gain" in lot_tax_cols
    assert "FY_Realized_LTCL" in lot_tax_cols
    assert "FY_Realized_STCL" in lot_tax_cols
    assert "FY_Realized_Loss" in lot_tax_cols
    assert "FY_Realized_Net_PnL" in lot_tax_cols
    assert "Equity_LTCG_Exemption" in lot_tax_cols
    assert "Stepup_Eligible" in lot_tax_cols
    assert "Can_Harvest_Loss" in lot_tax_cols
    assert "Harvest_Recommendation" in lot_tax_cols

    re_tax_cols = get_capability_columns(CapabilityId.TAX, DatasetId.INVESTMENT_REALIZED_EVENTS)
    assert "Applied_Rate" in re_tax_cols
    assert "Estimated_Tax" in re_tax_cols

    isin_tax_cols = get_capability_columns(CapabilityId.TAX, DatasetId.INVESTMENT_BY_ISIN)
    assert "LTCG_Tax_If_Sold" in isin_tax_cols
    assert "STCG_Tax_If_Sold" in isin_tax_cols
    assert "Unrealized_LTCG" in isin_tax_cols
    assert "Unrealized_STCG" in isin_tax_cols
    assert "Unrealized_LTCL" in isin_tax_cols
    assert "Unrealized_STCL" in isin_tax_cols

    wealth_tax_cols = get_capability_columns(
        CapabilityId.TAX, DatasetId.INVESTMENT_PORTFOLIO_SUMMARY
    )
    assert "ISIN_Harvestable_Loss" in wealth_tax_cols
    assert "Tax_Harvesting_Priority_Score" in wealth_tax_cols

    # Verify entire tax tables are marked as owned by TAX
    tax_year_cols = get_capability_columns(CapabilityId.TAX, DatasetId.TAX_YEAR_SUMMARY)
    assert "Gross_Taxable_Income" in tax_year_cols
    assert "Net_Tax_Payable" in tax_year_cols

    assert CapabilityId.TAX in CAPABILITY_COLUMN_INVENTORY


def test_tax_requested_without_investment_evidence_fails_source_planning() -> None:
    """Verify that requesting TAX with household-only evidence fails in SourcePlanner."""
    fake_sources = (
        SourceConfig(
            source_id=SourceId("fake_sqlite"),
            provider_type=ProviderType.SQLITE,
            location="/nonexistent/fake.sqlite",
            enabled=True,
        ),
        SourceConfig(
            source_id=SourceId("fake_csv"),
            provider_type=ProviderType.CSV,
            location="/nonexistent/fake.csv",
            enabled=True,
        ),
    )
    # Only household datasets, zero investment orders or market data
    fake_datasets = (
        SourceDatasetConfig(
            source_id=SourceId("fake_sqlite"),
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            selector=SqliteSelector(table_name="ZCATEGORY"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("fake_sqlite"),
            dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
            selector=SqliteSelector(table_name="ASSETGROUP"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("fake_sqlite"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("fake_sqlite"),
            dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
            selector=SqliteSelector(table_name="CURRENCY"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("fake_sqlite"),
            dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
            selector=SqliteSelector(table_name="INOUTCOME"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("fake_csv"),
            dataset_id=DatasetId.HOUSEHOLD_OPENING_BALANCES,
            selector=CsvSelector(),
            enabled=True,
        ),
    )

    cfg = SourceConfiguration(
        sources=fake_sources,
        datasets=fake_datasets,
    )

    plan = CapabilityPlanner().create_plan(requested_capabilities=(CapabilityId.TAX,))
    planner = SourcePlanner(cfg, plan)

    with pytest.raises(SourcePlanningError) as exc_info:
        planner.compile_plan()

    assert "cannot be satisfied by configured source bindings" in str(exc_info.value)


class _CaptureSink:
    """In-memory sink capturing canonical events for test assertions."""

    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass


def test_pipeline_executor_skips_tax_engine_when_tax_disabled() -> None:
    """Verify PipelineExecutor emits SKIP telemetry and bypasses TaxEngine when TAX is inactive."""
    plan = CapabilityPlanner().create_plan(
        requested_capabilities=[
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )
    assert not plan.is_capability_active(CapabilityId.TAX)

    sink = _CaptureSink()
    emitter = ObservabilityEmitter(sinks=[sink])

    executor = PipelineExecutor(
        cfg=Settings(),
        status_queue=MagicMock(),
        db_manager=MagicMock(),
        plan=plan,
        emitter=emitter,
    )

    executor._run_quant_engine = MagicMock()  # type: ignore[method-assign]
    executor._run_tax_engine = MagicMock()  # type: ignore[method-assign]
    executor._run_presentation_engine = MagicMock()  # type: ignore[method-assign]
    executor.run_engines(cp=None, run_id="test_run_tax_disabled")

    # Assert _run_quant_engine was called but _run_tax_engine was NEVER called
    executor._run_quant_engine.assert_called_once_with("test_run_tax_disabled")
    executor._run_tax_engine.assert_not_called()

    # Assert EventCode.TAX_ENGINE_START with PresentationKind.SKIP was emitted
    tax_skips = [
        e
        for e in sink.events
        if getattr(e, "event_code", None) == EventCode.TAX_ENGINE_START
        and getattr(e, "presentation_kind", None) == PresentationKind.SKIP
    ]
    assert len(tax_skips) == 1
    assert "tax" in str(getattr(tax_skips[0], "message", "")).lower()
    assert "inactive" in str(getattr(tax_skips[0], "message", "")).lower()
