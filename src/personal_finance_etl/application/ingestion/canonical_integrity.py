"""Authoritative cross-dataset referential integrity validation for canonical Bronze datasets.

Owns
----
- CanonicalIntegrityRule: Declarative referential contract linking source foreign keys to target primary keys.
- CanonicalIntegrityValidator: Evaluates referential integrity across active Bronze datasets before Silver execution.
- BUILTIN_CANONICAL_INTEGRITY_RULES: Authoritative registry of known cross-dataset canonical constraints.

Does not own
-------------
- Pandera schema validation of individual datasets (owned by infrastructure.validation).
- Vectorized route execution or fragment production (owned by application.ingestion.route_executor).
- Silver domain transformations or financial calculations (owned by domain.*).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.contracts.canonical_recipes import CanonicalIntegrityError
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "BUILTIN_CANONICAL_INTEGRITY_RULES",
    "CanonicalIntegrityRule",
    "CanonicalIntegrityValidator",
]


@dataclass(frozen=True, slots=True)
class CanonicalIntegrityRule:
    """Declarative referential constraint between two canonical datasets.

    Parameters
    ----------
    source_dataset_id : DatasetId
        Canonical dataset containing the referencing foreign key column.
    foreign_key : str
        Name of the foreign key column in source dataset.
    target_dataset_id : DatasetId
        Canonical dataset containing the authoritative primary/unique key.
    target_key : str
        Name of the key column in target dataset.
    allow_null : bool, default True
        Whether null or empty values in the foreign key are permitted.
    description : str, default ""
        Human-readable explanation of the referential relationship.
    """

    source_dataset_id: DatasetId
    foreign_key: str
    target_dataset_id: DatasetId
    target_key: str
    allow_null: bool = True
    description: str = ""


# Authoritative known canonical integrity rules across Bronze Medallion layer
BUILTIN_CANONICAL_INTEGRITY_RULES: tuple[CanonicalIntegrityRule, ...] = (
    CanonicalIntegrityRule(
        source_dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        foreign_key="ACCOUNT_ID",
        target_dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        target_key="UID",
        allow_null=True,
        description="Household income/expense/transfer transactions reference valid asset accounts.",
    ),
    CanonicalIntegrityRule(
        source_dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        foreign_key="CATEGORY_ID",
        target_dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        target_key="UID",
        allow_null=True,
        description="Household transactions reference valid category definitions.",
    ),
    CanonicalIntegrityRule(
        source_dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        foreign_key="ASSET_GROUP_ID",
        target_dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        target_key="UID",
        allow_null=True,
        description="Household asset accounts reference valid asset groups.",
    ),
    CanonicalIntegrityRule(
        source_dataset_id=DatasetId.HOUSEHOLD_OPENING_BALANCES,
        foreign_key="ACCOUNT_ID",
        target_dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        target_key="UID",
        allow_null=False,
        description="Household opening balances must reference valid asset accounts.",
    ),
)


class CanonicalIntegrityValidator:
    """Validates declared cross-dataset referential integrity across active Bronze datasets.

    Parameters
    ----------
    rules : Sequence[CanonicalIntegrityRule] | None, default None
        Authoritative integrity rules to evaluate. If None, uses BUILTIN_CANONICAL_INTEGRITY_RULES.
    """

    def __init__(self, rules: Sequence[CanonicalIntegrityRule] | None = None) -> None:
        self.rules = tuple(rules) if rules is not None else BUILTIN_CANONICAL_INTEGRITY_RULES

    def validate_integrity(
        self,
        collection: DatasetCollection | Mapping[DatasetId, pl.DataFrame],
    ) -> None:
        """Validate referential integrity across all available canonical datasets.

        Parameters
        ----------
        collection : DatasetCollection | Mapping[DatasetId, pl.DataFrame]
            Collection or mapping of active canonical Bronze DataFrames.

        Raises
        ------
        CanonicalIntegrityError
            If any declared foreign reference points to non-existent target keys.
        """
        for rule in self.rules:
            # Check if both datasets are active/present in collection
            if rule.source_dataset_id not in collection:
                continue
            if rule.target_dataset_id not in collection:
                continue

            raw_src = collection[rule.source_dataset_id]
            src_df: pl.DataFrame = (
                raw_src.collect() if isinstance(raw_src, pl.LazyFrame) else raw_src
            )
            raw_tgt = collection[rule.target_dataset_id]
            tgt_df: pl.DataFrame = (
                raw_tgt.collect() if isinstance(raw_tgt, pl.LazyFrame) else raw_tgt
            )

            if rule.foreign_key not in src_df.columns or rule.target_key not in tgt_df.columns:
                continue

            # Build target key set
            target_keys_series = tgt_df[rule.target_key].drop_nulls().cast(pl.String)
            target_keys_set = set(target_keys_series.to_list())

            # Filter source foreign keys
            src_fk_series = src_df[rule.foreign_key]
            if rule.allow_null:
                src_fk_series = src_fk_series.drop_nulls()
            else:
                null_count = int(src_fk_series.null_count())
                if null_count > 0:
                    raise CanonicalIntegrityError(
                        message=(
                            f"Dataset '{rule.source_dataset_id.value}' contains {null_count} null foreign keys "
                            f"in non-nullable column '{rule.foreign_key}' referencing '{rule.target_dataset_id.value}'."
                        ),
                        dataset_id=rule.source_dataset_id,
                        foreign_key=rule.foreign_key,
                        target_dataset_id=rule.target_dataset_id,
                        orphan_count=null_count,
                        sample_orphans=("<NULL>",),
                    )

            # Cast to string for safe scalar comparison
            src_fks = [str(v) for v in src_fk_series.cast(pl.String).to_list() if str(v).strip()]
            orphan_values = [k for k in src_fks if k not in target_keys_set]

            if orphan_values:
                orphan_count = len(orphan_values)
                sample = tuple(sorted(set(orphan_values))[:5])
                msg = (
                    f"Referential integrity failure: dataset '{rule.source_dataset_id.value}' column "
                    f"'{rule.foreign_key}' contains {orphan_count} orphan reference(s) not found in "
                    f"target dataset '{rule.target_dataset_id.value}' column '{rule.target_key}'. "
                    f"Sample orphan keys: {sample}."
                )
                raise CanonicalIntegrityError(
                    message=msg,
                    dataset_id=rule.source_dataset_id,
                    foreign_key=rule.foreign_key,
                    target_dataset_id=rule.target_dataset_id,
                    orphan_count=orphan_count,
                    sample_orphans=sample,
                )
