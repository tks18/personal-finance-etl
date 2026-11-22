"""Unit and integration tests for source binding planning.

Validates that SourcePlanner compiles physical source binding plans from the decoupled
source topology, correctly links parent sources to child bindings, propagates enablement
and change-detection policies, and provides reliable binding plan lookups.
"""

from __future__ import annotations

import pytest

from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.config.sources.compiler import derive_source_binding_id
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector, ExcelSelector
from personal_finance_etl.contracts.canonical_plans import SourceBindingPlan
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.sources import ProviderType, SourceBindingId, SourceId


@pytest.fixture
def multi_binding_source_configuration() -> SourceConfiguration:
    """Fixture providing a source configuration with multiple sources and bindings."""
    src1 = SourceConfig(
        source_id=SourceId("broker_alpha"),
        provider_type=ProviderType.EXCEL,
        location="data/alpha",
        enabled=True,
    )
    src2 = SourceConfig(
        source_id=SourceId("broker_beta"),
        provider_type=ProviderType.CSV,
        location="data/beta",
        enabled=False,
    )

    ds1 = SourceDatasetConfig(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        source_id=SourceId("broker_alpha"),
        selector=ExcelSelector(sheet_name="Orders"),
        mapping=[],
        normalization=[],
        identity=None,
        fields=[],
    )
    ds2 = SourceDatasetConfig(
        dataset_id=DatasetId.MARKET_STOCK_HOLDINGS,
        source_id=SourceId("broker_alpha"),
        selector=ExcelSelector(sheet_name="Holdings"),
        mapping=[],
        normalization=[],
        identity=None,
        fields=[],
    )
    ds3 = SourceDatasetConfig(
        dataset_id=DatasetId.INVESTMENT_MF_ORDERS,
        source_id=SourceId("broker_beta"),
        selector=CsvSelector(file_pattern="*.csv"),
        mapping=[],
        normalization=[],
        identity=None,
        fields=[],
    )

    return SourceConfiguration(sources=(src1, src2), datasets=(ds1, ds2, ds3))


@pytest.fixture
def active_execution_plan() -> ExecutionPlan:
    """Fixture providing an active execution plan requiring standard investments."""
    return ExecutionPlan(
        plan_fingerprint="test_plan_fp",
        requested_capabilities=(),
        resolved_capabilities=(),
        required_bronze_datasets=(
            DatasetId.INVESTMENT_STOCK_ORDERS,
            DatasetId.MARKET_STOCK_HOLDINGS,
            DatasetId.INVESTMENT_MF_ORDERS,
        ),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )


def test_source_planner_compiles_binding_plans(
    multi_binding_source_configuration: SourceConfiguration,
    active_execution_plan: ExecutionPlan,
) -> None:
    """Verify that SourcePlanner compiles distinct binding plans for all configured streams."""
    planner = SourcePlanner(multi_binding_source_configuration, active_execution_plan)
    compiled_plan = planner.compile_plan()

    assert len(compiled_plan.binding_plans) >= 3

    binding_alpha_orders = derive_source_binding_id(
        SourceId("broker_alpha"), DatasetId.INVESTMENT_STOCK_ORDERS
    )
    binding_alpha_holdings = derive_source_binding_id(
        SourceId("broker_alpha"), DatasetId.MARKET_STOCK_HOLDINGS
    )
    binding_beta_mf = derive_source_binding_id(
        SourceId("broker_beta"), DatasetId.INVESTMENT_MF_ORDERS
    )

    plan_alpha_orders = compiled_plan.get_binding_plan(binding_alpha_orders)
    assert isinstance(plan_alpha_orders, SourceBindingPlan)
    assert plan_alpha_orders.source_id == SourceId("broker_alpha")
    assert plan_alpha_orders.provider_type == ProviderType.EXCEL
    assert plan_alpha_orders.enabled is True

    plan_alpha_holdings = compiled_plan.get_binding_plan(binding_alpha_holdings)
    assert plan_alpha_holdings is not None
    assert plan_alpha_holdings.source_id == SourceId("broker_alpha")
    assert plan_alpha_holdings.enabled is True

    plan_beta_mf = compiled_plan.get_binding_plan(binding_beta_mf)
    assert plan_beta_mf is not None
    assert plan_beta_mf.source_id == SourceId("broker_beta")
    assert plan_beta_mf.enabled is False  # Parent source broker_beta is disabled


def test_source_planner_binding_lookup_and_enablement(
    multi_binding_source_configuration: SourceConfiguration,
    active_execution_plan: ExecutionPlan,
) -> None:
    """Verify that CompiledSourcePlan lookup methods correctly reflect binding status."""
    planner = SourcePlanner(multi_binding_source_configuration, active_execution_plan)
    compiled_plan = planner.compile_plan()

    binding_alpha_orders = derive_source_binding_id(
        SourceId("broker_alpha"), DatasetId.INVESTMENT_STOCK_ORDERS
    )
    binding_beta_mf = derive_source_binding_id(
        SourceId("broker_beta"), DatasetId.INVESTMENT_MF_ORDERS
    )

    assert compiled_plan.is_binding_enabled(binding_alpha_orders) is True
    assert compiled_plan.is_binding_enabled(binding_beta_mf) is False

    unknown_id = SourceBindingId("nonexistent_binding")
    assert compiled_plan.is_binding_enabled(unknown_id) is False
    assert compiled_plan.get_binding_plan(unknown_id) is None
