"""Tests for canonical Bronze field vocabularies and validation contracts.

Owns
----
- Verification of CANONICAL_PROVENANCE_FIELDS stability.
- Coverage test proving all 20 canonical Bronze datasets have registered target vocabularies.
- Positive and negative tests for is_valid_canonical_field and get_canonical_fields.
"""

from __future__ import annotations

from personal_finance_etl.contracts.canonical_fields import (
    CANONICAL_BRONZE_FIELDS,
    CANONICAL_PROVENANCE_FIELDS,
    get_canonical_fields,
    is_valid_canonical_field,
)
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    DatasetId,
)


def test_provenance_fields_invariants() -> None:
    """Verify that canonical provenance fields contain the required pipeline lineage names."""
    expected = {"artifact_id", "__file_name__", "__folder_path__"}
    assert CANONICAL_PROVENANCE_FIELDS == expected


def test_all_bronze_datasets_registered() -> None:
    """Verify that every Bronze dataset defined in BRONZE_DATASET_ORIGIN_MAP has a target vocabulary."""
    all_bronze_datasets = set(BRONZE_DATASET_ORIGIN_MAP.keys())
    registered_datasets = set(CANONICAL_BRONZE_FIELDS.keys())

    assert registered_datasets == all_bronze_datasets
    assert len(registered_datasets) == 20


def test_is_valid_canonical_field_domain_and_provenance() -> None:
    """Verify is_valid_canonical_field accepts valid domain and provenance fields."""
    # Provenance fields are valid for every registered dataset
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_ZCATEGORY, "artifact_id")
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_ZCATEGORY, "__file_name__")
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_ZCATEGORY, "__folder_path__")

    # Domain fields are valid for their specific dataset
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_ZCATEGORY, "CATEGORY_NAME")
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_ASSET_GROUP, "ASSET_GROUP")
    assert is_valid_canonical_field(DatasetId.INVESTMENT_MF_ISIN_MAPPING, "ISIN")


def test_is_valid_canonical_field_rejects_invalid_fields() -> None:
    """Verify is_valid_canonical_field rejects unregistered or arbitrary field names."""
    # Unknown field for this dataset
    assert not is_valid_canonical_field(DatasetId.HOUSEHOLD_ZCATEGORY, "NON_EXISTENT_FIELD")
    assert not is_valid_canonical_field(DatasetId.HOUSEHOLD_ASSET_GROUP, "CATEGORY_NAME")

    # Non-Bronze dataset (e.g. Silver dimension) returns False
    assert not is_valid_canonical_field(DatasetId.WEALTH_INCOME_CATEGORY, "CATEGORY_NAME")


def test_get_canonical_fields_returns_union_with_provenance() -> None:
    """Verify get_canonical_fields returns the union of domain and provenance fields."""
    fields = get_canonical_fields(DatasetId.HOUSEHOLD_ASSET_GROUP)
    assert fields is not None
    assert "ASSET_GROUP" in fields
    assert "UID" in fields
    assert "artifact_id" in fields
    assert "__file_name__" in fields
    assert "__folder_path__" in fields


def test_get_canonical_fields_unregistered_returns_none() -> None:
    """Verify get_canonical_fields returns None for unregistered or non-Bronze datasets."""
    assert get_canonical_fields(DatasetId.WEALTH_INCOME_CATEGORY) is None
