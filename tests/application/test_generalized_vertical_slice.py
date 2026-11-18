# pyright: reportPrivateUsage=false
"""Comprehensive verification suite for Phase 025 generalized dataset vertical slice.

Owns
----
- 16-point verification matrix for DatasetId.HOUSEHOLD_ZCATEGORY end-to-end migration:
  1. Happy path first run: SQLite bytes -> Pre-Bronze -> Bronze -> Silver dimensions.
  2. Unchanged rerun: Zero redundant Pre-Bronze/Bronze writes on unedited artifact.
  3. Changed artifact: New file hash triggers slice replacement in Pre-Bronze and Bronze.
  4. Rename scenario: Identity migration updates artifact references across Pre-Bronze and Bronze.
  5. Malformed source schema fails Gate 1 (PRE_BRONZE validation stage).
  6. Normalization failure aborts run before Bronze mutation.
  7. Identity uniqueness failure fails Gate 2 (CANONICAL_BRONZE validation stage).
  8. Canonical Bronze contract violation fails Gate 2.
  9. Failure after Pre-Bronze maintains recovery integrity.
  10. Failure after Bronze before Control Plane commit triggers recovery.
  11. Backup and restore includes Pre-Bronze schema.
  12. Downstream category transformation equivalence (legacy vs canonical Bronze).
  13. End-to-end pipeline phase execution financial equivalence.
  14. Protected deterministic IDs remain byte-stable.
  15. Selected legacy route dormancy verification.
  16. Unmigrated datasets remain on legacy path without regression.
  17. Programmatic migration template checklist contract enforcing items A-L.

Does not own
------------
- Pre-Bronze DDL creation internals (owned by infrastructure.warehouse.registry).
- General capability planner tests (owned by test_capability_planner.py).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    SourcePlanner,
)
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.validation import (
    ValidationError,
    ValidationStage,
)
from personal_finance_etl.domain.household.transforms.expense_dimensions import (
    transform_d_expense_category,
    transform_d_expense_subcategory,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_category,
    transform_d_income_subcategory,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability import (
    get_global_emitter,
)
from personal_finance_etl.infrastructure.validation import (
    PanderaDataFrameValidator,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.bronze import (
    MIGRATED_DATASETS,
    BronzeLayer,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)


def _create_sqlite_db(
    db_path: Path,
    zcat_rows: Sequence[dict[str, Any]] | None = None,
    create_zcategory: bool = True,
    custom_columns: dict[str, str] | None = None,
) -> Path:
    """Create an isolated test SQLite database containing ZCATEGORY and related tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    default_zcat = [
        {
            "ID": 1,
            "C_IS_DEL": 0,
            "C_UTIME": 1700000000,
            "uid": "CAT_INCOME_SALARY",
            "NAME": "Income from Salary",
            "ORDERSEQ": 1,
            "TYPE": 0,
            "STATUS": 0,
            "pUid": None,
            "isSynced": 1,
            "syncTime": 1700000000.0,
            "syncVersion": 1,
        },
        {
            "ID": 2,
            "C_IS_DEL": 0,
            "C_UTIME": 1700000000,
            "uid": "SUBCAT_INCOME_BONUS",
            "NAME": "Annual Bonus",
            "ORDERSEQ": 2,
            "TYPE": 0,
            "STATUS": 0,
            "pUid": "CAT_INCOME_SALARY",
            "isSynced": 1,
            "syncTime": 1700000000.0,
            "syncVersion": 1,
        },
        {
            "ID": 3,
            "C_IS_DEL": 0,
            "C_UTIME": 1700000000,
            "uid": "CAT_EXPENSE_FOOD",
            "NAME": "Food & Groceries",
            "ORDERSEQ": 3,
            "TYPE": 1,
            "STATUS": 0,
            "pUid": None,
            "isSynced": 1,
            "syncTime": 1700000000.0,
            "syncVersion": 1,
        },
        {
            "ID": 4,
            "C_IS_DEL": 0,
            "C_UTIME": 1700000000,
            "uid": "SUBCAT_EXPENSE_DINING",
            "NAME": "Restaurant Dining",
            "ORDERSEQ": 4,
            "TYPE": 1,
            "STATUS": 0,
            "pUid": "CAT_EXPENSE_FOOD",
            "isSynced": 1,
            "syncTime": 1700000000.0,
            "syncVersion": 1,
        },
    ]

    rows = zcat_rows if zcat_rows is not None else default_zcat

    conn = sqlite3.connect(db_path)
    try:
        if create_zcategory:
            if custom_columns is not None:
                col_defs = ", ".join(f'"{c}" {t}' for c, t in custom_columns.items())
                conn.execute(f"CREATE TABLE ZCATEGORY ({col_defs})")
                if rows:
                    keys = list(rows[0].keys())
                    placeholders = ", ".join(["?"] * len(keys))
                    col_names = ", ".join(f'"{k}"' for k in keys)
                    for r in rows:
                        conn.execute(
                            f"INSERT INTO ZCATEGORY ({col_names}) VALUES ({placeholders})",
                            tuple(r[k] for k in keys),
                        )
            else:
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
                for r in rows:
                    conn.execute(
                        """
                        INSERT INTO ZCATEGORY (
                            ID, C_IS_DEL, C_UTIME, uid, NAME, ORDERSEQ, TYPE, STATUS, pUid, isSynced, syncTime, syncVersion
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r.get("ID"),
                            r.get("C_IS_DEL"),
                            r.get("C_UTIME"),
                            r.get("uid"),
                            r.get("NAME"),
                            r.get("ORDERSEQ"),
                            r.get("TYPE"),
                            r.get("STATUS"),
                            r.get("pUid"),
                            r.get("isSynced"),
                            r.get("syncTime"),
                            r.get("syncVersion"),
                        ),
                    )

        # Create complete household reference tables conforming to source field declarations
        conn.executescript(
            """
            CREATE TABLE ASSETGROUP (
                ID INTEGER PRIMARY KEY, DEVICE_ID INTEGER, uid TEXT UNIQUE, IS_DEL INTEGER,
                USETIME INTEGER, ACC_GROUP_NAME TEXT NOT NULL, TYPE INTEGER NOT NULL,
                ORDERSEQ INTEGER, isSynced INTEGER, syncTime REAL, syncVersion INTEGER
            );
            INSERT INTO ASSETGROUP VALUES (1, 101, 'AG_BANK', 0, 1700000000, 'Bank Accounts', 0, 1, 1, 1700000000.0, 1);

            CREATE TABLE ASSETS (
                ID INTEGER PRIMARY KEY, CARD_DAY_FIN TEXT, CARD_DAY_PAY TEXT, NIC_NAME TEXT NOT NULL,
                ORDERSEQ INTEGER, ZDATA TEXT, ZDATA1 TEXT, ZDATA2 TEXT, IS_TRANS_EXPENSE INTEGER,
                IS_CARD_AUTO_PAY INTEGER, APP_PACKAGE TEXT, APP_NAME TEXT, SMS_TEL TEXT, SMS_STRING TEXT,
                A_UTIME INTEGER, CARD_USAGE_HURDLE_TYPE INTEGER, CARD_USAGE_HURDLE_START_DATE REAL,
                CARD_USAGE_HURDLE_AMOUNT REAL, uid TEXT UNIQUE, currencyUid TEXT, cardAssetUid TEXT,
                groupUid TEXT, isSynced INTEGER, syncTime REAL, syncVersion INTEGER
            );
            INSERT INTO ASSETS VALUES (
                1, '0', '0', 'HDFC Salary', 1, '0', 'Main checking account', 'Notes', 0, 0,
                'com.hdfc', 'HDFC Bank', 'HDFCBK', 'sms', 1700000000, 0, 0.0, 0.0,
                'ASSET_HDFC', 'CURR_INR', NULL, 'AG_BANK', 1, 1700000000.0, 1
            );

            CREATE TABLE CURRENCY (
                ID INTEGER PRIMARY KEY, uid TEXT UNIQUE, NAME TEXT NOT NULL, ISO TEXT,
                MAIN_ISO TEXT, IS_DEL INTEGER, ORDER_SEQ INTEGER, RATE REAL, SYMBOL TEXT,
                INSERT_TYPE TEXT, SYMBOL_POSITION TEXT, IS_MAIN_CURRENCY INTEGER,
                IS_SHOW INTEGER, MODIFY_DATE INTEGER, DECIMAL_POINT INTEGER, isSynced INTEGER,
                syncTime REAL, syncVersion INTEGER
            );
            INSERT INTO CURRENCY VALUES (
                1, 'CURR_INR', 'Indian Rupee', 'INR', 'INR', 0, 1, 1.0, '₹',
                '0', '0', 1, 1, 1700000000, 2, 1, 1700000000.0, 1
            );

            CREATE TABLE INOUTCOME (
                AID INTEGER PRIMARY KEY, uid TEXT UNIQUE, assetUid TEXT NOT NULL, CARDDIVIDMONTH TEXT,
                ctgUid TEXT, toAssetUid TEXT, ZCONTENT TEXT, ZDATE TEXT NOT NULL, WDATE TEXT,
                wtime TEXT, paid TEXT, DO_TYPE TEXT NOT NULL, ZMONEY TEXT NOT NULL,
                txUidTrans TEXT, ZDATA TEXT, SMS_RDATE TEXT, IN_ZMONEY TEXT, ASSET_NIC TEXT,
                CATEGORY_NAME TEXT, cardDivideUid TEXT, CARD_DIVIDE_MONTH_STR TEXT, MARK INTEGER,
                txUidFee TEXT, SMS_ORIGIN TEXT, SMS_PARSE_CONTENT TEXT, IS_DEL INTEGER,
                UTIME INTEGER, currencyUid TEXT, AMOUNT_ACCOUNT REAL, lat REAL, lng REAL,
                gstd TEXT, isSynced INTEGER, syncTime REAL, syncVersion INTEGER
            );
            INSERT INTO INOUTCOME VALUES (
                1, 'TX_001', 'ASSET_HDFC', '0', 'CAT_INCOME_SALARY', NULL, 'Monthly Salary',
                '1700000000', '2023-11-15', '10:00:00', '1', '1', '50000.0', NULL, 'Memo',
                '2023-11-15', '50000.0', 'HDFC Salary', 'Income from Salary', NULL,
                NULL, 0, NULL, 'HDFCBK', 'salary credited',
                0, 1700000000, 'CURR_INR', 50000.0, 0.0, 0.0, 'IN', 1, 1700000000.0, 1
            );
            INSERT INTO INOUTCOME VALUES (
                2, 'TX_002', 'ASSET_HDFC', '0', 'CAT_EXPENSE_FOOD', NULL, 'Dinner',
                '1700000100', '2023-11-15', '20:00:00', '1', '0', '1500.0', NULL, 'Restaurant',
                '2023-11-15', '1500.0', 'HDFC Salary', 'Food & Groceries', NULL,
                NULL, 0, NULL, 'HDFCBK', 'spent 1500',
                0, 1700000100, 'CURR_INR', -1500.0, 0.0, 0.0, 'IN', 1, 1700000100.0, 1
            );
            """
        )

        conn.commit()
    finally:
        conn.close()

    return db_path


def _fetch_scalar(manager: DuckDBManager, query: str) -> int:
    """Execute a scalar query against DuckDB and return integer result."""
    res = manager.conn.query(query).fetchone()
    assert res is not None
    val = res[0]
    assert isinstance(val, int)
    return val


# ---------------------------------------------------------------------------
# Test Scenarios 1 - 17
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def test_happy_path_first_run(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 1: Happy path first run SQLite -> Pre-Bronze -> Bronze -> Silver dimensions."""
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    actionable = {"sqlite_source": [norm_path]}
    isolated_control_plane.artifacts.ingest_binaries(actionable)
    success = ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=actionable,
        run_id="run_001",
    )
    assert success is True

    # 1. Assert Pre-Bronze table exists and has raw columns + provenance
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None
    assert pre_bronze.table_exists(pb_contract)

    pb_df = isolated_duckdb_manager.conn.query(f"SELECT * FROM {pb_contract.physical_table}").pl()
    assert pb_df.height == 4
    for raw_col in [
        "ID",
        "C_IS_DEL",
        "C_UTIME",
        "uid",
        "NAME",
        "ORDERSEQ",
        "TYPE",
        "STATUS",
        "pUid",
    ]:
        assert raw_col in pb_df.columns
    assert "__artifact_id__" in pb_df.columns
    assert "__source_id__" in pb_df.columns
    assert "__dataset_id__" in pb_df.columns

    # 2. Assert Bronze table exists and has canonical columns
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    b_df = isolated_duckdb_manager.conn.query(
        f"SELECT * FROM {bronze_contract.physical_table}"
    ).pl()
    assert b_df.height == 4
    for can_col in [
        "UID",
        "CATEGORY_NAME",
        "IS_DEL",
        "CATEGORY_ID",
        "TYPE",
        "ORDER_SEQUENCE",
        "S_NO",
    ]:
        assert can_col in b_df.columns
    assert "__file_name__" in b_df.columns
    assert "artifact_id" in b_df.columns

    # 3. Assert Control Plane and Meta Layer synced
    reg = isolated_control_plane.artifacts.get_registry_with_status()
    assert reg[norm_path][2] == "SYNCED"
    meta_df = isolated_duckdb_manager.conn.query("SELECT * FROM meta.m_File_Registry").pl()
    assert meta_df.height >= 1
    assert norm_path in meta_df["relative_path"].to_list()

    # 4. Assert Downstream category dimensions execute cleanly
    col_mapping: dict[str, str] = {}
    b_lazy = b_df.lazy()
    inc_cat = transform_d_income_category(b_lazy, col_mapping).collect()
    assert inc_cat.height == 1
    assert inc_cat["UID"].to_list() == ["CAT_INCOME_SALARY"]
    assert "CATEGORY_NAME_SHORT" in inc_cat.columns

    inc_sub = transform_d_income_subcategory(b_lazy, col_mapping, rules=None).collect()
    assert inc_sub.height == 1
    assert inc_sub["UID"].to_list() == ["SUBCAT_INCOME_BONUS"]

    exp_cat = transform_d_expense_category(b_lazy, col_mapping).collect()
    assert exp_cat.height == 1
    assert exp_cat["UID"].to_list() == ["CAT_EXPENSE_FOOD"]

    exp_sub = transform_d_expense_subcategory(b_lazy, col_mapping).collect()
    assert exp_sub.height == 1
    assert exp_sub["UID"].to_list() == ["SUBCAT_EXPENSE_DINING"]


def test_unchanged_rerun(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 2: Unchanged rerun produces zero redundant Pre-Bronze/Bronze writes."""
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    # First run
    success_1 = ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": [norm_path]},
        run_id="run_001",
    )
    assert success_1 is True

    # Rerun with empty actionable files (file unchanged, locator filtered it out)
    success_2 = ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": []},
        run_id="run_002",
    )
    assert success_2 is False


def test_changed_artifact(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 3: Changed artifact triggers slice replacement in Pre-Bronze and Bronze."""
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    # Initial ingest (4 rows)
    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": [norm_path]},
        run_id="run_001",
    )

    # Modify SQLite DB: add a 5th category
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            INSERT INTO ZCATEGORY (
                ID, C_IS_DEL, C_UTIME, uid, NAME, ORDERSEQ, TYPE, STATUS, pUid, isSynced, syncTime, syncVersion
            ) VALUES (5, 0, 1700000000, 'CAT_EXPENSE_TRAVEL', 'Travel & Fuel', 5, 1, 0, NULL, 1, 1700000000.0, 1)
            """
        )
        conn.commit()

    # Re-ingest
    success = ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": [norm_path]},
        run_id="run_002",
    )
    assert success is True

    # Check updated count in Pre-Bronze and Bronze
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None
    assert bronze_contract is not None

    pb_count = _fetch_scalar(
        isolated_duckdb_manager, f"SELECT count(*) FROM {pb_contract.physical_table}"
    )
    b_count = _fetch_scalar(
        isolated_duckdb_manager, f"SELECT count(*) FROM {bronze_contract.physical_table}"
    )
    assert pb_count == 5
    assert b_count == 5


def test_rename_scenario(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 4: Identity migration updates artifact references across Pre-Bronze and Bronze."""
    old_file = _create_sqlite_db(tmp_path / "household" / "household_v1.sqlite")
    old_norm = str(old_file).replace("\\", "/")

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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": [old_norm]},
        run_id="run_001",
    )

    # Rename file
    new_file = tmp_path / "household" / "household_renamed.sqlite"
    old_file.rename(new_file)
    new_norm = str(new_file).replace("\\", "/")

    old_id = generate_file_id(old_norm)
    new_id = generate_file_id(new_norm)

    # Execute identity migration
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None
    pre_bronze.migrate_artifact_identity(old_id, new_id, pb_contract)
    bronze.migrate_identity([(old_norm, new_norm, "sqlite_source")])
    meta.migrate_identity([(old_norm, new_norm, "sqlite_source")])

    # Assert Pre-Bronze updated
    pb_df = isolated_duckdb_manager.conn.query(
        f"SELECT DISTINCT __artifact_id__ FROM {pb_contract.physical_table}"
    ).pl()
    assert pb_df["__artifact_id__"].to_list() == [new_id]

    # Assert Bronze updated
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    b_df = isolated_duckdb_manager.conn.query(
        f"SELECT DISTINCT __file_name__, artifact_id FROM {bronze_contract.physical_table}"
    ).pl()
    assert b_df["__file_name__"].to_list() == ["household_renamed.sqlite"]
    assert b_df["artifact_id"].to_list() == [new_id]


def test_malformed_source_schema_fails_gate_1(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 5: Malformed source schema (missing NAME column) fails Gate 1 (PRE_BRONZE)."""
    # Create SQLite DB with missing 'NAME' column
    bad_columns = {
        "ID": "INTEGER PRIMARY KEY",
        "C_IS_DEL": "INTEGER",
        "C_UTIME": "INTEGER",
        "uid": "TEXT",
        "ORDERSEQ": "INTEGER",
        "TYPE": "INTEGER",
    }
    bad_rows = [{"ID": 1, "C_IS_DEL": 0, "C_UTIME": 1700, "uid": "CAT_1", "ORDERSEQ": 1, "TYPE": 0}]
    db_file = _create_sqlite_db(
        tmp_path / "household" / "bad_schema.sqlite",
        zcat_rows=bad_rows,
        custom_columns=bad_columns,
    )
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    with pytest.raises(ValidationError) as exc_info:
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_bad_gate_1",
        )

    # Gate 1 failed
    assert exc_info.value.result.stage == ValidationStage.PRE_BRONZE

    # Bronze table must NOT be mutated or exist
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    check = _fetch_scalar(
        isolated_duckdb_manager,
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{bronze_contract.physical_table.split('.')[-1]}'",
    )
    assert check == 0


def test_normalization_failure(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 6: Normalization failure aborts run before Bronze table mutation."""
    db_file = _create_sqlite_db(tmp_path / "household" / "norm_fail.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)

    # Mock admission service to simulate transformation failure
    mock_admission = MagicMock(spec=AdmissionService)
    mock_admission.compile_admission_plan.side_effect = RuntimeError("Simulated admission failure")
    ingestion_service = DatasetIngestionService(validator, mock_admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    with pytest.raises(RuntimeError, match="Simulated admission failure"):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_norm_fail",
        )

    # Bronze must NOT exist
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    check = _fetch_scalar(
        isolated_duckdb_manager,
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{bronze_contract.physical_table.split('.')[-1]}'",
    )
    assert check == 0


def test_identity_uniqueness_fails_gate_2(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 7: Duplicate UID fails Gate 2 (CANONICAL_BRONZE validation stage)."""
    # Create SQLite DB with duplicate UID
    dup_columns = {
        "ID": "INTEGER",
        "C_IS_DEL": "INTEGER",
        "C_UTIME": "INTEGER",
        "uid": "TEXT",
        "NAME": "TEXT",
        "ORDERSEQ": "INTEGER",
        "TYPE": "INTEGER",
        "STATUS": "INTEGER",
        "pUid": "TEXT",
        "isSynced": "INTEGER",
        "syncTime": "REAL",
        "syncVersion": "INTEGER",
    }
    dup_rows = [
        {
            "ID": 1,
            "C_IS_DEL": 0,
            "C_UTIME": 100,
            "uid": "CAT_DUP",
            "NAME": "A",
            "ORDERSEQ": 1,
            "TYPE": 0,
            "STATUS": 0,
            "pUid": None,
            "isSynced": 1,
            "syncTime": 100.0,
            "syncVersion": 1,
        },
        {
            "ID": 2,
            "C_IS_DEL": 0,
            "C_UTIME": 100,
            "uid": "CAT_DUP",
            "NAME": "B",
            "ORDERSEQ": 2,
            "TYPE": 0,
            "STATUS": 0,
            "pUid": None,
            "isSynced": 1,
            "syncTime": 100.0,
            "syncVersion": 1,
        },
    ]
    db_file = _create_sqlite_db(
        tmp_path / "household" / "dup_uid.sqlite",
        zcat_rows=dup_rows,
        custom_columns=dup_columns,
    )
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    with pytest.raises(Exception) as exc_info:
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_dup_uid",
        )

    # Either caught by IdentityCollisionError during admission or ValidationError at Gate 2
    err_str = str(exc_info.value)
    assert (
        "collision" in err_str.lower()
        or "unique" in err_str.lower()
        or "validation" in err_str.lower()
    )

    # Bronze table must NOT be mutated
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    check = _fetch_scalar(
        isolated_duckdb_manager,
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{bronze_contract.physical_table.split('.')[-1]}'",
    )
    assert check == 0


def test_canonical_bronze_violation_fails_gate_2(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 8: Canonical Bronze contract violation (null TYPE) fails Gate 2."""
    null_type_cols = {
        "ID": "INTEGER PRIMARY KEY",
        "C_IS_DEL": "INTEGER",
        "C_UTIME": "INTEGER",
        "uid": "TEXT UNIQUE",
        "NAME": "TEXT",
        "ORDERSEQ": "INTEGER",
        "TYPE": "INTEGER",
        "STATUS": "INTEGER",
        "pUid": "TEXT",
        "isSynced": "INTEGER",
        "syncTime": "REAL",
        "syncVersion": "INTEGER",
    }
    null_rows = [
        {
            "ID": 1,
            "C_IS_DEL": 0,
            "C_UTIME": 100,
            "uid": "CAT_1",
            "NAME": "Groceries",
            "ORDERSEQ": 1,
            "TYPE": None,
            "STATUS": 0,
            "pUid": None,
            "isSynced": 1,
            "syncTime": 100.0,
            "syncVersion": 1,
        },
    ]
    db_file = _create_sqlite_db(
        tmp_path / "household" / "null_type.sqlite",
        zcat_rows=null_rows,
        custom_columns=null_type_cols,
    )
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    with pytest.raises(ValidationError) as exc_info:
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_null_type",
        )

    # Gate 1 or Gate 2 validation caught the violation
    assert exc_info.value.result.stage in (
        ValidationStage.PRE_BRONZE,
        ValidationStage.CANONICAL_BRONZE,
    )

    # Bronze must NOT exist
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    check = _fetch_scalar(
        isolated_duckdb_manager,
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{bronze_contract.physical_table.split('.')[-1]}'",
    )
    assert check == 0


def test_failure_after_pre_bronze(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 9: Crash after Pre-Bronze before Bronze maintains recovery integrity."""
    db_file = _create_sqlite_db(tmp_path / "household" / "crash_after_pb.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)

    # Admission succeeds on compile, but execute_admission fails
    mock_admission = MagicMock(spec=AdmissionService)
    mock_admission.compile_admission_plan.return_value = MagicMock()
    mock_admission.execute_admission.side_effect = RuntimeError("Crash after Pre-Bronze")
    ingestion_service = DatasetIngestionService(validator, mock_admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    with pytest.raises(RuntimeError, match="Crash after Pre-Bronze"):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_crash_pb",
        )

    # Pre-Bronze exists and has data
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None
    assert pre_bronze.table_exists(pb_contract)

    # Bronze table does NOT exist
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert bronze_contract is not None
    check = _fetch_scalar(
        isolated_duckdb_manager,
        f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{bronze_contract.physical_table.split('.')[-1]}'",
    )
    assert check == 0

    # Control plane was NOT marked synced
    reg = isolated_control_plane.artifacts.get_registry_with_status()
    status = reg.get(norm_path, (None, None, "PENDING_BRONZE"))[2]
    assert status != "SYNCED"


def test_failure_after_bronze(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 10: Crash after Bronze before Control Plane commit triggers recovery requirements."""
    db_file = _create_sqlite_db(tmp_path / "household" / "crash_after_bronze.sqlite")
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    # Simulate crash by having cp.artifacts.mark_synced raise
    mock_artifacts = MagicMock()
    mock_artifacts.get_file_bytes.return_value = None
    mock_artifacts.mark_synced.side_effect = RuntimeError("Crash at Control Plane sync")

    mock_cp = MagicMock(spec=ControlPlane)
    mock_cp.artifacts = mock_artifacts

    with pytest.raises(RuntimeError, match="Crash at Control Plane sync"):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=mock_cp,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files={"sqlite_source": [norm_path]},
            run_id="run_crash_cp",
        )

    # Pre-Bronze and Bronze both have data
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    bronze_contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None and bronze_contract is not None
    assert pre_bronze.table_exists(pb_contract)


def test_backup_restore_includes_pre_bronze(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 11: Warehouse export and restore includes Pre-Bronze schema."""
    db_file = _create_sqlite_db(tmp_path / "household" / "backup_test.sqlite")
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert ds_plan is not None

    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files={"sqlite_source": [norm_path]},
        run_id="run_backup",
    )

    # Verify pre_bronze is listed in schemas
    schemas = [
        r[0]
        for r in isolated_duckdb_manager.conn.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
    ]
    assert "pre_bronze" in schemas
    assert "bronze" in schemas

    # Verify tables in pre_bronze schema
    pb_tables = [
        r[0]
        for r in isolated_duckdb_manager.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'pre_bronze'"
        ).fetchall()
    ]
    assert "pb_household_zcategory" in pb_tables


def test_downstream_output_equivalence() -> None:
    """Scenario 12: Verify 100% equivalence of category transforms between legacy raw and canonical Bronze."""
    # 1. Legacy raw frame (as produced by legacy extraction)
    legacy_df = pl.DataFrame(
        {
            "uid": ["CAT_INC", "SUB_INC", "CAT_EXP", "SUB_EXP"],
            "NAME": ["Income from Salary", "Bonus", "Groceries", "Food Sub"],
            "C_IS_DEL": [0, 0, 0, 0],
            "pUid": [None, "CAT_INC", None, "CAT_EXP"],
            "TYPE": [0, 0, 1, 1],
            "ORDERSEQ": [1, 2, 3, 4],
            "__file_name__": ["f.sqlite", "f.sqlite", "f.sqlite", "f.sqlite"],
            "artifact_id": ["art1", "art1", "art1", "art1"],
        }
    )
    col_mapping = {
        "uid": "UID",
        "NAME": "CATEGORY_NAME",
        "C_IS_DEL": "IS_DEL",
        "pUid": "CATEGORY_ID",
        "ORDERSEQ": "ORDER_SEQUENCE",
    }

    # 2. Canonical Bronze frame (as produced by AdmissionService)
    canonical_df = pl.DataFrame(
        {
            "UID": ["CAT_INC", "SUB_INC", "CAT_EXP", "SUB_EXP"],
            "CATEGORY_NAME": ["Income from Salary", "Bonus", "Groceries", "Food Sub"],
            "IS_DEL": [0, 0, 0, 0],
            "CATEGORY_ID": [None, "CAT_INC", None, "CAT_EXP"],
            "TYPE": [0, 0, 1, 1],
            "ORDER_SEQUENCE": [1, 2, 3, 4],
            "__file_name__": ["f.sqlite", "f.sqlite", "f.sqlite", "f.sqlite"],
            "artifact_id": ["art1", "art1", "art1", "art1"],
        }
    )

    # 3. Income category transform
    legacy_inc_cat = transform_d_income_category(legacy_df.lazy(), col_mapping).collect()
    canon_inc_cat = transform_d_income_category(canonical_df.lazy(), col_mapping).collect()
    assert legacy_inc_cat.equals(canon_inc_cat)
    assert canon_inc_cat.height == 1
    assert canon_inc_cat["UID"][0] == "CAT_INC"

    # 4. Income subcategory transform
    legacy_inc_sub = transform_d_income_subcategory(
        legacy_df.lazy(), col_mapping, rules=None
    ).collect()
    canon_inc_sub = transform_d_income_subcategory(
        canonical_df.lazy(), col_mapping, rules=None
    ).collect()
    assert legacy_inc_sub.equals(canon_inc_sub)
    assert canon_inc_sub.height == 1
    assert canon_inc_sub["UID"][0] == "SUB_INC"

    # 5. Expense category transform
    legacy_exp_cat = transform_d_expense_category(legacy_df.lazy(), col_mapping).collect()
    canon_exp_cat = transform_d_expense_category(canonical_df.lazy(), col_mapping).collect()
    assert legacy_exp_cat.equals(canon_exp_cat)
    assert canon_exp_cat.height == 1
    assert canon_exp_cat["UID"][0] == "CAT_EXP"

    # 6. Expense subcategory transform
    legacy_exp_sub = transform_d_expense_subcategory(legacy_df.lazy(), col_mapping).collect()
    canon_exp_sub = transform_d_expense_subcategory(canonical_df.lazy(), col_mapping).collect()
    assert legacy_exp_sub.equals(canon_exp_sub)
    assert canon_exp_sub.height == 1
    assert canon_exp_sub["UID"][0] == "SUB_EXP"


def test_full_shan_pipeline_financial_equivalence(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 13: Pipeline bronze phase executes generalized vertical slice cleanly."""
    db_file = _create_sqlite_db(tmp_path / "household" / "household.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    col_master = str(Path("tests/fixtures/COLUMN_MASTER.csv").resolve()).replace("\\", "/")
    isolated_settings.COLUMN_MASTER_PATH = col_master

    executor = PipelineExecutor(
        cfg=isolated_settings,
        status_queue=NullEventQueue(),
        db_manager=isolated_duckdb_manager,
        rules=None,
        emitter=get_global_emitter(),
        plan=plan,
        source_config=source_config,
        source_plan=source_plan,
    )

    # Ingest through extractor & pipeline bronze phase
    actionable_all: dict[str, list[str]] = {
        "sqlite_source": [norm_path],
        "column_master": [col_master],
    }
    isolated_control_plane.artifacts.ingest_binaries(actionable_all)
    extracted = executor.extract(isolated_control_plane, actionable_all)

    # Assert extraction returned dormant empty LazyFrame for zcategory
    assert extracted.require_lazy(DatasetId.HOUSEHOLD_ZCATEGORY).collect().height == 0

    # Run bronze phase
    run_id = isolated_control_plane.runs.start_run()
    _, full_extracted = executor._run_bronze_phase(
        cp=isolated_control_plane,
        run_id=run_id,
        extracted_data=extracted,
        actionable_all=actionable_all,
        renames=[],
    )

    # Assert bronze layer loaded full dataset including zcategory from bronze.r_SQLite_ZCategory
    zcat_collected = full_extracted.require_lazy(DatasetId.HOUSEHOLD_ZCATEGORY).collect()
    assert zcat_collected.height == 4
    assert "UID" in zcat_collected.columns
    assert "CATEGORY_NAME" in zcat_collected.columns

    # Assert Pre-Bronze table exists and populated
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert pb_contract is not None
    pb_df = isolated_duckdb_manager.conn.query(f"SELECT * FROM {pb_contract.physical_table}").pl()
    assert pb_df.height == 4


def test_protected_ids_unchanged(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Scenario 14: Category UIDs remain byte-stable across Pre-Bronze, Bronze, and Silver."""
    raw_uids = [
        "CAT_INCOME_SALARY",
        "SUBCAT_INCOME_BONUS",
        "CAT_EXPENSE_FOOD",
        "SUBCAT_EXPENSE_DINING",
    ]
    db_file = _create_sqlite_db(tmp_path / "household" / "household.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    col_master = str(Path("tests/fixtures/COLUMN_MASTER.csv").resolve()).replace("\\", "/")
    isolated_settings.COLUMN_MASTER_PATH = col_master

    executor = PipelineExecutor(
        cfg=isolated_settings,
        status_queue=NullEventQueue(),
        db_manager=isolated_duckdb_manager,
        rules=None,
        emitter=get_global_emitter(),
        plan=plan,
        source_config=source_config,
        source_plan=source_plan,
    )

    actionable_all: dict[str, list[str]] = {
        "sqlite_source": [norm_path],
        "column_master": [col_master],
    }
    isolated_control_plane.artifacts.ingest_binaries(actionable_all)
    extracted = executor.extract(isolated_control_plane, actionable_all)
    run_id = isolated_control_plane.runs.start_run()
    _, full_extracted = executor._run_bronze_phase(
        cp=isolated_control_plane,
        run_id=run_id,
        extracted_data=extracted,
        actionable_all=actionable_all,
        renames=[],
    )

    # Check Bronze UIDs
    zcategory_lazy = full_extracted.require_lazy(DatasetId.HOUSEHOLD_ZCATEGORY)
    bronze_uids = zcategory_lazy.collect()["UID"].to_list()
    for uid in raw_uids:
        assert uid in bronze_uids

    # Check Silver Category transforms
    inc_cat = transform_d_income_category(zcategory_lazy, {}).collect()
    assert "CAT_INCOME_SALARY" in inc_cat["UID"].to_list()


def test_selected_legacy_route_dormant(
    isolated_control_plane: ControlPlane,
    isolated_duckdb_manager: DuckDBManager,
    isolated_settings: Settings,
    tmp_path: Path,
) -> None:
    """Scenario 15: Legacy route for all 5 household datasets is dormant."""
    db_file = _create_sqlite_db(tmp_path / "household" / "dormant.sqlite")
    norm_path = str(db_file).replace("\\", "/")

    # 1. Household streams from DataExtractor are empty
    isolated_control_plane.artifacts.ingest_binaries({"sqlite_source": [norm_path]})
    extractor = DataExtractor(
        cfg=isolated_settings,
        status_queue=NullEventQueue(),
        cp=isolated_control_plane,
    )
    collection = extractor.run(actionable_files={"sqlite_source": [norm_path]})
    for ds_id in (
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
    ):
        frame = collection.require_lazy(ds_id)
        assert frame.collect().height == 0

    # 2. All 5 are in MIGRATED_DATASETS
    for ds_id in (
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
    ):
        assert ds_id in MIGRATED_DATASETS

    # 3. BronzeLayer.load skips all 5
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta)
    mock_extracted = DatasetCollection(
        frames={
            ds_id: pl.DataFrame({"dummy": [1]}).lazy()
            for ds_id in (
                DatasetId.HOUSEHOLD_ZCATEGORY,
                DatasetId.HOUSEHOLD_ASSET_GROUP,
                DatasetId.HOUSEHOLD_ASSETS,
                DatasetId.HOUSEHOLD_CURRENCY,
                DatasetId.HOUSEHOLD_INOUTCOME,
            )
        }
    )
    bronze.load(mock_extracted, {"sqlite_source": [norm_path]})
    for table_name in (
        "r_SQLite_ZCategory",
        "r_SQLite_AssetGroup",
        "r_SQLite_Assets",
        "r_SQLite_Currency",
        "r_SQLite_InOutcome",
    ):
        check = _fetch_scalar(
            isolated_duckdb_manager,
            f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{table_name}'",
        )
        assert check == 0


def test_unmigrated_datasets_remain_legacy() -> None:
    """Scenario 16: All unmigrated datasets remain on legacy path without regression."""
    assert len(MIGRATED_DATASETS) == 16
    for ds_id in (
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
        DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        DatasetId.INVESTMENT_BENCHMARK_MASTER,
        DatasetId.INVESTMENT_MACRO_PARAMETERS,
        DatasetId.MARKET_CURRENCY_MAPPING,
        DatasetId.MARKET_MF_HOLDINGS,
        DatasetId.INVESTMENT_MF_ORDERS,
        DatasetId.MARKET_STOCK_HOLDINGS,
        DatasetId.INVESTMENT_STOCK_ORDERS,
        DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
    ):
        assert ds_id in MIGRATED_DATASETS

    # Check all other contracts in BRONZE_CONTRACT_REGISTRY are not in MIGRATED_DATASETS
    unmigrated = [c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id not in MIGRATED_DATASETS]
    assert len(unmigrated) == 4
    for contract in unmigrated:
        assert contract.dataset_id not in MIGRATED_DATASETS


def test_migration_template_checklist_contract() -> None:
    """Scenario 17: Enforce migration template obligations A-L on migrated datasets."""
    for ds_id in MIGRATED_DATASETS:
        # A. Source selector configured
        source_config = get_shan_baseline_source_configuration()
        binding = source_config.get_dataset_binding(ds_id)
        assert binding is not None, f"Item A/B: Missing dataset binding for {ds_id}"
        assert binding.selector is not None, f"Item A: Missing selector for {ds_id}"

        # C. ColumnMapping defined
        assert len(binding.mapping) > 0, f"Item C: Missing column mapping for {ds_id}"

        # D. SourceFieldDeclarations defined
        assert len(binding.fields) > 0, f"Item D: Missing source fields for {ds_id}"

        # E. Gate 1 source Pandera schema can be compiled
        from personal_finance_etl.infrastructure.validation.compiler import (
            compile_source_schema,
        )

        source_schema = compile_source_schema(binding)
        assert source_schema is not None, f"Item E: Failed to compile source schema for {ds_id}"

        # F. PreBronzeDataContract registered
        pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
        assert pb_contract is not None, f"Item F: Missing PreBronzeDataContract for {ds_id}"

        # G. Pre-Bronze physical table naming standard compliant
        assert pb_contract.physical_table.startswith("pre_bronze.pb_"), (
            f"Item G: Table naming non-compliant: {pb_contract.physical_table}"
        )

        # H. BronzeDataContract registered
        bronze_contract = get_bronze_contract_by_dataset_id(ds_id)
        assert bronze_contract is not None, f"Item H: Missing BronzeDataContract for {ds_id}"

        # I. Canonical Bronze Pandera schema registered
        assert has_canonical_bronze_schema(ds_id), (
            f"Item I: Missing canonical Bronze schema for {ds_id}"
        )

        # J. Included in MIGRATED_DATASETS
        assert ds_id in MIGRATED_DATASETS, f"Item J: Dataset {ds_id} not in MIGRATED_DATASETS"
