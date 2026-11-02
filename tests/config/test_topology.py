"""Tests for declarative v9.5.3 external evidence source topology and Bronze coverage.

Owns
----
- Coverage tests proving all 20 Bronze datasets in BRONZE_CONTRACT_REGISTRY are classified.
- Verification that Shan's v9.5.3 baseline topology covers 100% of external Bronze evidence.
- Multi-dataset per single source proof for SQLite household evidence.
- Provider-generated separation proof (no fake file sources for market history streams).
- Transitional status tracking for column master.
- Optionality and enabled toggle tests for US stock transactions.
- Diagnostics tests for missing, unaccounted, and duplicate dataset configurations.
- Serialization round-trip tests for the complete baseline topology.

Does not own
------------
- Physical database execution (owned by infrastructure.warehouse).
- Runtime pipeline orchestration (owned by application.pipeline).
"""

from __future__ import annotations

import json

import pytest

from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.topology import (
    evaluate_bronze_topology_coverage,
)
from personal_finance_etl.config.sources.validation import (
    validate_source_dataset_bindings,
)
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    EXTERNAL_CONFIGURED_DATASETS,
    PROVIDER_GENERATED_DATASETS,
    TRANSITIONAL_DATASETS,
    DatasetId,
    DatasetOrigin,
    get_bronze_dataset_origin,
)
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)


def test_bronze_universe_completeness_and_classification() -> None:
    """Verify that all 20 entries in BRONZE_CONTRACT_REGISTRY are authoritatively classified."""
    registry_dataset_ids = {contract.dataset_id for contract in BRONZE_CONTRACT_REGISTRY}
    classified_dataset_ids = set(BRONZE_DATASET_ORIGIN_MAP.keys())

    # Exactly 20 datasets
    assert len(registry_dataset_ids) == 20
    assert len(classified_dataset_ids) == 20

    # 100% equivalence between registry and classification map
    assert registry_dataset_ids == classified_dataset_ids

    # Exact breakdown of the 20 datasets
    external_count = sum(
        1
        for origin in BRONZE_DATASET_ORIGIN_MAP.values()
        if origin == DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE
    )
    provider_count = sum(
        1
        for origin in BRONZE_DATASET_ORIGIN_MAP.values()
        if origin == DatasetOrigin.PROVIDER_GENERATED
    )
    transitional_count = sum(
        1
        for origin in BRONZE_DATASET_ORIGIN_MAP.values()
        if origin == DatasetOrigin.TRANSITIONAL_CONFIGURATION_DATASET
    )

    assert external_count == 16
    assert provider_count == 3
    assert transitional_count == 1
    assert external_count + provider_count + transitional_count == 20


def test_v953_baseline_topology_coverage(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify that Shan's v9.5.3 baseline topology covers 100% of externally supplied Bronze evidence."""
    sources, bindings = v953_baseline_topology

    # Cross-model aggregate validation passes
    validate_source_dataset_bindings(sources, bindings)

    # Topology coverage evaluation passes with zero gaps
    report = evaluate_bronze_topology_coverage(bindings)
    assert report.is_complete is True
    assert len(report.missing_datasets) == 0
    assert len(report.unaccounted_datasets) == 0
    assert len(report.duplicate_datasets) == 0

    # All external and transitional datasets are covered
    assert report.configured_datasets == EXTERNAL_CONFIGURED_DATASETS
    assert report.transitional_datasets == TRANSITIONAL_DATASETS
    assert report.provider_generated_datasets == PROVIDER_GENERATED_DATASETS


def test_sqlite_one_source_multi_dataset(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify that five household datasets share a single SQLite SourceId with distinct table names."""
    _, bindings = v953_baseline_topology

    household_bindings = [b for b in bindings if b.source_id == "household_db"]
    assert len(household_bindings) == 5

    expected_household_tables = {
        DatasetId.HOUSEHOLD_ZCATEGORY: "ZCATEGORY",
        DatasetId.HOUSEHOLD_ASSET_GROUP: "ASSETGROUP",
        DatasetId.HOUSEHOLD_ASSETS: "ASSETS",
        DatasetId.HOUSEHOLD_CURRENCY: "CURRENCY",
        DatasetId.HOUSEHOLD_INOUTCOME: "INOUTCOME",
    }

    for binding in household_bindings:
        assert isinstance(binding.selector, SqliteSelector)
        assert binding.selector.provider_type == ProviderType.SQLITE
        expected_table = expected_household_tables[binding.dataset_id]
        assert binding.selector.table_name == expected_table


def test_provider_generated_datasets_require_no_user_sources(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify that provider-generated streams are not bound to fake user file sources."""
    _, bindings = v953_baseline_topology

    bound_dataset_ids = {b.dataset_id for b in bindings}

    for provider_dataset in PROVIDER_GENERATED_DATASETS:
        assert provider_dataset not in bound_dataset_ids

    assert DatasetId.MARKET_CURRENCY_FX_RATES in PROVIDER_GENERATED_DATASETS
    assert DatasetId.MARKET_BENCHMARK_HISTORY in PROVIDER_GENERATED_DATASETS
    assert DatasetId.MARKET_US_STOCK_PRICES in PROVIDER_GENERATED_DATASETS


def test_transitional_column_master_tracked(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify column_master is explicitly tracked as transitional with documented retirement."""
    _, bindings = v953_baseline_topology

    column_master_binding = next(
        b for b in bindings if b.dataset_id == DatasetId.COMMON_COLUMN_MASTER
    )
    assert column_master_binding.source_id == "column_master_csv"
    assert column_master_binding.description is not None
    assert "retirement" in column_master_binding.description.lower()
    assert (
        get_bronze_dataset_origin(DatasetId.COMMON_COLUMN_MASTER)
        == DatasetOrigin.TRANSITIONAL_CONFIGURATION_DATASET
    )


def test_us_stock_transactions_optionality(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify that the US stock transaction source can be toggled without affecting other sources."""
    sources, bindings = v953_baseline_topology

    us_source = next(s for s in sources if s.source_id == "us_stock_transactions")
    us_binding = next(b for b in bindings if b.source_id == "us_stock_transactions")

    # Default is disabled (optional capability)
    assert us_source.enabled is False
    assert us_binding.enabled is False

    # Enabling US stock transactions preserves full validity
    enabled_source = us_source.model_copy(update={"enabled": True})
    enabled_binding = us_binding.model_copy(update={"enabled": True})

    updated_sources = [
        s if s.source_id != "us_stock_transactions" else enabled_source for s in sources
    ]
    updated_bindings = [
        b if b.source_id != "us_stock_transactions" else enabled_binding for b in bindings
    ]

    validate_source_dataset_bindings(updated_sources, updated_bindings)
    report = evaluate_bronze_topology_coverage(updated_bindings)
    assert report.is_complete is True


def test_baseline_topology_serialization_roundtrip(
    v953_baseline_topology: tuple[list[SourceConfig], list[SourceDatasetConfig]],
) -> None:
    """Verify JSON round-trip serialization of the complete baseline topology fixture."""
    sources, bindings = v953_baseline_topology

    # Sources round-trip
    sources_payload = json.dumps([s.model_dump() for s in sources])
    reconstructed_sources = [
        SourceConfig.model_validate(raw) for raw in json.loads(sources_payload)
    ]
    assert reconstructed_sources == sources

    # Dataset bindings round-trip preserving concrete selector types
    bindings_payload = json.dumps([b.model_dump() for b in bindings])
    reconstructed_bindings = [
        SourceDatasetConfig.model_validate(raw) for raw in json.loads(bindings_payload)
    ]
    assert reconstructed_bindings == bindings

    # Verify selectors retain concrete types
    sqlite_bindings = [b for b in reconstructed_bindings if isinstance(b.selector, SqliteSelector)]
    excel_bindings = [b for b in reconstructed_bindings if isinstance(b.selector, ExcelSelector)]
    csv_bindings = [b for b in reconstructed_bindings if isinstance(b.selector, CsvSelector)]

    assert len(sqlite_bindings) == 5
    assert len(excel_bindings) == 4
    assert len(csv_bindings) == 8


def test_topology_coverage_diagnostics() -> None:
    """Verify diagnostic reporting when datasets are missing, unaccounted, or duplicated."""
    # 1. Missing dataset diagnostic
    partial_bindings = [
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            selector=SqliteSelector(table_name="ZCATEGORY"),
        )
    ]
    report = evaluate_bronze_topology_coverage(partial_bindings)
    assert report.is_complete is False
    assert len(report.missing_datasets) == 16  # 17 total external - 1 configured
    assert DatasetId.MARKET_MF_HOLDINGS in report.missing_datasets

    # 2. Duplicate dataset diagnostic
    duplicate_bindings = [
        SourceDatasetConfig(
            source_id=SourceId("src_a"),
            dataset_id=DatasetId.MARKET_MF_HOLDINGS,
            selector=ExcelSelector(sheet_name="Holdings"),
        ),
        SourceDatasetConfig(
            source_id=SourceId("src_b"),
            dataset_id=DatasetId.MARKET_MF_HOLDINGS,
            selector=ExcelSelector(sheet_name="Holdings_Alt"),
        ),
    ]
    dup_report = evaluate_bronze_topology_coverage(duplicate_bindings)
    assert dup_report.is_complete is False
    assert DatasetId.MARKET_MF_HOLDINGS in dup_report.duplicate_datasets

    # 3. Unaccounted dataset diagnostic (configuring a provider-generated dataset)
    unaccounted_binding = [
        SourceDatasetConfig(
            source_id=SourceId("fake_source"),
            dataset_id=DatasetId.MARKET_CURRENCY_FX_RATES,
            selector=CsvSelector(),
        )
    ]
    unacc_report = evaluate_bronze_topology_coverage(unaccounted_binding)
    assert unacc_report.is_complete is False
    assert DatasetId.MARKET_CURRENCY_FX_RATES in unacc_report.unaccounted_datasets


def test_get_bronze_dataset_origin_lookup_and_unknown() -> None:
    """Verify get_bronze_dataset_origin resolves valid Bronze datasets and raises KeyError for others."""
    # Valid lookups
    assert (
        get_bronze_dataset_origin(DatasetId.HOUSEHOLD_ZCATEGORY)
        == DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE
    )
    assert (
        get_bronze_dataset_origin(DatasetId.MARKET_CURRENCY_FX_RATES)
        == DatasetOrigin.PROVIDER_GENERATED
    )
    assert (
        get_bronze_dataset_origin(DatasetId.COMMON_COLUMN_MASTER)
        == DatasetOrigin.TRANSITIONAL_CONFIGURATION_DATASET
    )

    # Silver/Gold dataset lookup raises KeyError
    with pytest.raises(KeyError, match="not an authoritative Bronze dataset"):
        get_bronze_dataset_origin(DatasetId.FIRE_ANALYTICS)

    with pytest.raises(KeyError, match="not an authoritative Bronze dataset"):
        get_bronze_dataset_origin(DatasetId.TAX_YEAR_SUMMARY)
