"""Tests for additive source binding and canonical production configuration models.

Owns
----
- Pydantic v2 serialization and round-trip tests for SourceBindingConfig, CanonicalRouteConfig,
  and CanonicalDatasetProductionConfig.
- Declarative 1:N topology proof (one source binding containing multiple canonical routes).
- Declarative N:1 topology proof (multiple routes assembling one canonical dataset via UNION).
- Validation tests for duplicate IDs, missing references, selector compatibility, and production rules.

Does not own
------------
- Legacy SourceDatasetConfig tests (owned by tests.config.test_topology).
- Physical file reading or provider execution (owned by infrastructure.providers).
"""

from __future__ import annotations

import pytest

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceConfig, SourceFieldDeclaration
from personal_finance_etl.config.sources.normalization import TrimRule
from personal_finance_etl.config.sources.selectors import CsvSelector, SqliteSelector
from personal_finance_etl.config.sources.validation import validate_source_bindings
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
    SourceId,
)


def test_source_binding_config_multi_route_1_to_n() -> None:
    """Verify one SourceBindingConfig can declare multiple distinct canonical routes (1:N proof)."""
    route_income = CanonicalRouteConfig(
        route_id=CanonicalRouteId("route_income"),
        target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
        mapping=[ColumnMapping(source_field="ZAMOUNT", canonical_field="BASE_AMOUNT")],
        normalization=[TrimRule(field="BASE_AMOUNT")],
    )
    route_expense = CanonicalRouteConfig(
        route_id=CanonicalRouteId("route_expense"),
        target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
        mapping=[ColumnMapping(source_field="ZAMOUNT", canonical_field="BASE_AMOUNT")],
    )

    binding = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite_inoutcome_stream"),
        source_id=SourceId("sqlite_household"),
        selector=SqliteSelector(table_name="INOUTCOME"),
        fields=[
            SourceFieldDeclaration(name="ZAMOUNT", data_type="Float64"),
            SourceFieldDeclaration(name="ZTYPE", data_type="Int64"),
        ],
        routes=[route_income, route_expense],
    )

    assert binding.binding_id == "sqlite_inoutcome_stream"
    assert len(binding.routes) == 2
    assert binding.routes[0].route_id == "route_income"
    assert binding.routes[1].route_id == "route_expense"

    # JSON round-trip serialization
    json_data = binding.model_dump_json()
    deserialized = SourceBindingConfig.model_validate_json(json_data)
    assert deserialized == binding


def test_canonical_production_config_union_n_to_1() -> None:
    """Verify CanonicalDatasetProductionConfig can assemble multiple routes via UNION (N:1 proof)."""
    prod = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.UNION,
        source_routes=[
            CanonicalRouteRef(SourceBindingId("mf_orders_csv"), CanonicalRouteId("route_mf")),
            CanonicalRouteRef(SourceBindingId("stock_orders_csv"), CanonicalRouteId("route_stock")),
            CanonicalRouteRef(SourceBindingId("us_trans_csv"), CanonicalRouteId("route_us")),
        ],
    )

    assert prod.dataset_id == DatasetId.INVESTMENT_TRANSACTIONS
    assert prod.assembly_mode == SourceAssemblyMode.UNION
    assert len(prod.source_routes) == 3

    # JSON round-trip serialization
    json_str = prod.model_dump_json()
    reconstructed = CanonicalDatasetProductionConfig.model_validate_json(json_str)
    assert reconstructed == prod


def test_source_binding_rejects_duplicate_route_ids() -> None:
    """Verify SourceBindingConfig raises ValueError on duplicate route_ids within the same binding."""
    r1 = CanonicalRouteConfig(
        route_id=CanonicalRouteId("same_route"),
        target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
    )
    r2 = CanonicalRouteConfig(
        route_id=CanonicalRouteId("same_route"),
        target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
    )

    with pytest.raises(ValueError, match="Duplicate route_id 'same_route'"):
        SourceBindingConfig(
            binding_id=SourceBindingId("test_binding"),
            source_id=SourceId("test_source"),
            selector=SqliteSelector(table_name="INOUTCOME"),
            routes=[r1, r2],
        )


def test_production_direct_assembly_rejects_multiple_routes() -> None:
    """Verify DIRECT assembly mode enforces at most one source route."""
    with pytest.raises(
        ValueError, match="DIRECT assembly mode .* cannot have more than one source route"
    ):
        CanonicalDatasetProductionConfig(
            dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            producer_kind=CanonicalProducerKind.SOURCE,
            assembly_mode=SourceAssemblyMode.DIRECT,
            source_routes=[
                CanonicalRouteRef(SourceBindingId("b1"), CanonicalRouteId("r1")),
                CanonicalRouteRef(SourceBindingId("b2"), CanonicalRouteId("r2")),
            ],
        )


def test_production_provider_requires_provider_type() -> None:
    """Verify PROVIDER producer kind requires non-None provider_type."""
    with pytest.raises(ValueError, match="must specify provider_type"):
        CanonicalDatasetProductionConfig(
            dataset_id=DatasetId.MARKET_BENCHMARK_PRICES,
            producer_kind=CanonicalProducerKind.PROVIDER,
            provider_type=None,
        )


def test_production_derived_requires_recipe_name() -> None:
    """Verify DERIVED producer kind requires non-empty recipe_name."""
    with pytest.raises(ValueError, match="must specify a non-empty recipe_name"):
        CanonicalDatasetProductionConfig(
            dataset_id=DatasetId.COMMON_CURRENCIES,
            producer_kind=CanonicalProducerKind.DERIVED,
            recipe_name="",
        )


def test_validate_source_bindings_topology() -> None:
    """Verify validate_source_bindings validates sources, bindings, and production cross-references."""
    src = SourceConfig(
        source_id=SourceId("src_csv"),
        provider_type=ProviderType.CSV,
        location="data/files",
    )
    route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_mf"),
        target_dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
    )
    binding = SourceBindingConfig(
        binding_id=SourceBindingId("bind_mf"),
        source_id=src.source_id,
        selector=CsvSelector(file_pattern="mf.csv"),
        routes=[route],
    )
    production = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        source_routes=[CanonicalRouteRef(binding.binding_id, route.route_id)],
    )

    # Valid topology passes cleanly
    validate_source_bindings(
        sources=[src],
        bindings=[binding],
        productions=[production],
    )

    # 1. Unknown SourceId
    bad_binding_src = SourceBindingConfig(
        binding_id=SourceBindingId("bind_bad_src"),
        source_id=SourceId("unknown_src"),
        selector=CsvSelector(file_pattern="test.csv"),
    )
    with pytest.raises(ValueError, match="references unknown source_id 'unknown_src'"):
        validate_source_bindings(sources=[src], bindings=[bad_binding_src])

    # 2. Duplicate binding_id
    duplicate_binding = SourceBindingConfig(
        binding_id=binding.binding_id,
        source_id=src.source_id,
        selector=CsvSelector(file_pattern="mf2.csv"),
    )
    with pytest.raises(ValueError, match="Duplicate source binding identifier found"):
        validate_source_bindings(sources=[src], bindings=[binding, duplicate_binding])

    # 3. Selector incompatibility
    incompat_binding = SourceBindingConfig(
        binding_id=SourceBindingId("bind_incompat"),
        source_id=src.source_id,
        selector=SqliteSelector(table_name="INOUTCOME"),
    )
    with pytest.raises(ValueError, match="incompatible with source"):
        validate_source_bindings(sources=[src], bindings=[incompat_binding])

    # 4. Production references non-existent binding
    bad_prod_binding = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        source_routes=[CanonicalRouteRef(SourceBindingId("ghost_binding"), CanonicalRouteId("r1"))],
    )
    with pytest.raises(ValueError, match="binding 'ghost_binding' does not exist"):
        validate_source_bindings(sources=[src], bindings=[binding], productions=[bad_prod_binding])

    # 5. Production references non-existent route within binding
    bad_prod_route = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        source_routes=[CanonicalRouteRef(binding.binding_id, CanonicalRouteId("ghost_route"))],
    )
    with pytest.raises(ValueError, match="route 'ghost_route' does not exist in binding 'bind_mf'"):
        validate_source_bindings(sources=[src], bindings=[binding], productions=[bad_prod_route])

    # 6. Production references route targeting different dataset
    route_wrong_target = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_diff"),
        target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
    )
    binding_wrong = SourceBindingConfig(
        binding_id=SourceBindingId("bind_wrong"),
        source_id=src.source_id,
        selector=CsvSelector(file_pattern="cat.csv"),
        routes=[route_wrong_target],
    )
    prod_mismatch = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        source_routes=[CanonicalRouteRef(binding_wrong.binding_id, route_wrong_target.route_id)],
    )
    with pytest.raises(ValueError, match="does not match production dataset"):
        validate_source_bindings(
            sources=[src], bindings=[binding_wrong], productions=[prod_mismatch]
        )
