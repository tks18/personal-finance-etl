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
    "CanonicalDatasetPlan",
    "CanonicalFragment",
    "CanonicalProducerKind",
    "CanonicalProductionPlan",
    "SourceAssemblyMode",
    "SourceBindingPlan",
]


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
    """

    binding_id: SourceBindingId
    source_id: SourceId
    provider_type: ProviderType
    location: str
    enabled: bool
    selector: object | None = None
    change_detection: object | None = None
    route_ids: tuple[CanonicalRouteId, ...] = ()


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
    """

    dataset_id: DatasetId
    producer_kind: CanonicalProducerKind
    assembly_mode: SourceAssemblyMode
    is_required: bool
    is_enabled: bool
    route_refs: tuple[CanonicalRouteRef, ...] = ()
    provider_type: ProviderType | None = None
    recipe_name: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalProductionPlan:
    """Complete immutable plan for producing canonical datasets across active capabilities.

    Parameters
    ----------
    dataset_plans : tuple[CanonicalDatasetPlan, ...]
        Compiled plans for each canonical dataset.
    binding_plans : tuple[SourceBindingPlan, ...], default ()
        Compiled physical source binding plans.
    """

    dataset_plans: tuple[CanonicalDatasetPlan, ...]
    binding_plans: tuple[SourceBindingPlan, ...] = ()

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
