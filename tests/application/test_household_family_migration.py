# pyright: reportPrivateUsage=false
"""Verification suite for Phase 028 Household Reference Evidence Family migration.

Owns
----
- Multi-dataset ingestion and UID stability across all 5 household datasets
  (HOUSEHOLD_ZCATEGORY, HOUSEHOLD_ASSET_GROUP, HOUSEHOLD_ASSETS, HOUSEHOLD_CURRENCY, HOUSEHOLD_INOUTCOME).
- Downstream TransformationDAG execution across all 4 category dimensions, asset dimensions,
  currency dimension, and transaction facts from canonical Bronze.
- Certification that legacy extraction routines (extract_base_tables, _extract_sqlite_tables)
  are permanently demolished.

Does not own
------------
- Single-slice generalized ingestion invariants (owned by test_generalized_vertical_slice.py).
- Downstream FIFO and Tax calculations (owned by test_tax_domain.py).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    SourcePlanner,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.domain.household.transforms.asset_dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
)
from personal_finance_etl.domain.household.transforms.expense_dimensions import (
    transform_d_expense_category,
    transform_d_expense_subcategory,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_category,
    transform_d_income_subcategory,
)
from personal_finance_etl.domain.household.transforms.reference_dimensions import (
    transform_d_currency,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability import (
    get_global_emitter,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)
from personal_finance_etl.infrastructure.validation import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)


def _create_sqlite_db(db_path: Path) -> Path:
    """Create an isolated test SQLite database containing all 5 household reference tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE ZCATEGORY (
                ID INTEGER PRIMARY KEY,
                C_IS_DEL INTEGER,
                C_UTIME INTEGER,
                uid TEXT UNIQUE,
                NAME TEXT NOT NULL,
                ORDERSEQ INTEGER,
                TYPE INTEGER NOT NULL,
                STATUS INTEGER,
                pUid TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        zcat_rows = [
            (
                1,
                0,
                1700000000,
                "CAT_INCOME_SALARY",
                "Income from Salary",
                1,
                0,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                2,
                0,
                1700000000,
                "SUBCAT_INCOME_BONUS",
                "Annual Bonus",
                2,
                0,
                0,
                "CAT_INCOME_SALARY",
                1,
                1700000000.0,
                1,
            ),
            (
                3,
                0,
                1700000000,
                "CAT_EXPENSE_FOOD",
                "Food & Groceries",
                3,
                1,
                0,
                None,
                1,
                1700000000.0,
                1,
            ),
            (
                4,
                0,
                1700000000,
                "SUBCAT_EXPENSE_DINING",
                "Restaurant Dining",
                4,
                1,
                0,
                "CAT_EXPENSE_FOOD",
                1,
                1700000000.0,
                1,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO ZCATEGORY (
                ID, C_IS_DEL, C_UTIME, uid, NAME, ORDERSEQ, TYPE, STATUS, pUid, isSynced, syncTime, syncVersion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            zcat_rows,
        )

        conn.execute(
            """
            CREATE TABLE ASSETGROUP (
                ID INTEGER PRIMARY KEY,
                DEVICE_ID INTEGER,
                uid TEXT UNIQUE,
                IS_DEL INTEGER,
                USETIME INTEGER,
                ACC_GROUP_NAME TEXT NOT NULL,
                TYPE INTEGER NOT NULL,
                ORDERSEQ INTEGER,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ASSETGROUP (
                ID, DEVICE_ID, uid, IS_DEL, USETIME, ACC_GROUP_NAME, TYPE, ORDERSEQ, isSynced, syncTime, syncVersion
            ) VALUES (1, 101, 'AG_BANK', 0, 1700000000, 'Bank Accounts', 0, 1, 1, 1700000000.0, 1)
            """
        )

        conn.execute(
            """
            CREATE TABLE ASSETS (
                ID INTEGER PRIMARY KEY,
                CARD_DAY_FIN TEXT,
                CARD_DAY_PAY TEXT,
                NIC_NAME TEXT NOT NULL,
                ORDERSEQ INTEGER,
                ZDATA TEXT,
                ZDATA1 TEXT,
                ZDATA2 TEXT,
                IS_TRANS_EXPENSE INTEGER,
                IS_CARD_AUTO_PAY INTEGER,
                APP_PACKAGE TEXT,
                APP_NAME TEXT,
                SMS_TEL TEXT,
                SMS_STRING TEXT,
                A_UTIME INTEGER,
                CARD_USAGE_HURDLE_TYPE INTEGER,
                CARD_USAGE_HURDLE_START_DATE REAL,
                CARD_USAGE_HURDLE_AMOUNT REAL,
                uid TEXT UNIQUE,
                currencyUid TEXT,
                cardAssetUid TEXT,
                groupUid TEXT,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ASSETS (
                ID, CARD_DAY_FIN, CARD_DAY_PAY, NIC_NAME, ORDERSEQ, ZDATA, ZDATA1, ZDATA2,
                IS_TRANS_EXPENSE, IS_CARD_AUTO_PAY, APP_PACKAGE, APP_NAME, SMS_TEL, SMS_STRING,
                A_UTIME, CARD_USAGE_HURDLE_TYPE, CARD_USAGE_HURDLE_START_DATE, CARD_USAGE_HURDLE_AMOUNT,
                uid, currencyUid, cardAssetUid, groupUid, isSynced, syncTime, syncVersion
            ) VALUES (
                1, '0', '0', 'HDFC Salary', 1, '0', 'Main checking account', 'Notes',
                0, 0, 'com.hdfc', 'HDFC Bank', 'HDFCBK', 'sms',
                1700000000, 0, 0.0, 0.0,
                'ASSET_HDFC', 'CURR_INR', NULL, 'AG_BANK', 1, 1700000000.0, 1
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE CURRENCY (
                ID INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
                NAME TEXT NOT NULL,
                ISO TEXT,
                MAIN_ISO TEXT,
                IS_DEL INTEGER,
                ORDER_SEQ INTEGER,
                RATE REAL,
                SYMBOL TEXT,
                INSERT_TYPE TEXT,
                SYMBOL_POSITION TEXT,
                IS_MAIN_CURRENCY INTEGER,
                IS_SHOW INTEGER,
                MODIFY_DATE INTEGER,
                DECIMAL_POINT INTEGER,
                isSynced INTEGER,
                syncTime REAL,
                syncVersion INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO CURRENCY (
                ID, uid, NAME, ISO, MAIN_ISO, IS_DEL, ORDER_SEQ, RATE, SYMBOL,
                INSERT_TYPE, SYMBOL_POSITION, IS_MAIN_CURRENCY, IS_SHOW, MODIFY_DATE,
                DECIMAL_POINT, isSynced, syncTime, syncVersion
            ) VALUES (
                1, 'CURR_INR', 'Indian Rupee', 'INR', 'INR', 0, 1, 1.0, '₹',
                '0', '0', 1, 1, 1700000000,
                2, 1, 1700000000.0, 1
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE INOUTCOME (
                AID INTEGER PRIMARY KEY,
                uid TEXT UNIQUE,
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


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def test_household_family_multi_dataset_ingestion_and_uid_stability(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Ingest all 5 household datasets from a single SQLite payload with UID stability."""
    db_file = _create_sqlite_db(tmp_path / "household" / "household.sqlite")
    norm_path = str(db_file).replace("\\", "/")
    expected_artifact_id = generate_file_id(norm_path)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    actionable = {"sqlite_source": [norm_path]}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    household_family = (
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
    )

    # 1. Ingest all 5 datasets through generalized vertical slice
    for ds_id in household_family:
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        success = ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_family_001",
        )
        assert success is True

    # 2. Verify all 5 Pre-Bronze tables created and link to same artifact_id
    for ds_id in household_family:
        pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
        assert pb_contract is not None
        assert pre_bronze.table_exists(pb_contract)
        pb_df = isolated_duckdb_manager.conn.query(
            f"SELECT * FROM {pb_contract.physical_table}"
        ).pl()
        assert pb_df.height > 0
        assert "artifact_id" in pb_df.columns
        assert pb_df["artifact_id"][0] == expected_artifact_id

    # 3. Verify all 5 Bronze tables created and contain exact trusted source UIDs
    expected_uids = {
        DatasetId.HOUSEHOLD_ZCATEGORY: {
            "CAT_INCOME_SALARY",
            "SUBCAT_INCOME_BONUS",
            "CAT_EXPENSE_FOOD",
            "SUBCAT_EXPENSE_DINING",
        },
        DatasetId.HOUSEHOLD_ASSET_GROUP: {"AG_BANK"},
        DatasetId.HOUSEHOLD_ASSETS: {"ASSET_HDFC"},
        DatasetId.HOUSEHOLD_CURRENCY: {"CURR_INR"},
        DatasetId.HOUSEHOLD_INOUTCOME: {"TX_001", "TX_002"},
    }
    for ds_id, uids in expected_uids.items():
        bronze_contract = get_bronze_contract_by_dataset_id(ds_id)
        assert bronze_contract is not None
        b_df = isolated_duckdb_manager.conn.query(
            f"SELECT * FROM {bronze_contract.physical_table}"
        ).pl()
        assert b_df.height >= len(uids)
        assert "UID" in b_df.columns
        assert "artifact_id" in b_df.columns
        assert b_df["artifact_id"][0] == expected_artifact_id
        actual_uids = set(b_df["UID"].to_list())
        for expected_uid in uids:
            assert expected_uid in actual_uids


def test_household_family_transformation_dag_all_dimensions_and_facts(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """All 4 category dimensions, asset dimensions, currency, and facts transform cleanly from Bronze."""
    db_file = _create_sqlite_db(tmp_path / "household" / "household.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    actionable = {"sqlite_source": [norm_path]}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    for ds_id in (
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
    ):
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_dag_001",
        )

    dataset_collection = bronze.get_dataset_collection()

    # 1. All 4 Category Dimensions derived from ZCATEGORY
    zcat = dataset_collection.require_lazy(DatasetId.HOUSEHOLD_ZCATEGORY)
    d_inc_cat = transform_d_income_category(zcat, {}, rules).collect()
    assert "CAT_INCOME_SALARY" in d_inc_cat["UID"].to_list()

    d_inc_subcat = transform_d_income_subcategory(zcat, {}, d_inc_cat.lazy(), rules).collect()
    assert "SUBCAT_INCOME_BONUS" in d_inc_subcat["UID"].to_list()

    d_exp_cat = transform_d_expense_category(zcat, {}).collect()
    assert "CAT_EXPENSE_FOOD" in d_exp_cat["UID"].to_list()

    d_exp_subcat = transform_d_expense_subcategory(zcat, {}, rules).collect()
    assert "SUBCAT_EXPENSE_DINING" in d_exp_subcat["UID"].to_list()

    # 2. Asset Category and Subcategory
    agrp = dataset_collection.require_lazy(DatasetId.HOUSEHOLD_ASSET_GROUP)
    d_asset_cat = transform_d_asset_category(agrp, {}, rules).collect()
    assert "AG_BANK" in d_asset_cat["UID"].to_list()

    asts = dataset_collection.require_lazy(DatasetId.HOUSEHOLD_ASSETS)
    d_asset_subcat = transform_d_asset_subcategory(asts, {}, rules).collect()
    assert "ASSET_HDFC" in d_asset_subcat["UID"].to_list()

    # 3. Currency Dimension
    curr = dataset_collection.require_lazy(DatasetId.HOUSEHOLD_CURRENCY)
    d_currency = transform_d_currency(curr, {}).collect()
    assert "CURR_INR" in d_currency["UID"].to_list()

    # 4. Transaction Facts (Income and Expense)
    inout = dataset_collection.require_lazy(DatasetId.HOUSEHOLD_INOUTCOME)
    base_tx = get_base_transactions(inout, {})
    f_income = transform_f_income_transactions(base_tx, rules, d_inc_subcat.lazy()).collect()
    assert "TX_001" in f_income["UID"].to_list()

    f_expense = transform_f_expense_transactions(base_tx, rules, d_exp_subcat.lazy()).collect()
    assert "TX_002" in f_expense["UID"].to_list()


def test_extractor_fixed_routines_permanently_demolished() -> None:
    """Ensure extract_base_tables and _extract_sqlite_tables are completely demolished."""
    assert not hasattr(SQLiteExtractor, "extract_base_tables")
    assert not hasattr(DataExtractor, "_extract_sqlite_tables")
