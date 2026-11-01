# pylint: skip-file
# flake8: noqa
"""Canonical dataset identity and registry contracts test suite.

Owns
----
- Invariant tests for DatasetId enum presence across all warehouse contracts.
- Deterministic lookup tests via get_contract_by_dataset_id and get_bronze_contract_by_dataset_id.
- Backward compatibility verification for physical table mappings and contract_id values.
- Registry validation tests including negative fixtures for duplicate/missing DatasetIds.
"""

from __future__ import annotations

import pytest

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    BronzeDataContract,
    DataContract,
)
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_contract_by_dataset_id,
    get_contract_by_table,
    validate_registry,
)


def test_dataset_id_enum_coverage() -> None:
    """Verify that every Bronze and analytical contract possesses a typed DatasetId."""
    assert len(BRONZE_CONTRACT_REGISTRY) == 20
    assert len(DATA_CONTRACT_REGISTRY) == 46

    bronze_ids = [c.dataset_id for c in BRONZE_CONTRACT_REGISTRY]
    analytical_ids = [c.dataset_id for c in DATA_CONTRACT_REGISTRY]

    # Type check
    for did in bronze_ids:
        assert isinstance(did, DatasetId)
    for did in analytical_ids:
        assert isinstance(did, DatasetId)

    # Within-layer uniqueness
    assert len(bronze_ids) == len(set(bronze_ids))
    assert len(analytical_ids) == len(set(analytical_ids))

    # Cross-layer global uniqueness (all 66 contracts distinct)
    all_ids = bronze_ids + analytical_ids
    assert len(all_ids) == len(set(all_ids))
    assert len(all_ids) == 66


def test_dataset_id_naming_conventions() -> None:
    """Verify that all DatasetId values follow lowercase snake_case without forbidden prefixes."""
    forbidden_prefixes = ("bronze_", "silver_", "gold_", "df_", "r_", "d_", "f_", "p_")
    for member in DatasetId:
        assert member.value == member.value.lower()
        assert not any(member.value.startswith(p) for p in forbidden_prefixes)
        # Naming family check
        assert any(
            member.name.startswith(family)
            for family in ("HOUSEHOLD_", "INVESTMENT_", "MARKET_", "TAX_", "WEALTH_", "FIRE_", "COMMON_")
        )


def test_registry_lookup_by_dataset_id() -> None:
    """Verify deterministic contract resolution via DatasetId enum and string values."""
    # Bronze lookup
    b_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert b_contract is not None
    assert b_contract.extraction_attribute == "zcategory"
    assert b_contract.physical_table == "bronze.r_SQLite_ZCategory"

    # String lookup equivalence
    b_contract_str = get_bronze_contract_by_dataset_id("household_zcategory")
    assert b_contract_str is b_contract

    # Analytical Silver lookup
    s_contract = get_contract_by_dataset_id(DatasetId.COMMON_CALENDAR)
    assert s_contract is not None
    assert s_contract.contract_id == "df_d_calendar"
    assert s_contract.physical_table == "silver.d_Calendar"

    s_contract_str = get_contract_by_dataset_id("common_calendar")
    assert s_contract_str is s_contract

    # Analytical Gold lookup
    g_contract = get_contract_by_dataset_id(DatasetId.TAX_YEAR_SUMMARY)
    assert g_contract is not None
    assert g_contract.contract_id == "df_p_tax_year_summary"
    assert g_contract.physical_table == "gold.Tax_Year_Summary"

    # Non-existent lookup
    assert get_bronze_contract_by_dataset_id("non_existent_id") is None
    assert get_contract_by_dataset_id("non_existent_id") is None


def test_legacy_key_and_physical_table_immutability() -> None:
    """Assert byte-for-byte stability of legacy physical tables, contract_ids, and extraction attributes."""
    expected_bronze_tables = {
        "bronze.r_SQLite_ZCategory",
        "bronze.r_SQLite_AssetGroup",
        "bronze.r_SQLite_Assets",
        "bronze.r_SQLite_Currency",
        "bronze.r_SQLite_InOutcome",
        "bronze.r_MF_ISIN_Mapping",
        "bronze.r_Benchmark_Mapping",
        "bronze.r_Opening_Balances",
        "bronze.r_Benchmark_Master",
        "bronze.r_Macro_Parameters",
        "bronze.r_Column_Master",
        "bronze.r_MF_Market_Data",
        "bronze.r_US_Stock_Transactions",
        "bronze.r_Currency_Mapping",
        "bronze.r_Currency_FX_Data",
        "bronze.r_MF_Transactions",
        "bronze.r_Stock_Market_Data",
        "bronze.r_Stock_Transactions",
        "bronze.r_Benchmark_Data",
        "bronze.r_US_Stock_Prices",
    }
    actual_bronze_tables = {c.physical_table for c in BRONZE_CONTRACT_REGISTRY}
    assert actual_bronze_tables == expected_bronze_tables

    # Legacy get_contract_by_table remains functional
    cal_contract = get_contract_by_table("silver.d_Calendar")
    assert cal_contract is not None
    assert cal_contract.dataset_id == DatasetId.COMMON_CALENDAR


def test_validate_registry_success() -> None:
    """Verify that current lakehouse registries pass comprehensive structural validation."""
    validate_registry()


def test_validate_registry_rejects_duplicate_bronze_dataset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify registry validation rejects duplicate Bronze DatasetId."""
    corrupted_bronze = list(BRONZE_CONTRACT_REGISTRY)
    # Duplicate first entry
    corrupted_bronze.append(
        BronzeDataContract(
            DatasetId.HOUSEHOLD_ZCATEGORY,
            "zcategory_dup",
            "sqlite_source",
            "bronze.r_SQLite_ZCategory_Dup",
            True,
        )
    )
    monkeypatch.setattr(
        "personal_finance_etl.infrastructure.warehouse.registry.BRONZE_CONTRACT_REGISTRY",
        corrupted_bronze,
    )
    with pytest.raises(ValueError, match="Duplicate Bronze DatasetId found"):
        validate_registry()


def test_validate_registry_rejects_duplicate_analytical_dataset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify registry validation rejects duplicate analytical DatasetId."""
    corrupted_data = list(DATA_CONTRACT_REGISTRY)
    # Duplicate first entry
    corrupted_data.append(
        DataContract(
            DatasetId.COMMON_CALENDAR,
            "df_d_calendar_dup",
            "silver",
            "silver.d_Calendar_Dup",
            "Common",
            "Day",
            "CoreEngine",
            15,
        )
    )
    monkeypatch.setattr(
        "personal_finance_etl.infrastructure.warehouse.registry.DATA_CONTRACT_REGISTRY",
        corrupted_data,
    )
    with pytest.raises(ValueError, match="Duplicate analytical DatasetId found"):
        validate_registry()


def test_fingerprint_incorporates_dataset_id() -> None:
    """Verify that metadata fingerprint calculation includes dataset_id."""
    meta1 = [
        {"dataset_id": "common_calendar", "table_name": "silver.d_Calendar", "grain": "Day", "producer": "CoreEngine"},
    ]
    meta2 = [
        {"dataset_id": "different_dataset", "table_name": "silver.d_Calendar", "grain": "Day", "producer": "CoreEngine"},
    ]
    fp1 = generate_contract_registry_fingerprint(meta1)
    fp2 = generate_contract_registry_fingerprint(meta2)
    assert fp1 != fp2

