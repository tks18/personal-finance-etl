"""Unit and integration tests for Pre-Bronze state upgrade, recovery, and backup.

Validates that legacy DatasetId-keyed Pre-Bronze tables are safely detected and upgraded
to binding-keyed tables without data loss from Control Plane, that split-commit failure
injection rolls back cleanly, and that backup and restore round-trips preserve binding tables.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.contracts.sources import SourceBindingId, SourceId
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PreBronzeDataContract,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer


@pytest.fixture
def pre_bronze_warehouse(
    tmp_path: Path,
) -> tuple[DuckDBManager, PreBronzeLayer]:
    """Fixture providing an isolated DuckDB manager and PreBronzeLayer."""
    db_path = str(tmp_path / "test_upgrade_recovery.duckdb")
    db_mgr = DuckDBManager(db_path)
    db_mgr.open()
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS pre_bronze")
    pb_layer = PreBronzeLayer(db_mgr)
    return db_mgr, pb_layer


def test_detect_and_upgrade_legacy_pre_bronze_tables(
    pre_bronze_warehouse: tuple[DuckDBManager, PreBronzeLayer],
) -> None:
    """Verify that detect_and_upgrade_legacy_tables drops unpartitioned tables for rebuild."""
    db_mgr, pb_layer = pre_bronze_warehouse

    # Create a legacy table without double-underscore binding separator
    db_mgr.conn.execute("CREATE TABLE pre_bronze.household_zcategory (id INT, name VARCHAR)")
    db_mgr.conn.execute("INSERT INTO pre_bronze.household_zcategory VALUES (1, 'Income')")

    # Create a modern binding-keyed table with double-underscore separator
    db_mgr.conn.execute(
        "CREATE TABLE pre_bronze.sqlite_source__household_zcategory (id INT, name VARCHAR)"
    )
    db_mgr.conn.execute(
        "INSERT INTO pre_bronze.sqlite_source__household_zcategory VALUES (2, 'Expense')"
    )

    # Execute upgrade detection
    dropped_tables = pb_layer.detect_and_upgrade_legacy_tables()

    # The legacy table must have been dropped
    assert "pre_bronze.household_zcategory" in dropped_tables
    assert not pb_layer.table_exists("pre_bronze.household_zcategory")

    # The modern binding-keyed table must remain untouched
    assert pb_layer.table_exists("pre_bronze.sqlite_source__household_zcategory")
    res = db_mgr.conn.execute(
        "SELECT count(*) FROM pre_bronze.sqlite_source__household_zcategory"
    ).fetchone()
    assert res is not None and res[0] == 1


def test_pre_bronze_transaction_rollback_on_failure(
    pre_bronze_warehouse: tuple[DuckDBManager, PreBronzeLayer],
) -> None:
    """Verify transaction rollback leaves Pre-Bronze clean if an operation fails mid-flight."""
    db_mgr, pb_layer = pre_bronze_warehouse
    binding_id = SourceBindingId("alpha_source__orders")
    contract = PreBronzeDataContract(
        binding_id=binding_id,
        physical_table=f"pre_bronze.{binding_id}",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )

    initial_df = pl.DataFrame({"order_id": ["O100"], "amount": [150.0]})
    pb_layer.write_incremental(
        contract, initial_df, artifact_id="art_init", source_id=SourceId("alpha")
    )
    assert pb_layer.read(binding_id).height == 1

    # Simulate transactional failure during a subsequent write batch
    db_mgr.conn.execute("BEGIN TRANSACTION")
    failed = False
    try:
        failing_df = pl.DataFrame({"order_id": ["O101"], "amount": [250.0]})
        pb_layer.write_incremental(
            contract, failing_df, artifact_id="art_fail", source_id=SourceId("alpha")
        )
        raise RuntimeError("Simulated crash before commit")
    except RuntimeError:
        db_mgr.conn.execute("ROLLBACK")
        failed = True

    assert failed is True
    # The rolled back row must not be present in the table
    remaining = pb_layer.read(binding_id)
    assert remaining.height == 1
    assert remaining["order_id"].to_list() == ["O100"]


def test_pre_bronze_backup_restore_round_trip(
    tmp_path: Path,
) -> None:
    """Verify backup and restore round-trip reproduces binding-keyed Pre-Bronze state exactly."""
    db_path = str(tmp_path / "orig_warehouse.duckdb")
    db_mgr = DuckDBManager(db_path)
    db_mgr.open()
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS pre_bronze")
    pb_layer = PreBronzeLayer(db_mgr)

    binding_id = SourceBindingId("backup_source__dataset_x")
    contract = PreBronzeDataContract(
        binding_id=binding_id,
        physical_table=f"pre_bronze.{binding_id}",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    sample_df = pl.DataFrame({"key": [1, 2, 3], "value": ["a", "b", "c"]})
    pb_layer.write_incremental(
        contract, sample_df, artifact_id="art_backup_1", source_id=SourceId("backup_source")
    )

    # Export table to Parquet backup file
    backup_file = str(tmp_path / "backup_table.parquet")
    db_mgr.conn.execute(f"COPY pre_bronze.{binding_id} TO '{backup_file}' (FORMAT PARQUET)")
    db_mgr.close()

    # Restore into a fresh warehouse database
    restored_db_path = str(tmp_path / "restored_warehouse.duckdb")
    restored_mgr = DuckDBManager(restored_db_path)
    restored_mgr.open()
    restored_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS pre_bronze")
    restored_mgr.conn.execute(
        f"CREATE TABLE pre_bronze.{binding_id} AS SELECT * FROM read_parquet('{backup_file}')"
    )
    restored_pb_layer = PreBronzeLayer(restored_mgr)

    restored_df = restored_pb_layer.read(binding_id, include_provenance=True)
    assert restored_df.height == 3
    assert restored_df["key"].to_list() == [1, 2, 3]
    restored_mgr.close()
