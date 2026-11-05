"""Unit and regression tests for application-level non-I/O SourcePlanner.

Verifies:
1. SourcePlanner compiles deterministic DatasetPlan and SourcePlan objects from SourceConfiguration + ExecutionPlan.
2. SourcePlanner performs zero I/O and succeeds on synthetic paths without file creation.
3. Missing or disabled required Bronze datasets trigger immediate SourcePlanningError failures.
4. Capability omission (e.g. BENCHMARK_ENRICHMENT) propagates is_enabled=False and is_required=False to child datasets.
5. Disabled physical sources propagate is_enabled=False to all bound datasets.
6. Shan source configuration corresponds cleanly to current Settings paths to prevent configuration drift.
7. ServiceContainer wires SourceConfiguration and CompiledSourcePlan into ETLOrchestrator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    CompiledSourcePlan,
    SourcePlanner,
    SourcePlanningError,
)
from personal_finance_etl.bootstrap.container import ServiceContainer
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    CapabilitySelection,
    SourceConfiguration,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector, SqliteSelector
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId, DatasetOrigin
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_source_planner_compilation_all_required_satisfied(
    source_config: SourceConfiguration,
) -> None:
    """Verify that SourcePlanner compiles complete Shan topology with all required datasets satisfied."""
    execution_plan = CapabilityPlanner().create_plan()
    planner = SourcePlanner(source_config, execution_plan)
    compiled = planner.compile_plan()

    assert isinstance(compiled, CompiledSourcePlan)
    assert len(compiled.source_plans) == len(source_config.sources)
    assert len(compiled.dataset_plans) == len(source_config.datasets)

    # Verify household_zcategory dataset plan
    dp = compiled.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert dp is not None
    assert dp.source_id == SourceId("household_db")
    assert dp.provider_type == ProviderType.SQLITE
    assert dp.origin == DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE
    assert dp.is_required is True
    assert dp.is_enabled is True
    assert dp.change_detection is not None
    assert dp.mapping_plan is None  # Placeholder until Phase 018

    # Verify source plan grouping
    sp = compiled.get_source_plan("household_db")
    assert sp is not None
    assert sp.enabled is True
    assert len(sp.dataset_plans) == 5

    # Lookups
    assert compiled.is_dataset_enabled(DatasetId.HOUSEHOLD_ZCATEGORY) is True
    assert compiled.is_dataset_enabled("nonexistent_dataset") is False


def test_source_planner_performs_no_io() -> None:
    """Verify that SourcePlanner does not perform file existence checks or filesystem I/O."""
    fake_sources = (
        SourceConfig(
            source_id=SourceId("fake_sqlite"),
            provider_type=ProviderType.SQLITE,
            location="/completely/nonexistent/disk/fake.sqlite",
            enabled=True,
        ),
        SourceConfig(
            source_id=SourceId("fake_csv"),
            provider_type=ProviderType.CSV,
            location="/completely/nonexistent/disk/fake.csv",
            enabled=True,
        ),
    )
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
        SourceDatasetConfig(
            source_id=SourceId("fake_csv"),
            dataset_id=DatasetId.COMMON_COLUMN_MASTER,
            selector=CsvSelector(),
            enabled=True,
        ),
    )

    cfg = SourceConfiguration(
        sources=fake_sources,
        datasets=fake_datasets,
        capabilities=CapabilitySelection(enabled=(CapabilityId.HOUSEHOLD_CORE,)),
    )

    plan = CapabilityPlanner().create_plan(requested_capabilities=(CapabilityId.HOUSEHOLD_CORE,))
    planner = SourcePlanner(cfg, plan)

    # Must compile without raising FileNotFoundError
    compiled = planner.compile_plan()
    assert compiled.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY) is not None


def test_source_planner_missing_required_dataset_fails(
    source_config: SourceConfiguration,
) -> None:
    """Verify that omitting a required Bronze dataset triggers SourcePlanningError."""
    # Exclude HOUSEHOLD_ZCATEGORY from datasets
    pruned_datasets = tuple(
        d for d in source_config.datasets if d.dataset_id != DatasetId.HOUSEHOLD_ZCATEGORY
    )
    incomplete_cfg = SourceConfiguration(
        sources=source_config.sources,
        datasets=pruned_datasets,
        capabilities=source_config.capabilities,
    )

    execution_plan = CapabilityPlanner().create_plan()
    planner = SourcePlanner(incomplete_cfg, execution_plan)

    with pytest.raises(
        SourcePlanningError,
        match="Required Bronze dataset 'household_zcategory' cannot be satisfied",
    ):
        planner.compile_plan()


def test_source_planner_disabled_capability_propagation(
    source_config: SourceConfiguration,
) -> None:
    """Verify that omitting a capability in ExecutionPlan marks its datasets as disabled/not-required."""
    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    execution_plan = CapabilityPlanner().create_plan(requested_capabilities=all_except_benchmark)

    planner = SourcePlanner(source_config, execution_plan)
    compiled = planner.compile_plan()

    dp_bm = compiled.get_dataset_plan(DatasetId.INVESTMENT_BENCHMARK_MASTER)
    assert dp_bm is not None
    assert dp_bm.is_required is False
    assert dp_bm.is_enabled is False

    # Core required dataset remains enabled
    dp_core = compiled.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert dp_core is not None
    assert dp_core.is_required is True
    assert dp_core.is_enabled is True


def test_source_planner_disabled_source_disables_dataset(
    source_config: SourceConfiguration,
) -> None:
    """Verify that an operationally disabled source propagates is_enabled=False to all its dataset plans."""
    execution_plan = CapabilityPlanner().create_plan()
    planner = SourcePlanner(source_config, execution_plan)
    compiled = planner.compile_plan()

    # In Shan baseline, us_stock_transactions is disabled (enabled=False)
    dp_us = compiled.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
    assert dp_us is not None
    assert dp_us.is_enabled is False


def test_shan_source_config_matches_settings_paths(
    source_config: SourceConfiguration,
    config_path: Path,
) -> None:
    """Verify that Shan SourceConfiguration paths correspond to Settings paths to detect drift."""
    settings = Settings.from_toml(config_path)

    # Normalize paths for comparison (ignoring extension differences between .sqlite and .db)
    def stem(p: str) -> str:
        return Path(p).stem

    def name(p: str) -> str:
        return Path(p).name

    # SQLite
    src_db = source_config.get_source("household_db")
    assert src_db is not None
    assert stem(src_db.location) == stem(settings.SOURCE_DB_FOLDER)

    # Direct CSV dependencies
    mapping_checks = [
        ("mf_isin_csv", settings.MF_ISIN_CSV_PATH),
        ("benchmark_mapping_csv", settings.BENCHMARK_MAPPING_CSV_PATH),
        ("opening_balance_csv", settings.OPENING_BALANCE_CSV_PATH),
        ("benchmark_master_csv", settings.BENCHMARK_MASTER_CSV_PATH),
        ("macro_parameters_csv", settings.MACRO_PARAMETERS_CSV_PATH),
        ("currency_mapping_csv", settings.CURRENCY_MAPPING_CSV_PATH),
        ("column_master_csv", settings.COLUMN_MASTER_PATH),
    ]

    for source_id, expected_path in mapping_checks:
        src = source_config.get_source(source_id)
        assert src is not None, f"Source '{source_id}' missing in configuration."
        assert name(src.location) == name(expected_path), (
            f"Source '{source_id}' path '{src.location}' does not match Settings '{expected_path}'."
        )


def test_service_container_creates_source_config_and_orchestrator(
    sources_path: Path,
    config_path: Path,
    rules_path: Path,
) -> None:
    """Verify ServiceContainer wires SourceConfiguration and CompiledSourcePlan into ETLOrchestrator."""
    container = ServiceContainer(
        default_config_path=str(config_path),
        default_rules_path=str(rules_path),
        default_sources_path=str(sources_path),
    )

    src_cfg = container.create_source_config()
    assert isinstance(src_cfg, SourceConfiguration)
    assert len(src_cfg.sources) == 13

    orchestrator = container.create_orchestrator()
    assert isinstance(orchestrator, ETLOrchestrator)
    assert orchestrator.source_config is not None
    assert orchestrator.source_plan is not None
    assert len(orchestrator.source_plan.dataset_plans) == 17
