"""Tests for AdmissionService and AdmissionPlan.

Verifies end-to-end Pre-Bronze admission coordinating column normalization,
provenance preservation, and deterministic row identity resolution.
"""

from __future__ import annotations

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.admission import (
    AdmissionPlan,
    AdmissionService,
)
from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionError,
    MissingIdentityFieldError,
)
from personal_finance_etl.config.sources.identity import (
    CompositeIdentity,
    DerivedDeterministicIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector, SqliteSelector
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    BronzeDataContract,
)


def _get_bronze_contract(dataset_id: DatasetId) -> BronzeDataContract:
    """Retrieve the authoritative BronzeDataContract for a dataset."""
    for c in BRONZE_CONTRACT_REGISTRY:
        if c.dataset_id == dataset_id:
            return c
    raise ValueError(f"No Bronze contract registered for {dataset_id}")


def test_admission_compile_and_execute_household_sqlite() -> None:
    """Verify full admission execution on a production household SQLite dataset."""
    config = get_shan_baseline_source_configuration()
    ds_config = next(d for d in config.datasets if d.dataset_id == DatasetId.HOUSEHOLD_ASSET_GROUP)
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ASSET_GROUP)

    service = AdmissionService()
    raw_columns = [
        "DEVICE_ID",
        "uid",
        "IS_DEL",
        "USETIME",
        "ACC_GROUP_NAME",
        "TYPE",
        "ORDERSEQ",
        "isSynced",
        "syncTime",
        "syncVersion",
    ]

    plan = service.compile_admission_plan(
        dataset_config=ds_config,
        bronze_contract=contract,
        available_source_columns=raw_columns,
    )

    assert isinstance(plan, AdmissionPlan)
    assert plan.dataset_id == DatasetId.HOUSEHOLD_ASSET_GROUP
    assert plan.source_id == SourceId("household_db")
    assert plan.id_column == "UID"

    # Input source frame
    input_df = pl.DataFrame(
        {
            "DEVICE_ID": ["dev-1", "dev-2"],
            "uid": ["asset-grp-001", "asset-grp-002"],
            "IS_DEL": ["0", "0"],
            "USETIME": ["2024-01-01", "2024-01-02"],
            "ACC_GROUP_NAME": ["Bank Accounts", "Investments"],
            "TYPE": ["1", "2"],
            "ORDERSEQ": ["10", "20"],
            "isSynced": ["1", "1"],
            "syncTime": ["2024-01-01 10:00:00", "2024-01-02 10:00:00"],
            "syncVersion": ["1", "1"],
        }
    )

    result_lf = service.execute_admission(plan, input_df)
    result_df = result_lf.collect()

    # Mapped canonical column names should be present
    assert "UID" in result_df.columns
    assert "ASSET_GROUP" in result_df.columns
    assert "ORDER_SEQUENCE" in result_df.columns

    # UID values must be preserved exactly
    assert result_df["UID"].to_list() == ["asset-grp-001", "asset-grp-002"]
    assert result_df["ASSET_GROUP"].to_list() == ["Bank Accounts", "Investments"]


def test_trusted_sqlite_id_preservation() -> None:
    """Assert that source SQLite primary keys (uid / Z_PK) flow through without hashing."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        identity=SourceFieldIdentity(field="UID"),
        mapping=[
            ColumnMapping(source_field="uid", canonical_field="UID"),
            ColumnMapping(source_field="NAME", canonical_field="CATEGORY_NAME"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)

    source_data = pl.DataFrame(
        {
            "uid": ["42", "999", "custom-sqlite-uuid-abc-123"],
            "NAME": ["Groceries", "Utilities", "Dining"],
        }
    )

    admitted_df = service.execute_admission(plan, source_data).collect()
    assert admitted_df["UID"].to_list() == ["42", "999", "custom-sqlite-uuid-abc-123"]
    assert admitted_df["CATEGORY_NAME"].to_list() == ["Groceries", "Utilities", "Dining"]


def test_admission_with_derived_deterministic_identity() -> None:
    """Verify deterministic SHA-256 identity derivation for datasets without source UIDs."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("benchmark_mapping_csv"),
        dataset_id=DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        selector=CsvSelector(),
        identity=DerivedDeterministicIdentity(
            fields=["Sector", "Industry"],
            namespace="TEST_BENCHMARK",
        ),
        mapping=[
            ColumnMapping(source_field="Sector", canonical_field="Sector"),
            ColumnMapping(source_field="Industry", canonical_field="Industry"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.INVESTMENT_BENCHMARK_MAPPING)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)

    source_data = pl.DataFrame(
        {
            "Sector": ["Consumer Discretionary", "Financial Services"],
            "Industry": ["Media & Entertainment", "Banks"],
        }
    )

    admitted_df = service.execute_admission(plan, source_data).collect()
    assert "UID" in admitted_df.columns

    expected_id1 = generate_deterministic_id(
        "TEST_BENCHMARK",
        {"Sector": "Consumer Discretionary", "Industry": "Media & Entertainment"},
    )
    expected_id2 = generate_deterministic_id(
        "TEST_BENCHMARK",
        {"Sector": "Financial Services", "Industry": "Banks"},
    )

    assert admitted_df["UID"].to_list() == [expected_id1, expected_id2]


def test_admission_with_composite_identity() -> None:
    """Verify composite natural key formatting during admission."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("column_master_csv"),
        dataset_id=DatasetId.COMMON_COLUMN_MASTER,
        selector=CsvSelector(),
        identity=CompositeIdentity(fields=["TABLE_NAME", "OLD_COLUMN"]),
        mapping=[
            ColumnMapping(source_field="TABLE_NAME", canonical_field="TABLE_NAME"),
            ColumnMapping(source_field="OLD_COLUMN", canonical_field="OLD_COLUMN"),
            ColumnMapping(source_field="NEW_COLUMN", canonical_field="NEW_COLUMN"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.COMMON_COLUMN_MASTER)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)

    source_data = pl.DataFrame(
        {
            "TABLE_NAME": ["CATEGORY", "ASSETS"],
            "OLD_COLUMN": ["ID", "NIC_NAME"],
            "NEW_COLUMN": ["S_NO", "ASSET_NAME"],
        }
    )

    admitted_df = service.execute_admission(plan, source_data).collect()
    assert admitted_df["UID"].to_list() == ["CATEGORY:ID", "ASSETS:NIC_NAME"]


def test_admission_macro_parameters_fy_identity() -> None:
    """Verify that macro parameters uses FY as trusted source identity."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("macro_parameters_csv"),
        dataset_id=DatasetId.INVESTMENT_MACRO_PARAMETERS,
        selector=CsvSelector(),
        identity=SourceFieldIdentity(field="FY"),
        mapping=[
            ColumnMapping(source_field="FY", canonical_field="FY"),
            ColumnMapping(source_field="Inflation_Rate", canonical_field="Inflation_Rate"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.INVESTMENT_MACRO_PARAMETERS)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)

    source_data = pl.DataFrame(
        {
            "FY": ["2023-24", "2024-25"],
            "Inflation_Rate": ["0.068", "0.062"],
        }
    )

    admitted_df = service.execute_admission(plan, source_data).collect()
    assert admitted_df["UID"].to_list() == ["2023-24", "2024-25"]


def test_admission_duplicate_collision_raises_error() -> None:
    """Assert that duplicate identity keys raise IdentityCollisionError with diagnostic details."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        identity=SourceFieldIdentity(field="UID"),
        mapping=[
            ColumnMapping(source_field="uid", canonical_field="UID"),
            ColumnMapping(source_field="NAME", canonical_field="CATEGORY_NAME"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)

    duplicate_data = pl.DataFrame(
        {
            "uid": ["dup-01", "dup-01", "unique-02"],
            "NAME": ["Category A", "Category B", "Category C"],
        }
    )

    with pytest.raises(IdentityCollisionError) as exc_info:
        service.execute_admission(plan, duplicate_data)

    diag = exc_info.value.diagnostic
    assert diag.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert diag.duplicate_count == 2
    assert diag.sample_duplicates == [("dup-01", 2)]


def test_admission_missing_identity_field_raises_error() -> None:
    """Assert that identity strategy referencing non-existent field fails at compilation time."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        identity=SourceFieldIdentity(field="NON_EXISTENT_FIELD"),
        mapping=[
            ColumnMapping(source_field="uid", canonical_field="UID"),
            ColumnMapping(source_field="NAME", canonical_field="CATEGORY_NAME"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.HOUSEHOLD_ZCATEGORY)

    service = AdmissionService()
    with pytest.raises(MissingIdentityFieldError) as exc_info:
        service.compile_admission_plan(ds_config, contract)

    assert "NON_EXISTENT_FIELD" in str(exc_info.value)


def test_admission_unconstrained_dataset_without_identity() -> None:
    """Verify transparent pass-through for datasets with IdentityRequirement.NONE and no identity."""
    contract = BronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        extraction_attribute="stock_orders",
        sync_category="orders",
        physical_table="bronze.orders",
        is_full_replace=False,
        identity_requirement=IdentityRequirement.NONE,
        grain="Order Execution",
    )
    ds_config = SourceDatasetConfig(
        source_id=SourceId("stock_orders_excel"),
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        selector=CsvSelector(),
        mapping=[
            ColumnMapping(source_field="Order No", canonical_field="Order No"),
            ColumnMapping(source_field="Symbol", canonical_field="Symbol"),
        ],
    )

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract)
    assert plan.identity_plan.strategy is None

    input_df = pl.DataFrame({"Order No": ["101", "102"], "Symbol": ["RELIANCE", "INFY"]})
    admitted_df = service.execute_admission(plan, input_df).collect()

    assert admitted_df.columns == ["Order No", "Symbol"]
    assert len(admitted_df) == 2


def test_custom_id_column_name() -> None:
    """Verify configuring custom identity column name during admission."""
    ds_config = SourceDatasetConfig(
        source_id=SourceId("column_master_csv"),
        dataset_id=DatasetId.COMMON_COLUMN_MASTER,
        selector=CsvSelector(),
        identity=CompositeIdentity(fields=["TABLE_NAME", "OLD_COLUMN"]),
        mapping=[
            ColumnMapping(source_field="TABLE_NAME", canonical_field="TABLE_NAME"),
            ColumnMapping(source_field="OLD_COLUMN", canonical_field="OLD_COLUMN"),
        ],
    )
    contract = _get_bronze_contract(DatasetId.COMMON_COLUMN_MASTER)

    service = AdmissionService()
    plan = service.compile_admission_plan(ds_config, contract, id_column="__pk__")
    assert plan.id_column == "__pk__"

    source_data = pl.DataFrame(
        {
            "TABLE_NAME": ["CURRENCY"],
            "OLD_COLUMN": ["ISO"],
        }
    )

    admitted_df = service.execute_admission(plan, source_data).collect()
    assert "__pk__" in admitted_df.columns
    assert admitted_df["__pk__"].to_list() == ["CURRENCY:ISO"]
