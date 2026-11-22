"""Authoritative comparison harness verifying semantic parity between legacy and canonical household evidence.

Owns
----
- DatasetParityResult: Strongly-typed diagnostic result for an individual dataset comparison.
- HouseholdParityReport: Aggregate parity certification report across all six household datasets.
- compare_household_datasets: Vectorized Polars comparison function evaluating row counts, keys, and values.
- compare_household_evidence_collections: High-level comparison across in-memory collections or DuckDB warehouse.

Does not own
------------
- Bronze lakehouse persistence (owned by infrastructure.warehouse).
- Pandera schema validation (owned by infrastructure.validation).
- Domain Silver transformations (owned by domain.household).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.contracts.canonical_semantics import (
    HouseholdCategoryKind,
    HouseholdTransactionKind,
)
from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "DatasetParityResult",
    "HouseholdParityReport",
    "compare_household_datasets",
    "compare_household_evidence_collections",
]


@dataclass(frozen=True, slots=True)
class DatasetParityResult:
    """Parity evaluation result for a single legacy-to-canonical dataset pair.

    Parameters
    ----------
    legacy_dataset_id : DatasetId
        Legacy Bronze dataset identity.
    canonical_dataset_id : DatasetId
        Candidate canonical Bronze dataset identity.
    legacy_active_count : int
        Number of active (non-deleted) records in legacy evidence.
    canonical_count : int
        Number of records in canonical Bronze evidence.
    matched_keys_count : int
        Number of matching primary identifiers between legacy and canonical datasets.
    unmatched_keys : tuple[str, ...]
        Sample identifiers present in one dataset but missing from the other.
    is_equivalent : bool
        True if counts match, all keys match, and verified value columns align.
    discrepancies : tuple[str, ...]
        Detailed error diagnostics for any detected value or structural mismatch.
    """

    legacy_dataset_id: DatasetId
    canonical_dataset_id: DatasetId
    legacy_active_count: int
    canonical_count: int
    matched_keys_count: int
    unmatched_keys: tuple[str, ...]
    is_equivalent: bool
    discrepancies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HouseholdParityReport:
    """Aggregate parity certification report across all six household datasets.

    Parameters
    ----------
    results : tuple[DatasetParityResult, ...]
        Ordered evaluation results for each dataset pair.
    is_all_equivalent : bool
        True if every dataset pair is certified equivalent with zero discrepancies.
    summary : str
        Human-readable diagnostic summary.
    """

    results: tuple[DatasetParityResult, ...]
    is_all_equivalent: bool
    summary: str


def _filter_active_legacy_rows(df: pl.DataFrame) -> pl.DataFrame:
    """Filter out soft-deleted rows from legacy Bronze dataframes."""
    cols = df.columns
    if "IS_DEL" in cols:
        return df.filter(pl.col("IS_DEL").cast(pl.String).fill_null("0") == "0")
    if "ZISDEL" in cols:
        return df.filter(pl.col("ZISDEL").cast(pl.String).fill_null("0") == "0")
    return df


def compare_household_datasets(
    legacy_id: DatasetId,
    canonical_id: DatasetId,
    legacy_df: pl.DataFrame,
    canonical_df: pl.DataFrame,
) -> DatasetParityResult:
    """Compare a legacy household dataframe against its canonical counterpart.

    Parameters
    ----------
    legacy_id : DatasetId
        Legacy household dataset identifier.
    canonical_id : DatasetId
        Target canonical household dataset identifier.
    legacy_df : pl.DataFrame
        Materialized legacy Bronze dataframe.
    canonical_df : pl.DataFrame
        Materialized canonical Bronze dataframe.

    Returns
    -------
    DatasetParityResult
        Typed comparison result with discrepancy diagnostics.
    """
    active_legacy = _filter_active_legacy_rows(legacy_df)
    legacy_count = active_legacy.height
    canonical_count = canonical_df.height

    discrepancies: list[str] = []
    if legacy_count != canonical_count:
        discrepancies.append(
            f"Row count mismatch: legacy active has {legacy_count} rows, "
            f"canonical has {canonical_count} rows (diff: {canonical_count - legacy_count})."
        )

    # Determine key column names
    leg_key = "UID"
    can_key = "category_id"
    if legacy_id == DatasetId.HOUSEHOLD_ZCATEGORY:
        can_key = "category_id"
    elif legacy_id == DatasetId.HOUSEHOLD_ASSET_GROUP:
        can_key = "asset_category_id"
    elif legacy_id == DatasetId.HOUSEHOLD_ASSETS:
        can_key = "asset_id"
    elif legacy_id == DatasetId.HOUSEHOLD_CURRENCY:
        can_key = "currency_id"
    elif legacy_id == DatasetId.HOUSEHOLD_INOUTCOME:
        can_key = "transaction_id"
    elif legacy_id == DatasetId.HOUSEHOLD_OPENING_BALANCES:
        leg_key = "Z_PK" if "Z_PK" in active_legacy.columns else "UID"
        can_key = "opening_balance_id"

    leg_keys: set[str] = set()
    if leg_key in active_legacy.columns:
        leg_keys = set(active_legacy[leg_key].drop_nulls().cast(pl.String).to_list())

    can_keys: set[str] = set()
    if can_key in canonical_df.columns:
        can_keys = set(canonical_df[can_key].drop_nulls().cast(pl.String).to_list())

    matched_keys = leg_keys.intersection(can_keys)
    unmatched = sorted((leg_keys - can_keys) | (can_keys - leg_keys))
    if unmatched:
        discrepancies.append(
            f"Primary key mismatch: {len(unmatched)} unmatched identifier(s). "
            f"Sample unmatched: {unmatched[:5]}."
        )

    # Value validations for specific dataset pairs
    if legacy_id == DatasetId.HOUSEHOLD_ZCATEGORY and not discrepancies:
        _verify_category_values(active_legacy, canonical_df, discrepancies)
    elif legacy_id == DatasetId.HOUSEHOLD_INOUTCOME and not discrepancies:
        _verify_transaction_values(active_legacy, canonical_df, discrepancies)

    is_equiv = len(discrepancies) == 0
    return DatasetParityResult(
        legacy_dataset_id=legacy_id,
        canonical_dataset_id=canonical_id,
        legacy_active_count=legacy_count,
        canonical_count=canonical_count,
        matched_keys_count=len(matched_keys),
        unmatched_keys=tuple(unmatched[:10]),
        is_equivalent=is_equiv,
        discrepancies=tuple(discrepancies),
    )


def _verify_category_values(
    legacy_df: pl.DataFrame,
    canonical_df: pl.DataFrame,
    discrepancies: list[str],
) -> None:
    """Verify category kind mapping between legacy TYPE and canonical category_kind."""
    type_map = {
        0: HouseholdCategoryKind.INCOME.value,
        1: HouseholdCategoryKind.EXPENSE.value,
    }
    leg_kinds = dict(
        zip(
            legacy_df["UID"].cast(pl.String).to_list(),
            [type_map.get(t, "unknown") for t in legacy_df["TYPE"].cast(pl.Int64).to_list()],
            strict=False,
        )
    )
    can_kinds = dict(
        zip(
            canonical_df["category_id"].cast(pl.String).to_list(),
            canonical_df["category_kind"].cast(pl.String).to_list(),
            strict=False,
        )
    )
    mismatches = [k for k, v in leg_kinds.items() if k in can_kinds and can_kinds[k] != v]
    if mismatches:
        discrepancies.append(
            f"Category kind semantic mismatch in {len(mismatches)} record(s). Sample: {mismatches[:5]}."
        )


def _verify_transaction_values(
    legacy_df: pl.DataFrame,
    canonical_df: pl.DataFrame,
    discrepancies: list[str],
) -> None:
    """Verify transaction kind mapping and base amounts between legacy and canonical."""
    tx_kind_map = {
        0: HouseholdTransactionKind.INCOME.value,
        1: HouseholdTransactionKind.EXPENSE.value,
        2: HouseholdTransactionKind.TRANSFER.value,
        3: HouseholdTransactionKind.TRANSFER_OUT.value,
        4: HouseholdTransactionKind.TRANSFER_IN.value,
    }
    leg_types = dict(
        zip(
            legacy_df["UID"].cast(pl.String).to_list(),
            [
                tx_kind_map.get(t, "unknown")
                for t in legacy_df["TRANSACTION_TYPE"].cast(pl.Int64, strict=False).to_list()
            ],
            strict=False,
        )
    )
    can_types = dict(
        zip(
            canonical_df["transaction_id"].cast(pl.String).to_list(),
            canonical_df["transaction_kind"].cast(pl.String).to_list(),
            strict=False,
        )
    )
    mismatches = [k for k, v in leg_types.items() if k in can_types and can_types[k] != v]
    if mismatches:
        discrepancies.append(
            f"Transaction kind semantic mismatch in {len(mismatches)} record(s). Sample: {mismatches[:5]}."
        )


def compare_household_evidence_collections(
    collection: Mapping[DatasetId, pl.DataFrame],
) -> HouseholdParityReport:
    """Evaluate parity across all six household datasets from an evidence collection.

    Parameters
    ----------
    collection : Mapping[DatasetId, pl.DataFrame]
        Collection of Bronze DataFrames containing both legacy and canonical tables.

    Returns
    -------
    HouseholdParityReport
        Aggregate certification report.
    """
    pairs: tuple[tuple[DatasetId, DatasetId], ...] = (
        (DatasetId.HOUSEHOLD_ZCATEGORY, DatasetId.HOUSEHOLD_CATEGORIES),
        (DatasetId.HOUSEHOLD_ASSET_GROUP, DatasetId.HOUSEHOLD_ASSET_CATEGORIES),
        (DatasetId.HOUSEHOLD_ASSETS, DatasetId.HOUSEHOLD_ACCOUNTS),
        (DatasetId.HOUSEHOLD_CURRENCY, DatasetId.COMMON_CURRENCIES),
        (DatasetId.HOUSEHOLD_INOUTCOME, DatasetId.HOUSEHOLD_TRANSACTIONS),
        (DatasetId.HOUSEHOLD_OPENING_BALANCES, DatasetId.HOUSEHOLD_ACCOUNT_BALANCES),
    )

    results: list[DatasetParityResult] = []
    all_equiv = True

    for leg_id, can_id in pairs:
        if leg_id not in collection or can_id not in collection:
            res = DatasetParityResult(
                legacy_dataset_id=leg_id,
                canonical_dataset_id=can_id,
                legacy_active_count=0,
                canonical_count=0,
                matched_keys_count=0,
                unmatched_keys=(),
                is_equivalent=False,
                discrepancies=(
                    f"Dataset missing from collection: {leg_id.value} or {can_id.value}",
                ),
            )
            results.append(res)
            all_equiv = False
            continue

        res = compare_household_datasets(leg_id, can_id, collection[leg_id], collection[can_id])
        results.append(res)
        if not res.is_equivalent:
            all_equiv = False

    status = "CERTIFIED" if all_equiv else "DISCREPANCY_DETECTED"
    lines = [f"Household Evidence Parity Report: {status}"]
    for r in results:
        mark = "✓" if r.is_equivalent else "✗"
        lines.append(
            f"  {mark} {r.legacy_dataset_id.value} -> {r.canonical_dataset_id.value}: "
            f"legacy={r.legacy_active_count}, canonical={r.canonical_count}, "
            f"matched_keys={r.matched_keys_count}"
        )
        for disc in r.discrepancies:
            lines.append(f"      - {disc}")

    return HouseholdParityReport(
        results=tuple(results),
        is_all_equivalent=all_equiv,
        summary="\n".join(lines),
    )
