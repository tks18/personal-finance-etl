"""Authoritative unit and integration tests for the household evidence parity comparison harness.

Owns
----
- Unit tests verifying compare_household_datasets catches row count, key, and value differences.
- Unit tests proving compare_household_evidence_collections certifies equivalent datasets.
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.application.diagnostics.household_parity import (
    compare_household_datasets,
    compare_household_evidence_collections,
)
from personal_finance_etl.contracts.canonical_semantics import (
    HouseholdCategoryKind,
    HouseholdTransactionKind,
)
from personal_finance_etl.contracts.datasets import DatasetId


def test_compare_household_categories_parity_success() -> None:
    """Verify parity check succeeds when legacy active and canonical categories match exactly."""
    legacy_df = pl.DataFrame(
        {
            "UID": ["cat_1", "cat_2", "cat_del"],
            "CATEGORY_NAME": ["Salary", "Food", "Deleted"],
            "TYPE": [0, 1, 1],
            "CATEGORY_ID": ["", "cat_1", ""],
            "IS_DEL": [0, 0, 1],
        }
    )
    canonical_df = pl.DataFrame(
        {
            "category_id": ["cat_1", "cat_2"],
            "category_name": ["Salary", "Food"],
            "category_kind": [
                HouseholdCategoryKind.INCOME.value,
                HouseholdCategoryKind.EXPENSE.value,
            ],
            "parent_category_id": [None, "cat_1"],
            "artifact_id": ["art_1", "art_1"],
        }
    )

    result = compare_household_datasets(
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_CATEGORIES,
        legacy_df,
        canonical_df,
    )
    assert result.is_equivalent is True
    assert result.legacy_active_count == 2
    assert result.canonical_count == 2
    assert result.matched_keys_count == 2
    assert len(result.discrepancies) == 0


def test_compare_household_categories_row_count_mismatch() -> None:
    """Verify parity check detects missing rows in canonical categories."""
    legacy_df = pl.DataFrame(
        {
            "UID": ["cat_1", "cat_2"],
            "CATEGORY_NAME": ["Salary", "Food"],
            "TYPE": [0, 1],
            "CATEGORY_ID": ["", ""],
            "IS_DEL": [0, 0],
        }
    )
    canonical_df = pl.DataFrame(
        {
            "category_id": ["cat_1"],
            "category_name": ["Salary"],
            "category_kind": [HouseholdCategoryKind.INCOME.value],
            "parent_category_id": [None],
        }
    )

    result = compare_household_datasets(
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_CATEGORIES,
        legacy_df,
        canonical_df,
    )
    assert result.is_equivalent is False
    assert any("Row count mismatch" in d for d in result.discrepancies)
    assert any("Primary key mismatch" in d for d in result.discrepancies)


def test_compare_household_categories_value_mismatch() -> None:
    """Verify parity check detects semantic kind discrepancy (income vs expense)."""
    legacy_df = pl.DataFrame(
        {
            "UID": ["cat_1"],
            "CATEGORY_NAME": ["Salary"],
            "TYPE": [0],  # Income in legacy
            "CATEGORY_ID": [""],
            "IS_DEL": [0],
        }
    )
    canonical_df = pl.DataFrame(
        {
            "category_id": ["cat_1"],
            "category_name": ["Salary"],
            "category_kind": ["expense"],  # Discrepant kind in canonical
            "parent_category_id": [None],
        }
    )

    result = compare_household_datasets(
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_CATEGORIES,
        legacy_df,
        canonical_df,
    )
    assert result.is_equivalent is False
    assert any("Category kind semantic mismatch" in d for d in result.discrepancies)


def test_compare_household_evidence_collections_certification() -> None:
    """Verify aggregate parity report certifies clean evidence collections."""
    collection = {
        DatasetId.HOUSEHOLD_ZCATEGORY: pl.DataFrame(
            {"UID": ["c1"], "CATEGORY_NAME": ["A"], "TYPE": [0], "IS_DEL": [0]}
        ),
        DatasetId.HOUSEHOLD_CATEGORIES: pl.DataFrame(
            {
                "category_id": ["c1"],
                "category_name": ["A"],
                "category_kind": ["income"],
                "parent_category_id": [None],
            }
        ),
        DatasetId.HOUSEHOLD_ASSET_GROUP: pl.DataFrame(
            {"UID": ["ag1"], "ASSET_GROUP": ["Bank"], "IS_DEL": [0]}
        ),
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES: pl.DataFrame(
            {"asset_category_id": ["ag1"], "asset_category_name": ["Bank"]}
        ),
        DatasetId.HOUSEHOLD_ASSETS: pl.DataFrame(
            {
                "UID": ["a1"],
                "ASSET_NAME": ["Checking"],
                "ASSET_GROUP_ID": ["ag1"],
                "CURRENCY_ID": ["inr"],
                "IS_DEL": ["0"],
            }
        ),
        DatasetId.HOUSEHOLD_ACCOUNTS: pl.DataFrame(
            {
                "asset_id": ["a1"],
                "asset_name": ["Checking"],
                "asset_category_id": ["ag1"],
                "currency_id": ["inr"],
            }
        ),
        DatasetId.HOUSEHOLD_CURRENCY: pl.DataFrame(
            {"UID": ["inr"], "CURRENCY_NAME": ["Rupee"], "ISO": ["INR"], "IS_DEL": [0]}
        ),
        DatasetId.COMMON_CURRENCIES: pl.DataFrame(
            {"currency_id": ["inr"], "currency_name": ["Rupee"], "iso_code": ["INR"]}
        ),
        DatasetId.HOUSEHOLD_INOUTCOME: pl.DataFrame(
            {
                "UID": ["tx1"],
                "DATE": ["2026-01-01"],
                "TRANSACTION_TYPE": ["0"],
                "BASE_AMOUNT": [100.0],
                "ASSET_ID": ["a1"],
                "CURRENCY_ID": ["inr"],
                "IS_DEL": [0],
            }
        ),
        DatasetId.HOUSEHOLD_TRANSACTIONS: pl.DataFrame(
            {
                "transaction_id": ["tx1"],
                "transaction_date": ["2026-01-01"],
                "transaction_kind": [HouseholdTransactionKind.INCOME.value],
                "base_amount": [100.0],
                "asset_id": ["a1"],
                "currency_id": ["inr"],
            }
        ),
        DatasetId.HOUSEHOLD_OPENING_BALANCES: pl.DataFrame(
            {
                "Z_PK": [1],
                "ZTXDATESTR": ["2026-01-01"],
                "ZAMOUNT": [1000.0],
                "ZASSETUID": ["a1"],
                "ZCURRENCYUID": ["inr"],
            }
        ),
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES: pl.DataFrame(
            {
                "opening_balance_id": ["1"],
                "balance_date": ["2026-01-01"],
                "opening_amount": [1000.0],
                "asset_id": ["a1"],
                "currency_id": ["inr"],
            }
        ),
    }

    report = compare_household_evidence_collections(collection)
    assert report.is_all_equivalent is True
    assert "CERTIFIED" in report.summary
    assert len(report.results) == 6
