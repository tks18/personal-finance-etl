"""Authoritative tests for cross-dataset referential integrity validation of canonical household evidence.

Owns
----
- Unit tests verifying referential integrity constraints across canonical household Bronze datasets.
- Verification that orphan foreign keys raise CanonicalIntegrityError with actionable diagnostics.
- Verification of category tree self-referential validation and opening balances account/currency validation.
"""

from __future__ import annotations

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.canonical_integrity import (
    CanonicalIntegrityValidator,
)
from personal_finance_etl.contracts.canonical_recipes import CanonicalIntegrityError
from personal_finance_etl.contracts.datasets import DatasetId


def test_canonical_household_referential_integrity_valid() -> None:
    """Verify that consistent canonical household datasets pass all integrity rules."""
    categories_df = pl.DataFrame(
        {
            "category_id": ["root_cat", "sub_cat"],
            "parent_category_id": [None, "root_cat"],  # Valid category hierarchy
        }
    )
    asset_categories_df = pl.DataFrame(
        {
            "asset_category_id": ["bank_cat"],
        }
    )
    currencies_df = pl.DataFrame(
        {
            "currency_id": ["inr", "usd"],
        }
    )
    accounts_df = pl.DataFrame(
        {
            "asset_id": ["acc_checking", "acc_savings"],
            "asset_category_id": ["bank_cat", "bank_cat"],
            "currency_id": ["inr", "inr"],
        }
    )
    transactions_df = pl.DataFrame(
        {
            "transaction_id": ["tx_1", "tx_2"],
            "asset_id": ["acc_checking", "acc_savings"],
            "category_id": ["sub_cat", None],
            "currency_id": ["inr", "inr"],
        }
    )
    balances_df = pl.DataFrame(
        {
            "opening_balance_id": ["bal_1"],
            "asset_id": ["acc_checking"],
            "currency_id": ["inr"],
        }
    )

    validator = CanonicalIntegrityValidator()
    collection = {
        DatasetId.HOUSEHOLD_CATEGORIES: categories_df,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES: asset_categories_df,
        DatasetId.COMMON_CURRENCIES: currencies_df,
        DatasetId.HOUSEHOLD_ACCOUNTS: accounts_df,
        DatasetId.HOUSEHOLD_TRANSACTIONS: transactions_df,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES: balances_df,
    }

    validator.validate_integrity(collection)


def test_canonical_household_orphan_account_in_transactions() -> None:
    """Verify that an orphan account reference in transactions triggers CanonicalIntegrityError."""
    accounts_df = pl.DataFrame({"asset_id": ["valid_acc"]})
    transactions_df = pl.DataFrame(
        {
            "transaction_id": ["tx_1"],
            "asset_id": ["ghost_acc"],
            "currency_id": ["inr"],
        }
    )

    validator = CanonicalIntegrityValidator()
    collection = {
        DatasetId.HOUSEHOLD_ACCOUNTS: accounts_df,
        DatasetId.HOUSEHOLD_TRANSACTIONS: transactions_df,
    }

    with pytest.raises(CanonicalIntegrityError) as exc_info:
        validator.validate_integrity(collection)

    err = exc_info.value
    assert err.dataset_id == DatasetId.HOUSEHOLD_TRANSACTIONS
    assert err.foreign_key == "asset_id"
    assert err.target_dataset_id == DatasetId.HOUSEHOLD_ACCOUNTS
    assert "ghost_acc" in err.sample_orphans


def test_canonical_household_orphan_parent_category() -> None:
    """Verify that an orphan parent category in the category tree triggers CanonicalIntegrityError."""
    categories_df = pl.DataFrame(
        {
            "category_id": ["sub_cat"],
            "parent_category_id": ["missing_parent_root"],
        }
    )

    validator = CanonicalIntegrityValidator()
    collection = {
        DatasetId.HOUSEHOLD_CATEGORIES: categories_df,
    }

    with pytest.raises(CanonicalIntegrityError) as exc_info:
        validator.validate_integrity(collection)

    err = exc_info.value
    assert err.dataset_id == DatasetId.HOUSEHOLD_CATEGORIES
    assert err.foreign_key == "parent_category_id"
    assert "missing_parent_root" in err.sample_orphans
