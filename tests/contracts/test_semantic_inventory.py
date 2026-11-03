"""Authoritative Silver and Gold semantic inventory test suite.

Owns
----
- Invariant tests verifying 1-to-1 parity between physical Silver DDL and the column disposition manifest.
- Verification that all 24 Silver contracts declare precise row grain, identity keys, and capability ownership.
- Verification that all 22 Gold presentation contracts have valid lineage pointing to real Silver datasets/columns.
- Regression tests ensuring zero unclassified columns and zero unresolved REVIEW_REQUIRED dispositions.
- Guard tests verifying future Silver DDL schema drift fails until explicitly classified in the inventory.

Does not own
-------------
- DuckDB engine persistence (owned by infrastructure.warehouse.connection).
- Financial math kernels (owned by domain layer).
- Extraction batch execution (owned by contracts.extraction).
"""

from __future__ import annotations

import duckdb
import pytest

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.semantic_inventory import (
    GOLD_CONTRACT_DEPENDENCIES,
    SILVER_COLUMN_DISPOSITIONS,
    SILVER_CONTRACT_SEMANTICS,
    ColumnClassification,
    ColumnDisposition,
    GoldContractDependency,
    SilverContractSemantics,
    get_columns_by_classification,
    get_columns_by_disposition,
    get_gold_contract_dependency,
    get_silver_column_disposition,
    get_silver_contract_semantics,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    DATA_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL


def _get_ddl_silver_columns() -> dict[str, list[str]]:
    """Extract all physical Silver table names and columns from declarative DDL."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA silver;")
    con.execute(SILVER_DDL)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='silver' ORDER BY table_name"
    ).fetchall()
    table_cols: dict[str, list[str]] = {}
    for (t,) in tables:
        cols = con.execute(f'PRAGMA table_info("silver.{t}")').fetchall()
        table_cols[f"silver.{t}"] = [c[1] for c in cols]
    con.close()
    return table_cols


def _get_ddl_gold_tables() -> set[str]:
    """Extract all physical Gold table names from declarative DDL."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA gold;")
    con.execute(GOLD_DDL)
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='gold' ORDER BY table_name"
    ).fetchall()
    con.close()
    return {f"gold.{t}" for (t,) in tables}


def test_silver_contract_semantics_coverage() -> None:
    """Verify that all 24 Silver contracts have complete semantic declarations."""
    silver_registry_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"]
    assert len(silver_registry_contracts) == 24
    assert len(SILVER_CONTRACT_SEMANTICS) == 24

    for reg in silver_registry_contracts:
        assert reg.dataset_id in SILVER_CONTRACT_SEMANTICS
        semantics = SILVER_CONTRACT_SEMANTICS[reg.dataset_id]
        assert isinstance(semantics, SilverContractSemantics)
        assert semantics.dataset_id == reg.dataset_id
        assert semantics.physical_table == reg.physical_table
        assert semantics.financial_domain == reg.domain
        assert semantics.current_producer == reg.producer
        assert len(semantics.row_grain.strip()) > 0
        assert "(" in semantics.row_grain and ")" in semantics.row_grain
        assert len(semantics.identity_keys) > 0
        assert len(semantics.future_capability_owner.strip()) > 0


def test_silver_column_disposition_ddl_exact_parity() -> None:
    """Assert exact 1-to-1 parity between physical Silver DDL and the disposition manifest."""
    ddl_cols_map = _get_ddl_silver_columns()
    ddl_table_col_pairs = {
        (table.lower(), col) for table, cols in ddl_cols_map.items() for col in cols
    }

    manifest_table_col_pairs = {
        (entry.physical_table.lower(), entry.column_name) for entry in SILVER_COLUMN_DISPOSITIONS
    }

    # Total column count assertion (exactly 534 physical columns)
    assert len(ddl_table_col_pairs) == 534
    assert len(SILVER_COLUMN_DISPOSITIONS) == 534

    # Parity assertions: no missing columns, no extraneous manifest entries
    missing_in_manifest = ddl_table_col_pairs - manifest_table_col_pairs
    assert not missing_in_manifest, (
        f"Columns in Silver DDL missing from manifest: {missing_in_manifest}"
    )

    unknown_in_manifest = manifest_table_col_pairs - ddl_table_col_pairs
    assert not unknown_in_manifest, f"Manifest declares non-existent columns: {unknown_in_manifest}"


def test_zero_review_required() -> None:
    """Assert that zero Silver columns remain with REVIEW_REQUIRED disposition."""
    review_cols = get_columns_by_disposition(ColumnDisposition.REVIEW_REQUIRED)
    assert len(review_cols) == 0, f"Unresolved columns marked REVIEW_REQUIRED: {review_cols}"


def test_known_residue_dispositions() -> None:
    """Verify that known source/provider residues have explicit classifications and non-RETAIN dispositions."""
    known_residue_names = {
        "__file_name__": (
            ColumnClassification.PROVENANCE_REFERENCE,
            ColumnDisposition.MOVE_TO_PROVENANCE,
        ),
        "__folder_path__": (
            ColumnClassification.PROVENANCE_REFERENCE,
            ColumnDisposition.MOVE_TO_PROVENANCE,
        ),
        "__file_category__": (
            ColumnClassification.SOURCE_TAXONOMY,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "S_NO": (
            ColumnClassification.IMPLEMENTATION_RESIDUE,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "MODIFY_DATE": (
            ColumnClassification.PROVENANCE_REFERENCE,
            ColumnDisposition.MOVE_TO_PROVENANCE,
        ),
        "DEVICE_ID": (
            ColumnClassification.IMPLEMENTATION_RESIDUE,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "USE_TIME": (
            ColumnClassification.IMPLEMENTATION_RESIDUE,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "ADDED_TIME": (
            ColumnClassification.IMPLEMENTATION_RESIDUE,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "INSERT_TYPE": (
            ColumnClassification.SOURCE_TAXONOMY,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "IS_SHOW": (
            ColumnClassification.SOURCE_TAXONOMY,
            ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION,
        ),
        "yF_Ticker": (
            ColumnClassification.PROVIDER_METADATA,
            ColumnDisposition.MOVE_TO_PROVIDER_MAPPING,
        ),
        "YAHOO_TICKER": (
            ColumnClassification.PROVIDER_METADATA,
            ColumnDisposition.MOVE_TO_PROVIDER_MAPPING,
        ),
    }

    found_names: set[str] = set()
    for entry in SILVER_COLUMN_DISPOSITIONS:
        if entry.column_name in known_residue_names:
            expected_class, expected_disp = known_residue_names[entry.column_name]
            assert entry.classification == expected_class, (
                f"Mismatch classification for {entry.physical_table}.{entry.column_name}: "
                f"expected {expected_class}, got {entry.classification}"
            )
            assert entry.disposition == expected_disp, (
                f"Mismatch disposition for {entry.physical_table}.{entry.column_name}: "
                f"expected {expected_disp}, got {entry.disposition}"
            )
            found_names.add(entry.column_name)

    # Prove all 12 targeted residues were evaluated
    assert found_names == set(known_residue_names.keys())


def test_gold_contract_dependency_coverage() -> None:
    """Verify that all 22 Gold contracts have complete dependency specifications."""
    gold_registry_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]
    assert len(gold_registry_contracts) == 22
    assert len(GOLD_CONTRACT_DEPENDENCIES) == 22

    ddl_gold_tables = _get_ddl_gold_tables()

    for reg in gold_registry_contracts:
        assert reg.dataset_id in GOLD_CONTRACT_DEPENDENCIES
        dep = GOLD_CONTRACT_DEPENDENCIES[reg.dataset_id]
        assert isinstance(dep, GoldContractDependency)
        assert dep.dataset_id == reg.dataset_id
        assert dep.physical_table == reg.physical_table
        assert dep.physical_table in ddl_gold_tables
        assert dep.producer == reg.producer
        assert len(dep.input_silver_datasets) > 0
        assert len(dep.output_grain.strip()) > 0
        assert len(dep.domain.strip()) > 0


def test_gold_dependencies_reference_real_silver_contracts_and_columns() -> None:
    """Assert that every Gold dependency references existing Silver contracts and physical columns."""
    ddl_silver_map = {k.lower(): v for k, v in _get_ddl_silver_columns().items()}
    silver_datasets = {
        c.dataset_id: c.physical_table.lower()
        for c in DATA_CONTRACT_REGISTRY
        if c.layer == "silver"
    }

    for g_id, dep in GOLD_CONTRACT_DEPENDENCIES.items():
        for s_id in dep.input_silver_datasets:
            assert s_id in silver_datasets, (
                f"Gold contract {g_id} references unregistered Silver DatasetId: {s_id}"
            )
            phys_table = silver_datasets[s_id]
            assert phys_table in ddl_silver_map, (
                f"Physical Silver table not found in DDL: {phys_table}"
            )

        for s_id, cols in dep.input_silver_columns.items():
            assert s_id in dep.input_silver_datasets
            phys_table = silver_datasets[s_id]
            available_cols = set(ddl_silver_map[phys_table])
            for col in cols:
                assert col in available_cols, (
                    f"Gold contract {g_id} references column '{col}' missing from {phys_table}"
                )


def test_future_silver_ddl_addition_fails_manifest_validation() -> None:
    """Verify that any unmapped column in Silver DDL fails parity validation."""
    ddl_cols_map = _get_ddl_silver_columns()
    # Artificially inject an unmanifested column into a table's list
    ddl_cols_map["silver.d_Calendar"].append("New_Unclassified_Column")

    ddl_table_col_pairs = {
        (table.lower(), col) for table, cols in ddl_cols_map.items() for col in cols
    }
    manifest_table_col_pairs = {
        (entry.physical_table.lower(), entry.column_name) for entry in SILVER_COLUMN_DISPOSITIONS
    }

    missing_in_manifest = ddl_table_col_pairs - manifest_table_col_pairs
    assert "New_Unclassified_Column" in {col for _, col in missing_in_manifest}


def test_semantic_inventory_query_helpers() -> None:
    """Verify behavior of semantic query functions and error handling."""
    # Silver semantics lookup
    sem = get_silver_contract_semantics(DatasetId.COMMON_CALENDAR)
    assert sem.physical_table == "silver.d_Calendar"
    assert sem.identity_keys == ("Date",)

    with pytest.raises(KeyError, match="not a registered Silver contract"):
        get_silver_contract_semantics(DatasetId.TAX_YEAR_SUMMARY)

    # Silver column disposition lookup
    col_disp = get_silver_column_disposition(DatasetId.COMMON_CALENDAR, "Date")
    assert col_disp.classification == ColumnClassification.CANONICAL_IDENTITY
    assert col_disp.disposition == ColumnDisposition.RETAIN

    with pytest.raises(KeyError, match="Column 'Non_Existent' not found"):
        get_silver_column_disposition(DatasetId.COMMON_CALENDAR, "Non_Existent")

    # Gold dependency lookup
    gold_dep = get_gold_contract_dependency(DatasetId.TAX_YEAR_SUMMARY)
    assert gold_dep.producer == "TaxEngine"
    assert DatasetId.TAX_EVENTS in gold_dep.input_silver_datasets

    with pytest.raises(KeyError, match="not a registered Gold contract"):
        get_gold_contract_dependency(DatasetId.COMMON_CALENDAR)

    # Classification and disposition filtering
    ident_cols = get_columns_by_classification(ColumnClassification.CANONICAL_IDENTITY)
    assert len(ident_cols) > 0

    prov_cols = get_columns_by_classification(ColumnClassification.PROVENANCE_REFERENCE)
    assert len(prov_cols) > 0

    retain_cols = get_columns_by_disposition(ColumnDisposition.RETAIN)
    assert len(retain_cols) > 0

    remove_cols = get_columns_by_disposition(ColumnDisposition.REMOVE_AFTER_CONSUMER_MIGRATION)
    assert len(remove_cols) > 0
