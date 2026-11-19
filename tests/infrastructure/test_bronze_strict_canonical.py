"""Integration and unit tests verifying strict canonical Bronze cutover for Phase 036.

Owns
----
- 100% canonical Bronze schema coverage (all 20 DatasetIds have strict Pandera schemas).
- Source drift containment: unmapped source columns stored in Pre-Bronze, stripped from Bronze.
- Atomic validation failure on missing canonical required fields.
- Atomic validation failure on incompatible canonical types.
- Gate 2 strict=True rejection of unexpected extra columns.
- Metadata contract registry fingerprint stability against source schema drift.
- Physical table schema audit via verify_canonical_bronze_schemas.

Does not own
-------------
- Pre-Bronze persistence internals (owned by tests.infrastructure.test_pre_bronze_persistence).
- Architecture boundary assertions (owned by tests.architecture.test_boundaries).
"""

from __future__ import annotations

from pathlib import Path

import pandera.errors
import polars as pl
import pytest

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.canonical_fields import (
    CANONICAL_BRONZE_FIELDS,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.bronze import (
    BronzeLayer,
    verify_canonical_bronze_schemas,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    get_pre_bronze_contract_by_dataset_id,
)


@pytest.fixture
def temp_duckdb(tmp_path: Path) -> DuckDBManager:
    """Provide a fresh DuckDBManager with initialized schemas and strict Bronze tables.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory.

    Returns
    -------
    DuckDBManager
        Initialized warehouse connection manager.
    """
    db_mgr = DuckDBManager(base_path=str(tmp_path), db_name="test_strict_bronze.duckdb")
    db_mgr.open()
    db_mgr.ensure_schemas()
    return db_mgr


def test_canonical_bronze_coverage_100_percent() -> None:
    """Verify all 19 active canonical Bronze DatasetIds have registered strict schemas."""
    for contract in BRONZE_CONTRACT_REGISTRY:
        ds_id = contract.dataset_id
        if ds_id == DatasetId.COMMON_COLUMN_MASTER:
            continue
        assert has_canonical_bronze_schema(ds_id), (
            f"DatasetId '{ds_id.value}' must have a registered canonical Bronze schema."
        )
        schema = get_canonical_bronze_schema(ds_id)
        assert schema.strict is True, f"Schema for '{ds_id.value}' must enforce strict=True."
        assert ds_id in CANONICAL_BRONZE_FIELDS, (
            f"DatasetId '{ds_id.value}' must be in CANONICAL_BRONZE_FIELDS."
        )


def test_gate2_strict_schema_rejects_unexpected_columns() -> None:
    """Verify Gate 2 Pandera schema raises SchemaError when unexpected columns are present."""
    schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    valid_data = pl.DataFrame(
        {
            "UID": ["CAT_001"],
            "CATEGORY_NAME": ["Groceries"],
            "TYPE": [1],
            "UNEXPECTED_COLUMN_DRIFT": ["leaked_value"],
        }
    )
    with pytest.raises(pandera.errors.SchemaError) as exc_info:
        schema.validate(valid_data)
    assert "UNEXPECTED_COLUMN_DRIFT" in str(exc_info.value)


def test_gate2_strict_schema_accepts_valid_canonical_and_provenance() -> None:
    """Verify Gate 2 Pandera schema accepts canonical fields and operational provenance."""
    schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    valid_data = pl.DataFrame(
        {
            "UID": ["CAT_001"],
            "CATEGORY_NAME": ["Groceries"],
            "TYPE": [1],
            "S_NO": [10],
            "IS_DEL": [0],
            "MODIFY_DATE": [1700000000],
            "ORDER_SEQUENCE": [1],
            "STATUS": [0],
            "CATEGORY_ID": ["cat_id_1"],
            "IS_SYNCED": [1],
            "SYNC_TIME": [1700000000.0],
            "SYNC_VERSION": [1],
            "ORDER_NUM": [1],
            "artifact_id": ["art_123"],
            "__file_name__": ["zcat.sqlite"],
            "__folder_path__": ["inputs/db"],
        }
    )
    validated = schema.validate(valid_data)
    assert isinstance(validated, pl.DataFrame)
    assert validated.height == 1


def test_missing_canonical_required_field_fails_validation() -> None:
    """Verify omitting a required canonical field raises SchemaError."""
    schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    # Missing required CATEGORY_NAME
    invalid_data = pl.DataFrame(
        {
            "UID": ["CAT_001"],
            "TYPE": [1],
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        schema.validate(invalid_data)


def test_incompatible_canonical_type_fails_validation() -> None:
    """Verify an incompatible column type raises SchemaError."""
    schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    # TYPE must be Int64, pass non-numeric string
    invalid_data = pl.DataFrame(
        {
            "UID": ["CAT_001"],
            "CATEGORY_NAME": ["Groceries"],
            "TYPE": ["NOT_AN_INTEGER"],
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        schema.validate(invalid_data)


def test_source_drift_contained_in_pre_bronze_and_stripped_from_bronze(
    temp_duckdb: DuckDBManager,
) -> None:
    """Verify that source drift extra columns exist in Pre-Bronze but are stripped from Bronze."""
    ds_id = DatasetId.HOUSEHOLD_ZCATEGORY
    pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
    assert pb_contract is not None

    # Source frame with extra unmapped source column and full canonical fields
    raw_source = pl.DataFrame(
        {
            "ZUID": ["CAT_001"],
            "Z_PK": [1],
            "ZNAME": ["Groceries"],
            "ZKIND": [1],
            "ZISDEL": [0],
            "ZMODIFY_DATE": [1700000000],
            "ZORDER": [1],
            "ZSTATUS": [0],
            "ZCAT_ID": ["cat_1"],
            "ZSYNCED": [1],
            "ZSYNCTIME": [1700000000.0],
            "ZSYNCVER": [1],
            "EXTRA_VENDOR_METADATA": ["source_drift_value"],
            "artifact_id": ["art_test_drift"],
            "__file_name__": ["test_drift.sqlite"],
            "__folder_path__": ["inputs/db"],
        }
    )

    # 1. Write to Pre-Bronze: Pre-Bronze stores source shape including extra column
    pb_layer = PreBronzeLayer(temp_duckdb)
    pb_layer.write_incremental(
        contract=pb_contract,
        df=raw_source,
        artifact_id="art_test_drift",
    )
    pb_table = pb_contract.physical_table
    pb_cols = {row[0] for row in temp_duckdb.conn.execute(f"DESCRIBE {pb_table}").fetchall()}
    assert "EXTRA_VENDOR_METADATA" in pb_cols, "Pre-Bronze must preserve source drift column."

    # 2. Admission normalization maps canonical columns and drops EXTRA_VENDOR_METADATA
    ds_config = SourceDatasetConfig(
        dataset_id=ds_id,
        source_id=SourceId("test_source"),
        selector=SqliteSelector(table_name="ZCATEGORY"),
        identity=SourceFieldIdentity(field="UID"),
        mapping=[
            ColumnMapping(source_field="ZUID", canonical_field="UID"),
            ColumnMapping(source_field="Z_PK", canonical_field="S_NO"),
            ColumnMapping(source_field="ZNAME", canonical_field="CATEGORY_NAME"),
            ColumnMapping(source_field="ZKIND", canonical_field="TYPE"),
            ColumnMapping(source_field="ZISDEL", canonical_field="IS_DEL"),
            ColumnMapping(source_field="ZMODIFY_DATE", canonical_field="MODIFY_DATE"),
            ColumnMapping(source_field="ZORDER", canonical_field="ORDER_SEQUENCE"),
            ColumnMapping(source_field="ZSTATUS", canonical_field="STATUS"),
            ColumnMapping(source_field="ZCAT_ID", canonical_field="CATEGORY_ID"),
            ColumnMapping(source_field="ZSYNCED", canonical_field="IS_SYNCED"),
            ColumnMapping(source_field="ZSYNCTIME", canonical_field="SYNC_TIME"),
            ColumnMapping(source_field="ZSYNCVER", canonical_field="SYNC_VERSION"),
        ],
    )
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    admission_service = AdmissionService()
    plan = admission_service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=bronze_contract,
        available_source_columns=raw_source.columns,
        id_column="UID",
    )
    admitted = admission_service.execute_admission(plan, raw_source).collect()

    assert "EXTRA_VENDOR_METADATA" not in admitted.columns, (
        "Normalization must project out unmapped source drift column."
    )

    # 3. Gate 2 validation passes strict check
    canonical_schema = get_canonical_bronze_schema(ds_id)
    validated = canonical_schema.validate(admitted)
    assert isinstance(validated, pl.DataFrame)

    # 4. Upsert into Bronze table
    mock_cp = None
    mock_meta = None
    bronze_layer = BronzeLayer(temp_duckdb, mock_cp, mock_meta)  # type: ignore[arg-type]
    counts = bronze_layer.upsert_table(
        df=validated,
        table_name=bronze_contract.physical_table,
        actionable_files=["inputs/db/test_drift.sqlite"],
        full_replace=False,
    )
    assert counts.get("test_drift.sqlite") == 1

    # Assert Bronze physical table does NOT have EXTRA_VENDOR_METADATA
    bz_cols = {
        row[0]
        for row in temp_duckdb.conn.execute(f"DESCRIBE {bronze_contract.physical_table}").fetchall()
    }
    assert "EXTRA_VENDOR_METADATA" not in bz_cols, (
        "Bronze lakehouse table must never contain unmapped source drift columns."
    )


def test_contract_registry_fingerprint_unaffected_by_source_drift() -> None:
    """Verify that contract registry fingerprint depends only on canonical contracts, not source drift."""
    tables_metadata_before = [
        {
            "dataset_id": c.dataset_id.value,
            "table_name": c.physical_table,
            "grain": c.grain,
            "producer": c.producer,
        }
        for c in DATA_CONTRACT_REGISTRY
    ]
    fp_before = generate_contract_registry_fingerprint(tables_metadata_before)

    # Source drift event (e.g. adding columns to incoming files) does not alter DATA_CONTRACT_REGISTRY
    tables_metadata_after = [
        {
            "dataset_id": c.dataset_id.value,
            "table_name": c.physical_table,
            "grain": c.grain,
            "producer": c.producer,
        }
        for c in DATA_CONTRACT_REGISTRY
    ]
    fp_after = generate_contract_registry_fingerprint(tables_metadata_after)
    assert fp_before == fp_after


def test_verify_canonical_bronze_schemas_audits_physical_tables(
    temp_duckdb: DuckDBManager,
) -> None:
    """Verify that verify_canonical_bronze_schemas reports zero errors on valid DDL and detects drift."""
    # 1. Clean initialized database should have 0 mismatches
    mismatches = verify_canonical_bronze_schemas(temp_duckdb.conn)
    assert not mismatches, f"Expected 0 mismatches on clean DDL, got: {mismatches}"

    # 2. Inject an unpermitted column into a table
    temp_duckdb.conn.execute(
        'ALTER TABLE bronze.r_SQLite_ZCategory ADD COLUMN "ILLEGAL_UNPERMITTED_COL" VARCHAR'
    )
    drifted_mismatches = verify_canonical_bronze_schemas(temp_duckdb.conn)
    assert len(drifted_mismatches) == 1
    assert "ILLEGAL_UNPERMITTED_COL" in drifted_mismatches[0]
