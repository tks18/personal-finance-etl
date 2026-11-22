"""Unit tests for deterministic cryptographic fingerprinting of compiled source binding topologies.

Owns
----
- Verification of deterministic repeatability for binding, route, production, and topology fingerprints.
- Verification of unordered collection invariance (reordering bindings/routes yields identical fingerprints).
- Verification of mutation sensitivity (modifying route mapping changes route and topology fingerprints).
- Verification of bounded prefix structure (src_bnd_, can_rt_, can_prd_, top_cfg_).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.binding_model import (
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.compiler import (
    CompiledSourceBindingTopology,
)
from personal_finance_etl.config.sources.fingerprint import (
    compute_canonical_production_fingerprint,
    compute_canonical_route_fingerprint,
    compute_compiled_topology_fingerprint,
    compute_source_binding_fingerprint,
)
from personal_finance_etl.config.sources.loader import get_shan_baseline_source_configuration
from personal_finance_etl.config.sources.normalization import TrimRule


def test_fingerprint_prefix_and_length_formats() -> None:
    """Verify that all compiled model fingerprints have standard prefixes and 24-char length."""
    config = get_shan_baseline_source_configuration()
    topology = config.compile_binding_topology()

    top_fp = compute_compiled_topology_fingerprint(topology)
    assert top_fp.startswith("top_cfg_")
    assert len(top_fp) == 24  # 'top_cfg_' (8) + 16 hex chars

    binding = topology.bindings[0]
    bnd_fp = compute_source_binding_fingerprint(binding)
    assert bnd_fp.startswith("src_bnd_")
    assert len(bnd_fp) == 24  # 'src_bnd_' (8) + 16 hex chars

    route = binding.routes[0]
    rt_fp = compute_canonical_route_fingerprint(route)
    assert rt_fp.startswith("can_rt_")
    assert len(rt_fp) == 23  # 'can_rt_' (7) + 16 hex chars

    production = topology.productions[0]
    prd_fp = compute_canonical_production_fingerprint(production)
    assert prd_fp.startswith("can_prd_")
    assert len(prd_fp) == 24  # 'can_prd_' (8) + 16 hex chars


def test_fingerprint_deterministic_repeatability() -> None:
    """Verify identical topologies compute byte-stable fingerprints."""
    config1 = get_shan_baseline_source_configuration()
    config2 = get_shan_baseline_source_configuration()

    top1 = config1.compile_binding_topology()
    top2 = config2.compile_binding_topology()

    assert compute_compiled_topology_fingerprint(top1) == compute_compiled_topology_fingerprint(
        top2
    )
    for b1, b2 in zip(top1.bindings, top2.bindings, strict=True):
        assert compute_source_binding_fingerprint(b1) == compute_source_binding_fingerprint(b2)
        assert compute_canonical_route_fingerprint(
            b1.routes[0]
        ) == compute_canonical_route_fingerprint(b2.routes[0])


def test_fingerprint_unordered_collection_invariance() -> None:
    """Verify reordering bindings or mapping columns produces identical fingerprints."""
    config = get_shan_baseline_source_configuration()
    top_original = config.compile_binding_topology()

    # Reorder bindings in reverse
    shuffled_bindings = tuple(reversed(top_original.bindings))
    shuffled_productions = tuple(reversed(top_original.productions))

    top_shuffled = CompiledSourceBindingTopology(
        bindings=shuffled_bindings,
        productions=shuffled_productions,
        binding_by_id=top_original.binding_by_id,
        production_by_dataset_id=top_original.production_by_dataset_id,
    )

    assert compute_compiled_topology_fingerprint(
        top_original
    ) == compute_compiled_topology_fingerprint(top_shuffled)


def test_fingerprint_mapping_reordering_invariance_on_route() -> None:
    """Verify reordering ColumnMapping rules on a CanonicalRouteConfig produces the same fingerprint."""
    config = get_shan_baseline_source_configuration()
    topology = config.compile_binding_topology()

    binding = topology.get_binding("household_db__household_zcategory")
    assert binding is not None
    original_route = binding.routes[0]

    # Create duplicate route with reversed mappings
    reversed_mappings = list(reversed(original_route.mapping))
    route_reversed = CanonicalRouteConfig(
        route_id=original_route.route_id,
        target_dataset_id=original_route.target_dataset_id,
        description=original_route.description,
        enabled=original_route.enabled,
        mapping=reversed_mappings,
        normalization=original_route.normalization,
        identity=original_route.identity,
    )

    assert compute_canonical_route_fingerprint(
        original_route
    ) == compute_canonical_route_fingerprint(route_reversed)


def test_fingerprint_mutation_sensitivity_and_isolation() -> None:
    """Verify modifying a route changes its fingerprint and topology, but not other routes."""
    config = get_shan_baseline_source_configuration()
    topology = config.compile_binding_topology()

    b1 = topology.bindings[0]
    b2 = topology.bindings[1]

    rt1_original_fp = compute_canonical_route_fingerprint(b1.routes[0])
    rt2_original_fp = compute_canonical_route_fingerprint(b2.routes[0])
    top_original_fp = compute_compiled_topology_fingerprint(topology)

    # Mutate route on b1 by adding a normalization rule
    mutated_norm = list(b1.routes[0].normalization) + [TrimRule(field="EXTRA_COL", mode="both")]
    mutated_rt1 = CanonicalRouteConfig(
        route_id=b1.routes[0].route_id,
        target_dataset_id=b1.routes[0].target_dataset_id,
        description=b1.routes[0].description,
        enabled=b1.routes[0].enabled,
        mapping=b1.routes[0].mapping,
        normalization=mutated_norm,
        identity=b1.routes[0].identity,
    )

    mutated_b1 = SourceBindingConfig(
        binding_id=b1.binding_id,
        source_id=b1.source_id,
        selector=b1.selector,
        enabled=b1.enabled,
        description=b1.description,
        change_detection=b1.change_detection,
        fields=b1.fields,
        routes=[mutated_rt1],
    )

    mutated_topology = CompiledSourceBindingTopology(
        bindings=(mutated_b1,) + topology.bindings[1:],
        productions=topology.productions,
        binding_by_id=dict(topology.binding_by_id, **{mutated_b1.binding_id: mutated_b1}),
        production_by_dataset_id=topology.production_by_dataset_id,
    )

    # Route 1 fingerprint changed
    assert compute_canonical_route_fingerprint(mutated_rt1) != rt1_original_fp

    # Topology fingerprint changed
    assert compute_compiled_topology_fingerprint(mutated_topology) != top_original_fp

    # Route 2 fingerprint remained completely unchanged (isolated)
    assert compute_canonical_route_fingerprint(b2.routes[0]) == rt2_original_fp
