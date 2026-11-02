"""Aggregate cross-model validation for sources and dataset bindings.

Owns
----
- validate_source_selector_compatibility: Ensures a dataset selector matches its source provider type.
- validate_source_dataset_bindings: Aggregate validation of source-dataset topologies.

Does not own
------------
- Physical extraction verification or file existence checks (owned by infrastructure.providers).
- Contract models definition (owned by config.sources.model and config.sources.selectors).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import DatasetSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId

__all__ = [
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
