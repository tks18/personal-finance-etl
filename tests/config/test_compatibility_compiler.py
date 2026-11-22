"""Tests for deterministic legacy-to-source-binding compatibility compilation.

Owns
----
- Verification of CompatibilitySourceBindingCompiler 1:1 translation.
- Verification that selector, fields, change detection, mapping, normalization, and identity are preserved.
- Verification that SourceBindingId is derived deterministically and remains path-independent.
- Verification that malformed legacy configurations fail validation before compilation.
- Verification of explicit Phase 055 demolition contract.

Removal Owner
-------------
- Phase 055 (when legacy SourceDatasetConfig is decommissioned).
"""

from __future__ import annotations

import inspect

import pytest

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    SyncStrategy,
)
from personal_finance_etl.config.sources.compiler import (
    DEFAULT_COMPATIBILITY_ROUTE_ID,
    CompatibilitySourceBindingCompiler,
    CompiledSourceBindingTopology,
    derive_source_binding_id,
)
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import (
    SourceConfig,
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
from personal_finance_etl.config.sources.normalization import NormalizationRule, TrimRule
from personal_finance_etl.config.sources.selectors import CsvSelector, SqliteSelector
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    ProviderType,
    SourceBindingId,
    SourceId,
)


def test_derive_source_binding_id_deterministic_and_path_independent() -> None:
    """Verify derive_source_binding_id produces stable IDs regardless of file paths."""
    b_id1 = derive_source_binding_id(SourceId("household_db"), DatasetId.HOUSEHOLD_ZCATEGORY)
    b_id2 = derive_source_binding_id("household_db", "household_zcategory")
    assert b_id1 == SourceBindingId("household_db__household_zcategory")
    assert b_id1 == b_id2

    # Path relocation does not alter SourceBindingId
    src_local = SourceConfig(
        source_id=SourceId("src_csv"),
        provider_type=ProviderType.CSV,
        location="data/local/file.csv",
    )
    src_remote = SourceConfig(
        source_id=SourceId("src_csv"),
        provider_type=ProviderType.CSV,
        location="/mnt/shared/data/file.csv",
    )
    assert src_local.source_id == src_remote.source_id
    b_local = derive_source_binding_id(src_local.source_id, DatasetId.INVESTMENT_STOCK_ORDERS)
    b_remote = derive_source_binding_id(src_remote.source_id, DatasetId.INVESTMENT_STOCK_ORDERS)
    assert b_local == b_remote


def test_compiler_translates_single_binding_preserving_all_attributes() -> None:
    """Verify compiler translates 1:1 legacy binding preserving all semantic attributes."""
    source = SourceConfig(
        source_id=SourceId("test_sqlite"),
        provider_type=ProviderType.SQLITE,
        location="data/test.sqlite",
    )
    selector = SqliteSelector(table_name="ZCATEGORY")
    cd_policy = ChangeDetectionPolicy(sync_strategy=SyncStrategy.FULL_REPLACE)
    ident = SourceFieldIdentity(field="UID")
    mapping = [ColumnMapping(source_field="Z_PK", canonical_field="CATEGORY_ID")]
    norm: list[NormalizationRule] = [TrimRule(field="ZNAME", mode="both")]
    fields = [SourceFieldDeclaration(name="Z_PK", data_type="Int64", nullable=False)]

    legacy_ds = SourceDatasetConfig(
        source_id=source.source_id,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=selector,
        enabled=True,
        description="Expense categories table",
        change_detection=cd_policy,
        identity=ident,
        mapping=mapping,
        normalization=norm,
        fields=fields,
    )

    config = SourceConfiguration(
        sources=(source,),
        datasets=(legacy_ds,),
    )

    topology = CompatibilitySourceBindingCompiler.compile(config)
    assert isinstance(topology, CompiledSourceBindingTopology)
    assert len(topology.bindings) == 1
    assert len(topology.productions) == 1

    compiled_binding = topology.bindings[0]
    assert isinstance(compiled_binding, SourceBindingConfig)
    assert compiled_binding.binding_id == SourceBindingId("test_sqlite__household_zcategory")
    assert compiled_binding.source_id == SourceId("test_sqlite")
    assert compiled_binding.selector == selector
    assert compiled_binding.enabled is True
    assert compiled_binding.description == "Expense categories table"
    assert compiled_binding.change_detection == cd_policy
    assert compiled_binding.fields == fields

    # Check child route
    assert len(compiled_binding.routes) == 1
    route = compiled_binding.routes[0]
    assert isinstance(route, CanonicalRouteConfig)
    assert route.route_id == DEFAULT_COMPATIBILITY_ROUTE_ID
    assert route.route_id == CanonicalRouteId("direct")
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert route.mapping == mapping
    assert route.normalization == norm
    assert route.identity == ident

    # Check production rule
    compiled_prod = topology.productions[0]
    assert isinstance(compiled_prod, CanonicalDatasetProductionConfig)
    assert compiled_prod.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert compiled_prod.producer_kind == CanonicalProducerKind.SOURCE
    assert compiled_prod.assembly_mode == SourceAssemblyMode.DIRECT
    assert len(compiled_prod.source_routes) == 1
    assert compiled_prod.source_routes[0].binding_id == compiled_binding.binding_id
    assert compiled_prod.source_routes[0].route_id == route.route_id
    assert compiled_prod.source_routes[0].to_string() == "test_sqlite__household_zcategory:direct"

    # Check lookups
    assert topology.get_binding(compiled_binding.binding_id) is compiled_binding
    assert topology.get_production(DatasetId.HOUSEHOLD_ZCATEGORY) is compiled_prod
    assert topology.get_bindings_for_source("test_sqlite") == (compiled_binding,)


def test_compiler_handles_disabled_bindings_properly() -> None:
    """Verify disabled legacy bindings compile to disabled bindings, routes, and productions."""
    source = SourceConfig(
        source_id=SourceId("csv_src"),
        provider_type=ProviderType.CSV,
        location="data/test.csv",
    )
    legacy_ds = SourceDatasetConfig(
        source_id=source.source_id,
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        selector=CsvSelector(file_pattern="trades.csv"),
        enabled=False,
    )
    config = SourceConfiguration(sources=(source,), datasets=(legacy_ds,))
    topology = config.compile_binding_topology()

    b = topology.bindings[0]
    assert b.enabled is False
    assert b.routes[0].enabled is False
    assert topology.productions[0].enabled is False


def test_compiler_rejects_malformed_bindings_with_unknown_source() -> None:
    """Verify compiler validation fails if a dataset references an unknown source."""
    source = SourceConfig(
        source_id=SourceId("known_source"),
        provider_type=ProviderType.CSV,
        location="data/file.csv",
    )
    legacy_ds = SourceDatasetConfig(
        source_id=SourceId("unknown_source"),
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        selector=CsvSelector(file_pattern="orders.csv"),
    )
    with pytest.raises(ValueError, match="unknown source_id"):
        CompatibilitySourceBindingCompiler.compile_bindings(
            sources=[source],
            datasets=[legacy_ds],
        )


def test_compiler_has_explicit_decommissioning_contract() -> None:
    """Verify CompatibilitySourceBindingCompiler documents Phase 055 removal ownership."""
    doc = inspect.getdoc(CompatibilitySourceBindingCompiler)
    assert doc is not None
    assert "Removal Owner" in doc
    assert "Phase 055" in doc

    topology_doc = inspect.getdoc(CompiledSourceBindingTopology)
    assert topology_doc is not None
    assert "Removal Owner" in topology_doc
    assert "Phase 055" in topology_doc


def test_baseline_source_configuration_compiles_cleanly() -> None:
    """Verify baseline configuration compiles all 17 dataset bindings with zero errors."""
    config = get_shan_baseline_source_configuration()

    # Legacy 1:1 topology compilation without candidate routes
    topology_1to1 = config.compile_binding_topology(include_candidate_household=False)
    assert len(topology_1to1.bindings) == 17
    assert len(topology_1to1.productions) == 17
    for b in topology_1to1.bindings:
        assert len(b.routes) == 1
        assert b.routes[0].route_id == "direct"

    # Multi-route topology with candidate canonical household routes (Phase 052)
    topology_with_candidates = config.compile_binding_topology(include_candidate_household=True)
    assert len(topology_with_candidates.bindings) == 17
    assert len(topology_with_candidates.productions) == 23
    target_b = topology_with_candidates.get_binding("household_db__household_zcategory")
    assert target_b is not None
    assert len(target_b.routes) == 2
