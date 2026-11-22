"""Authoritative tests for canonical cross-dataset referential integrity validation.

Owns
----
- Verification of referential constraints between active Bronze datasets before Silver execution.
- Verification that orphan foreign keys raise CanonicalIntegrityError with actionable diagnostics.
- Verification of nullability handling across foreign references.
"""

from __future__ import annotations

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.canonical_integrity import (
    CanonicalIntegrityRule,
    CanonicalIntegrityValidator,
)
from personal_finance_etl.contracts.canonical_recipes import CanonicalIntegrityError
from personal_finance_etl.contracts.datasets import DatasetId


def test_referential_integrity_valid_relationships() -> None:
    """Verify that valid foreign key references between active datasets pass validation."""
    assets_df = pl.DataFrame({"UID": ["acc_1", "acc_2"], "NAME": ["Checking", "Savings"]})
    cat_df = pl.DataFrame({"UID": ["cat_10", "cat_20"], "CATEGORY_NAME": ["Groceries", "Salary"]})
    inoutcome_df = pl.DataFrame(
        {
            "UID": ["tx_1", "tx_2"],
            "ACCOUNT_ID": ["acc_1", "acc_2"],
            "CATEGORY_ID": ["cat_10", "cat_20"],
            "AMOUNT": [100.0, 5000.0],
        }
    )

    validator = CanonicalIntegrityValidator()
    collection = {
        DatasetId.HOUSEHOLD_ASSETS: assets_df,
        DatasetId.HOUSEHOLD_ZCATEGORY: cat_df,
        DatasetId.HOUSEHOLD_INOUTCOME: inoutcome_df,
    }

    # Should succeed without raising
    validator.validate_integrity(collection)


def test_referential_integrity_orphaned_keys_fail() -> None:
    """Verify that orphan foreign keys trigger CanonicalIntegrityError with diagnostic details."""
    assets_df = pl.DataFrame({"UID": ["acc_1", "acc_2"]})
    inoutcome_df = pl.DataFrame(
        {
            "UID": ["tx_1", "tx_2", "tx_3"],
            "ACCOUNT_ID": ["acc_1", "ghost_account_1", "ghost_account_2"],
        }
    )

    validator = CanonicalIntegrityValidator()
    collection = {
        DatasetId.HOUSEHOLD_ASSETS: assets_df,
        DatasetId.HOUSEHOLD_INOUTCOME: inoutcome_df,
    }

    with pytest.raises(CanonicalIntegrityError) as exc_info:
        validator.validate_integrity(collection)

    err = exc_info.value
    assert err.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME.value
    assert err.foreign_key == "ACCOUNT_ID"
    assert err.target_dataset_id == DatasetId.HOUSEHOLD_ASSETS.value
    assert err.orphan_count == 2
    assert "ghost_account_1" in err.sample_orphans
    assert "ghost_account_2" in err.sample_orphans


def test_referential_integrity_null_handling() -> None:
    """Verify that nullable references permit nulls, while non-nullable foreign keys reject nulls."""
    assets_df = pl.DataFrame({"UID": ["acc_1"]})

    # 1. Nullable foreign key: inoutcome category can be null
    cat_df = pl.DataFrame({"UID": ["cat_1"]})
    inoutcome_df = pl.DataFrame(
        {
            "UID": ["tx_1"],
            "ACCOUNT_ID": ["acc_1"],
            "CATEGORY_ID": [None],  # Null category allowed
        }
    )

    validator = CanonicalIntegrityValidator()
    validator.validate_integrity(
        {
            DatasetId.HOUSEHOLD_ASSETS: assets_df,
            DatasetId.HOUSEHOLD_ZCATEGORY: cat_df,
            DatasetId.HOUSEHOLD_INOUTCOME: inoutcome_df,
        }
    )

    # 2. Non-nullable foreign key: opening balance account_id cannot be null
    opening_df = pl.DataFrame(
        {
            "UID": ["ob_1"],
            "ACCOUNT_ID": [None],  # Non-nullable foreign key contains null
        }
    )
    with pytest.raises(CanonicalIntegrityError) as exc_info:
        validator.validate_integrity(
            {
                DatasetId.HOUSEHOLD_ASSETS: assets_df,
                DatasetId.HOUSEHOLD_OPENING_BALANCES: opening_df,
            }
        )

    assert exc_info.value.orphan_count == 1
    assert "<NULL>" in exc_info.value.sample_orphans


def test_custom_rule_validation() -> None:
    """Verify custom integrity rule registration and execution."""
    custom_rule = CanonicalIntegrityRule(
        source_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        foreign_key="ISIN",
        target_dataset_id=DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        target_key="ISIN",
        allow_null=False,
    )
    validator = CanonicalIntegrityValidator(rules=[custom_rule])

    mapping_df = pl.DataFrame({"ISIN": ["INE001A01036"]})
    orders_df = pl.DataFrame({"ISIN": ["INE999UNKNOWN"]})

    with pytest.raises(CanonicalIntegrityError) as exc_info:
        validator.validate_integrity(
            {
                DatasetId.INVESTMENT_BENCHMARK_MAPPING: mapping_df,
                DatasetId.INVESTMENT_STOCK_ORDERS: orders_df,
            }
        )

    assert exc_info.value.foreign_key == "ISIN"
    assert "INE999UNKNOWN" in exc_info.value.sample_orphans
