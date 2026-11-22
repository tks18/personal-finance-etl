"""Aggregate cross-model validation for sources and dataset bindings.

Owns
----
- validate_source_selector_compatibility: Ensures a dataset selector matches its source provider type.
- validate_source_dataset_bindings: Aggregate validation of legacy source-dataset topologies.
- validate_source_bindings: Aggregate validation of additive source binding and production topologies.

Does not own
------------
- Physical extraction verification or file existence checks (owned by infrastructure.providers).
- Contract models definition (owned by config.sources.model and config.sources.selectors).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import DatasetSelector
from personal_finance_etl.config.sources.semantics import SemanticConstantRule
from personal_finance_etl.contracts.canonical_fields import is_valid_canonical_field
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    SourceBindingId,
    SourceId,
)

__all__ = [
    "validate_source_bindings",
    "validate_source_dataset_bindings",
    "validate_source_selector_compatibility",
]


def validate_source_selector_compatibility(
    source: SourceConfig,
    selector: DatasetSelector,
) -> None:
    """Validate that a dataset selector is compatible with its source provider type.

    Parameters
    ----------
    source : SourceConfig
        The configured physical evidence source.
    selector : DatasetSelector
        The candidate dataset selector.

    Raises
    ------
    ValueError
        If the selector's provider_type does not match the source's provider_type.
    """
    if source.provider_type != selector.provider_type:
        raise ValueError(
            f"Selector provider '{selector.provider_type}' is incompatible with "
            f"source '{source.source_id}' provider '{source.provider_type}'."
        )


def validate_source_dataset_bindings(
    sources: Sequence[SourceConfig] | Mapping[SourceId, SourceConfig],
    bindings: Sequence[SourceDatasetConfig],
) -> None:
    """Validate cross-object semantic consistency across a collection of sources and bindings.

    Parameters
    ----------
    sources : Sequence[SourceConfig] | Mapping[SourceId, SourceConfig]
        Collection of configured physical evidence sources.
    bindings : Sequence[SourceDatasetConfig]
        Collection of source-to-canonical-dataset bindings.

    Raises
    ------
    ValueError
        If any binding references an unknown SourceId, if duplicate (source_id, dataset_id)
        bindings exist, if an invalid dataset_id is supplied, or if a selector is incompatible
        with its referenced source provider type.
    """
    sources_map: dict[SourceId, SourceConfig]
    if isinstance(sources, Mapping):
        sources_map = dict(sources)
    else:
        sources_map = {}
        for src in sources:
            if src.source_id in sources_map:
                raise ValueError(f"Duplicate source definition for source_id '{src.source_id}'.")
            sources_map[src.source_id] = src

    seen_bindings: set[tuple[SourceId, DatasetId]] = set()

    for binding in bindings:
        # 1. Validate SourceId reference exists
        source = sources_map.get(binding.source_id)
        if source is None:
            known_ids = sorted(str(s) for s in sources_map.keys())
            raise ValueError(
                f"SourceDatasetConfig references unknown source_id '{binding.source_id}'. "
                f"Available sources: {known_ids}."
            )

        # 2. Validate uniqueness of (source_id, dataset_id) pair
        binding_key = (binding.source_id, binding.dataset_id)
        if binding_key in seen_bindings:
            raise ValueError(
                f"Duplicate source dataset binding for source '{binding.source_id}' "
                f"and dataset '{binding.dataset_id}'."
            )
        seen_bindings.add(binding_key)

        # 3. Validate selector-provider compatibility
        validate_source_selector_compatibility(source, binding.selector)


def validate_source_bindings(
    sources: Sequence[SourceConfig] | Mapping[SourceId, SourceConfig],
    bindings: Sequence[SourceBindingConfig],
    productions: Sequence[CanonicalDatasetProductionConfig] | None = None,
) -> None:
    """Validate cross-object semantic consistency for additive source bindings and production plans.

    Parameters
    ----------
    sources : Sequence[SourceConfig] | Mapping[SourceId, SourceConfig]
        Collection of configured physical evidence sources.
    bindings : Sequence[SourceBindingConfig]
        Collection of physical tabular stream bindings.
    productions : Sequence[CanonicalDatasetProductionConfig] | None, default None
        Optional collection of canonical dataset production rules.

    Raises
    ------
    ValueError
        If duplicate binding IDs exist, any binding references an unknown SourceId,
        selectors are incompatible with source providers, or production rules reference
        non-existent source routes.
    """
    sources_map: dict[SourceId, SourceConfig]
    if isinstance(sources, Mapping):
        sources_map = dict(sources)
    else:
        sources_map = {}
        for src in sources:
            if src.source_id in sources_map:
                raise ValueError(f"Duplicate source definition for source_id '{src.source_id}'.")
            sources_map[src.source_id] = src

    seen_bindings: set[SourceBindingId] = set()
    routes_by_binding: dict[SourceBindingId, dict[CanonicalRouteId, DatasetId]] = {}

    for binding in bindings:
        # 1. Validate uniqueness of binding_id
        if binding.binding_id in seen_bindings:
            raise ValueError(f"Duplicate source binding identifier found: '{binding.binding_id}'.")
        seen_bindings.add(binding.binding_id)

        # 2. Validate SourceId reference exists
        source = sources_map.get(binding.source_id)
        if source is None:
            known_ids = sorted(str(s) for s in sources_map.keys())
            raise ValueError(
                f"SourceBindingConfig '{binding.binding_id}' references unknown source_id '{binding.source_id}'. "
                f"Available sources: {known_ids}."
            )

        # 3. Validate selector-provider compatibility
        validate_source_selector_compatibility(source, binding.selector)

        # 4. Catalog routes and validate target canonical fields
        declared_field_names: set[str] = (
            {f.name for f in binding.fields} if binding.fields else set()
        )
        binding_routes: dict[CanonicalRouteId, DatasetId] = {}
        for r in binding.routes:
            binding_routes[r.route_id] = r.target_dataset_id

            # Validate target canonical fields
            for m in r.mapping:
                if not is_valid_canonical_field(r.target_dataset_id, m.canonical_field):
                    raise ValueError(
                        f"Route '{r.route_id}' in binding '{binding.binding_id}' maps to invalid canonical field "
                        f"'{m.canonical_field}' for target dataset '{r.target_dataset_id}'."
                    )
            for s in r.semantics:
                if isinstance(s, SemanticConstantRule):
                    if not is_valid_canonical_field(r.target_dataset_id, s.field):
                        raise ValueError(
                            f"Route '{r.route_id}' in binding '{binding.binding_id}' injects invalid canonical field "
                            f"'{s.field}' for target dataset '{r.target_dataset_id}'."
                        )
            # If source fields are explicitly declared, validate referenced fields
            if declared_field_names:
                for m in r.mapping:
                    if m.source_field not in declared_field_names:
                        raise ValueError(
                            f"Route '{r.route_id}' in binding '{binding.binding_id}' references unknown source field "
                            f"'{m.source_field}' not declared in binding fields."
                        )
                for p in r.predicates:
                    if p.field not in declared_field_names:
                        raise ValueError(
                            f"Predicate in route '{r.route_id}' of binding '{binding.binding_id}' references unknown field "
                            f"'{p.field}'."
                        )
        routes_by_binding[binding.binding_id] = binding_routes

    # 5. Validate productions if provided
    if productions:
        for prod in productions:
            for route_ref in prod.source_routes:
                matched_routes = routes_by_binding.get(route_ref.binding_id)
                if matched_routes is None:
                    raise ValueError(
                        f"Canonical production for dataset '{prod.dataset_id}' references route '{route_ref.to_string()}', "
                        f"but binding '{route_ref.binding_id}' does not exist."
                    )
                target_ds = matched_routes.get(route_ref.route_id)
                if target_ds is None:
                    raise ValueError(
                        f"Canonical production for dataset '{prod.dataset_id}' references route '{route_ref.to_string()}', "
                        f"but route '{route_ref.route_id}' does not exist in binding '{route_ref.binding_id}'."
                    )
                if target_ds != prod.dataset_id:
                    raise ValueError(
                        f"Route '{route_ref.to_string()}' targets dataset '{target_ds}', "
                        f"which does not match production dataset '{prod.dataset_id}'."
                    )
