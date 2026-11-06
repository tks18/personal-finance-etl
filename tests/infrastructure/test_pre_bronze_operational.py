"""Pre-Bronze warehouse operational, recovery, and backup integration test suite.

Owns
----
- Verification of coordinated backup and restore round-trip preserving Pre-Bronze state.
- Transaction failure and rollback tests proving zero partial mutation in Pre-Bronze.
- Split-commit RECOVERY_REQUIRED simulation and convergence proofs.
- Meta layer publishing verification for Pre-Bronze contracts and table metrics.
- Artifact-keyed healing tests verifying removal of Pre-Bronze rows via __artifact_id__.
- Orphan table cleanup guard asserting contracted Pre-Bronze tables are preserved.
- Architecture guard verifying centralized warehouse schema enumerations.
- Backward compatibility tests asserting pre-v9.9.0 legacy databases initialize additively.

Does not own
-------------
- Production pipeline orchestration (owned by tests.application.test_forensic_pipeline).
- Low-level Pre-Bronze persistence mechanics (owned by tests.infrastructure.test_pre_bronze_persistence).
- Pure contract model unit tests (owned by tests.contracts.test_datasets).
"""

from __future__ import annotations

import os
import tempfile

import duckdb
import polars as pl

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.recovery import RestoreOutcome, SnapshotOutcome
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager
from personal_finance_etl.infrastructure.recovery.restore import SnapshotRestorer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    MANAGED_WAREHOUSE_SCHEMAS,
    PERSISTED_DATA_SCHEMAS,
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_CONTRACT_REGISTRY,
    PreBronzeDataContract,
    WarehouseLayer,
)
from personal_finance_etl.infrastructure.warehouse.meta.healing import DuckDBRegistryHealer
from personal_finance_etl.infrastructure.warehouse.meta.layer import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer


def test_pre_bronze_backup_restore_round_trip() -> None:
    """Verify coordinated backup and restore preserves Pre-Bronze tables and provenance."""
    with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
        # 1. Initialize source environment
        db_mgr = DuckDBManager(source_dir, "Personal_Finance_DB.duckdb")
        db_mgr.open()
        db_mgr.ensure_schemas()

        cp = ControlPlane(source_dir, "Raw_Documents.sqlite")
        cp.open()
        cp.ensure_schema()

        # 2. Persist Pre-Bronze state
        pb_layer = PreBronzeLayer(db_mgr)
        contract_hh = PreBronzeDataContract(
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            physical_table="pre_bronze.pb_household_zcategory",
            sync_strategy=SyncStrategy.FULL_REPLACE,
        )
        df_hh = pl.DataFrame({"cat_id": [1, 2, 3], "cat_name": ["Income", "Expense", "Transfer"]})
        pb_layer.write_full_replace(
            contract_hh, df_hh, artifact_id="art_hh_001", source_id=SourceId("sqlite_hh")
        )

        contract_stock = PreBronzeDataContract(
            dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
            physical_table="pre_bronze.pb_investment_stock_orders",
            sync_strategy=SyncStrategy.INCREMENTAL,
        )
        df_stock = pl.DataFrame({"order_id": ["O1", "O2"], "symbol": ["TCS", "INFY"]})
        pb_layer.write_incremental(
            contract_stock, df_stock, artifact_id="art_stock_002", source_id=SourceId("zerodha")
        )

        # Flush DuckDB and close connection before snapshot
        db_mgr.close()
        cp.close()

        # 3. Create coordinated snapshot archive
        backup_mgr = SystemBackupManager(source_dir)
        snapshot_res = backup_mgr.create_snapshot()
        assert snapshot_res.outcome == SnapshotOutcome.SNAPSHOT_PUBLISHED
        assert snapshot_res.zip_path is not None
        assert os.path.isfile(snapshot_res.zip_path)

        # 4. Restore snapshot into clean target directory
        restorer = SnapshotRestorer(
            base_path=target_dir,
            sqlite_path=os.path.join(target_dir, "Raw_Documents.sqlite"),
            duckdb_path=os.path.join(target_dir, "Personal_Finance_DB.duckdb"),
        )
        restore_res = restorer.restore_snapshot(snapshot_res.zip_path)
        assert restore_res.outcome == RestoreOutcome.RESTORE_SUCCEEDED

        # 5. Connect to restored DuckDB and verify Pre-Bronze state
        restored_db_mgr = DuckDBManager(target_dir, "Personal_Finance_DB.duckdb")
        restored_db_mgr.open()
        restored_pb_layer = PreBronzeLayer(restored_db_mgr)

        res_hh = restored_pb_layer.read(contract_hh.dataset_id, include_provenance=True)
        assert res_hh.height == 3
        assert res_hh["cat_id"].to_list() == [1, 2, 3]
        assert res_hh[PRE_BRONZE_ARTIFACT_ID].to_list() == ["art_hh_001"] * 3

        res_stock = restored_pb_layer.read(contract_stock.dataset_id, include_provenance=True)
        assert res_stock.height == 2
        assert res_stock["order_id"].to_list() == ["O1", "O2"]
        assert res_stock[PRE_BRONZE_ARTIFACT_ID].to_list() == ["art_stock_002"] * 2

        restored_db_mgr.close()


def test_pre_bronze_failure_and_transaction_rollback(
    isolated_duckdb_manager: DuckDBManager,
) -> None:
    """Verify DuckDB rollback removes uncommitted Pre-Bronze mutations without partial state."""
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()
    pb_layer = PreBronzeLayer(isolated_duckdb_manager)

    contract = PreBronzeDataContract(
        dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        physical_table="pre_bronze.pb_household_assets",
        sync_strategy=SyncStrategy.FULL_REPLACE,
    )
    df = pl.DataFrame({"asset_id": [101, 102], "asset_name": ["Checking", "Savings"]})

    # Start explicit transaction
    isolated_duckdb_manager.conn.execute("BEGIN TRANSACTION")
    pb_layer.write_full_replace(contract, df, artifact_id="art_tx_fail")
    assert pb_layer.table_exists(contract)
    assert pb_layer.read(contract.dataset_id).height == 2

    # Simulate deliberate error and rollback
    isolated_duckdb_manager.conn.execute("ROLLBACK")

    # Table must be rolled back completely
    assert not pb_layer.table_exists(contract)
    assert pb_layer.read(contract.dataset_id).height == 0


def test_pre_bronze_split_commit_recovery_convergence(
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    isolated_settings: Settings,
) -> None:
    """Verify split-commit recovery marks RECOVERY_REQUIRED and converges on next run."""
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()

    # 1. Simulate DuckDB commit with Pre-Bronze writes
    pb_layer = PreBronzeLayer(isolated_duckdb_manager)
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df = pl.DataFrame({"order_id": ["S1"], "symbol": ["WIPRO"]})

    isolated_duckdb_manager.conn.execute("BEGIN TRANSACTION")
    pb_layer.write_incremental(contract, df, artifact_id="split_commit_art")
    isolated_duckdb_manager.conn.execute("COMMIT")

    # 2. Simulate SQLite Control Plane commit failure
    split_run_id = isolated_control_plane.runs.start_run()
    isolated_control_plane.runs.mark_recovery_required(
        split_run_id,
        error_message="Simulated SQLite commit crash after DuckDB commit",
        stage="COMMIT",
    )

    # Verify run is marked RECOVERY_REQUIRED
    pending = isolated_control_plane.runs.get_recovery_required_runs()
    assert split_run_id in pending

    # 3. Simulate subsequent recovery run: Meta healing reconciles and converges
    meta_layer = MetaLayer(isolated_duckdb_manager, isolated_settings)
    meta_layer.heal_duckdb_registry(isolated_control_plane)

    # Mark prior run converged upon successful completion of subsequent run
    reconciling_run_id = isolated_control_plane.runs.start_run()
    isolated_control_plane.runs.mark_recovery_converged(
        recovered_run_id=split_run_id,
        reconciling_run_id=reconciling_run_id,
    )

    # Verify no more pending recovery runs remain
    remaining_pending = isolated_control_plane.runs.get_recovery_required_runs()
    assert split_run_id not in remaining_pending


def test_pre_bronze_meta_catalog_publishing(
    isolated_pre_bronze_layer: PreBronzeLayer,
    isolated_duckdb_manager: DuckDBManager,
    isolated_settings: Settings,
) -> None:
    """Verify Pre-Bronze contracts and table metrics are published into Meta layer."""
    # Write Pre-Bronze table
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df = pl.DataFrame({"order_id": ["O1", "O2", "O3"], "symbol": ["A", "B", "C"]})
    isolated_pre_bronze_layer.write_incremental(contract, df, artifact_id="art_meta_test")

    # Execute MetaLayer load
    meta_layer = MetaLayer(isolated_duckdb_manager, isolated_settings)
    meta_layer.load(dfs={})

    # Verify m_Data_Contracts contains pre_bronze contracts
    pb_contracts = isolated_duckdb_manager.conn.execute(
        "SELECT contract_id, layer, physical_table, is_full_replace "
        "FROM meta.m_Data_Contracts WHERE layer = 'pre_bronze'"
    ).fetchall()
    assert len(pb_contracts) == len(PRE_BRONZE_CONTRACT_REGISTRY)

    # Verify m_Table_Row_Counts records pre_bronze table metrics
    row_counts = isolated_duckdb_manager.conn.execute(
        "SELECT schema_name, table_name, row_count "
        "FROM meta.m_Table_Row_Counts WHERE schema_name = 'pre_bronze'"
    ).fetchall()
    assert len(row_counts) > 0
    pb_metric = next(r for r in row_counts if r[1] == "pb_investment_stock_orders")
    assert pb_metric[2] == 3


def test_pre_bronze_meta_healing_with_artifact_provenance(
    isolated_pre_bronze_layer: PreBronzeLayer,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
) -> None:
    """Verify DuckDBRegistryHealer prunes Pre-Bronze rows via __artifact_id__ when file is deleted."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()

    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df = pl.DataFrame({"order_id": ["D1", "D2"], "symbol": ["TCS", "INFY"]})
    orphan_artifact_id = "orphan_art_sha_999"

    # 1. Write rows into Pre-Bronze table
    isolated_pre_bronze_layer.write_incremental(contract, df, artifact_id=orphan_artifact_id)
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 2

    # 2. Register file in DuckDB meta.m_File_Registry
    isolated_duckdb_manager.conn.execute(
        """
        INSERT INTO meta.m_File_Registry (
            file_id, file_name, relative_path, file_category, file_type,
            file_hash, file_size_bytes, first_ingested, last_ingested, row_count
        ) VALUES (?, 'orphan.csv', 'Statements/Orders/orphan.csv', 'stock_orders', 'csv', 'hash123', 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 2)
        """,
        [orphan_artifact_id],
    )

    # Note: SQLite cp_file_registry does NOT contain this file (simulating deletion/pruning)
    healer = DuckDBRegistryHealer(isolated_duckdb_manager.conn)
    healer.heal_duckdb_registry(isolated_control_plane)

    # 3. Verify entry was pruned from meta.m_File_Registry
    meta_rows = isolated_duckdb_manager.conn.execute(
        "SELECT 1 FROM meta.m_File_Registry WHERE file_id = ?", [orphan_artifact_id]
    ).fetchall()
    assert len(meta_rows) == 0

    # 4. Verify rows in Pre-Bronze were pruned via __artifact_id__
    remaining_pb = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert remaining_pb.height == 0


def test_pre_bronze_orphaned_table_cleanup_guard(
    isolated_duckdb_manager: DuckDBManager,
    isolated_settings: Settings,
) -> None:
    """Verify _cleanup_orphaned_tables preserves contracted Pre-Bronze tables and drops rogue tables."""
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    # 1. Create a contracted Pre-Bronze table (declared in PRE_BRONZE_CONTRACT_REGISTRY)
    contracted_table = "pre_bronze.pb_household_zcategory"
    isolated_duckdb_manager.conn.execute(f"CREATE TABLE {contracted_table} (id INT)")  # nosec B608

    # 2. Create an uncontracted rogue scratch table in pre_bronze
    rogue_table = "pre_bronze.pb_rogue_uncontracted_table"
    isolated_duckdb_manager.conn.execute(f"CREATE TABLE {rogue_table} (id INT)")  # nosec B608

    meta_layer = MetaLayer(isolated_duckdb_manager, isolated_settings)
    meta_layer.cleanup_orphaned_tables()

    # Verify contracted table is preserved
    contracted_check = isolated_duckdb_manager.conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE lower(table_schema) = 'pre_bronze' AND lower(table_name) = 'pb_household_zcategory'"
    ).fetchall()
    assert len(contracted_check) == 1

    # Verify rogue table was dropped as an orphan
    rogue_check = isolated_duckdb_manager.conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE lower(table_schema) = 'pre_bronze' AND lower(table_name) = 'pb_rogue_uncontracted_table'"
    ).fetchall()
    assert len(rogue_check) == 0


def test_managed_warehouse_schema_enumeration_centralized() -> None:
    """Architecture guard verifying centralized warehouse schema taxonomies."""
    assert WarehouseLayer.PRE_BRONZE.value == "pre_bronze"
    assert WarehouseLayer.BRONZE.value == "bronze"
    assert WarehouseLayer.SILVER.value == "silver"
    assert WarehouseLayer.GOLD.value == "gold"
    assert WarehouseLayer.META.value == "meta"

    assert "pre_bronze" in MANAGED_WAREHOUSE_SCHEMAS
    assert "bronze" in MANAGED_WAREHOUSE_SCHEMAS
    assert "silver" in MANAGED_WAREHOUSE_SCHEMAS
    assert "gold" in MANAGED_WAREHOUSE_SCHEMAS
    assert "meta" in MANAGED_WAREHOUSE_SCHEMAS

    assert "pre_bronze" in PERSISTED_DATA_SCHEMAS
    assert "meta" not in PERSISTED_DATA_SCHEMAS


def test_old_database_compatibility_additive_initialization() -> None:
    """Verify pre-v9.9.0 legacy DuckDB files initialize pre_bronze additively without data loss."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "legacy_warehouse.duckdb")

        # Simulate older database created without pre_bronze schema
        raw_conn = duckdb.connect(db_path)
        raw_conn.execute("CREATE SCHEMA bronze")
        raw_conn.execute("CREATE SCHEMA silver")
        raw_conn.execute("CREATE SCHEMA gold")
        raw_conn.execute("CREATE SCHEMA meta")
        raw_conn.execute("CREATE TABLE bronze.r_legacy_sample (id INT, val TEXT)")
        raw_conn.execute("INSERT INTO bronze.r_legacy_sample VALUES (42, 'retained')")
        raw_conn.close()

        # Open through DuckDBManager and execute ensure_schemas
        mgr = DuckDBManager(tmpdir, "legacy_warehouse.duckdb")
        mgr.open()
        mgr.ensure_schemas()

        # Verify pre_bronze schema now exists
        schemata = {
            str(r[0])
            for r in mgr.conn.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        assert "pre_bronze" in schemata

        # Verify legacy bronze table was untouched
        legacy_data = mgr.conn.execute("SELECT * FROM bronze.r_legacy_sample").fetchall()
        assert legacy_data == [(42, "retained")]

        mgr.close()
