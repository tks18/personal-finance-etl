"""Tests for Source and Canonical Bronze validation admission contracts (Phase 024).

Owns
----
- Exact legacy route verification and documentation against codebase anchors.
- Unit tests for source schema compiler (POLARS_TYPE_MAP, compile_source_schema).
- Unit tests for SourceDatasetConfig field declaration dict coercion and validation.
- Unit tests for Canonical Bronze schemas (CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA).
- In-memory dual-gate pipeline verification (Source Gate -> Admission -> Canonical Bronze Gate).
- Discriminating failure tests at Source (PRE_BRONZE) vs Canonical Bronze (CANONICAL_BRONZE).
- Identity uniqueness enforcement tests at CANONICAL_BRONZE stage.
- Empty-dataset semantics verification (absent vs configured-empty vs malformed).
"""

from __future__ import annotations

import dataclasses

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.model import (
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.canonical_fields import (
    CANONICAL_BRONZE_FIELDS,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.contracts.validation import (
    ValidationContext,
    ValidationError,
    ValidationResult,
    ValidationStage,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_category,
)
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA,
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.validation.compiler import (
    compile_source_schema,
)
from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    BronzeDataContract,
)


def _get_bronze_contract(dataset_id: DatasetId) -> BronzeDataContract:
    """Retrieve the authoritative BronzeDataContract for a dataset from the registry."""
    for c in BRONZE_CONTRACT_REGISTRY:
        if c.dataset_id == dataset_id:
            return c
    raise ValueError(f"No Bronze contract registered for {dataset_id}")


def _create_valid_raw_zcategory_df() -> pl.DataFrame:
    """Create a realistic valid raw source DataFrame matching SQLite ZCATEGORY evidence."""
    return pl.DataFrame(
        {
            "ID": [1, 2, 3],
            "C_IS_DEL": [0, 0, 0],
            "C_UTIME": [1700000000000, 1700000001000, 1700000002000],
            "uid": ["cat_food", "cat_salary", "cat_rent"],
            "NAME": ["Food & Dining", "Income from Salary", "Housing & Rent"],
            "ORDERSEQ": [10, 20, 30],
            "TYPE": [1, 0, 1],
            "STATUS": [0, 0, 0],
            "pUid": pl.Series([None, None, None], dtype=pl.String),
            "isSynced": [1, 1, 1],
            "syncTime": [1700000000000, 1700000001000, 1700000002000],
            "syncVersion": [1, 1, 1],
            "artifact_id": ["art_sqlite_001", "art_sqlite_001", "art_sqlite_001"],
            "__file_name__": ["SOURCE_DB.sqlite", "SOURCE_DB.sqlite", "SOURCE_DB.sqlite"],
            "__folder_path__": ["inputs", "inputs", "inputs"],
        },
        schema_overrides={"pUid": pl.String},
    )


def test_exact_legacy_route_documented() -> None:
    """Verify that the documented legacy route for HOUSEHOLD_ZCATEGORY matches codebase anchors.

    Exact route:
    discovery: pending_files['sqlite_source']
        -> category: 'zcategory'
        -> provider: SQLite (table ZCATEGORY)
        -> ExtractionResult.zcategory
        -> Bronze table: bronze.r_SQLite_ZCategory
        -> downstream consumer: transform_d_income_category in domain.household.transforms
    """
    # 1. ExtractionResult transport field exists on dataclass
    extraction_fields: set[str] = {f.name for f in dataclasses.fields(ExtractionResult)}
    assert "zcategory" in extraction_fields

    # 2. Bronze contract anchors
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert contract.sync_category == "sqlite_source"
    assert contract.extraction_attribute == "zcategory"
    assert contract.physical_table == "bronze.r_SQLite_ZCategory"
    assert contract.is_full_replace is True

    # 3. Baseline source configuration binding
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    assert ds_config.source_id == SourceId("household_db")
    assert isinstance(ds_config.selector, SqliteSelector)
    assert ds_config.selector.table_name == "ZCATEGORY"
    assert ds_config.selector.provider_type == ProviderType.SQLITE

    # 4. Downstream transformation consumer is callable
    assert callable(transform_d_income_category)


def test_compile_source_schema_from_config() -> None:
    """Verify compilation of SourceDatasetConfig with SourceFieldDeclaration into Pandera schema."""
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    assert len(ds_config.fields) == 12

    schema = compile_source_schema(ds_config)
    assert getattr(schema, "name", None) == "pre_bronze_household_zcategory"

    # Verify column presence, data types, nullability, and uniqueness
    cols = schema.columns
    assert "ID" in cols
    assert cols["ID"].dtype.type == pl.Int64
    assert cols["ID"].nullable is False
    assert cols["ID"].unique is True

    assert "uid" in cols
    assert cols["uid"].dtype.type == pl.String
    assert cols["uid"].nullable is False
    assert cols["uid"].unique is True

    assert "NAME" in cols
    assert cols["NAME"].dtype.type == pl.String
    assert cols["NAME"].nullable is False
    assert cols["NAME"].unique is False

    assert "TYPE" in cols
    assert cols["TYPE"].dtype.type == pl.Int64
    assert cols["TYPE"].nullable is False

    assert "pUid" in cols
    assert cols["pUid"].nullable is True


def test_source_schema_dict_coercion() -> None:
    """Verify that dict-based field declarations in SourceDatasetConfig are properly coerced."""
    dict_fields = {
        "ID": "Int64",
        "uid": {"data_type": "String", "nullable": False, "unique": True},
        "NAME": {"data_type": "String", "nullable": False},
        "notes": {"data_type": "String", "nullable": True, "description": "User notes"},
    }
    ds = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        fields=dict_fields,  # type: ignore[arg-type]
    )

    assert len(ds.fields) == 4
    id_field = next(f for f in ds.fields if f.name == "ID")
    assert id_field.data_type == "Int64"
    assert id_field.nullable is True

    uid_field = next(f for f in ds.fields if f.name == "uid")
    assert uid_field.nullable is False
    assert uid_field.unique is True

    notes_field = next(f for f in ds.fields if f.name == "notes")
    assert notes_field.description == "User notes"

    schema = compile_source_schema(ds)
    assert len(schema.columns) == 4


def test_source_schema_validation_errors() -> None:
    """Verify defensive errors during source contract compilation."""
    # 1. Empty fields error
    empty_ds = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        fields=[],
    )
    with pytest.raises(ValueError, match="config.fields is empty"):
        compile_source_schema(empty_ds)

    # 2. Unsupported data type error
    bad_type_ds = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        fields=[SourceFieldDeclaration(name="col_x", data_type="UnknownSpecialType")],
    )
    with pytest.raises(ValueError, match="Unsupported or unknown data type"):
        compile_source_schema(bad_type_ds)

    # 3. Duplicate field name error
    dup_ds = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        fields=[
            SourceFieldDeclaration(name="col_a", data_type="String"),
            SourceFieldDeclaration(name="col_a", data_type="Int64"),
        ],
    )
    with pytest.raises(ValueError, match="Duplicate source field declaration 'col_a'"):
        compile_source_schema(dup_ds)


def test_canonical_bronze_schema_independent_and_authoritative() -> None:
    """Verify that canonical Bronze schemas are authoritative, independent of user config."""
    assert has_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY) is True
    assert has_canonical_bronze_schema(DatasetId.INVESTMENT_MF_ORDERS) is False

    with pytest.raises(KeyError, match="No canonical Bronze validation schema registered"):
        get_canonical_bronze_schema(DatasetId.INVESTMENT_MF_ORDERS)

    schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert schema is CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA
    assert getattr(schema, "name", None) == "canonical_bronze_household_zcategory"

    # Verify all 13 canonical Bronze fields from contracts are covered
    expected_fields = CANONICAL_BRONZE_FIELDS[DatasetId.HOUSEHOLD_ZCATEGORY]
    for field_name in expected_fields:
        assert field_name in schema.columns, f"Missing canonical field: {field_name}"

    # Verify authoritative financial constraints
    assert schema.columns["UID"].nullable is False
    assert schema.columns["UID"].unique is True
    assert schema.columns["CATEGORY_NAME"].nullable is False
    assert schema.columns["TYPE"].nullable is False


def test_in_memory_happy_path_pipeline() -> None:
    """Verify complete in-memory pipeline: Source Gate -> Admission Normalization -> Canonical Bronze Gate."""
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)
    validator = PanderaDataFrameValidator()

    # 1. Source Admission Gate
    raw_df = _create_valid_raw_zcategory_df()
    source_schema = compile_source_schema(ds_config)
    source_ctx = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=ds_config.source_id,
        contract_id="pre_bronze_household_zcategory",
    )
    source_result = validator.validate(raw_df, source_schema, source_ctx)
    assert isinstance(source_result, ValidationResult)
    assert source_result.is_valid is True
    assert source_result.affected_row_count == 0

    # 2. Admission Normalization & Identity Resolution
    admission_service = AdmissionService()
    admission_plan = admission_service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=contract,
        available_source_columns=raw_df.columns,
    )
    admitted_lf = admission_service.execute_admission(admission_plan, raw_df)
    admitted_df = admitted_lf.collect()

    # 3. Canonical Bronze Admission Gate
    canonical_schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    canonical_ctx = ValidationContext(
        stage=ValidationStage.CANONICAL_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=ds_config.source_id,
        contract_id=contract.physical_table,
    )
    canonical_result = validator.validate(admitted_df, canonical_schema, canonical_ctx)
    assert isinstance(canonical_result, ValidationResult)
    assert canonical_result.is_valid is True
    assert canonical_result.affected_row_count == 0


def test_source_validation_catches_source_failures() -> None:
    """Verify that source-level structural defects fail at the PRE_BRONZE validation stage."""
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    source_schema = compile_source_schema(ds_config)
    validator = PanderaDataFrameValidator()
    ctx = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=ds_config.source_id,
    )

    # 1. Missing required column
    bad_df_missing = _create_valid_raw_zcategory_df().drop("uid")
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(bad_df_missing, source_schema, ctx)
    res = exc_info.value.result
    assert res.is_valid is False
    assert res.stage == ValidationStage.PRE_BRONZE
    assert any("column_in_dataframe" in f.check for f in res.failures)

    # 2. Null in non-nullable column
    bad_df_null = _create_valid_raw_zcategory_df().with_columns(
        pl.when(pl.col("uid") == "cat_salary").then(None).otherwise(pl.col("uid")).alias("uid")
    )
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(bad_df_null, source_schema, ctx)
    res = exc_info.value.result
    assert res.is_valid is False
    assert res.stage == ValidationStage.PRE_BRONZE
    assert res.remediation is not None
    assert "null" in res.remediation.lower()

    # 3. Wrong data type
    bad_df_type = _create_valid_raw_zcategory_df().with_columns(pl.lit("not_an_int").alias("ID"))
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(bad_df_type, source_schema, ctx)
    res = exc_info.value.result
    assert res.is_valid is False
    assert res.stage == ValidationStage.PRE_BRONZE


def test_canonical_bronze_validation_catches_canonical_failures() -> None:
    """Verify that canonical defects fail at the CANONICAL_BRONZE stage with appropriate remediation."""
    canonical_schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    validator = PanderaDataFrameValidator()
    ctx = ValidationContext(
        stage=ValidationStage.CANONICAL_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=SourceId("household_db"),
    )

    # DataFrame passing through normalization but containing a null in non-nullable CATEGORY_NAME
    raw_df = _create_valid_raw_zcategory_df()
    admission_service = AdmissionService()
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    plan = admission_service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=contract,
        available_source_columns=raw_df.columns,
    )
    admitted_df = admission_service.execute_admission(plan, raw_df).collect()

    bad_canonical_df = admitted_df.with_columns(
        pl.when(pl.col("CATEGORY_NAME") == "Income from Salary")
        .then(None)
        .otherwise(pl.col("CATEGORY_NAME"))
        .alias("CATEGORY_NAME")
    )

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(bad_canonical_df, canonical_schema, ctx)

    res = exc_info.value.result
    assert res.is_valid is False
    assert res.stage == ValidationStage.CANONICAL_BRONZE
    assert any(f.column == "CATEGORY_NAME" for f in res.failures)
    assert res.remediation is not None
    assert "CATEGORY_NAME" in res.remediation


def test_identity_uniqueness_enforced_at_canonical_bronze() -> None:
    """Verify that duplicate UID identities are rejected at CANONICAL_BRONZE."""
    canonical_schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    validator = PanderaDataFrameValidator()
    ctx = ValidationContext(
        stage=ValidationStage.CANONICAL_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=SourceId("household_db"),
    )

    raw_df = _create_valid_raw_zcategory_df()
    admission_service = AdmissionService()
    config = get_shan_baseline_source_configuration()
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    plan = admission_service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=contract,
        available_source_columns=raw_df.columns,
    )
    admitted_df = admission_service.execute_admission(plan, raw_df).collect()

    # Introduce duplicate UID
    duplicate_df = admitted_df.with_columns(pl.lit("cat_duplicate").alias("UID"))

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(duplicate_df, canonical_schema, ctx)

    res = exc_info.value.result
    assert res.is_valid is False
    assert res.stage == ValidationStage.CANONICAL_BRONZE
    assert any(f.check == "field_uniqueness" and f.column == "UID" for f in res.failures)
    assert res.remediation is not None
    assert "Deduplicate" in res.remediation


def test_empty_dataset_semantics() -> None:
    """Verify and freeze empty-dataset semantics for HOUSEHOLD_ZCATEGORY.

    Semantics:
    1. Dataset absent/unconfigured: get_dataset_binding returns None.
    2. Configured dataset with 0 rows (valid empty frame):
       - Preserves full column schema.
       - Passes Source Gate (PRE_BRONZE) with is_valid=True.
       - Successfully executes Admission Normalization.
       - Passes Canonical Bronze Gate (CANONICAL_BRONZE) with is_valid=True.
       - Must NOT be treated as missing or malformed.
    3. Configured dataset with malformed rows (e.g. wrong type):
       - Fails validation with ValidationError.
    """
    config = get_shan_baseline_source_configuration()
    validator = PanderaDataFrameValidator()

    # 1. Dataset absent / not configured
    assert config.get_dataset_binding("completely_unknown_dataset") is None

    # 2. Configured dataset with zero rows (valid empty dataset)
    ds_config = config.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_config is not None
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    raw_df = _create_valid_raw_zcategory_df()
    empty_raw_df = raw_df.clear()
    assert empty_raw_df.height == 0
    assert len(empty_raw_df.columns) == len(raw_df.columns)

    # Empty frame passes Source Gate
    source_schema = compile_source_schema(ds_config)
    source_ctx = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=ds_config.source_id,
    )
    source_res = validator.validate(empty_raw_df, source_schema, source_ctx)
    assert source_res.is_valid is True
    assert source_res.affected_row_count == 0

    # Admission Normalization preserves 0-row grain
    admission_service = AdmissionService()
    plan = admission_service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=contract,
        available_source_columns=empty_raw_df.columns,
    )
    empty_admitted_df = admission_service.execute_admission(plan, empty_raw_df).collect()
    assert empty_admitted_df.height == 0

    # Empty admitted frame passes Canonical Bronze Gate
    canonical_schema = get_canonical_bronze_schema(DatasetId.HOUSEHOLD_ZCATEGORY)
    canonical_ctx = ValidationContext(
        stage=ValidationStage.CANONICAL_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=ds_config.source_id,
    )
    canonical_res = validator.validate(empty_admitted_df, canonical_schema, canonical_ctx)
    assert canonical_res.is_valid is True
    assert canonical_res.affected_row_count == 0

    # 3. Malformed frame (wrong type) fails even with 1 row
    malformed_df = pl.DataFrame(
        {
            "ID": ["string_instead_of_int"],
            "C_IS_DEL": [0],
            "C_UTIME": [1700000000000],
            "uid": ["cat_test"],
            "NAME": ["Test"],
            "ORDERSEQ": [1],
            "TYPE": [1],
            "STATUS": [0],
            "pUid": pl.Series([None], dtype=pl.String),
            "isSynced": [1],
            "syncTime": [1700000000000],
            "syncVersion": [1],
        },
        schema_overrides={"pUid": pl.String},
    )
    with pytest.raises(ValidationError):
        validator.validate(malformed_df, source_schema, source_ctx)
