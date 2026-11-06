"""Authoritative execution plan models for dataset mapping and normalization.

Owns
----
- NormalizationPlan: Immutable slotted recipe for applying mappings and normalization rules.

Does not own
-------------
- Plan compilation mechanics (owned by application.normalization.compiler).
- Vectorized frame execution (owned by application.normalization.executor).
- User-authored configuration models (owned by config.sources.mapping and config.sources.normalization).
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_finance_etl.config.sources.normalization import NormalizationRule
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId

__all__ = ["NormalizationPlan"]


@dataclass(frozen=True, slots=True)
class NormalizationPlan:
    """Deterministic, immutable recipe for executing mappings and normalization on a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier being produced.
    source_id : SourceId | None
        Physical source supplying the raw evidence, if bound.
    column_mapping : dict[str, str]
        Dictionary mapping raw source column names to canonical Bronze column names.
    pre_rename_rules : tuple[NormalizationRule, ...]
        Ordered normalization operations to execute on source columns prior to renaming.
    post_rename_rules : tuple[NormalizationRule, ...]
        Ordered normalization operations to execute on canonical columns following renaming.
    expected_output_fields : tuple[str, ...]
        Ordered list of canonical columns expected in the final normalized frame.
    provenance_fields : tuple[str, ...]
        Pipeline lineage and audit metadata columns to preserve throughout execution.
    """

    dataset_id: DatasetId
    source_id: SourceId | None
    column_mapping: dict[str, str]
    pre_rename_rules: tuple[NormalizationRule, ...]
    post_rename_rules: tuple[NormalizationRule, ...]
    expected_output_fields: tuple[str, ...]
    provenance_fields: tuple[str, ...]
