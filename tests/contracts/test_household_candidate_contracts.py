"""Authoritative contract and registry tests for Phase 052 household candidate datasets.

Owns
----
- Unit tests verifying the six candidate household DatasetIds are registered in CANDIDATE_BRONZE_DATASETS.
- Schema tests verifying DuckDB DDL schemas and Pandera Gate-2 schemas match CANONICAL_BRONZE_FIELDS.
- Capability metadata tests verifying FUTURE_CAPABILITY_CANDIDATES and helper functions.
"""

from __future__ import annotations

from personal_finance_etl.contracts.canonical_fields import (
    CANONICAL_BRONZE_FIELDS,
    get_canonical_fields,
    is_valid_canonical_field,
)
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    get_future_capability_bronze_requirements,
)
from personal_finance_etl.contracts.datasets import (
    CANDIDATE_BRONZE_DATASETS,
    DatasetId,
)
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    CANDIDATE_BRONZE_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
)
from personal_finance_etl.infrastructure.warehouse.schema.bronze import (
    BRONZE_TABLE_SCHEMAS,
    generate_bronze_ddl,
)


def test_household_candidate_datasets_registered() -> None:
    """Verify that all six household candidate datasets are properly registered."""
    household_candidates = (
        DatasetId.HOUSEHOLD_CATEGORIES,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        DatasetId.HOUSEHOLD_ACCOUNTS,
        DatasetId.COMMON_CURRENCIES,
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
    )
    for ds in household_candidates:
        assert ds in CANDIDATE_BRONZE_DATASETS
        assert ds in CANONICAL_BRONZE_FIELDS
        assert has_canonical_bronze_schema(ds) is True
        schema = get_canonical_bronze_schema(ds)
        assert schema is not None
        assert ds in BRONZE_TABLE_SCHEMAS


def test_household_candidate_contracts_in_registry() -> None:
    """Verify BronzeDataContracts exist for all six candidate household datasets."""
    household_candidates = {
        DatasetId.HOUSEHOLD_CATEGORIES,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        DatasetId.HOUSEHOLD_ACCOUNTS,
        DatasetId.COMMON_CURRENCIES,
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
    }
    registered_ids = {c.dataset_id for c in CANDIDATE_BRONZE_CONTRACT_REGISTRY}
    assert household_candidates.issubset(registered_ids)
    for ds in household_candidates:
        assert get_bronze_contract_by_dataset_id(ds) is not None


def test_household_candidate_ddl_generation() -> None:
    """Verify generate_bronze_ddl includes CREATE TABLE for all six candidate tables."""
    ddl = generate_bronze_ddl()
    assert "CREATE TABLE IF NOT EXISTS bronze.household_categories (" in ddl
    assert "CREATE TABLE IF NOT EXISTS bronze.household_asset_categories (" in ddl
    assert "CREATE TABLE IF NOT EXISTS bronze.household_accounts (" in ddl
    assert "CREATE TABLE IF NOT EXISTS bronze.common_currencies (" in ddl
    assert "CREATE TABLE IF NOT EXISTS bronze.household_transactions (" in ddl
    assert "CREATE TABLE IF NOT EXISTS bronze.household_account_balances (" in ddl


def test_future_capability_candidate_requirements() -> None:
    """Verify FUTURE_CAPABILITY_CANDIDATES provides exact requirements for HOUSEHOLD_CORE."""
    reqs = get_future_capability_bronze_requirements(CapabilityId.HOUSEHOLD_CORE)
    assert reqs is not None
    assert set(reqs) == {
        DatasetId.HOUSEHOLD_CATEGORIES,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        DatasetId.HOUSEHOLD_ACCOUNTS,
        DatasetId.COMMON_CURRENCIES,
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
    }
    assert get_future_capability_bronze_requirements(CapabilityId.TAX) is None


def test_canonical_fields_validation_predicate() -> None:
    """Verify is_valid_canonical_field permits canonical and provenance fields."""
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_CATEGORIES, "category_id") is True
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_CATEGORIES, "category_kind") is True
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_CATEGORIES, "artifact_id") is True
    assert is_valid_canonical_field(DatasetId.HOUSEHOLD_CATEGORIES, "IS_DEL") is False

    fields = get_canonical_fields(DatasetId.HOUSEHOLD_TRANSACTIONS)
    assert fields is not None
    assert "transaction_id" in fields
    assert "transaction_kind" in fields
    assert "artifact_id" in fields
    assert "TRANSACTION_TYPE" not in fields
