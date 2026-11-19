"""Integration and unit tests verifying artifact-key operational provenance cutover for Phase 037.

Owns
----
- Dual-run row ownership equivalence proving artifact_id identifies identical rows to filename.
- Changed-artifact deletion and replacement strictly through artifact_id.
- Rename identity migration updating artifact_id across Pre-Bronze and Bronze without filename rewrite.
- Meta healing operational consistency using artifact_id without filename predicates.
- Rollback and recovery convergence during simulated partial mutation.

Does not own
-------------
- Architecture boundary assertions (owned by tests.architecture.test_bronze_canonical_guards).
- Pure financial calculation verification (owned by tests.domain).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    get_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta.healing import DuckDBRegistryHealer
from personal_finance_etl.infrastructure.warehouse.meta.layer import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    get_pre_bronze_contract_by_dataset_id,
)


@pytest.fixture
def temp_duckdb(tmp_path: Path) -> DuckDBManager:
    """Provide a fresh DuckDBManager with initialized schemas and strict Bronze tables.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory fixture.

    Returns
    -------
    DuckDBManager
        Initialized warehouse manager connected to temp database.
    """
    db_file = tmp_path / "test_cutover.duckdb"
    manager = DuckDBManager(str(db_file))
    manager.open()
    manager.ensure_schemas()
    return manager


def _create_sample_raw_frame(artifact_id: str, count: int = 3) -> pl.DataFrame:
    """Create a sample raw source frame with canonical fields and artifact_id.

    Parameters
    ----------
    artifact_id : str
        Authoritative artifact identifier.
    count : int, default=3
        Number of rows to generate.

    Returns
    -------
    pl.DataFrame
        Source DataFrame ready for admission.
    """
    return pl.DataFrame(
        {
            "ZUID": [f"CAT_{i:03d}" for i in range(count)],
            "Z_PK": list(range(1, count + 1)),
            "ZNAME": [f"Category_{i}" for i in range(count)],
            "ZKIND": [1] * count,
            "ZISDEL": [0] * count,
            "ZMODIFY_DATE": [1700000000 + i for i in range(count)],
            "ZORDER": list(range(1, count + 1)),
            "ZSTATUS": [0] * count,
            "ZCAT_ID": [f"cat_{i}" for i in range(count)],
            "ZSYNCED": [1] * count,
            "ZSYNCTIME": [1700000000.0] * count,
            "ZSYNCVER": [1] * count,
            "artifact_id": [artifact_id] * count,
            "__file_name__": ["sample.sqlite"] * count,
            "__folder_path__": ["inputs/db"] * count,
        }
    )


def test_dual_run_ownership_equivalence(temp_duckdb: DuckDBManager) -> None:
    """Prove that artifact_id identifies the exact same rows as legacy filename predicates."""
    ds_id = DatasetId.HOUSEHOLD_ZCATEGORY
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    file_path = "inputs/db/sample_1.sqlite"
    art_id = generate_file_id(file_path)

    raw_source = _create_sample_raw_frame(art_id, count=4)

    # Normalize and admit frame
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
    admission = AdmissionService()
    plan = admission.compile_admission_plan(
        ds_config, bronze_contract, raw_source.columns, id_column="UID"
    )
    admitted = admission.execute_admission(plan, raw_source).collect()

    schema = get_canonical_bronze_schema(ds_id)
    validated = schema.validate(admitted)

    bronze = BronzeLayer(temp_duckdb, None, None)  # type: ignore[arg-type]
    counts = bronze.upsert_table(
        df=validated,
        table_name=bronze_contract.physical_table,
        actionable_files=[file_path],
        full_replace=False,
    )
    assert counts.get(art_id) == 4
    assert counts.get("sample_1.sqlite") == 4

    # Verify query by artifact_id matches all 4 rows
    rows_by_art = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [art_id],
    ).fetchone()
    assert rows_by_art is not None
    assert rows_by_art[0] == 4


def test_changed_artifact_replacement_by_artifact_id(temp_duckdb: DuckDBManager) -> None:
    """Verify that updating an artifact deletes old rows and inserts new rows strictly by artifact_id."""
    ds_id = DatasetId.HOUSEHOLD_ZCATEGORY
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    file_path = "inputs/db/sample_change.sqlite"
    art_id = generate_file_id(file_path)

    # Ingest initial 3 rows
    raw_v1 = _create_sample_raw_frame(art_id, count=3)
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
    admission = AdmissionService()
    plan = admission.compile_admission_plan(
        ds_config, bronze_contract, raw_v1.columns, id_column="UID"
    )
    admitted_v1 = admission.execute_admission(plan, raw_v1).collect()

    bronze = BronzeLayer(temp_duckdb, None, None)  # type: ignore[arg-type]
    bronze.upsert_table(
        df=admitted_v1,
        table_name=bronze_contract.physical_table,
        actionable_files=[file_path],
        full_replace=False,
    )

    count_v1 = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [art_id],
    ).fetchone()
    assert count_v1 is not None and count_v1[0] == 3

    # Now change content: version 2 has 5 rows
    raw_v2 = _create_sample_raw_frame(art_id, count=5)
    admitted_v2 = admission.execute_admission(plan, raw_v2).collect()

    bronze.upsert_table(
        df=admitted_v2,
        table_name=bronze_contract.physical_table,
        actionable_files=[file_path],
        full_replace=False,
    )

    # Old 3 rows must be deleted, replaced by new 5 rows
    count_v2 = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [art_id],
    ).fetchone()
    assert count_v2 is not None and count_v2[0] == 5


def test_rename_migrates_artifact_id_without_filename_rewrite(temp_duckdb: DuckDBManager) -> None:
    """Verify that file rename migrates artifact_id without modifying or requiring filename."""
    ds_id = DatasetId.HOUSEHOLD_ZCATEGORY
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
    assert pb_contract is not None

    old_path = "inputs/db/old_name.sqlite"
    new_path = "inputs/db/renamed_target.sqlite"
    old_id = generate_file_id(old_path)
    new_id = generate_file_id(new_path)

    raw_frame = _create_sample_raw_frame(old_id, count=2)

    # 1. Pre-Bronze write
    pb_layer = PreBronzeLayer(temp_duckdb)
    pb_layer.write_incremental(contract=pb_contract, df=raw_frame, artifact_id=old_id)

    # 2. Bronze write
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
    admission = AdmissionService()
    plan = admission.compile_admission_plan(
        ds_config, bronze_contract, raw_frame.columns, id_column="UID"
    )
    admitted = admission.execute_admission(plan, raw_frame).collect()

    bronze = BronzeLayer(temp_duckdb, None, None)  # type: ignore[arg-type]
    bronze.upsert_table(
        df=admitted,
        table_name=bronze_contract.physical_table,
        actionable_files=[old_path],
        full_replace=False,
    )

    # 3. Execute identity migration
    renames = [(old_path, new_path, ds_id.value)]
    bronze.migrate_identity(renames)
    pb_layer.migrate_artifact_identity(old_id, new_id, pb_contract)

    # Verify Bronze has new_id and 0 rows for old_id
    b_new = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [new_id],
    ).fetchone()
    assert b_new is not None and b_new[0] == 2

    b_old = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [old_id],
    ).fetchone()
    assert b_old is not None and b_old[0] == 0

    # Verify Pre-Bronze has new_id
    pb_new = temp_duckdb.conn.execute(
        f"SELECT count(*) FROM {pb_contract.physical_table} WHERE __artifact_id__ = ?",
        [new_id],
    ).fetchone()
    assert pb_new is not None and pb_new[0] == 2


def test_meta_healing_pruning_and_sync_by_artifact_id(
    temp_duckdb: DuckDBManager,
    isolated_control_plane: ControlPlane,
    isolated_settings: Settings,
) -> None:
    """Verify that MetaHealingService uses artifact_id to detect missing rows and prune unregistered files."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    ds_id = DatasetId.HOUSEHOLD_ZCATEGORY
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    file_path = "inputs/db/heal_test.sqlite"
    file_id = generate_file_id(file_path)

    raw_frame = _create_sample_raw_frame(file_id, count=3)
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
    admission = AdmissionService()
    plan = admission.compile_admission_plan(
        ds_config, bronze_contract, raw_frame.columns, id_column="UID"
    )
    admitted = admission.execute_admission(plan, raw_frame).collect()

    pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
    assert pb_contract is not None
    pb_layer = PreBronzeLayer(temp_duckdb)
    pb_layer.write_incremental(contract=pb_contract, df=raw_frame, artifact_id=file_id)

    meta_layer = MetaLayer(temp_duckdb, isolated_settings, None)
    bronze = BronzeLayer(temp_duckdb, isolated_control_plane, meta_layer)
    bronze.upsert_table(
        df=admitted,
        table_name=bronze_contract.physical_table,
        actionable_files=[file_path],
        full_replace=False,
    )

    # Register in control plane as SYNCED
    isolated_control_plane.artifacts.db.conn.execute(
        """
        INSERT INTO cp_file_registry 
        (file_id, file_name, relative_path, file_category, file_hash, sync_status, first_seen_at, last_seen_at)
        VALUES (?, 'heal_test.sqlite', ?, ?, 'hash_123', 'SYNCED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        [file_id, file_path, ds_id.value],
    )
    meta_layer.register_file(file_path, ds_id.value, 3, isolated_control_plane)

    # Healing with matching artifact_id does not trigger any re-queuing or pruning
    healer = DuckDBRegistryHealer(temp_duckdb.conn)
    healer.heal_duckdb_registry(isolated_control_plane)

    status_row = isolated_control_plane.artifacts.db.conn.execute(
        "SELECT sync_status FROM cp_file_registry WHERE file_id = ?",
        [file_id],
    ).fetchone()
    assert status_row is not None and status_row[0] == "SYNCED"

    # Now simulate dropped Bronze table: drop table
    temp_duckdb.conn.execute(f"DROP TABLE {bronze_contract.physical_table}")

    # Healing should detect dropped table and re-queue file to PENDING_BRONZE
    healer.heal_duckdb_registry(isolated_control_plane)

    requeued_row = isolated_control_plane.artifacts.db.conn.execute(
        "SELECT sync_status FROM cp_file_registry WHERE file_id = ?",
        [file_id],
    ).fetchone()
    assert requeued_row is not None and requeued_row[0] == "PENDING_BRONZE"


def test_meta_healing_incremental_dropped_artifact_rows_requeued(
    temp_duckdb: DuckDBManager,
    isolated_control_plane: ControlPlane,
    isolated_settings: Settings,
) -> None:
    """Verify that MetaHealing detects dropped rows by artifact_id in incremental tables and re-queues."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    ds_id = DatasetId.INVESTMENT_STOCK_ORDERS
    bronze_contract = next(c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == ds_id)
    assert bronze_contract.is_full_replace is False

    pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
    assert pb_contract is not None

    file_path = "inputs/orders/stock_orders_jan.xlsx"
    file_id = generate_file_id(file_path)

    # Insert rows into Pre-Bronze and Bronze with artifact_id
    raw_frame = pl.DataFrame(
        {
            "Stock name": ["Reliance"],
            "Symbol": ["RELIANCE"],
            "ISIN": ["INE002A01018"],
            "Type": ["BUY"],
            "Quantity": [10],
            "Value": [25000.0],
            "Exchange": ["NSE"],
            "Exchange Order Id": ["ORD_123"],
            "Execution date and time": ["2026-01-15 10:00:00"],
            "Order status": ["COMPLETE"],
            "__file_category__": ["stock_orders"],
            "artifact_id": [file_id],
        }
    )
    pb_layer = PreBronzeLayer(temp_duckdb)
    pb_layer.write_incremental(contract=pb_contract, df=raw_frame, artifact_id=file_id)

    meta_layer = MetaLayer(temp_duckdb, isolated_settings, None)
    bronze = BronzeLayer(temp_duckdb, isolated_control_plane, meta_layer)
    bronze.upsert_table(
        df=raw_frame,
        table_name=bronze_contract.physical_table,
        actionable_files=[file_path],
        full_replace=False,
    )

    # Register in control plane as SYNCED
    isolated_control_plane.artifacts.db.conn.execute(
        """
        INSERT INTO cp_file_registry 
        (file_id, file_name, relative_path, file_category, file_hash, sync_status, first_seen_at, last_seen_at)
        VALUES (?, 'stock_orders_jan.xlsx', ?, 'stock_orders', 'hash_orders', 'SYNCED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        [file_id, file_path],
    )
    meta_layer.register_file(file_path, "stock_orders", 1, isolated_control_plane)

    # Verify initial healing passes cleanly
    healer = DuckDBRegistryHealer(temp_duckdb.conn)
    healer.heal_duckdb_registry(isolated_control_plane)

    status_row = isolated_control_plane.artifacts.db.conn.execute(
        "SELECT sync_status FROM cp_file_registry WHERE file_id = ?",
        [file_id],
    ).fetchone()
    assert status_row is not None and status_row[0] == "SYNCED"

    # Now delete rows matching artifact_id from incremental Bronze table
    temp_duckdb.conn.execute(
        f"DELETE FROM {bronze_contract.physical_table} WHERE artifact_id = ?",
        [file_id],
    )

    # Healing must detect artifact_id missing from table and re-queue to PENDING_BRONZE
    healer.heal_duckdb_registry(isolated_control_plane)

    requeued_row = isolated_control_plane.artifacts.db.conn.execute(
        "SELECT sync_status FROM cp_file_registry WHERE file_id = ?",
        [file_id],
    ).fetchone()
    assert requeued_row is not None and requeued_row[0] == "PENDING_BRONZE"
