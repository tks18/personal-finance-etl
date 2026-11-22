"""Unit test suite for CanonicalSatisfiabilityPlanner and production graph resolution.

Owns
----
- Single source producer auto-resolution verification.
- Explicit UNION route resolution verification.
- Provider evidence resolution without network I/O.
- Derived recipe resolution and recursive dependency resolution.
- Rejection of missing required producers with typed UnsatisfiedCanonicalEvidenceError.
- Rejection of ambiguous producers without explicit selection with AmbiguousCanonicalProducerError.
- Explicit selection resolving competing alternatives.
- Cycle detection in derived recipe dependencies with CyclicCanonicalDependencyError.
- Safe omission of optional unsatisfied evidence without fake-empty datasets.
- Exclusion of disabled bindings from satisfiability.
- Deterministic order-invariant production plan fingerprinting.
- Replay dependency closure extension for derived canonical dependents.
"""

from __future__ import annotations

import json

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.canonical_recipes import (
    CanonicalRecipeRegistry,
    get_global_recipe_registry,
)
from personal_finance_etl.application.pipeline.planner import (
    DEFAULT_ENGINE_STAGES,
)
from personal_finance_etl.application.pipeline.replay import SourceConfigChangeClassifier
from personal_finance_etl.application.pipeline.satisfiability import (
    CanonicalSatisfiabilityPlanner,
)
from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.compiler import CompiledSourceBindingTopology
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.canonical_plans import (
    AmbiguousCanonicalProducerError,
    CanonicalProducerKind,
    CanonicalProductionPlan,
    CyclicCanonicalDependencyError,
    SourceAssemblyMode,
    UnsatisfiedCanonicalEvidenceError,
)
from personal_finance_etl.contracts.canonical_recipes import CanonicalRecipeDescriptor
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.recovery import ReplayAction
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
    SourceId,
)


def _make_source_config(
    binding_configs: list[SourceBindingConfig],
    productions: list[CanonicalDatasetProductionConfig] | None = None,
) -> CompiledSourceBindingTopology:
    """Helper creating a CompiledSourceBindingTopology for unit testing."""
    binding_by_id = {b.binding_id: b for b in binding_configs}
    production_by_id = {p.dataset_id: p for p in productions} if productions else {}
    return CompiledSourceBindingTopology(
        bindings=tuple(binding_configs),
        productions=tuple(productions) if productions else (),
        binding_by_id=binding_by_id,
        production_by_dataset_id=production_by_id,
    )


def _make_exec_plan(
    required_bronze: tuple[DatasetId, ...] = (),
    optional_bronze: tuple[DatasetId, ...] = (),
    capabilities: tuple[CapabilityId, ...] = (CapabilityId.HOUSEHOLD_CORE,),
) -> ExecutionPlan:
    """Helper creating an ExecutionPlan with default engine stages for unit testing."""
    return ExecutionPlan(
        plan_fingerprint="test_plan",
        requested_capabilities=capabilities,
        resolved_capabilities=capabilities,
        required_bronze_datasets=required_bronze,
        optional_bronze_datasets=optional_bronze,
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=DEFAULT_ENGINE_STAGES,
    )


def test_single_source_producer_auto_resolution() -> None:
    """Verify a required canonical dataset with exactly one source binding route auto-resolves cleanly."""
    binding = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__zcategory"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="ZCATEGORY"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    topology = _make_source_config([binding])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    assert isinstance(prod_plan, CanonicalProductionPlan)
    assert len(prod_plan.dataset_plans) == 1
    dp = prod_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert dp is not None
    assert dp.producer_kind == CanonicalProducerKind.SOURCE
    assert dp.assembly_mode == SourceAssemblyMode.DIRECT
    assert dp.is_required is True
    assert dp.is_enabled is True
    assert len(dp.route_refs) == 1
    assert dp.route_refs[0].binding_id == SourceBindingId("sqlite__zcategory")
    assert dp.route_refs[0].route_id == CanonicalRouteId("direct")
    assert prod_plan.plan_fingerprint.startswith("cprod_")


def test_explicit_union_route_resolution() -> None:
    """Verify an explicit UNION production resolves strictly to the declared route references."""
    b1 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__part1"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="P1"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("r1"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    b2 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__part2"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="P2"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("r2"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    union_prod = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.UNION,
        source_routes=[
            CanonicalRouteRef(
                binding_id=SourceBindingId("sqlite__part1"), route_id=CanonicalRouteId("r1")
            ),
            CanonicalRouteRef(
                binding_id=SourceBindingId("sqlite__part2"), route_id=CanonicalRouteId("r2")
            ),
        ],
    )
    topology = _make_source_config([b1, b2], [union_prod])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    dp = prod_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert dp is not None
    assert dp.producer_kind == CanonicalProducerKind.SOURCE
    assert dp.assembly_mode == SourceAssemblyMode.UNION
    assert len(dp.route_refs) == 2


def test_provider_production_resolution() -> None:
    """Verify provider-generated market datasets resolve without network I/O."""
    topology = _make_source_config([])

    exec_plan = _make_exec_plan(
        required_bronze=(DatasetId.MARKET_BENCHMARK_HISTORY,),
        capabilities=(CapabilityId.BENCHMARK_ENRICHMENT,),
    )

    planner = CanonicalSatisfiabilityPlanner()
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    dp = prod_plan.get_dataset_plan(DatasetId.MARKET_BENCHMARK_HISTORY)
    assert dp is not None
    assert dp.producer_kind == CanonicalProducerKind.PROVIDER
    assert dp.provider_type == ProviderType.MARKET_DATA


def test_derived_recipe_resolution_and_topological_sort() -> None:
    """Verify registered derived recipes resolve their dependencies in strict topological order."""
    registry = CanonicalRecipeRegistry()
    registry.register(
        CanonicalRecipeDescriptor(
            recipe_id="derive_categories",
            version="1.0.0",
            target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            dependencies=(DatasetId.HOUSEHOLD_ZCATEGORY,),
            description="Derive canonical household categories",
        ),
        lambda inputs: pl.DataFrame(),
    )

    b1 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__zcat"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="ZCATEGORY"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    topology = _make_source_config([b1])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_CATEGORIES,))

    planner = CanonicalSatisfiabilityPlanner(recipe_registry=registry)
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    assert len(prod_plan.dataset_plans) == 2
    # Verify topological order: upstream dependency HOUSEHOLD_ZCATEGORY must appear BEFORE derived HOUSEHOLD_CATEGORIES
    order = prod_plan.topological_order
    assert order.index(DatasetId.HOUSEHOLD_ZCATEGORY) < order.index(DatasetId.HOUSEHOLD_CATEGORIES)

    dp_derived = prod_plan.get_dataset_plan(DatasetId.HOUSEHOLD_CATEGORIES)
    assert dp_derived is not None
    assert dp_derived.producer_kind == CanonicalProducerKind.DERIVED
    assert dp_derived.recipe_name == "derive_categories"
    assert dp_derived.dependencies == (DatasetId.HOUSEHOLD_ZCATEGORY,)


def test_missing_required_producer_raises_unsatisfied_error() -> None:
    """Verify a required canonical dataset with zero candidate producers raises UnsatisfiedCanonicalEvidenceError."""
    topology = _make_source_config([])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    with pytest.raises(UnsatisfiedCanonicalEvidenceError) as exc_info:
        planner.plan(execution_plan=exec_plan, source_config=topology)

    assert exc_info.value.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert "household_zcategory" in str(exc_info.value)


def test_ambiguous_producers_without_explicit_config_raises_ambiguity_error() -> None:
    """Verify multiple candidate producers for the same dataset without explicit production config fails fast."""
    b1 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__stream1"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="S1"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    b2 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__stream2"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="S2"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    topology = _make_source_config([b1, b2])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    with pytest.raises(AmbiguousCanonicalProducerError) as exc_info:
        planner.plan(execution_plan=exec_plan, source_config=topology)

    assert exc_info.value.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY


def test_explicit_selection_resolves_ambiguity() -> None:
    """Verify declaring an explicit production selection resolves multiple candidate producers deterministically."""
    b1 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__primary"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="S1"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    b2 = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__backup"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="S2"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    explicit_selection = CanonicalDatasetProductionConfig(
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        source_routes=[
            CanonicalRouteRef(
                binding_id=SourceBindingId("sqlite__primary"), route_id=CanonicalRouteId("direct")
            )
        ],
    )
    topology = _make_source_config([b1, b2], [explicit_selection])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    dp = prod_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert dp is not None
    assert len(dp.route_refs) == 1
    assert dp.route_refs[0].binding_id == SourceBindingId("sqlite__primary")


def test_dependency_cycle_raises_cyclic_error() -> None:
    """Verify cyclic dependencies among derived recipes are detected and raise CyclicCanonicalDependencyError."""
    registry = CanonicalRecipeRegistry()
    registry.register(
        CanonicalRecipeDescriptor(
            recipe_id="recipe_a",
            version="1.0.0",
            target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            dependencies=(DatasetId.HOUSEHOLD_ASSETS,),
            description="A depends on B",
        ),
        lambda inputs: pl.DataFrame(),
    )
    registry.register(
        CanonicalRecipeDescriptor(
            recipe_id="recipe_b",
            version="1.0.0",
            target_dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            dependencies=(DatasetId.HOUSEHOLD_CATEGORIES,),
            description="B depends on A",
        ),
        lambda inputs: pl.DataFrame(),
    )

    topology = _make_source_config([])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_CATEGORIES,))

    planner = CanonicalSatisfiabilityPlanner(recipe_registry=registry)
    with pytest.raises(CyclicCanonicalDependencyError) as exc_info:
        planner.plan(execution_plan=exec_plan, source_config=topology)

    assert len(exc_info.value.cycle_path) >= 2


def test_optional_unsatisfied_evidence_is_omitted() -> None:
    """Verify missing optional canonical datasets remain absent without materializing fake empty datasets."""
    topology = _make_source_config([])

    exec_plan = _make_exec_plan(optional_bronze=(DatasetId.HOUSEHOLD_OPENING_BALANCES,))

    planner = CanonicalSatisfiabilityPlanner()
    prod_plan = planner.plan(execution_plan=exec_plan, source_config=topology)

    assert len(prod_plan.dataset_plans) == 0
    assert prod_plan.get_dataset_plan(DatasetId.HOUSEHOLD_OPENING_BALANCES) is None


def test_disabled_binding_cannot_satisfy_evidence() -> None:
    """Verify disabled source bindings are excluded from candidate discovery and cannot satisfy required evidence."""
    binding = SourceBindingConfig(
        binding_id=SourceBindingId("sqlite__zcategory"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="ZCATEGORY"),
        enabled=False,  # Explicitly disabled
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    topology = _make_source_config([binding])

    exec_plan = _make_exec_plan(required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY,))

    planner = CanonicalSatisfiabilityPlanner()
    with pytest.raises(UnsatisfiedCanonicalEvidenceError):
        planner.plan(execution_plan=exec_plan, source_config=topology)


def test_plan_fingerprint_order_invariance() -> None:
    """Verify reordering bindings or routes produces identical plan fingerprints and topological orders."""
    b1 = SourceBindingConfig(
        binding_id=SourceBindingId("b1_zcat"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="ZCAT"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            )
        ],
    )
    b2 = SourceBindingConfig(
        binding_id=SourceBindingId("b2_assets"),
        source_id=SourceId("sqlite_db"),
        selector=SqliteSelector(table_name="ASSETS"),
        routes=[
            CanonicalRouteConfig(
                route_id=CanonicalRouteId("direct"),
                target_dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            )
        ],
    )

    top_forward = _make_source_config([b1, b2])
    top_reverse = _make_source_config([b2, b1])

    exec_plan = _make_exec_plan(
        required_bronze=(DatasetId.HOUSEHOLD_ZCATEGORY, DatasetId.HOUSEHOLD_ASSETS)
    )

    planner = CanonicalSatisfiabilityPlanner()
    plan_fwd = planner.plan(execution_plan=exec_plan, source_config=top_forward)
    plan_rev = planner.plan(execution_plan=exec_plan, source_config=top_reverse)

    assert plan_fwd.plan_fingerprint == plan_rev.plan_fingerprint
    assert plan_fwd.topological_order == plan_rev.topological_order


def test_replay_closure_includes_derived_canonical_dependents() -> None:
    """Verify configuration change classifier propagates replay actions to derived canonical dependents."""
    registry = CanonicalRecipeRegistry()
    registry.register(
        CanonicalRecipeDescriptor(
            recipe_id="derive_categories_replay",
            version="1.0.0",
            target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            dependencies=(DatasetId.HOUSEHOLD_ZCATEGORY,),
            description="Derived categories depending on zcategory",
        ),
        lambda inputs: pl.DataFrame(),
    )

    prior_snapshot = json.dumps(
        {
            "datasets": [
                {
                    "dataset_id": "household_zcategory",
                    "mapping": [{"source_field": "NAME", "canonical_field": "CATEGORY_NAME"}],
                }
            ]
        }
    )

    # Simulate mapping change on household_zcategory
    current_source = SourceConfig(
        source_id=SourceId("sqlite_db"),
        provider_type=ProviderType.SQLITE,
        location="data/test.sqlite",
    )
    curr_ds = SourceDatasetConfig(
        source_id=SourceId("sqlite_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        mapping=[ColumnMapping(source_field="NAME", canonical_field="CATEGORY_NEW_NAME")],
    )

    curr_cfg = SourceConfiguration(
        sources=(current_source,),
        datasets=(curr_ds,),
    )

    # Register the recipe in global registry so replay picks it up
    get_global_recipe_registry().register(
        CanonicalRecipeDescriptor(
            recipe_id="derive_categories_replay",
            version="1.0.0",
            target_dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
            dependencies=(DatasetId.HOUSEHOLD_ZCATEGORY,),
            description="Derived categories depending on zcategory",
        ),
        lambda inputs: pl.DataFrame(),
    )

    replay_plan = SourceConfigChangeClassifier.classify(prior_snapshot, curr_cfg)

    assert replay_plan.overall_action == ReplayAction.REPLAY_AFFECTED_DATASETS
    assert DatasetId.HOUSEHOLD_ZCATEGORY in replay_plan.affected_dataset_ids
    # Crucial check: HOUSEHOLD_CATEGORIES was automatically pulled into affected closure because it derives from HOUSEHOLD_ZCATEGORY
    assert DatasetId.HOUSEHOLD_CATEGORIES in replay_plan.affected_dataset_ids
