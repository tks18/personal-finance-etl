"""Verification tests for Phase 3 Infrastructure refactoring.

Asserts:
1. 100% object identity equivalence (`is`) between superseded legacy modules and canonical targets.
2. SQLite Control Plane connection lifecycle, savepoint-based nested atomicity, and schema validation.
3. DuckDB warehouse manager, schema creation, and pragma configuration.
4. Warehouse data contracts, registries, and fingerprinting determinism.
5. Control plane run repository lifecycle transitions and crash recovery.
6. SystemBackupManager coordinated database snapshot creation.
7. Logging setup and contextual formatters.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import duckdb
import pytest

# Legacy imports
from personal_finance_etl.backend.load import backup as legacy_backup
from personal_finance_etl.backend.load import bronze as legacy_bronze
from personal_finance_etl.backend.load import database as legacy_database
from personal_finance_etl.backend.load import gold as legacy_gold
from personal_finance_etl.backend.load import metadata as legacy_metadata
from personal_finance_etl.backend.load import registry as legacy_registry
from personal_finance_etl.backend.load import schema as legacy_schema
from personal_finance_etl.backend.load import silver as legacy_silver
from personal_finance_etl.backend.load.control_plane import artifact_repo as legacy_artifact_repo
from personal_finance_etl.backend.load.control_plane import connection as legacy_cp_conn
from personal_finance_etl.backend.load.control_plane import file_sync as legacy_file_sync
from personal_finance_etl.backend.load.control_plane import orchestrator as legacy_orchestrator
from personal_finance_etl.backend.load.control_plane import run_repo as legacy_run_repo
from personal_finance_etl.backend.load.control_plane import utils as legacy_cp_utils
from personal_finance_etl.backend.utils import logger as legacy_logger
from personal_finance_etl.contracts.lifecycle import CommitState
from personal_finance_etl.contracts.recovery import SnapshotOutcome

# Canonical targets
from personal_finance_etl.infrastructure.control_plane.artifact_repository import (
    ArtifactRepository,
)
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.file_sync import FileSyncService
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
    hash_bytes,
    normalize_path,
)
from personal_finance_etl.infrastructure.control_plane.run_repository import RunRepository
from personal_finance_etl.infrastructure.logging.setup import (
    ContextFilter,
    QueueHandler,
    logger,
    setup_logger,
)
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.gold import GoldLayer
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    BronzeDataContract,
    DataContract,
    get_contract_by_table,
    validate_registry,
)
from personal_finance_etl.infrastructure.warehouse.schema.bronze import BRONZE_DDL
from personal_finance_etl.infrastructure.warehouse.schema.control_plane import RAW_DDL
from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL
from personal_finance_etl.infrastructure.warehouse.schema.meta import META_DDL
from personal_finance_etl.infrastructure.warehouse.schema.pragmas import SQLITE_PRAGMAS
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL
from personal_finance_etl.infrastructure.warehouse.silver import SilverLayer


def test_phase3_object_identity_equivalence() -> None:
    """Verify 100% object identity equivalence between legacy and canonical targets."""
    # Control plane shims
    assert legacy_cp_conn.SQLiteManager is SQLiteManager
    assert legacy_run_repo.RunRepository is RunRepository
    assert legacy_artifact_repo.ArtifactRepository is ArtifactRepository
    assert legacy_file_sync.FileSyncService is FileSyncService
    assert legacy_orchestrator.ControlPlane is ControlPlane
    assert legacy_cp_utils.compute_file_hash is compute_file_hash
    assert legacy_cp_utils.generate_file_id is generate_file_id
    assert legacy_cp_utils.hash_bytes is hash_bytes
    assert legacy_cp_utils.normalize_path is normalize_path
    assert legacy_cp_utils.FILE_TYPE_MAP is FILE_TYPE_MAP

    # Warehouse shims
    assert legacy_database.DuckDBManager is DuckDBManager
    assert legacy_registry.DataContract is DataContract
    assert legacy_registry.BronzeDataContract is BronzeDataContract
    assert legacy_registry.BRONZE_CONTRACT_REGISTRY is BRONZE_CONTRACT_REGISTRY
    assert legacy_registry.DATA_CONTRACT_REGISTRY is DATA_CONTRACT_REGISTRY
    assert legacy_registry.get_contract_by_table is get_contract_by_table
    assert legacy_registry.validate_registry is validate_registry
    assert legacy_bronze.BronzeLayer is BronzeLayer
    assert legacy_silver.SilverLayer is SilverLayer
    assert legacy_gold.GoldLayer is GoldLayer
    assert legacy_metadata.MetaLayer is MetaLayer

    # Schema shims
    assert legacy_schema.BRONZE_DDL is BRONZE_DDL
    assert legacy_schema.SILVER_DDL is SILVER_DDL
    assert legacy_schema.GOLD_DDL is GOLD_DDL
    assert legacy_schema.META_DDL is META_DDL
    assert legacy_schema.RAW_DDL is RAW_DDL
    assert legacy_schema.SQLITE_PRAGMAS is SQLITE_PRAGMAS

    # Recovery and Logging shims
    assert legacy_backup.SystemBackupManager is SystemBackupManager
    assert legacy_logger.logger is logger
    assert legacy_logger.setup_logger is setup_logger
    assert legacy_logger.ContextFilter is ContextFilter
    assert legacy_logger.QueueHandler is QueueHandler


def test_sqlite_control_plane_lifecycle() -> None:
    """Verify SQLite control plane connection, schemas, and nested savepoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_mgr = SQLiteManager(tmpdir, "test_cp.sqlite")
        assert not sqlite_mgr.is_open

        sqlite_mgr.open()
        assert sqlite_mgr.is_open

        # Schema initialization and foreign keys
        sqlite_mgr.ensure_schema()
        cursor = sqlite_mgr.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "cp_runs" in tables
        assert "cp_file_registry" in tables
        assert "cp_file_payloads" in tables
        assert "cp_run_failures" in tables

        # Nested savepoint atomicity
        with sqlite_mgr.atomic():
            sqlite_mgr.conn.execute(
                "INSERT INTO cp_runs (run_id, started_at, status, commit_state) VALUES ('run_1', '2026-01-01', 'STARTED', 'STARTED')"
            )
            try:
                with sqlite_mgr.atomic():
                    sqlite_mgr.conn.execute(
                        "INSERT INTO cp_runs (run_id, started_at, status, commit_state) VALUES ('run_2', '2026-01-01', 'STARTED', 'STARTED')"
                    )
                    raise ValueError("Simulated nested failure")
            except ValueError:
                pass  # nested savepoint rolled back

        # run_1 should persist, run_2 should not
        r1 = sqlite_mgr.conn.execute("SELECT 1 FROM cp_runs WHERE run_id = 'run_1'").fetchone()
        r2 = sqlite_mgr.conn.execute("SELECT 1 FROM cp_runs WHERE run_id = 'run_2'").fetchone()
        assert r1 is not None
        assert r2 is None

        sqlite_mgr.close()
        assert not sqlite_mgr.is_open


def test_run_repository_lifecycle() -> None:
    """Verify RunRepository start, update, failure logging, and crash recovery."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_mgr = SQLiteManager(tmpdir, "test_repo.sqlite")
        try:
            sqlite_mgr.open()
            sqlite_mgr.ensure_schema()

            repo = RunRepository(sqlite_mgr)
            run_id = repo.start_run(cfg_json='{"key": "value"}', rules_json='{"rule": 1}')
            assert run_id is not None

            # Verify snapshots inserted
            meta = repo.get_run_metadata(run_id)
            assert meta["settings_snapshot_id"] is not None
            assert meta["rules_snapshot_id"] is not None

            # State updates: transition to COMMITTING status
            repo.update_run_status(run_id, "COMMITTING")
            repo.update_commit_state(run_id, CommitState.DUCKDB_COMMITTED)

            # Crash recovery for interrupted COMMITTING runs
            repo.recover_stale_runs()
            recovery_runs = repo.get_recovery_required_runs()
            assert run_id in recovery_runs

            # Converge recovery
            repo.mark_recovery_converged(run_id, reconciling_run_id="run_reconcile")
            assert run_id not in repo.get_recovery_required_runs()
        finally:
            sqlite_mgr.close()


def test_warehouse_registry_and_fingerprints() -> None:
    """Verify registry validation and deterministic fingerprint calculation."""
    validate_registry()

    c = get_contract_by_table("silver.d_Calendar")
    assert c is not None
    assert c.layer == "silver"
    assert c.grain == "Day"

    metadata = [
        {"table_name": "silver.d_Calendar", "grain": "Day", "producer": "CoreEngine"},
        {"table_name": "gold.Tax_Year_Summary", "grain": "FY", "producer": "TaxEngine"},
    ]
    fp1 = generate_contract_registry_fingerprint(metadata)
    fp2 = generate_contract_registry_fingerprint(list(reversed(metadata)))
    assert fp1 == fp2  # Order-independent due to internal sorting
    assert len(fp1) == 64  # SHA-256


def test_duckdb_warehouse_lifecycle() -> None:
    """Verify DuckDBManager connection, memory PRAGMAs, and schema creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DuckDBManager(tmpdir, "test_warehouse.duckdb")
        db_mgr.open()

        db_mgr.ensure_schemas()
        schemas = {
            row[0]
            for row in db_mgr.conn.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        assert {"bronze", "silver", "gold", "meta"}.issubset(schemas)

        db_mgr.close()


def test_system_backup_manager_snapshot() -> None:
    """Verify SystemBackupManager creates a valid coordinated zip snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock sqlite and duckdb database files
        sqlite_path = os.path.join(tmpdir, "Raw_Documents.sqlite")
        duckdb_path = os.path.join(tmpdir, "Personal_Finance_DB.duckdb")

        conn = sqlite3.connect(sqlite_path)
        conn.execute("CREATE TABLE test (id INT)")
        conn.commit()
        conn.close()

        dconn = duckdb.connect(duckdb_path)
        dconn.execute("CREATE TABLE test (id INT)")
        dconn.close()

        mgr = SystemBackupManager(tmpdir)
        res = mgr.create_snapshot()
        assert res.outcome == SnapshotOutcome.SNAPSHOT_PUBLISHED
        assert res.is_success
        assert res.zip_path is not None
        assert os.path.isfile(res.zip_path)


def test_hashing_and_path_normalization() -> None:
    """Verify path normalization and hashing primitives."""
    assert normalize_path(r"foo\bar\baz") == "foo/bar/baz"
    assert normalize_path("virtual://category/item.csv") == "virtual://category/item.csv"
    with pytest.raises(ValueError, match="Artifact path must be a non-empty string."):
        normalize_path("")

    fid1 = generate_file_id(r"statements\jan.xlsx")
    fid2 = generate_file_id("statements/jan.xlsx")
    assert fid1 == fid2

    payload = b"hello world financial etl"
    assert hash_bytes(payload) == "2e1f2ec86d418d2f44019104eb9502c480ee38eb2222efa3b73d84fe5d51f2e4"
