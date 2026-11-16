# pyright: reportPrivateUsage=false
"""Verification suite for Phase 029: Household Transaction Evidence and No-UID Identity Proof.

Owns
----
- Shan production UID preservation proof (Z_PK and natural UID strings remain unmodified).
- External CSV statement ingestion without native source UID columns.
- Deterministic identity derivation (DerivedDeterministicIdentity) order invariance.
- Duplicate identity key collision detection atomicity (zero warehouse mutations).
- Downstream domain transformation equivalence (pure financial logic accepts external evidence).
- Household opening balances generalized vertical slice cutover verification.

Does not own
-------------
- Pre-Bronze self-healing and recovery algorithms (owned by test_pre_bronze_operational.py).
- Downstream tax and FIFO calculations (owned by test_tax_domain.py).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionError,
)
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    DatasetPlan,
    SourcePlanner,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import FileHashPolicy, Settings
from personal_finance_etl.config.sources import (
    SourceConfig,
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
from personal_finance_etl.config.sources.change_detection import (
    resolve_change_detection_policy,
)
from personal_finance_etl.config.sources.identity import (
    DerivedDeterministicIdentity,
)
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.datasets import DatasetId, DatasetOrigin
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.household.transforms.transactions import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized.

    Parameters
    ----------
    isolated_control_plane : ControlPlane
        Isolated Control Plane fixture.

    Yields
    ------
    None
    """
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def _create_sqlite_db_with_inoutcome(db_path: Path) -> Path:
    """Create an isolated test SQLite database containing the INOUTCOME table.

    Parameters
    ----------
    db_path : Path
        Filesystem destination for SQLite database file.

    Returns
    -------
    Path
        Created database path.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE INOUTCOME (
                AID INTEGER PRIMARY KEY,
                uid TEXT UNIQUE NOT NULL,
                assetUid TEXT NOT NULL,
                CARDDIVIDMONTH TEXT,
                ctgUid TEXT,
                toAssetUid TEXT,
                ZCONTENT TEXT,
                ZDATE TEXT NOT NULL,
                WDATE TEXT,
                wtime TEXT,
                paid TEXT,
                DO_TYPE TEXT NOT NULL,
                ZMONEY TEXT NOT NULL,
                txUidTrans TEXT,
                ZDATA TEXT,
                SMS_RDATE TEXT,
                IN_ZMONEY TEXT,
                ASSET_NIC TEXT,
                CATEGORY_NAME TEXT,
                cardDivideUid TEXT,
                CARD_DIVIDE_MONTH_STR TEXT,
                MARK INTEGER,
                txUidFee TEXT,
                SMS_ORIGIN TEXT,
                SMS_PARSE_CONTENT TEXT,
                IS_DEL INTEGER,
                UTIME INTEGER,
                currencyUid TEXT,
                AMOUNT_ACCOUNT REAL,
                lat REAL,
                lng REAL,
                gstd TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO INOUTCOME (
                AID, uid, assetUid, CARDDIVIDMONTH, ctgUid, toAssetUid, ZCONTENT,
                ZDATE, WDATE, wtime, paid, DO_TYPE, ZMONEY, txUidTrans, ZDATA,
                SMS_RDATE, IN_ZMONEY, ASSET_NIC, CATEGORY_NAME, cardDivideUid,
                CARD_DIVIDE_MONTH_STR, MARK, txUidFee, SMS_ORIGIN, SMS_PARSE_CONTENT,
                IS_DEL, UTIME, currencyUid, AMOUNT_ACCOUNT, lat, lng, gstd,
                isSynced, syncTime, syncVersion
            ) VALUES (
                1, 'TX_001', 'ASSET_HDFC', '0', 'CAT_INCOME_SALARY', NULL, 'Monthly Salary',
                '1700000000', '2023-11-15', '10:00:00', '1', '0', '50000.0', NULL, 'Memo',
                '2023-11-15', '50000.0', 'HDFC Salary', 'Income from Salary', NULL,
                NULL, 0, NULL, 'HDFCBK', 'salary credited',
                0, 1700000000, 'CURR_INR', 50000.0, 0.0, 0.0, 'IN',
                1, 1700000000.0, 1
            )
            """
        )
        conn.execute(
            """
            INSERT INTO INOUTCOME (
                AID, uid, assetUid, CARDDIVIDMONTH, ctgUid, toAssetUid, ZCONTENT,
                ZDATE, WDATE, wtime, paid, DO_TYPE, ZMONEY, txUidTrans, ZDATA,
                SMS_RDATE, IN_ZMONEY, ASSET_NIC, CATEGORY_NAME, cardDivideUid,
                CARD_DIVIDE_MONTH_STR, MARK, txUidFee, SMS_ORIGIN, SMS_PARSE_CONTENT,
                IS_DEL, UTIME, currencyUid, AMOUNT_ACCOUNT, lat, lng, gstd,
                isSynced, syncTime, syncVersion
            ) VALUES (
                2, 'TX_002', 'ASSET_HDFC', '0', 'CAT_EXPENSE_FOOD', NULL, 'Dinner',
                '1700000100', '2023-11-15', '20:00:00', '1', '1', '1500.0', NULL, 'Restaurant',
                '2023-11-15', '1500.0', 'HDFC Salary', 'Food & Groceries', NULL,
                NULL, 0, NULL, 'HDFCBK', 'spent 1500',
                0, 1700000100, 'CURR_INR', -1500.0, 0.0, 0.0, 'IN',
                1, 1700000100.0, 1
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    return db_path


def _create_opening_balances_csv(csv_path: Path) -> Path:
    """Create an isolated test opening balances CSV file with 53 canonical columns.

    Parameters
    ----------
    csv_path : Path
        Filesystem destination for opening balances CSV.

    Returns
    -------
    Path
        Created CSV path.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "Z_PK,Z_ENT,Z_OPT,ZASSET_GROUP,ZASSET_ID,ZCATEGORY_ID,ZOPPOSITEAID,ZAID,"
        "ZCATEGORYID,ZCURRENCYID,ZFEE_ID,ZISDEL,ZISSYNCED,ZMARK,ZSYNCCHECK,ZSYNCVERSION,"
        "ZUTIME,ZDATE,ZAMOUNT,ZAMOUNTACCOUNT,ZAMOUNTSUB,ZSYNCTIME,ZASSET_NAME,ZASSET_NIC,"
        "ZCARDDIVIDID,ZCATEGORY_NAME,ZCONTENT,ZDO_TYPE,ZMONEY,ZASSETUID,ZCARDDIVIDEMONTH,"
        "ZCARDDIVIDEMONTHSTR,ZCARDDIVIDEUID,ZCARDTIMESTAMPSTR,ZCATEGORYUID,ZCURRENCY,"
        "ZCURRENCYUID,ZGSTD,ZLAT,ZLNG,ZMEMO,ZPAID,ZSMSORIGINE,ZSMSPARSECONTENTS,ZSMSRDATE,"
        "ZTOASSETUID,ZTXDATESTR,ZTXUIDFEE,ZTXUIDTRANS,ZUID,ZWTIME,ZZDATA1,ZZDATA2\n"
    )
    row_1 = (
        "1,1,1,1,1,1,0,1,1,1,0,0,1,0,0,1,1672531200,1672531200,100000.0,100000.0,0.0,"
        "1672531200.0,Savings Account,HDFC Savings,0,Opening Balance,Initial Corpus,0,100000.0,"
        "ASSET_HDFC,0,0,0,0,0,INR,CURR_INR,0,0.0,0.0,Initial deposit,1,0,0,0,0,"
        "2023-01-01 00:00:00,0,0,OP_001,00:00:00,0,0\n"
    )
    row_2 = (
        "2,1,1,1,2,1,0,2,1,1,0,0,1,0,0,1,1672531200,1672531200,25000.0,25000.0,0.0,"
        "1672531200.0,Wallet Cash,Physical Cash,0,Opening Balance,Cash in Hand,0,25000.0,"
        "ASSET_CASH,0,0,0,0,0,INR,CURR_INR,0,0.0,0.0,Cash reserve,1,0,0,0,0,"
        "2023-01-01 00:00:00,0,0,OP_002,00:00:00,0,0\n"
    )
    csv_path.write_text(header + row_1 + row_2, encoding="utf-8")
    return csv_path


def _build_external_csv_statement_bytes(
    rows: list[dict[str, str]],
) -> bytes:
    """Serialize a list of external statement row dictionaries into in-memory CSV bytes.

    Parameters
    ----------
    rows : list[dict[str, str]]
        List of row dicts matching external CSV header schema.

    Returns
    -------
    bytes
        UTF-8 encoded CSV bytes.
    """
    fieldnames = [
        "TxDate",
        "AccountName",
        "PayeeDescription",
        "TransactionAmount",
        "CategoryName",
        "TransactionType",
        "AssetId",
        "CategoryId",
        "Timestamp",
        "IsDel",
        "LocalAmount",
        "AmountAccount",
        "CurrencyId",
        "ToAssetId",
        "TransferUid",
        "Time",
    ]
    lines = [",".join(fieldnames)]
    for r in rows:
        r_with_del = dict(r)
        if "IsDel" not in r_with_del:
            r_with_del["IsDel"] = "0"
        if "LocalAmount" not in r_with_del:
            r_with_del["LocalAmount"] = r_with_del.get("TransactionAmount", "0.0")
        if "AmountAccount" not in r_with_del:
            r_with_del["AmountAccount"] = r_with_del.get("TransactionAmount", "0.0")
        if "CurrencyId" not in r_with_del:
            r_with_del["CurrencyId"] = "CURR_INR"
        if "ToAssetId" not in r_with_del:
            r_with_del["ToAssetId"] = ""
        if "TransferUid" not in r_with_del:
            r_with_del["TransferUid"] = ""
        if "Time" not in r_with_del:
            r_with_del["Time"] = "10:00:00"
        lines.append(",".join(str(r_with_del.get(f, "")) for f in fieldnames))
    return "\n".join(lines).encode("utf-8")


def _get_external_statement_config() -> SourceDatasetConfig:
    """Construct a declarative SourceDatasetConfig for external statements without source UIDs.

    Returns
    -------
    SourceDatasetConfig
        Configured binding with DerivedDeterministicIdentity strategy.
    """
    mapping = [
        ColumnMapping(source_field="TxDate", canonical_field="DATE"),
        ColumnMapping(source_field="AccountName", canonical_field="ASSET_NAME"),
        ColumnMapping(source_field="PayeeDescription", canonical_field="DESCRIPTION"),
        ColumnMapping(source_field="TransactionAmount", canonical_field="BASE_AMOUNT"),
        ColumnMapping(source_field="CategoryName", canonical_field="CATEGORY_NAME"),
        ColumnMapping(source_field="TransactionType", canonical_field="TRANSACTION_TYPE"),
        ColumnMapping(source_field="AssetId", canonical_field="ASSET_ID"),
        ColumnMapping(source_field="CategoryId", canonical_field="CATEGORY_ID"),
        ColumnMapping(source_field="Timestamp", canonical_field="TIMESTAMP"),
        ColumnMapping(source_field="IsDel", canonical_field="IS_DEL"),
        ColumnMapping(source_field="LocalAmount", canonical_field="LOCAL_AMOUNT"),
        ColumnMapping(source_field="AmountAccount", canonical_field="AMOUNT_ACCOUNT"),
        ColumnMapping(source_field="CurrencyId", canonical_field="CURRENCY_ID"),
        ColumnMapping(source_field="ToAssetId", canonical_field="TO_ASSET_ID"),
        ColumnMapping(source_field="TransferUid", canonical_field="TRANSFER_UID"),
        ColumnMapping(source_field="Time", canonical_field="TIME"),
    ]
    fields = [
        SourceFieldDeclaration(name="TxDate", data_type="String", nullable=False),
        SourceFieldDeclaration(name="AccountName", data_type="String", nullable=False),
        SourceFieldDeclaration(name="PayeeDescription", data_type="String", nullable=False),
        SourceFieldDeclaration(name="TransactionAmount", data_type="String", nullable=False),
        SourceFieldDeclaration(name="CategoryName", data_type="String", nullable=True),
        SourceFieldDeclaration(name="TransactionType", data_type="String", nullable=False),
        SourceFieldDeclaration(name="AssetId", data_type="String", nullable=False),
        SourceFieldDeclaration(name="CategoryId", data_type="String", nullable=True),
        SourceFieldDeclaration(name="Timestamp", data_type="String", nullable=False),
        SourceFieldDeclaration(name="IsDel", data_type="Int64", nullable=True),
        SourceFieldDeclaration(name="LocalAmount", data_type="String", nullable=True),
        SourceFieldDeclaration(name="AmountAccount", data_type="Float64", nullable=True),
        SourceFieldDeclaration(name="CurrencyId", data_type="String", nullable=True),
        SourceFieldDeclaration(name="ToAssetId", data_type="String", nullable=True),
        SourceFieldDeclaration(name="TransferUid", data_type="String", nullable=True),
        SourceFieldDeclaration(name="Time", data_type="String", nullable=True),
    ]
    return SourceDatasetConfig(
        source_id=SourceId("ext_bank_statement"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        selector=CsvSelector(),
        enabled=True,
        description="External bank CSV statement without native UID",
        identity=DerivedDeterministicIdentity(
            fields=["DATE", "ASSET_NAME", "DESCRIPTION", "BASE_AMOUNT"],
            namespace="EXT_TX",
            version="v2",
        ),
        mapping=mapping,
        fields=fields,
    )


def test_shan_trusted_id_preservation(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify Shan production SQLite transactions preserve native UID strings unchanged."""
    db_path = _create_sqlite_db_with_inoutcome(tmp_path / "inputs" / "SOURCE_DB.sqlite")
    norm_path = str(db_path).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_INOUTCOME)
    assert ds_plan is not None

    service = DatasetIngestionService()
    success = service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path],
        run_id="run_shan_id_test",
    )
    assert success is True

    # Check Bronze table has preserved exact original UIDs
    df_bronze = isolated_duckdb_manager.conn.execute(
        "SELECT UID, DESCRIPTION, BASE_AMOUNT FROM bronze.r_SQLite_InOutcome ORDER BY UID"
    ).pl()
    assert df_bronze.height == 2
    uids = df_bronze["UID"].to_list()
    assert uids == ["TX_001", "TX_002"]


def test_external_no_uid_csv_ingestion_and_derived_identity(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify external statement CSV without native UIDs ingests via DerivedDeterministicIdentity."""
    rows = [
        {
            "TxDate": "2023-11-15",
            "AccountName": "Checking Account",
            "PayeeDescription": "Direct Deposit Salary",
            "TransactionAmount": "50000.0",
            "CategoryName": "Income from Salary",
            "TransactionType": "0",
            "AssetId": "ASSET_CHK",
            "CategoryId": "CAT_SALARY",
            "Timestamp": "1700000000",
        },
        {
            "TxDate": "2023-11-16",
            "AccountName": "Checking Account",
            "PayeeDescription": "Whole Foods Groceries",
            "TransactionAmount": "1500.0",
            "CategoryName": "Food & Groceries",
            "TransactionType": "1",
            "AssetId": "ASSET_CHK",
            "CategoryId": "CAT_GROC",
            "Timestamp": "1700086400",
        },
    ]
    raw_csv = _build_external_csv_statement_bytes(rows)
    csv_file = tmp_path / "inputs" / "ext_bank_statement.csv"
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file.write_bytes(raw_csv)

    norm_path = str(csv_file).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    ext_ds_config = _get_external_statement_config()
    source_config = SourceConfiguration(
        schema_version="1.0.0",
        sources=(
            SourceConfig(
                source_id=SourceId("ext_bank_statement"),
                provider_type=ProviderType.CSV,
                location=norm_path,
                enabled=True,
            ),
        ),
        datasets=(ext_ds_config,),
    )

    ds_plan = DatasetPlan(
        source_id=SourceId("ext_bank_statement"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        provider_type=ProviderType.CSV,
        location=norm_path,
        selector=CsvSelector(),
        change_detection=resolve_change_detection_policy(
            file_type="csv",
            is_full_replace=True,
            hash_policy=FileHashPolicy(),
        ),
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )

    service = DatasetIngestionService()
    success = service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path],
        run_id="run_ext_no_uid_test",
    )
    assert success is True

    # 1. Verify Pre-Bronze contains raw source shape
    df_pb = isolated_duckdb_manager.conn.execute(
        "SELECT TxDate, AccountName, PayeeDescription, TransactionAmount, __artifact_id__ "
        "FROM pre_bronze.pb_household_inoutcome"
    ).pl()
    assert df_pb.height == 2
    assert "TxDate" in df_pb.columns
    assert "PayeeDescription" in df_pb.columns

    # 2. Verify Bronze contains canonical schema and derived UIDs
    df_bronze = isolated_duckdb_manager.conn.execute(
        "SELECT UID, DATE, ASSET_NAME, DESCRIPTION, BASE_AMOUNT FROM bronze.r_SQLite_InOutcome"
    ).pl()
    assert df_bronze.height == 2

    # Verify deterministic UID values
    expected_uid_1 = generate_deterministic_id(
        "EXT_TX",
        {
            "DATE": "2023-11-15",
            "ASSET_NAME": "Checking Account",
            "DESCRIPTION": "Direct Deposit Salary",
            "BASE_AMOUNT": "50000.0",
        },
    )
    expected_uid_2 = generate_deterministic_id(
        "EXT_TX",
        {
            "DATE": "2023-11-16",
            "ASSET_NAME": "Checking Account",
            "DESCRIPTION": "Whole Foods Groceries",
            "BASE_AMOUNT": "1500.0",
        },
    )
    bronze_uids = set(df_bronze["UID"].to_list())
    assert expected_uid_1 in bronze_uids
    assert expected_uid_2 in bronze_uids


def test_derived_identity_order_invariance(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify DerivedDeterministicIdentity generates byte-identical IDs regardless of row order."""
    row_a = {
        "TxDate": "2023-11-15",
        "AccountName": "Checking Account",
        "PayeeDescription": "Alpha Corp",
        "TransactionAmount": "100.0",
        "CategoryName": "Services",
        "TransactionType": "1",
        "AssetId": "ASSET_A",
        "CategoryId": "CAT_A",
        "Timestamp": "1700000000",
    }
    row_b = {
        "TxDate": "2023-11-16",
        "AccountName": "Savings Account",
        "PayeeDescription": "Beta Corp",
        "TransactionAmount": "200.0",
        "CategoryName": "Services",
        "TransactionType": "1",
        "AssetId": "ASSET_B",
        "CategoryId": "CAT_B",
        "Timestamp": "1700086400",
    }

    # Run 1: Order [A, B]
    csv_bytes_1 = _build_external_csv_statement_bytes([row_a, row_b])
    csv_file_1 = tmp_path / "inputs" / "order_normal.csv"
    csv_file_1.parent.mkdir(parents=True, exist_ok=True)
    csv_file_1.write_bytes(csv_bytes_1)
    norm_path_1 = str(csv_file_1).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path_1]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    ext_ds_config = _get_external_statement_config()
    source_config = SourceConfiguration(
        schema_version="1.0.0",
        sources=(
            SourceConfig(
                source_id=SourceId("ext_bank_statement"),
                provider_type=ProviderType.CSV,
                location=norm_path_1,
                enabled=True,
            ),
        ),
        datasets=(ext_ds_config,),
    )
    ds_plan = DatasetPlan(
        source_id=SourceId("ext_bank_statement"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        provider_type=ProviderType.CSV,
        location=norm_path_1,
        selector=CsvSelector(),
        change_detection=resolve_change_detection_policy(
            file_type="csv",
            is_full_replace=True,
            hash_policy=FileHashPolicy(),
        ),
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )

    service = DatasetIngestionService()
    service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path_1],
        run_id="run_order_1",
    )

    df_1 = isolated_duckdb_manager.conn.execute(
        "SELECT UID, DESCRIPTION FROM bronze.r_SQLite_InOutcome"
    ).pl()
    uid_map_1 = dict(zip(df_1["DESCRIPTION"].to_list(), df_1["UID"].to_list(), strict=True))

    # Run 2: Order [B, A] (reversed)
    csv_bytes_2 = _build_external_csv_statement_bytes([row_b, row_a])
    csv_file_2 = tmp_path / "inputs" / "order_reversed.csv"
    csv_file_2.parent.mkdir(parents=True, exist_ok=True)
    csv_file_2.write_bytes(csv_bytes_2)
    norm_path_2 = str(csv_file_2).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path_2]})

    service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path_2],
        run_id="run_order_2",
    )

    df_2 = isolated_duckdb_manager.conn.execute(
        "SELECT UID, DESCRIPTION FROM bronze.r_SQLite_InOutcome"
    ).pl()
    uid_map_2 = dict(zip(df_2["DESCRIPTION"].to_list(), df_2["UID"].to_list(), strict=True))

    # Assert byte-for-byte identity equality
    assert uid_map_1["Alpha Corp"] == uid_map_2["Alpha Corp"]
    assert uid_map_1["Beta Corp"] == uid_map_2["Beta Corp"]


def test_duplicate_identity_collision_atomicity(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify duplicate identity keys trigger IdentityCollisionError and abort before mutation."""
    duplicate_row = {
        "TxDate": "2023-11-15",
        "AccountName": "Checking Account",
        "PayeeDescription": "Duplicate Test",
        "TransactionAmount": "100.0",
        "CategoryName": "General",
        "TransactionType": "1",
        "AssetId": "ASSET_A",
        "CategoryId": "CAT_A",
        "Timestamp": "1700000000",
    }
    raw_csv = _build_external_csv_statement_bytes([duplicate_row, duplicate_row])
    csv_file = tmp_path / "inputs" / "collision_test.csv"
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file.write_bytes(raw_csv)
    norm_path = str(csv_file).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    ext_ds_config = _get_external_statement_config()
    source_config = SourceConfiguration(
        schema_version="1.0.0",
        sources=(
            SourceConfig(
                source_id=SourceId("ext_bank_statement"),
                provider_type=ProviderType.CSV,
                location=norm_path,
                enabled=True,
            ),
        ),
        datasets=(ext_ds_config,),
    )
    ds_plan = DatasetPlan(
        source_id=SourceId("ext_bank_statement"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        provider_type=ProviderType.CSV,
        location=norm_path,
        selector=CsvSelector(),
        change_detection=resolve_change_detection_policy(
            file_type="csv",
            is_full_replace=True,
            hash_policy=FileHashPolicy(),
        ),
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )

    service = DatasetIngestionService()
    with pytest.raises(IdentityCollisionError) as exc_info:
        service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=[norm_path],
            run_id="run_collision_test",
        )

    # Diagnostic inspection
    diag = exc_info.value.diagnostic
    assert diag.duplicate_count == 2
    assert diag.strategy_fields == ("DATE", "ASSET_NAME", "DESCRIPTION", "BASE_AMOUNT")
    assert diag.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME

    # Verify Bronze table was NOT populated with colliding records
    bronze_tables = [
        r[0]
        for r in isolated_duckdb_manager.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze'"
        ).fetchall()
    ]
    if "r_SQLite_InOutcome" in bronze_tables:
        res = isolated_duckdb_manager.conn.execute(
            "SELECT count(*) FROM bronze.r_SQLite_InOutcome"
        ).fetchone()
        assert res is not None
        assert res[0] == 0


def test_downstream_household_transforms_accept_external_evidence(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify pure domain transforms execute identically on external canonical evidence."""
    rows = [
        {
            "TxDate": "2023-11-15",
            "AccountName": "HDFC Salary",
            "PayeeDescription": "Monthly Consulting Salary",
            "TransactionAmount": "75000.0",
            "CategoryName": "Income from Salary",
            "TransactionType": "0",  # 0 is Income
            "AssetId": "ASSET_HDFC",
            "CategoryId": "CAT_INCOME_SALARY",
            "Timestamp": "1700000000",
        },
        {
            "TxDate": "2023-11-16",
            "AccountName": "HDFC Salary",
            "PayeeDescription": "Restaurant Dinner",
            "TransactionAmount": "2500.0",
            "CategoryName": "Food & Groceries",
            "TransactionType": "1",  # 1 is Expense
            "AssetId": "ASSET_HDFC",
            "CategoryId": "CAT_EXPENSE_FOOD",
            "Timestamp": "1700086400",
        },
    ]
    raw_csv = _build_external_csv_statement_bytes(rows)
    csv_file = tmp_path / "inputs" / "ext_statement_transforms.csv"
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file.write_bytes(raw_csv)
    norm_path = str(csv_file).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    ext_ds_config = _get_external_statement_config()
    source_config = SourceConfiguration(
        schema_version="1.0.0",
        sources=(
            SourceConfig(
                source_id=SourceId("ext_bank_statement"),
                provider_type=ProviderType.CSV,
                location=norm_path,
                enabled=True,
            ),
        ),
        datasets=(ext_ds_config,),
    )
    ds_plan = DatasetPlan(
        source_id=SourceId("ext_bank_statement"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        provider_type=ProviderType.CSV,
        location=norm_path,
        selector=CsvSelector(),
        change_detection=resolve_change_detection_policy(
            file_type="csv",
            is_full_replace=True,
            hash_policy=FileHashPolicy(),
        ),
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )

    service = DatasetIngestionService()
    service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path],
        run_id="run_ext_transform_test",
    )

    # Fetch canonical Bronze DataFrame
    df_bronze = isolated_duckdb_manager.conn.execute("SELECT * FROM bronze.r_SQLite_InOutcome").pl()
    assert df_bronze.height == 2

    # Feed into downstream domain transformation pipeline
    base_tx_lazy = get_base_transactions(df_bronze.lazy(), column_mapping={})
    df_base = base_tx_lazy.collect()
    assert df_base.height == 2
    assert "BASE_AMOUNT" in df_base.columns
    assert "UID" in df_base.columns

    # Mock dimension lookups for income and expense subcategories
    d_income_subcat = pl.LazyFrame(
        {
            "UID": ["CAT_INCOME_SALARY"],
            "CATEGORY_ID": ["CAT_INCOME_PARENT"],
            "Income_Category": ["Salary"],
            "Income_Subcategory": ["Salary"],
        }
    )
    d_expense_subcat = pl.LazyFrame(
        {
            "UID": ["CAT_EXPENSE_FOOD"],
            "CATEGORY_ID": ["CAT_EXPENSE_PARENT"],
            "Expense_Category": ["Food"],
            "Expense_Subcategory": ["Groceries"],
        }
    )

    # Execute downstream domain fact transformations
    income_facts = transform_f_income_transactions(base_tx_lazy, rules, d_income_subcat).collect()
    expense_facts = transform_f_expense_transactions(
        base_tx_lazy, rules, d_expense_subcat
    ).collect()

    assert income_facts.height == 1
    assert income_facts["BASE_AMOUNT"][0] == 75000.0

    assert expense_facts.height == 1
    assert expense_facts["BASE_AMOUNT"][0] == 2500.0


def test_household_opening_balances_ingestion_and_transformation(
    tmp_path: Path,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
) -> None:
    """Verify HOUSEHOLD_OPENING_BALANCES ingests through generalized slice and transforms to facts."""
    csv_file = _create_opening_balances_csv(tmp_path / "inputs" / "OPENING_BALANCE.csv")
    norm_path = str(csv_file).replace("\\", "/")
    isolated_control_plane.artifacts.ingest_binaries({"opening_balances": [norm_path]})

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    meta = MetaLayer(isolated_duckdb_manager, Settings(), rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    pre_bronze = PreBronzeLayer(isolated_duckdb_manager)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_OPENING_BALANCES)
    assert ds_plan is not None

    service = DatasetIngestionService()
    success = service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=[norm_path],
        run_id="run_opbal_test",
    )
    assert success is True

    # 1. Verify Pre-Bronze table persistence
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_OPENING_BALANCES)
    assert pb_contract is not None
    assert pre_bronze.table_exists(pb_contract)

    df_pb = isolated_duckdb_manager.conn.execute(
        f"SELECT Z_PK, ZAMOUNT, ZTXDATESTR, __artifact_id__ FROM {pb_contract.physical_table}"
    ).pl()
    assert df_pb.height == 2

    # 2. Verify Canonical Bronze table persistence
    b_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_OPENING_BALANCES)
    assert b_contract is not None

    df_bronze = isolated_duckdb_manager.conn.execute(
        f"SELECT * FROM {b_contract.physical_table} ORDER BY Z_PK"
    ).pl()
    assert df_bronze.height == 2
    assert df_bronze["UID"].to_list() == ["1", "2"]
    assert df_bronze["Z_PK"].to_list() == [1, 2]

    # 3. Verify Downstream domain transformation into f_Opening_Balances
    f_opbal = transform_f_opening_balances(df_bronze.lazy(), column_mapping={}).collect()
    assert f_opbal.height == 2
    assert set(f_opbal.columns) == {
        "Z_PK",
        "Date",
        "ASSET_SUBCATEGORY_ID",
        "CURRENCY_ID",
        "Opening_Amount",
        "Opening_Amount_Account",
        "artifact_id",
    }
    assert f_opbal["Opening_Amount"].to_list() == [100000.0, 25000.0]
    assert f_opbal["Date"].to_list() == [date(2023, 1, 1), date(2023, 1, 1)]
