"""Authoritative declarative planning and assembly contracts for canonical production.

Owns
----
- CanonicalProducerKind: Closed enum for canonical dataset producers (SOURCE, PROVIDER, DERIVED).
- SourceAssemblyMode: Closed enum for combining source fragments (DIRECT, UNION).
- CanonicalFragment: Immutable descriptor for a routed source fragment ready for canonical assembly.
- SourceBindingPlan: Immutable compilation descriptor for a physical source binding.
- CanonicalDatasetPlan: Immutable compilation descriptor for producing an individual canonical dataset.
- CanonicalProductionPlan: Complete immutable execution plan for all active canonical datasets.

Does not own
------------
- Polars LazyFrames, Pandera schemas, or DuckDB execution (owned by infrastructure/application).
- Capability graph or execution planning (owned by contracts.capabilities and application.pipeline.planner).
- Physical file access or provider extraction (owned by infrastructure.providers).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
    SourceId,
)

__all__ = [
    "AmbiguousCanonicalProducerError",
    "CanonicalDatasetPlan",
    "CanonicalFragment",
    "CanonicalProducerCandidate",
    "CanonicalProducerKind",
    "CanonicalProductionPlan",
    "CyclicCanonicalDependencyError",
    "InvalidExplicitProducerSelectionError",
    "SatisfiabilityPlanningError",
    "SourceAssemblyMode",
    "SourceBindingPlan",
    "UnsatisfiedCanonicalEvidenceError",
]


class SatisfiabilityPlanningError(Exception):
    """Base exception for canonical evidence satisfiability planning failures."""


class UnsatisfiedCanonicalEvidenceError(SatisfiabilityPlanningError):
    """Raised when a required canonical dataset cannot be produced by any candidate producer.

    Parameters
    ----------
    dataset_id : DatasetId
        The required canonical dataset identifier that could not be satisfied.
    required_by_capabilities : tuple[str, ...], default ()
        Names of active capabilities that mandate this dataset.
    """

    def __init__(
        self,
        dataset_id: DatasetId,
        required_by_capabilities: tuple[str, ...] = (),
    ) -> None:
        self.dataset_id = dataset_id
        self.required_by_capabilities = required_by_capabilities
        caps_str = (
            f" (mandated by: {', '.join(required_by_capabilities)})"
            if required_by_capabilities
            else ""
        )
        super().__init__(
            f"Required canonical dataset '{dataset_id}' cannot be satisfied by any configured producer{caps_str}."
        )


class AmbiguousCanonicalProducerError(SatisfiabilityPlanningError):
    """Raised when multiple candidate producers exist for a canonical dataset without an explicit selection.

    Parameters
    ----------
    dataset_id : DatasetId
        The canonical dataset identifier with ambiguous producer candidates.
    candidates : tuple[str, ...], default ()
        Descriptions or identifiers of the competing candidate producers.
    """

    def __init__(
        self,
        dataset_id: DatasetId,
        candidates: tuple[str, ...] = (),
    ) -> None:
        self.dataset_id = dataset_id
        self.candidates = candidates
        cands_str = f": {', '.join(candidates)}" if candidates else ""
        super().__init__(
            f"Ambiguous producers discovered for canonical dataset '{dataset_id}'{cands_str}. "
            "An explicit production selection in configuration is required."
        )


class CyclicCanonicalDependencyError(SatisfiabilityPlanningError):
    """Raised when canonical derivation recipes form a cyclic dependency graph.

    Parameters
    ----------
    cycle_path : tuple[DatasetId, ...]
        Ordered sequence of dataset identifiers tracing the dependency cycle.
    """

    def __init__(self, cycle_path: tuple[DatasetId, ...]) -> None:
        self.cycle_path = cycle_path
        cycle_str = " -> ".join(str(d) for d in cycle_path)
        super().__init__(
            f"Cyclic dependency detected among canonical dataset producers: {cycle_str}."
        )


class InvalidExplicitProducerSelectionError(SatisfiabilityPlanningError):
    """Raised when an explicit production declaration references nonexistent or disabled routes/recipes.

    Parameters
    ----------
    dataset_id : DatasetId
        The canonical dataset identifier for which explicit selection failed.
    reason : str
        Detailed description of the validation failure.
    """

    def __init__(self, dataset_id: DatasetId, reason: str) -> None:
        self.dataset_id = dataset_id
        self.reason = reason
        super().__init__(
            f"Explicit producer selection for canonical dataset '{dataset_id}' is invalid: {reason}."
        )


class CanonicalProducerKind(StrEnum):
    """Authoritative classification of canonical evidence producer mechanisms."""

    SOURCE = "source"
    PROVIDER = "provider"
    DERIVED = "derived"


class SourceAssemblyMode(StrEnum):
    """Authoritative strategy for assembling source routes into a canonical dataset."""

    DIRECT = "direct"
    UNION = "union"


@dataclass(frozen=True, slots=True)
class CanonicalFragment:
    """Immutable descriptor of a single routed fragment ready for canonical assembly.

    Parameters
    ----------
    fragment_id : str
        Deterministic identifier for this fragment.
    binding_id : SourceBindingId
        The physical source binding supplying this fragment.
    route_id : CanonicalRouteId
        The specific route within the binding.
    target_dataset_id : DatasetId
        Canonical dataset target intended for this fragment.
    row_count : int | None, default None
        Optional observed or estimated row count.
    schema_fingerprint : str | None, default None
        Optional cryptographic fingerprint of the fragment schema.
    provenance_fingerprint : str | None, default None
        Optional cryptographic fingerprint of the fragment provenance.
    """

    fragment_id: str
    binding_id: SourceBindingId
    route_id: CanonicalRouteId
    target_dataset_id: DatasetId
    row_count: int | None = None
    schema_fingerprint: str | None = None
    provenance_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SourceBindingPlan:
    """Immutable compilation plan for a physical tabular stream binding.

    Parameters
    ----------
    binding_id : SourceBindingId
        Logical identifier of the physical source binding.
    source_id : SourceId
        Logical identifier of the parent physical evidence source.
    provider_type : ProviderType
        Physical extractor provider type.
    location : str
        Configured filesystem location or URI.
    enabled : bool
        Whether this binding is operationally enabled.
    selector : object | None, default None
        Optional provider-specific typed selector descriptor.
    change_detection : object | None, default None
        Optional resolved change-detection and synchronization policy descriptor.
    route_ids : tuple[CanonicalRouteId, ...], default ()
        Compiled canonical routes owned by this binding.
    binding_config : object | None, default None
        Optional authoritative source binding configuration descriptor.
    legacy_dataset_config : object | None, default None
        Optional legacy source dataset configuration descriptor for transitional compatibility.
    target_dataset_id : DatasetId | None, default None
        Optional transitional target canonical dataset identifier.
    """

    binding_id: SourceBindingId
    source_id: SourceId
    provider_type: ProviderType
    location: str
    enabled: bool
    selector: object | None = None
    change_detection: object | None = None
    route_ids: tuple[CanonicalRouteId, ...] = ()
    binding_config: object | None = None
    legacy_dataset_config: object | None = None
    target_dataset_id: DatasetId | None = None


@dataclass(frozen=True, slots=True)
class CanonicalProducerCandidate:
    """Immutable descriptor of a candidate evidence source discovered during satisfiability planning.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset target identifier.
    producer_kind : CanonicalProducerKind
        Producer mechanism (SOURCE, PROVIDER, DERIVED).
    assembly_mode : SourceAssemblyMode | None, default None
        Source assembly mode if producer_kind is SOURCE.
    route_refs : tuple[CanonicalRouteRef, ...], default ()
        Referenced source routes if producer_kind is SOURCE.
    provider_type : ProviderType | None, default None
        External provider type if producer_kind is PROVIDER.
    recipe_name : str | None, default None
        Derivation recipe name if producer_kind is DERIVED.
    dependencies : tuple[DatasetId, ...], default ()
        Upstream canonical dataset dependencies for DERIVED recipes.
    is_explicit : bool, default False
        Whether this candidate was explicitly selected in source configuration.
    enabled : bool, default True
        Whether this candidate producer is operationally enabled.
    description : str | None, default None
        Optional human-readable description.
    """

    dataset_id: DatasetId
    producer_kind: CanonicalProducerKind
    assembly_mode: SourceAssemblyMode | None = None
    route_refs: tuple[CanonicalRouteRef, ...] = ()
    provider_type: ProviderType | None = None
    recipe_name: str | None = None
    dependencies: tuple[DatasetId, ...] = ()
    is_explicit: bool = False
    enabled: bool = True
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalDatasetPlan:
    """Immutable compilation plan for producing a canonical PFETL dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Target canonical dataset identifier.
    producer_kind : CanonicalProducerKind
        Producer mechanism (SOURCE, PROVIDER, DERIVED).
    assembly_mode : SourceAssemblyMode
        Source fragment assembly mode (DIRECT, UNION).
    is_required : bool
        Whether this dataset is mandatory under the active ExecutionPlan.
    is_enabled : bool
        Whether this dataset is actively enabled for execution.
    route_refs : tuple[CanonicalRouteRef, ...], default ()
        Source route references consumed by this dataset.
    provider_type : ProviderType | None, default None
        Provider type when producer_kind is PROVIDER.
    recipe_name : str | None, default None
        Registered derivation recipe name when producer_kind is DERIVED.
    dependencies : tuple[DatasetId, ...], default ()
        Upstream canonical dataset dependencies when producer_kind is DERIVED.
    """

    dataset_id: DatasetId
    producer_kind: CanonicalProducerKind
    assembly_mode: SourceAssemblyMode
    is_required: bool
    is_enabled: bool
    route_refs: tuple[CanonicalRouteRef, ...] = ()
    provider_type: ProviderType | None = None
    recipe_name: str | None = None
    dependencies: tuple[DatasetId, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalProductionPlan:
    """Complete immutable plan for producing canonical datasets across active capabilities.

    Parameters
    ----------
    dataset_plans : tuple[CanonicalDatasetPlan, ...]
        Compiled plans for each canonical dataset.
    binding_plans : tuple[SourceBindingPlan, ...], default ()
        Compiled physical source binding plans.
    plan_fingerprint : str, default ""
        Cryptographic SHA-256 fingerprint uniquely identifying the production graph.
    topological_order : tuple[DatasetId, ...], default ()
        Topologically sorted execution sequence of canonical datasets.
    """

    dataset_plans: tuple[CanonicalDatasetPlan, ...]
    binding_plans: tuple[SourceBindingPlan, ...] = ()
    plan_fingerprint: str = ""
    topological_order: tuple[DatasetId, ...] = ()

    def get_dataset_plan(self, dataset_id: DatasetId | str) -> CanonicalDatasetPlan | None:
        """Look up a canonical dataset plan by DatasetId.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Canonical dataset identifier candidate.

        Returns
        -------
        CanonicalDatasetPlan | None
            Matching dataset plan if present, else None.
        """
        target = str(dataset_id)
        for dp in self.dataset_plans:
            if str(dp.dataset_id) == target:
                return dp
        return None

    def get_binding_plan(self, binding_id: SourceBindingId | str) -> SourceBindingPlan | None:
        """Look up a source binding plan by SourceBindingId.

        Parameters
        ----------
        binding_id : SourceBindingId | str
            Source binding identifier candidate.

        Returns
        -------
        SourceBindingPlan | None
            Matching source binding plan if present, else None.
        """
        target = str(binding_id)
        for bp in self.binding_plans:
            if str(bp.binding_id) == target:
                return bp
        return None

    def dependencies_for(self, dataset_id: DatasetId | str) -> tuple[DatasetId, ...]:
        """Look up the declared upstream dependencies for a canonical dataset.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Canonical dataset identifier candidate.

        Returns
        -------
        tuple[DatasetId, ...]
            Tuple of upstream canonical dataset dependencies, if any.
        """
        dp = self.get_dataset_plan(dataset_id)
        return dp.dependencies if dp is not None else ()
