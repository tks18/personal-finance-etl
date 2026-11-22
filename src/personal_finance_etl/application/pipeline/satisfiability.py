"""Application planning service proving canonical evidence producibility before physical execution.

Owns
----
- CanonicalSatisfiabilityPlanner: Preflight compiler resolving ExecutionPlan, source topology,
  providers, and derivation recipes into a deterministic acyclic CanonicalProductionPlan.
- Candidate discovery across SOURCE, PROVIDER, and DERIVED producer mechanisms.
- Ambiguity and satisfiability resolution enforcement (explicit configuration > single auto-resolution).
- Dependency DAG construction and cycle detection for derived canonical recipes.
- Cryptographic, order-invariant CanonicalProductionPlan fingerprint generation.

Does not own
------------
- Capability dependency resolution (owned by contracts.capabilities.CapabilityGraph).
- Physical source extraction or network provider calls (owned by infrastructure.providers).
- Physical dataframe assembly or Gate-2 Pandera validation (owned by CanonicalProductionEngine).
- Database transaction management (owned by RunLifecycleCoordinator).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence

from personal_finance_etl.application.ingestion.canonical_recipes import (
    CanonicalRecipeRegistry,
    get_global_recipe_registry,
)
from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
)
from personal_finance_etl.config.sources.compiler import CompiledSourceBindingTopology
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.contracts.canonical_plans import (
    AmbiguousCanonicalProducerError,
    CanonicalDatasetPlan,
    CanonicalProducerCandidate,
    CanonicalProducerKind,
    CanonicalProductionPlan,
    CyclicCanonicalDependencyError,
    InvalidExplicitProducerSelectionError,
    SourceAssemblyMode,
    SourceBindingPlan,
    UnsatisfiedCanonicalEvidenceError,
)
from personal_finance_etl.contracts.capabilities import CapabilityGraph
from personal_finance_etl.contracts.datasets import (
    PROVIDER_GENERATED_DATASETS,
    DatasetId,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.sources import (
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
)

__all__ = ["CanonicalSatisfiabilityPlanner"]


class CanonicalSatisfiabilityPlanner:
    """Proves canonical evidence satisfiability and resolves deterministic production DAGs.

    Parameters
    ----------
    recipe_registry : CanonicalRecipeRegistry | None, default None
        Optional registered derivation recipe authority. If None, uses the global registry.
    capability_graph : CapabilityGraph | None, default None
        Optional capability dependency graph for tracing mandating capabilities.
    """

    def __init__(
        self,
        recipe_registry: CanonicalRecipeRegistry | None = None,
        capability_graph: CapabilityGraph | None = None,
    ) -> None:
        self._recipe_registry = recipe_registry or get_global_recipe_registry()
        self._capability_graph = capability_graph or CapabilityGraph()

    def plan(
        self,
        execution_plan: ExecutionPlan,
        source_config: SourceConfiguration | CompiledSourceBindingTopology,
        binding_plans: Sequence[SourceBindingPlan] | None = None,
    ) -> CanonicalProductionPlan:
        """Resolve active capabilities and configured sources into an immutable production plan.

        Parameters
        ----------
        execution_plan : ExecutionPlan
            Active execution plan dictating required and optional canonical Bronze datasets.
        source_config : SourceConfiguration | CompiledSourceBindingTopology
            Configured physical evidence sources or pre-compiled source binding topology.
        binding_plans : Sequence[SourceBindingPlan] | None, default None
            Optional compiled physical source binding plans to attach to the final plan.

        Returns
        -------
        CanonicalProductionPlan
            Validated, topologically sorted, and deterministically fingerprinted production plan.

        Raises
        ------
        UnsatisfiedCanonicalEvidenceError
            If any required canonical dataset has zero candidate producers.
        AmbiguousCanonicalProducerError
            If multiple candidate producers exist for a dataset without an explicit selection.
        CyclicCanonicalDependencyError
            If derived canonical recipes form a cyclic dependency loop.
        InvalidExplicitProducerSelectionError
            If an explicit production declaration references nonexistent or disabled routes/recipes.
        """
        topology: CompiledSourceBindingTopology
        if isinstance(source_config, SourceConfiguration):
            topology = source_config.compile_binding_topology()
        else:
            topology = source_config

        # 1. Discover all candidate producers across all mechanisms
        candidates_by_dataset = self._discover_candidates(topology)

        # 2. Build index of explicit production declarations
        explicit_productions: dict[DatasetId, CanonicalDatasetProductionConfig] = {
            p.dataset_id: p for p in topology.productions
        }

        # 3. Determine requested and required dataset sets
        required_set = set(execution_plan.required_bronze_datasets)
        optional_set = set(execution_plan.optional_bronze_datasets)
        target_datasets = required_set | optional_set

        # 4. Resolve candidate producer for each requested dataset
        resolved_plans: dict[DatasetId, CanonicalDatasetPlan] = {}
        pending_queue = deque(sorted(target_datasets, key=lambda d: d.value))
        processed_datasets: set[DatasetId] = set()

        while pending_queue:
            target_ds = pending_queue.popleft()
            if target_ds in processed_datasets:
                continue
            processed_datasets.add(target_ds)

            is_required = target_ds in required_set
            explicit_config = explicit_productions.get(target_ds)
            candidates = candidates_by_dataset.get(target_ds, [])

            resolved = self._resolve_producer(
                dataset_id=target_ds,
                candidates=candidates,
                explicit_config=explicit_config,
                is_required=is_required,
                execution_plan=execution_plan,
            )

            if resolved is None:
                # Optional unsatisfied dataset remains absent; never materialize fake-empty
                continue

            resolved_plans[target_ds] = resolved

            # If derived, queue its dependencies for satisfiability proof
            for dep in resolved.dependencies:
                required_set.add(dep)  # Dependencies of active derivations are mandatory
                if dep not in processed_datasets:
                    pending_queue.append(dep)

        # 5. Build dependency DAG and topologically sort
        sorted_plans = self._build_dependency_dag_and_sort(resolved_plans)

        # 6. Extract or compile physical binding plans
        final_binding_plans: tuple[SourceBindingPlan, ...] = (
            tuple(binding_plans) if binding_plans is not None else ()
        )

        # 7. Compute deterministic cryptographic plan fingerprint
        plan_fingerprint = self._compute_production_fingerprint(
            execution_plan=execution_plan,
            sorted_plans=sorted_plans,
            binding_plans=final_binding_plans,
        )

        topological_order = tuple(dp.dataset_id for dp in sorted_plans)

        return CanonicalProductionPlan(
            dataset_plans=sorted_plans,
            binding_plans=final_binding_plans,
            plan_fingerprint=plan_fingerprint,
            topological_order=topological_order,
        )

    def _discover_candidates(
        self,
        topology: CompiledSourceBindingTopology,
    ) -> dict[DatasetId, list[CanonicalProducerCandidate]]:
        """Discover all viable candidate producers from bindings, providers, and recipes."""
        candidates_by_dataset: dict[DatasetId, list[CanonicalProducerCandidate]] = defaultdict(list)

        # A. Discovered from physical source bindings and routes
        routes_by_dataset: dict[DatasetId, list[tuple[SourceBindingId, CanonicalRouteRef]]] = (
            defaultdict(list)
        )
        for binding in topology.bindings:
            if not binding.enabled:
                continue
            for route in binding.routes:
                if not route.enabled:
                    continue
                route_ref = CanonicalRouteRef(
                    binding_id=binding.binding_id, route_id=route.route_id
                )
                routes_by_dataset[route.target_dataset_id].append((binding.binding_id, route_ref))

        # Check explicit production declarations for assembly mode
        explicit_prod_by_id = {p.dataset_id: p for p in topology.productions}

        for target_ds, route_items in routes_by_dataset.items():
            explicit_prod = explicit_prod_by_id.get(target_ds)
            if (
                explicit_prod is not None
                and explicit_prod.producer_kind == CanonicalProducerKind.SOURCE
            ):
                # Explicit source production configuration governs assembly
                candidates_by_dataset[target_ds].append(
                    CanonicalProducerCandidate(
                        dataset_id=target_ds,
                        producer_kind=CanonicalProducerKind.SOURCE,
                        assembly_mode=explicit_prod.assembly_mode,
                        route_refs=tuple(explicit_prod.source_routes),
                        is_explicit=True,
                        enabled=explicit_prod.enabled,
                    )
                )
            else:
                # Default 1:1 candidate route creation
                for _, ref in route_items:
                    candidates_by_dataset[target_ds].append(
                        CanonicalProducerCandidate(
                            dataset_id=target_ds,
                            producer_kind=CanonicalProducerKind.SOURCE,
                            assembly_mode=SourceAssemblyMode.DIRECT,
                            route_refs=(ref,),
                            is_explicit=False,
                            enabled=True,
                        )
                    )

        # B. Discovered from provider-generated datasets
        for prov_ds in PROVIDER_GENERATED_DATASETS:
            explicit_prod = explicit_prod_by_id.get(prov_ds)
            is_explicit = (
                explicit_prod is not None
                and explicit_prod.producer_kind == CanonicalProducerKind.PROVIDER
            )
            candidates_by_dataset[prov_ds].append(
                CanonicalProducerCandidate(
                    dataset_id=prov_ds,
                    producer_kind=CanonicalProducerKind.PROVIDER,
                    provider_type=ProviderType.MARKET_DATA,
                    is_explicit=is_explicit,
                    enabled=explicit_prod.enabled if explicit_prod else True,
                )
            )

        # C. Discovered from registered derivation recipes
        for recipe in self._recipe_registry.list_recipes():
            target_ds = recipe.target_dataset_id
            explicit_prod = explicit_prod_by_id.get(target_ds)
            is_explicit = (
                explicit_prod is not None
                and explicit_prod.producer_kind == CanonicalProducerKind.DERIVED
                and explicit_prod.recipe_name == recipe.recipe_id
            )
            candidates_by_dataset[target_ds].append(
                CanonicalProducerCandidate(
                    dataset_id=target_ds,
                    producer_kind=CanonicalProducerKind.DERIVED,
                    recipe_name=recipe.recipe_id,
                    dependencies=recipe.dependencies,
                    is_explicit=is_explicit,
                    enabled=explicit_prod.enabled if explicit_prod else True,
                )
            )

        return candidates_by_dataset

    def _resolve_producer(
        self,
        dataset_id: DatasetId,
        candidates: Sequence[CanonicalProducerCandidate],
        explicit_config: CanonicalDatasetProductionConfig | None,
        is_required: bool,
        execution_plan: ExecutionPlan,
    ) -> CanonicalDatasetPlan | None:
        """Apply deterministic resolution rules to select exactly one producer or raise."""
        # 1. Explicit declaration resolution
        if explicit_config is not None:
            return self._resolve_explicit_producer(
                dataset_id=dataset_id,
                explicit_config=explicit_config,
                candidates=candidates,
                is_required=is_required,
            )

        # Filter enabled candidates
        enabled_candidates = [c for c in candidates if c.enabled]

        # 2. Zero candidate resolution
        if not enabled_candidates:
            if is_required:
                mandating_caps = self._find_mandating_capabilities(dataset_id, execution_plan)
                raise UnsatisfiedCanonicalEvidenceError(
                    dataset_id=dataset_id,
                    required_by_capabilities=mandating_caps,
                )
            return None

        # 3. Single candidate auto-resolution
        if len(enabled_candidates) == 1:
            chosen = enabled_candidates[0]
            return CanonicalDatasetPlan(
                dataset_id=dataset_id,
                producer_kind=chosen.producer_kind,
                assembly_mode=chosen.assembly_mode or SourceAssemblyMode.DIRECT,
                is_required=is_required,
                is_enabled=chosen.enabled,
                route_refs=chosen.route_refs,
                provider_type=chosen.provider_type,
                recipe_name=chosen.recipe_name,
                dependencies=chosen.dependencies,
            )

        # 4. Ambiguity error (>1 enabled candidates without explicit selection)
        candidate_descriptions = tuple(
            f"{c.producer_kind.value}:"
            + (
                f"{c.recipe_name}"
                if c.recipe_name
                else (
                    f"{c.provider_type.value}"
                    if c.provider_type
                    else "/".join(f"{r.binding_id}:{r.route_id}" for r in c.route_refs)
                )
            )
            for c in enabled_candidates
        )
        raise AmbiguousCanonicalProducerError(
            dataset_id=dataset_id,
            candidates=candidate_descriptions,
        )

    def _resolve_explicit_producer(
        self,
        dataset_id: DatasetId,
        explicit_config: CanonicalDatasetProductionConfig,
        candidates: Sequence[CanonicalProducerCandidate],
        is_required: bool,
    ) -> CanonicalDatasetPlan | None:
        """Validate and resolve an explicit producer selection."""
        if not explicit_config.enabled:
            return CanonicalDatasetPlan(
                dataset_id=dataset_id,
                producer_kind=explicit_config.producer_kind,
                assembly_mode=explicit_config.assembly_mode,
                is_required=is_required,
                is_enabled=False,
                route_refs=tuple(explicit_config.source_routes),
                provider_type=explicit_config.provider_type,
                recipe_name=explicit_config.recipe_name,
            )

        if explicit_config.producer_kind == CanonicalProducerKind.SOURCE:
            if not explicit_config.source_routes:
                raise InvalidExplicitProducerSelectionError(
                    dataset_id=dataset_id,
                    reason="SOURCE production requires at least one source route in source_routes",
                )
            if (
                explicit_config.assembly_mode == SourceAssemblyMode.DIRECT
                and len(explicit_config.source_routes) != 1
            ):
                raise InvalidExplicitProducerSelectionError(
                    dataset_id=dataset_id,
                    reason=f"DIRECT assembly mode requires exactly 1 route, found {len(explicit_config.source_routes)}",
                )
            return CanonicalDatasetPlan(
                dataset_id=dataset_id,
                producer_kind=CanonicalProducerKind.SOURCE,
                assembly_mode=explicit_config.assembly_mode,
                is_required=is_required,
                is_enabled=explicit_config.enabled,
                route_refs=tuple(explicit_config.source_routes),
            )

        if explicit_config.producer_kind == CanonicalProducerKind.PROVIDER:
            if explicit_config.provider_type is None:
                raise InvalidExplicitProducerSelectionError(
                    dataset_id=dataset_id,
                    reason="PROVIDER production requires a non-null provider_type",
                )
            return CanonicalDatasetPlan(
                dataset_id=dataset_id,
                producer_kind=CanonicalProducerKind.PROVIDER,
                assembly_mode=SourceAssemblyMode.DIRECT,
                is_required=is_required,
                is_enabled=explicit_config.enabled,
                provider_type=explicit_config.provider_type,
            )

        if explicit_config.producer_kind == CanonicalProducerKind.DERIVED:
            if explicit_config.recipe_name is None:
                raise InvalidExplicitProducerSelectionError(
                    dataset_id=dataset_id,
                    reason="DERIVED production requires a non-null recipe_name",
                )
            recipe = self._recipe_registry.get_recipe(explicit_config.recipe_name)
            if recipe is None:
                raise InvalidExplicitProducerSelectionError(
                    dataset_id=dataset_id,
                    reason=f"Recipe '{explicit_config.recipe_name}' is not registered in CanonicalRecipeRegistry",
                )
            return CanonicalDatasetPlan(
                dataset_id=dataset_id,
                producer_kind=CanonicalProducerKind.DERIVED,
                assembly_mode=SourceAssemblyMode.DIRECT,
                is_required=is_required,
                is_enabled=explicit_config.enabled,
                recipe_name=explicit_config.recipe_name,
                dependencies=recipe.dependencies,
            )

        raise InvalidExplicitProducerSelectionError(
            dataset_id=dataset_id,
            reason=f"Unsupported producer kind '{explicit_config.producer_kind}'",
        )

    def _find_mandating_capabilities(
        self,
        dataset_id: DatasetId,
        execution_plan: ExecutionPlan,
    ) -> tuple[str, ...]:
        """Find active capability IDs that explicitly require a given canonical dataset."""
        mandating: list[str] = []
        for cap_id in execution_plan.resolved_capabilities:
            desc = self._capability_graph.get_descriptor(cap_id)
            if dataset_id in desc.required_bronze_datasets:
                mandating.append(cap_id.value)
        return tuple(sorted(mandating))

    def _build_dependency_dag_and_sort(
        self,
        plans: Mapping[DatasetId, CanonicalDatasetPlan],
    ) -> tuple[CanonicalDatasetPlan, ...]:
        """Construct dependency DAG, detect cycles, and produce topological sort."""
        # Nodes: all dataset_ids in plans
        in_degree: dict[DatasetId, int] = {ds_id: 0 for ds_id in plans}
        dependents_map: dict[DatasetId, list[DatasetId]] = defaultdict(list)

        for ds_id, plan in plans.items():
            for dep in plan.dependencies:
                if dep in plans:
                    in_degree[ds_id] += 1
                    dependents_map[dep].append(ds_id)

        # Ready queue: datasets with 0 dependencies among resolved plans
        ready_queue = deque(
            sorted([ds_id for ds_id, deg in in_degree.items() if deg == 0], key=lambda d: d.value)
        )
        sorted_dataset_ids: list[DatasetId] = []

        while ready_queue:
            current = ready_queue.popleft()
            sorted_dataset_ids.append(current)

            for dependent in sorted(dependents_map[current], key=lambda d: d.value):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready_queue.append(dependent)

        if len(sorted_dataset_ids) != len(plans):
            # Dependency cycle detected
            unresolved = {ds_id for ds_id, deg in in_degree.items() if deg > 0}
            cycle = self._trace_cycle(unresolved, plans)
            raise CyclicCanonicalDependencyError(cycle_path=cycle)

        return tuple(plans[ds_id] for ds_id in sorted_dataset_ids)

    def _trace_cycle(
        self,
        unresolved: set[DatasetId],
        plans: Mapping[DatasetId, CanonicalDatasetPlan],
    ) -> tuple[DatasetId, ...]:
        """Trace a concrete dependency cycle among unresolved datasets."""
        visited: set[DatasetId] = set()
        path: list[DatasetId] = []

        def dfs(node: DatasetId) -> tuple[DatasetId, ...] | None:
            if node in path:
                cycle_start = path.index(node)
                return tuple(path[cycle_start:] + [node])
            if node in visited:
                return None

            visited.add(node)
            path.append(node)

            for dep in plans.get(
                node,
                CanonicalDatasetPlan(
                    node, CanonicalProducerKind.SOURCE, SourceAssemblyMode.DIRECT, False, False
                ),
            ).dependencies:
                if dep in unresolved:
                    found = dfs(dep)
                    if found is not None:
                        return found

            path.pop()
            return None

        for start_node in sorted(unresolved, key=lambda d: d.value):
            result = dfs(start_node)
            if result is not None:
                return result

        return tuple(sorted(unresolved, key=lambda d: d.value))

    def _compute_production_fingerprint(
        self,
        execution_plan: ExecutionPlan,
        sorted_plans: Sequence[CanonicalDatasetPlan],
        binding_plans: Sequence[SourceBindingPlan],
    ) -> str:
        """Compute stable cryptographic SHA-256 fingerprint for the production plan."""
        canonical_datasets_payload: list[dict[str, object]] = []
        for dp in sorted_plans:
            sorted_routes = sorted(f"{r.binding_id}:{r.route_id}" for r in dp.route_refs)
            sorted_deps = sorted(d.value for d in dp.dependencies)
            canonical_datasets_payload.append(
                {
                    "assembly_mode": dp.assembly_mode.value,
                    "dataset_id": dp.dataset_id.value,
                    "dependencies": sorted_deps,
                    "is_enabled": dp.is_enabled,
                    "is_required": dp.is_required,
                    "producer_kind": dp.producer_kind.value,
                    "provider_type": dp.provider_type.value if dp.provider_type else None,
                    "recipe_name": dp.recipe_name,
                    "route_refs": sorted_routes,
                }
            )

        canonical_bindings_payload: list[dict[str, object]] = []
        for bp in sorted(binding_plans, key=lambda b: str(b.binding_id)):
            canonical_bindings_payload.append(
                {
                    "binding_id": str(bp.binding_id),
                    "enabled": bp.enabled,
                    "location": bp.location,
                    "provider_type": bp.provider_type.value,
                    "route_ids": sorted(str(r) for r in bp.route_ids),
                }
            )

        payload = {
            "capabilities": sorted(c.value for c in execution_plan.requested_capabilities),
            "datasets": canonical_datasets_payload,
            "bindings": canonical_bindings_payload,
        }

        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"cprod_{digest}"
