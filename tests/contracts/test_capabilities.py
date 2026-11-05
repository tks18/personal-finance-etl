"""Enterprise test suite for capability graph, descriptors, and topological resolution.

Owns
----
- Verification of the 7 canonical financial capabilities and descriptors.
- Structural graph validation: cycle detection, unknown dependencies, dataset validity, and duplicate claims.
- 100% analytical contract coverage proof (24 Silver + 22 Gold = 46 contracts).
- 100% Bronze dataset coverage proof (all 20 Bronze datasets accounted for).
- Deterministic topological resolution and transitive dependency expansion.
- Cross-capability optional contribution activation semantics.

Does not own
-------------
- Runtime execution planning or pipeline orchestration (owned by application.pipeline).
- Financial transformation calculations (owned by domain layer).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import dataclasses

import pytest

from personal_finance_etl.contracts.capabilities import (
    CAPABILITY_REGISTRY,
    COMMON_PRODUCED_SILVER_DATASETS,
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityGraphError,
    CapabilityId,
    ContributionScope,
    ExternalEnrichmentId,
    ResolvedCapabilityGraph,
)
from personal_finance_etl.contracts.datasets import (
    DatasetId,
)
from personal_finance_etl.contracts.semantic_inventory import (
    GOLD_CONTRACT_DEPENDENCIES,
    SILVER_CONTRACT_SEMANTICS,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)


def test_exact_capability_vocabulary() -> None:
    """Verify that CapabilityId defines the exact set of 7 financial capabilities."""
    expected = {
        "household_core",
        "investment_accounting",
        "benchmark_enrichment",
        "foreign_asset_enrichment",
        "tax",
        "wealth",
        "fire",
    }
    actual = {c.value for c in CapabilityId}
    assert actual == expected
    assert len(CapabilityId) == 7


def test_registry_completeness_and_immutability() -> None:
    """Verify that CAPABILITY_REGISTRY contains immutable descriptors for all capabilities."""
    assert len(CAPABILITY_REGISTRY) == 7
    for cid in CapabilityId:
        assert cid in CAPABILITY_REGISTRY
        desc = CAPABILITY_REGISTRY[cid]
        assert isinstance(desc, CapabilityDescriptor)
        assert desc.capability_id == cid
        assert desc.description.strip() != ""
        # Check immutability
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(desc, "description", "mutated")  # noqa: B010

    # Ensure descriptors contain zero callables
    for desc in CAPABILITY_REGISTRY.values():
        for field in dataclasses.fields(desc):
            val = getattr(desc, field.name)
            assert not callable(val), (
                f"Descriptor {desc.capability_id}.{field.name} must not be callable"
            )


def test_all_bronze_datasets_accounted_for() -> None:
    """Verify that all 20 canonical Bronze datasets are accounted for across capability descriptors."""
    all_registered_bronze = {c.dataset_id for c in BRONZE_CONTRACT_REGISTRY}
    assert len(all_registered_bronze) == 20

    accounted_bronze: set[DatasetId] = set()
    for desc in CAPABILITY_REGISTRY.values():
        accounted_bronze.update(desc.required_bronze_datasets)
        accounted_bronze.update(desc.optional_bronze_datasets)

    assert accounted_bronze == all_registered_bronze
    assert len(accounted_bronze) == 20


def test_all_silver_contracts_accounted_for() -> None:
    """Verify that all 24 canonical Silver contracts are accounted for with no duplicate claims."""
    all_registered_silver = set(SILVER_CONTRACT_SEMANTICS.keys())
    assert len(all_registered_silver) == 24

    claimed_silver: set[DatasetId] = set()
    for desc in CAPABILITY_REGISTRY.values():
        for s_id in desc.produced_silver_datasets:
            assert s_id not in claimed_silver, (
                f"Silver dataset {s_id} claimed by multiple capabilities"
            )
            assert s_id not in COMMON_PRODUCED_SILVER_DATASETS, (
                f"Common dataset {s_id} claimed by capability"
            )
            claimed_silver.add(s_id)

    total_silver = claimed_silver | COMMON_PRODUCED_SILVER_DATASETS
    assert total_silver == all_registered_silver
    assert len(total_silver) == 24
    assert len(COMMON_PRODUCED_SILVER_DATASETS) == 2


def test_all_gold_contracts_accounted_for() -> None:
    """Verify that all 22 canonical Gold presentation contracts are accounted for with no duplicate claims."""
    all_registered_gold = set(GOLD_CONTRACT_DEPENDENCIES.keys())
    assert len(all_registered_gold) == 22

    claimed_gold: set[DatasetId] = set()
    for desc in CAPABILITY_REGISTRY.values():
        for g_id in desc.produced_gold_datasets:
            assert g_id not in claimed_gold, f"Gold dataset {g_id} claimed by multiple capabilities"
            claimed_gold.add(g_id)

    assert claimed_gold == all_registered_gold
    assert len(claimed_gold) == 22


def test_total_analytical_universe_parity() -> None:
    """Verify that produced Silver + Gold datasets match exactly the 46 contracts in DATA_CONTRACT_REGISTRY."""
    produced_silver: set[DatasetId] = set(COMMON_PRODUCED_SILVER_DATASETS)
    produced_gold: set[DatasetId] = set()

    for desc in CAPABILITY_REGISTRY.values():
        produced_silver.update(desc.produced_silver_datasets)
        produced_gold.update(desc.produced_gold_datasets)

    assert len(produced_silver) == 24
    assert len(produced_gold) == 22
    total_produced = produced_silver | produced_gold
    assert len(total_produced) == 46

    registry_analytical_datasets = {c.dataset_id for c in DATA_CONTRACT_REGISTRY}
    assert total_produced == registry_analytical_datasets


def test_graph_validation_detects_unknown_dependency() -> None:
    """Verify that an unregistered prerequisite capability raises CapabilityGraphError."""
    # Create invalid registry with non-existent prerequisite
    invalid_desc = CapabilityDescriptor(
        capability_id=CapabilityId.HOUSEHOLD_CORE,
        description="Invalid",
        required_capabilities=(
            CapabilityId.TAX,
        ),  # TAX requires HOUSEHOLD_CORE, but if we remove TAX:
    )
    # Remove TAX from registry
    partial_reg: dict[CapabilityId, CapabilityDescriptor] = {
        k: v for k, v in CAPABILITY_REGISTRY.items() if k != CapabilityId.TAX
    }
    partial_reg[CapabilityId.HOUSEHOLD_CORE] = invalid_desc

    with pytest.raises(CapabilityGraphError, match="requires unregistered capability"):
        CapabilityGraph(partial_reg)


def test_graph_validation_detects_cycles() -> None:
    """Verify that circular capability dependencies raise CapabilityGraphError."""
    # Create a 2-cycle: HOUSEHOLD_CORE -> WEALTH -> HOUSEHOLD_CORE
    cyclic_hh = CapabilityDescriptor(
        capability_id=CapabilityId.HOUSEHOLD_CORE,
        description="Household",
        required_capabilities=(CapabilityId.WEALTH,),
        required_bronze_datasets=CAPABILITY_REGISTRY[
            CapabilityId.HOUSEHOLD_CORE
        ].required_bronze_datasets,
        produced_silver_datasets=CAPABILITY_REGISTRY[
            CapabilityId.HOUSEHOLD_CORE
        ].produced_silver_datasets,
    )
    cyclic_reg = dict(CAPABILITY_REGISTRY)
    cyclic_reg[CapabilityId.HOUSEHOLD_CORE] = cyclic_hh

    with pytest.raises(CapabilityGraphError, match="Circular capability dependency detected"):
        CapabilityGraph(cyclic_reg)


def test_graph_validation_detects_unknown_dataset() -> None:
    """Verify that specifying an unknown dataset raises CapabilityGraphError."""
    # Use a Gold dataset where a Silver dataset is expected
    invalid_hh = CapabilityDescriptor(
        capability_id=CapabilityId.HOUSEHOLD_CORE,
        description="Household",
        required_bronze_datasets=CAPABILITY_REGISTRY[
            CapabilityId.HOUSEHOLD_CORE
        ].required_bronze_datasets,
        produced_silver_datasets=(DatasetId.WEALTH_CORE_MONTHLY,),  # Gold dataset in silver!
    )
    invalid_reg = dict(CAPABILITY_REGISTRY)
    invalid_reg[CapabilityId.HOUSEHOLD_CORE] = invalid_hh

    with pytest.raises(CapabilityGraphError, match="specifies unknown produced Silver dataset"):
        CapabilityGraph(invalid_reg)


def test_graph_validation_detects_duplicate_claim() -> None:
    """Verify that two capabilities claiming the same output dataset raises CapabilityGraphError."""
    invalid_tax = CapabilityDescriptor(
        capability_id=CapabilityId.TAX,
        description="Tax",
        required_capabilities=(CapabilityId.HOUSEHOLD_CORE, CapabilityId.INVESTMENT_ACCOUNTING),
        produced_silver_datasets=(
            DatasetId.TAX_EVENTS,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,  # Already owned by HOUSEHOLD_CORE!
        ),
    )
    invalid_reg = dict(CAPABILITY_REGISTRY)
    invalid_reg[CapabilityId.TAX] = invalid_tax

    with pytest.raises(CapabilityGraphError, match="Conflicting Silver dataset ownership"):
        CapabilityGraph(invalid_reg)


def test_full_system_topological_resolution() -> None:
    """Verify that resolving all capabilities produces a deterministic topological plan."""
    graph = CapabilityGraph()
    plan: ResolvedCapabilityGraph = graph.resolve()

    assert len(plan.active_capabilities) == 7
    assert plan.requested_capabilities == tuple(CapabilityId)

    # Topological invariant: prerequisites must appear before their dependents
    pos = {cid: idx for idx, cid in enumerate(plan.active_capabilities)}
    for cid in plan.active_capabilities:
        desc = graph.get_descriptor(cid)
        for req in desc.required_capabilities:
            assert pos[req] < pos[cid], f"{req} must precede {cid} in topological order"

    # Datasets coverage
    assert len(plan.produced_silver_datasets) == 24
    assert len(plan.produced_gold_datasets) == 22
    assert (
        len(plan.required_bronze_datasets) == 19
    )  # 6 HH + 6 Inv + 3 BM + 4 FA = 19 required bronze
    assert len(plan.optional_bronze_datasets) == 2  # COLUMN_MASTER + US_STOCK_TRANSACTIONS
    assert len(plan.required_external_enrichments) == 3

    # All 3 external enrichments accounted for
    assert plan.required_external_enrichments == {
        ExternalEnrichmentId.BENCHMARK_PRICES,
        ExternalEnrichmentId.CURRENCY_FX_RATES,
        ExternalEnrichmentId.US_STOCK_PRICES,
    }


def test_subgraph_resolution_household_only() -> None:
    """Verify that requesting HOUSEHOLD_CORE resolves only household datasets and zero investment outputs."""
    graph = CapabilityGraph()
    plan = graph.resolve([CapabilityId.HOUSEHOLD_CORE])

    assert plan.active_capabilities == (CapabilityId.HOUSEHOLD_CORE,)
    assert plan.required_external_enrichments == frozenset()
    assert plan.produced_gold_datasets == frozenset()

    # Produced Silver includes 10 household + 2 common
    assert len(plan.produced_silver_datasets) == 12
    assert DatasetId.COMMON_CALENDAR in plan.produced_silver_datasets
    assert DatasetId.COMMON_CURRENCY in plan.produced_silver_datasets
    assert DatasetId.WEALTH_INCOME_TRANSACTIONS in plan.produced_silver_datasets

    # Zero investment datasets
    assert DatasetId.INVESTMENT_MASTER not in plan.produced_silver_datasets
    assert DatasetId.INVESTMENT_BY_ISIN not in plan.produced_gold_datasets

    # Zero active contributions since peer capabilities are inactive
    assert len(plan.active_contributions) == 0


def test_subgraph_resolution_fire_pulls_prerequisites() -> None:
    """Verify that requesting FIRE transitively activates HOUSEHOLD_CORE and WEALTH."""
    graph = CapabilityGraph()
    plan = graph.resolve([CapabilityId.FIRE])

    # FIRE requires WEALTH, WEALTH requires HOUSEHOLD_CORE
    assert set(plan.active_capabilities) == {
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.WEALTH,
        CapabilityId.FIRE,
    }
    pos = {cid: idx for idx, cid in enumerate(plan.active_capabilities)}
    assert pos[CapabilityId.HOUSEHOLD_CORE] < pos[CapabilityId.WEALTH]
    assert pos[CapabilityId.WEALTH] < pos[CapabilityId.FIRE]

    # Gold outputs include Wealth and FIRE
    assert DatasetId.FIRE_ANALYTICS in plan.produced_gold_datasets
    assert DatasetId.WEALTH_CORE_MONTHLY in plan.produced_gold_datasets
    assert DatasetId.TAX_YEAR_SUMMARY not in plan.produced_gold_datasets


def test_subgraph_resolution_tax_pulls_prerequisites() -> None:
    """Verify that requesting TAX transitively activates HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING."""
    graph = CapabilityGraph()
    plan = graph.resolve([CapabilityId.TAX])

    assert set(plan.active_capabilities) == {
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
        CapabilityId.TAX,
    }
    pos = {cid: idx for idx, cid in enumerate(plan.active_capabilities)}
    assert pos[CapabilityId.HOUSEHOLD_CORE] < pos[CapabilityId.TAX]
    assert pos[CapabilityId.INVESTMENT_ACCOUNTING] < pos[CapabilityId.TAX]

    assert DatasetId.TAX_EVENTS in plan.produced_silver_datasets
    assert DatasetId.TAX_YEAR_SUMMARY in plan.produced_gold_datasets


def test_cross_capability_contributions_activation() -> None:
    """Verify that optional contributions activate only when both source and target capabilities are active."""
    graph = CapabilityGraph()

    # 1. Household only: investment contributions inactive
    plan_hh = graph.resolve([CapabilityId.HOUSEHOLD_CORE])
    assert len(plan_hh.active_contributions) == 0

    # 2. Investments only: household is not active, so contribution to household is inactive
    plan_inv = graph.resolve([CapabilityId.INVESTMENT_ACCOUNTING])
    assert len(plan_inv.active_contributions) == 0

    # 3. Household + Investments: cashflow movement contribution active!
    plan_both = graph.resolve([CapabilityId.HOUSEHOLD_CORE, CapabilityId.INVESTMENT_ACCOUNTING])
    assert len(plan_both.active_contributions) == 1
    contrib = plan_both.active_contributions[0]
    assert contrib.target_capability == CapabilityId.HOUSEHOLD_CORE
    assert contrib.scope == ContributionScope.CASHFLOW_MOVEMENTS

    # 4. Household + Wealth + Investments: cashflow and portfolio valuation contributions active!
    plan_wealth = graph.resolve(
        [
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.WEALTH,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )
    scopes = {c.scope for c in plan_wealth.active_contributions}
    assert ContributionScope.CASHFLOW_MOVEMENTS in scopes
    assert ContributionScope.PORTFOLIO_VALUATION in scopes
    assert ContributionScope.REALIZED_GAINS not in scopes

    # 5. Full system: all 3 contributions active!
    plan_full = graph.resolve()
    assert len(plan_full.active_contributions) == 3
    full_scopes = {c.scope for c in plan_full.active_contributions}
    assert full_scopes == {
        ContributionScope.CASHFLOW_MOVEMENTS,
        ContributionScope.PORTFOLIO_VALUATION,
        ContributionScope.REALIZED_GAINS,
    }
