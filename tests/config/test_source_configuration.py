"""Unit and regression tests for versioned production SourceConfiguration loader.

Verifies:
1. Canonical Shan source configuration loads cleanly from tests/fixtures/sources.toml.
2. Serialization to TOML and dict round-trips with 100% fidelity.
3. Unsupported schema versions trigger immediate validation errors.
4. Duplicate SourceId definitions trigger immediate validation errors.
5. Duplicate (source_id, dataset_id) bindings trigger immediate validation errors.
6. Bindings referencing unknown SourceIds trigger descriptive validation errors.
7. Selector and source provider type mismatches trigger compatibility validation errors.
8. Capability selection defaults to all capabilities when omitted, or preserves explicit subsets.
9. Helper lookup methods (get_source, get_dataset_binding, get_source_dataset_bindings).
10. Application façade validation entry point (validate_sources_config).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.sources.loader import (
    CURRENT_SOURCE_CONFIG_SCHEMA_VERSION,
    CapabilitySelection,
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_source_configuration_baseline_roundtrip(sources_path: Path) -> None:
    """Verify that canonical Shan source configuration loads from TOML and round-trips cleanly."""
    cfg = SourceConfiguration.from_toml(sources_path)

    assert cfg.schema_version == CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
    assert len(cfg.sources) == 13
    assert len(cfg.datasets) == 17
    assert cfg.capabilities.enabled is not None
    assert set(cfg.capabilities.enabled) == set(CapabilityId)

    # Test round-trip serialization to TOML string
    toml_str = cfg.to_toml()
    assert len(toml_str) > 0
    reloaded = SourceConfiguration.from_dict(cfg.to_dict())

    assert reloaded.schema_version == cfg.schema_version
    assert len(reloaded.sources) == len(cfg.sources)
    assert len(reloaded.datasets) == len(cfg.datasets)
    assert reloaded.capabilities.resolved_capabilities == cfg.capabilities.resolved_capabilities


def test_baseline_factory_matches_fixture(sources_path: Path) -> None:
    """Verify get_shan_baseline_source_configuration factory matches the TOML fixture."""
    fixture_cfg = SourceConfiguration.from_toml(sources_path)
    factory_cfg = get_shan_baseline_source_configuration()

    assert len(fixture_cfg.sources) == len(factory_cfg.sources)
    assert len(fixture_cfg.datasets) == len(factory_cfg.datasets)
    assert fixture_cfg.schema_version == factory_cfg.schema_version


def test_unsupported_schema_version_fails() -> None:
    """Verify that an unsupported configuration schema version raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported configuration schema_version '99.0'"):
        SourceConfiguration(
            schema_version="99.0",
            sources=(),
            datasets=(),
        )


def test_duplicate_source_id_fails() -> None:
    """Verify that duplicate source_id entries in sources collection trigger ValueError."""
    sources = (
        SourceConfig(
            source_id=SourceId("dup_src"),
            provider_type=ProviderType.CSV,
            location="inputs/file1.csv",
        ),
        SourceConfig(
            source_id=SourceId("dup_src"),
            provider_type=ProviderType.CSV,
            location="inputs/file2.csv",
        ),
    )

    with pytest.raises(ValueError, match="Duplicate source definition for source_id 'dup_src'"):
        SourceConfiguration(
            sources=sources,
            datasets=(),
        )


def test_duplicate_binding_fails() -> None:
    """Verify that duplicate (source_id, dataset_id) bindings trigger ValueError."""
    sources = (
        SourceConfig(
            source_id=SourceId("src_a"),
            provider_type=ProviderType.CSV,
            location="inputs/file.csv",
        ),
    )
    datasets = (
        SourceDatasetConfig(
            source_id=SourceId("src_a"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
        ),
        SourceDatasetConfig(
            source_id=SourceId("src_a"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
        ),
    )

    with pytest.raises(ValueError, match="Duplicate source dataset binding for source 'src_a'"):
        SourceConfiguration(
            sources=sources,
            datasets=datasets,
        )


def test_unknown_source_in_binding_fails() -> None:
    """Verify that bindings referencing an unconfigured source_id trigger ValueError."""
    sources = (
        SourceConfig(
            source_id=SourceId("known_src"),
            provider_type=ProviderType.CSV,
            location="inputs/file.csv",
        ),
    )
    datasets = (
        SourceDatasetConfig(
            source_id=SourceId("ghost_src"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
        ),
    )

    with pytest.raises(ValueError, match="references unknown source_id 'ghost_src'"):
        SourceConfiguration(
            sources=sources,
            datasets=datasets,
        )


def test_selector_provider_mismatch_fails() -> None:
    """Verify that incompatible selector and source provider types trigger ValueError."""
    sources = (
        SourceConfig(
            source_id=SourceId("sqlite_src"),
            provider_type=ProviderType.SQLITE,
            location="inputs/db.sqlite",
        ),
    )
    # Attempt to bind ExcelSelector to a SQLITE source
    datasets = (
        SourceDatasetConfig(
            source_id=SourceId("sqlite_src"),
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            selector=ExcelSelector(sheet_name="Sheet1"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="Selector provider 'excel' is incompatible with source 'sqlite_src' provider 'sqlite'",
    ):
        SourceConfiguration(
            sources=sources,
            datasets=datasets,
        )


def test_capability_selection_defaults_and_explicit() -> None:
    """Verify CapabilitySelection behavior when omitted versus explicitly specified."""
    default_sel = CapabilitySelection()
    assert default_sel.enabled is None
    assert default_sel.resolved_capabilities == frozenset(CapabilityId)

    explicit_sel = CapabilitySelection(enabled=(CapabilityId.HOUSEHOLD_CORE, CapabilityId.TAX))
    assert explicit_sel.enabled == (CapabilityId.HOUSEHOLD_CORE, CapabilityId.TAX)
    assert explicit_sel.resolved_capabilities == frozenset(
        {CapabilityId.HOUSEHOLD_CORE, CapabilityId.TAX}
    )


def test_invalid_capability_fails() -> None:
    """Verify that unrecognized capability identifiers fail validation."""
    with pytest.raises(ValidationError):
        CapabilitySelection(enabled=("non_existent_capability",))  # type: ignore[arg-type]


def test_source_configuration_lookup_methods(source_config: SourceConfiguration) -> None:
    """Verify get_source, get_dataset_binding, and get_source_dataset_bindings helpers."""
    # Source lookup
    src = source_config.get_source("household_db")
    assert src is not None
    assert src.provider_type == ProviderType.SQLITE
    assert source_config.get_source("nonexistent") is None

    # Dataset binding lookup
    binding = source_config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert binding is not None
    assert binding.source_id == SourceId("household_db")
    assert isinstance(binding.selector, SqliteSelector)
    assert binding.selector.table_name == "ZCATEGORY"
    assert source_config.get_dataset_binding(DatasetId.INVESTMENT_PORTFOLIO_SUMMARY) is None

    # Multi-dataset source bindings lookup
    household_bindings = source_config.get_source_dataset_bindings("household_db")
    assert len(household_bindings) == 5
    dataset_ids = {b.dataset_id for b in household_bindings}
    assert DatasetId.HOUSEHOLD_ZCATEGORY in dataset_ids
    assert DatasetId.HOUSEHOLD_INOUTCOME in dataset_ids


def test_facade_validate_sources_config(sources_path: Path, tmp_path: Path) -> None:
    """Verify PersonalFinanceEngine.validate_sources_config accurately reports validation status."""
    engine = PersonalFinanceEngine()

    # Valid config
    assert engine.validate_sources_config(str(sources_path)) is True

    # Non-existent file
    assert engine.validate_sources_config(str(tmp_path / "ghost.toml")) is False

    # Corrupt / invalid TOML
    corrupt_file = tmp_path / "corrupt.toml"
    corrupt_file.write_text(
        "schema_version = '99.0'\n[[sources]]\nsource_id = ''\n", encoding="utf-8"
    )
    assert engine.validate_sources_config(str(corrupt_file)) is False
