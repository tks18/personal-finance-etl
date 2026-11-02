"""Declarative external evidence source topology evaluation and diagnostics.

Owns
----
- TopologyCoverageReport: Diagnostic value object summarizing Bronze dataset coverage.
- evaluate_bronze_topology_coverage: Evaluator comparing configured bindings against Bronze contracts.

Does not own
------------
- Physical file reading or provider execution (owned by infrastructure.providers).
- Raw-to-Bronze lakehouse contracts definitions (owned by contracts.datasets and infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    EXTERNAL_CONFIGURED_DATASETS,
    PROVIDER_GENERATED_DATASETS,
    DatasetId,
    DatasetOrigin,
)

__all__ = [
    "TopologyCoverageReport",
    "evaluate_bronze_topology_coverage",
]


@dataclass(frozen=True, slots=True)
class TopologyCoverageReport:
    """Diagnostic report evaluating declarative coverage of Bronze lakehouse datasets.

    Parameters
    ----------
    configured_datasets : frozenset[DatasetId]
        All canonical dataset IDs bound to configured sources.
    provider_generated_datasets : frozenset[DatasetId]
        Canonical Bronze datasets fulfilled dynamically by provider workflows.
    transitional_datasets : frozenset[DatasetId]
        Canonical Bronze datasets scheduled for migration or retirement.
    missing_datasets : frozenset[DatasetId]
        Authoritative external Bronze datasets missing from configured bindings.
    unaccounted_datasets : frozenset[DatasetId]
        Configured datasets that are not external Bronze datasets.
    duplicate_datasets : frozenset[DatasetId]
        Dataset IDs configured multiple times across bindings.
    """

    configured_datasets: frozenset[DatasetId]
    provider_generated_datasets: frozenset[DatasetId]
    transitional_datasets: frozenset[DatasetId]
    missing_datasets: frozenset[DatasetId]
    unaccounted_datasets: frozenset[DatasetId]
    duplicate_datasets: frozenset[DatasetId]

    @property
    def is_complete(self) -> bool:
        """Return True if all external Bronze datasets are covered with zero missing or duplicates.

        Returns
        -------
        bool
            True if all external Bronze datasets are covered and no anomalies exist.
        """
        return (
            len(self.missing_datasets) == 0
            and len(self.unaccounted_datasets) == 0
            and len(self.duplicate_datasets) == 0
        )


def evaluate_bronze_topology_coverage(
    bindings: Sequence[SourceDatasetConfig],
) -> TopologyCoverageReport:
    """Evaluate whether configured source bindings cover all externally supplied Bronze datasets.

    Parameters
    ----------
    bindings : Sequence[SourceDatasetConfig]
        Collection of configured source-to-canonical-dataset bindings.

    Returns
    -------
    TopologyCoverageReport
        Diagnostic report showing covered, missing, provider-generated, and duplicate datasets.
    """
    configured_set: set[DatasetId] = set()
    duplicates: set[DatasetId] = set()

    for binding in bindings:
        if binding.dataset_id in configured_set:
            duplicates.add(binding.dataset_id)
        configured_set.add(binding.dataset_id)

    configured_frozen = frozenset(configured_set)

    # Missing datasets are those in EXTERNAL_CONFIGURED_DATASETS not configured by user
    missing = EXTERNAL_CONFIGURED_DATASETS - configured_frozen

    # Unaccounted datasets are those configured by user that are not in EXTERNAL_CONFIGURED_DATASETS
    # (e.g., configuring a provider-generated dataset or a non-Bronze dataset)
    unaccounted = configured_frozen - EXTERNAL_CONFIGURED_DATASETS

    # Transitional datasets that are configured
    transitional = frozenset(
        d
        for d in configured_frozen
        if BRONZE_DATASET_ORIGIN_MAP.get(d) == DatasetOrigin.TRANSITIONAL_CONFIGURATION_DATASET
    )

    return TopologyCoverageReport(
        configured_datasets=configured_frozen,
        provider_generated_datasets=PROVIDER_GENERATED_DATASETS,
        transitional_datasets=transitional,
        missing_datasets=missing,
        unaccounted_datasets=unaccounted,
        duplicate_datasets=frozenset(duplicates),
    )
