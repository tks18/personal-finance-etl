"""Deterministic compatibility compiler translating legacy source-dataset bindings to source bindings.

Owns
----
- CompatibilitySourceBindingCompiler: Compiles legacy 1:1 SourceDatasetConfig declarations
  into SourceBindingConfig, CanonicalRouteConfig, and CanonicalDatasetProductionConfig models.
- CompiledSourceBindingTopology: Immutable compiled topology container with indexed lookups.
- derive_source_binding_id: Deterministic mapping from physical SourceId and transitional DatasetId
  to a stable, path-independent SourceBindingId.
- DEFAULT_COMPATIBILITY_ROUTE_ID: Fixed route identifier for 1:1 transitional compatibility routes.

Does not own
------------
- SourceConfiguration parsing or TOML deserialization (owned by config.sources.loader).
- Runtime physical planning or Pre-Bronze acquisition (owned by application.pipeline.source_planner).
- Physical provider extraction mechanics (owned by infrastructure.providers).

Removal Owner
-------------
- Phase 055 (when legacy SourceDatasetConfig is decommissioned and source bindings become the direct input).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.household_routes import (
    build_household_canonical_production,
    build_household_canonical_route,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.validation import validate_source_bindings
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    SourceBindingId,
    SourceId,
    validate_source_binding_id,
)

__all__ = [
    "DEFAULT_COMPATIBILITY_ROUTE_ID",
    "CompatibilitySourceBindingCompiler",
    "CompiledSourceBindingTopology",
    "derive_source_binding_id",
]

DEFAULT_COMPATIBILITY_ROUTE_ID: CanonicalRouteId = CanonicalRouteId("direct")


class _SourceConfigHolder(Protocol):
    """Protocol for configurations providing sources and dataset bindings."""

    @property
    def sources(self) -> Sequence[SourceConfig]:
        """Configured physical evidence sources."""
        ...

    @property
    def datasets(self) -> Sequence[SourceDatasetConfig]:
        """Configured legacy source dataset bindings."""
        ...


def derive_source_binding_id(
    source_id: SourceId | str,
    dataset_id: DatasetId | str,
) -> SourceBindingId:
    """Derive a deterministic, path-independent SourceBindingId from source and dataset identities.

    Parameters
    ----------
    source_id : SourceId | str
        Physical evidence source identifier.
    dataset_id : DatasetId | str
        Transitional canonical dataset identifier.

    Returns
    -------
    SourceBindingId
        Deterministic, validated source binding identifier formatted as '<source_id>__<dataset_id>'.
    """
    s_val = str(source_id).strip()
    d_val = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id).strip()
    return validate_source_binding_id(f"{s_val}__{d_val}")


def _empty_binding_by_id() -> dict[SourceBindingId, SourceBindingConfig]:
    """Create an empty dict mapping SourceBindingId to SourceBindingConfig."""
    return {}


def _empty_production_by_dataset_id() -> dict[DatasetId, CanonicalDatasetProductionConfig]:
    """Create an empty dict mapping DatasetId to CanonicalDatasetProductionConfig."""
    return {}


@dataclass(frozen=True, slots=True)
class CompiledSourceBindingTopology:
    """Immutable compiled container representing the decoupled source binding topology.

    Removal Owner
    -------------
    Phase 055 (decommissioning legacy SourceDatasetConfig).

    Parameters
    ----------
    bindings : tuple[SourceBindingConfig, ...]
        Ordered sequence of compiled physical tabular stream bindings.
    productions : tuple[CanonicalDatasetProductionConfig, ...]
        Ordered sequence of compiled canonical dataset production rules.
    binding_by_id : dict[SourceBindingId, SourceBindingConfig]
        Lookup index of bindings keyed by SourceBindingId.
    production_by_dataset_id : dict[DatasetId, CanonicalDatasetProductionConfig]
        Lookup index of production rules keyed by produced DatasetId.
    """

    bindings: tuple[SourceBindingConfig, ...]
    productions: tuple[CanonicalDatasetProductionConfig, ...]
    binding_by_id: dict[SourceBindingId, SourceBindingConfig] = field(
        default_factory=_empty_binding_by_id
    )
    production_by_dataset_id: dict[DatasetId, CanonicalDatasetProductionConfig] = field(
        default_factory=_empty_production_by_dataset_id
    )

    def get_binding(self, binding_id: SourceBindingId | str) -> SourceBindingConfig | None:
        """Retrieve a compiled binding by its SourceBindingId.

        Parameters
        ----------
        binding_id : SourceBindingId | str
            Target source binding identifier.

        Returns
        -------
        SourceBindingConfig | None
            Matching binding if present, else None.
        """
        target = str(binding_id)
        for b_id, b in self.binding_by_id.items():
            if str(b_id) == target:
                return b
        return None

    def get_production(
        self, dataset_id: DatasetId | str
    ) -> CanonicalDatasetProductionConfig | None:
        """Retrieve a compiled production rule by its produced DatasetId.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Target canonical dataset identifier.

        Returns
        -------
        CanonicalDatasetProductionConfig | None
            Matching production rule if present, else None.
        """
        target = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id)
        for d_id, prod in self.production_by_dataset_id.items():
            if d_id.value == target:
                return prod
        return None

    def get_bindings_for_source(self, source_id: SourceId | str) -> tuple[SourceBindingConfig, ...]:
        """Retrieve all compiled bindings belonging to a physical source.

        Parameters
        ----------
        source_id : SourceId | str
            Physical source identifier.

        Returns
        -------
        tuple[SourceBindingConfig, ...]
            All bindings associated with the target source.
        """
        target = str(source_id)
        return tuple(b for b in self.bindings if str(b.source_id) == target)


class CompatibilitySourceBindingCompiler:
    """Deterministic compatibility compiler translating legacy bindings into source bindings.

    Translates each 1:1 SourceDatasetConfig into:
    1. Exactly one SourceBindingConfig (keyed by derive_source_binding_id);
    2. Exactly one child CanonicalRouteConfig (route_id='direct', targeting transitional DatasetId);
    3. Exactly one CanonicalDatasetProductionConfig (DIRECT assembly, SOURCE producer).

    Removal Owner
    -------------
    Phase 055 (decommissioning legacy SourceDatasetConfig).
    """

    @classmethod
    def compile(
        cls,
        source_config: _SourceConfigHolder,
        *,
        include_candidate_household_routes: bool = True,
    ) -> CompiledSourceBindingTopology:
        """Compile a complete SourceConfiguration instance into a CompiledSourceBindingTopology.

        Parameters
        ----------
        source_config : _SourceConfigHolder
            Authoritative source configuration instance providing sources and datasets.
        include_candidate_household_routes : bool, default True
            Whether to attach candidate canonical routes and productions for household datasets.

        Returns
        -------
        CompiledSourceBindingTopology
            Validated immutable compiled topology.
        """
        return cls.compile_bindings(
            sources=source_config.sources,
            datasets=source_config.datasets,
            include_candidate_household_routes=include_candidate_household_routes,
        )

    @classmethod
    def compile_bindings(
        cls,
        sources: Sequence[SourceConfig],
        datasets: Sequence[SourceDatasetConfig],
        *,
        include_candidate_household_routes: bool = True,
    ) -> CompiledSourceBindingTopology:
        """Compile collections of sources and dataset bindings into a topology.

        Parameters
        ----------
        sources : Sequence[SourceConfig]
            Configured physical evidence sources.
        datasets : Sequence[SourceDatasetConfig]
            Legacy source dataset bindings.
        include_candidate_household_routes : bool, default True
            Whether to attach candidate canonical routes and productions for household datasets.

        Returns
        -------
        CompiledSourceBindingTopology
            Validated immutable compiled topology.

        Raises
        ------
        ValueError
            If validation fails across the compiled bindings and production definitions.
        """
        compiled_bindings: list[SourceBindingConfig] = []
        compiled_productions: list[CanonicalDatasetProductionConfig] = []
        binding_by_id: dict[SourceBindingId, SourceBindingConfig] = {}
        production_by_dataset_id: dict[DatasetId, CanonicalDatasetProductionConfig] = {}

        for ds in datasets:
            binding_id = derive_source_binding_id(ds.source_id, ds.dataset_id)
            route_id = DEFAULT_COMPATIBILITY_ROUTE_ID

            # 1. Compile 1:1 transitional canonical route
            route = CanonicalRouteConfig(
                route_id=route_id,
                target_dataset_id=ds.dataset_id,
                description=ds.description,
                enabled=ds.enabled,
                mapping=list(ds.mapping),
                normalization=list(ds.normalization),
                identity=ds.identity,
            )

            # 2. Compile physical tabular stream binding
            binding_routes = [route]
            canonical_route = None
            if include_candidate_household_routes and ds.source_id in (
                SourceId("household_db"),
                SourceId("opening_balance_csv"),
            ):
                canonical_route = build_household_canonical_route(ds.dataset_id)
                if canonical_route is not None:
                    binding_routes.append(canonical_route)

            binding = SourceBindingConfig(
                binding_id=binding_id,
                source_id=ds.source_id,
                selector=ds.selector,
                enabled=ds.enabled,
                description=ds.description,
                change_detection=ds.change_detection,
                fields=list(ds.fields),
                routes=binding_routes,
            )

            # 3. Compile transitional DIRECT source production definition
            production = CanonicalDatasetProductionConfig(
                dataset_id=ds.dataset_id,
                producer_kind=CanonicalProducerKind.SOURCE,
                assembly_mode=SourceAssemblyMode.DIRECT,
                source_routes=[CanonicalRouteRef(binding_id=binding_id, route_id=route_id)],
                enabled=ds.enabled,
            )

            compiled_bindings.append(binding)
            compiled_productions.append(production)
            binding_by_id[binding_id] = binding
            production_by_dataset_id[ds.dataset_id] = production

            if canonical_route is not None:
                canonical_prod = build_household_canonical_production(binding_id, ds.dataset_id)
                if canonical_prod is not None:
                    compiled_productions.append(canonical_prod)
                    production_by_dataset_id[canonical_prod.dataset_id] = canonical_prod

        # Validate aggregate compiled topology
        validate_source_bindings(
            sources=sources,
            bindings=compiled_bindings,
            productions=compiled_productions,
        )

        return CompiledSourceBindingTopology(
            bindings=tuple(compiled_bindings),
            productions=tuple(compiled_productions),
            binding_by_id=binding_by_id,
            production_by_dataset_id=production_by_dataset_id,
        )
