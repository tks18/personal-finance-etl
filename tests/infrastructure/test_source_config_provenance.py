"""Unit and integration tests for SQLite Control Plane source configuration provenance.

Verifies:
1. Schema DDL: cp_source_config_snapshots table creation and required columns.
2. Non-destructive migration: cp_runs.source_config_snapshot_id column migration.
3. Snapshot persistence: Run initialization captures source configuration snapshots.
4. Snapshot deduplication: Identical configurations share snapshots via INSERT OR IGNORE.
5. Change detection: has_source_config_changed_since_last_success compares against latest SUCCESS.
6. Lifecycle integration: RunLifecycleCoordinator populates context and emits provenance events.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.fingerprint import (
    compute_source_config_fingerprint,
)
from personal_finance_etl.config.sources.loader import (
    CURRENT_SOURCE_CONFIG_SCHEMA_VERSION,
    CapabilitySelection,
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
    ObservabilitySink,
)
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.control_plane.schema import (
    REQUIRED_SCHEMA_COLUMNS,
    _migrate_runs,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_current_context,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


class CapturingSink(ObservabilitySink):
    """Sink that captures emitted events in an in-memory list for assertion."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        """Capture incoming event."""
        self.events.append(event)

    def flush(self) -> None:
        """No-op flush."""


def test_schema_ddl_and_columns(tmp_path: Path) -> None:
    """Verify cp_source_config_snapshots and cp_runs columns in fresh control plane database."""
    cp = ControlPlane(str(tmp_path), "test_store.sqlite")
    cp.open()
    cp.ensure_schema()

    with cp.db.conn:
        tables = {
            str(r[0])
            for r in cp.db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "cp_source_config_snapshots" in tables

        snapshot_cols = {
            str(r[1])
            for r in cp.db.conn.execute("PRAGMA table_info(cp_source_config_snapshots)").fetchall()
        }
        assert snapshot_cols == REQUIRED_SCHEMA_COLUMNS["cp_source_config_snapshots"]

        run_cols = {str(r[1]) for r in cp.db.conn.execute("PRAGMA table_info(cp_runs)").fetchall()}
        assert "source_config_snapshot_id" in run_cols
    cp.close()


def test_migration_adds_column_to_legacy_runs(tmp_path: Path) -> None:
    """Verify _migrate_runs non-destructively adds source_config_snapshot_id to legacy cp_runs."""
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    # Create legacy cp_runs table lacking source_config_snapshot_id
    conn.execute(
        """
        CREATE TABLE cp_runs (
            run_id TEXT PRIMARY KEY,
            started_at TIMESTAMP NOT NULL,
            status TEXT
        )
        """
    )
    conn.commit()

    _migrate_runs(conn, {"cp_runs"})

    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(cp_runs)").fetchall()}
    assert "source_config_snapshot_id" in cols
    conn.close()


def test_snapshot_persistence_and_run_linkage(tmp_path: Path) -> None:
    """Verify starting a run with source_config records snapshot and links snapshot ID."""
    cp = ControlPlane(str(tmp_path), "provenance_test.sqlite")
    cp.open()
    cp.ensure_schema()

    source_cfg = get_shan_baseline_source_configuration()
    sc_fp = compute_source_config_fingerprint(source_cfg)

    run_id = cp.runs.start_run(source_config=source_cfg)
    assert run_id is not None

    # Check snapshot retrieved by snapshot_id
    expected_snapshot_id = f"snap_src_{sc_fp.content_hash}"
    snapshot = cp.runs.get_source_config_snapshot(expected_snapshot_id)
    assert snapshot is not None
    assert snapshot["snapshot_id"] == expected_snapshot_id
    assert snapshot["content_hash"] == sc_fp.content_hash
    assert snapshot["schema_version"] == CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
    assert snapshot["canonical_payload"] == sc_fp.canonical_payload

    # Check run metadata
    metadata = cp.runs.get_run_metadata(run_id)
    assert metadata["source_config_snapshot_id"] == expected_snapshot_id

    # Check run status
    status = cp.runs.get_run_status(run_id)
    assert status is not None
    assert status["source_config_snapshot_id"] == expected_snapshot_id
    cp.close()


def test_snapshot_deduplication_across_runs(tmp_path: Path) -> None:
    """Verify consecutive runs with identical source_config reuse existing snapshot row."""
    cp = ControlPlane(str(tmp_path), "dedup_test.sqlite")
    cp.open()
    cp.ensure_schema()

    source_cfg = get_shan_baseline_source_configuration()

    run1 = cp.runs.start_run(source_config=source_cfg)
    run2 = cp.runs.start_run(source_config=source_cfg)

    meta1 = cp.runs.get_run_metadata(run1)
    meta2 = cp.runs.get_run_metadata(run2)

    assert meta1["source_config_snapshot_id"] == meta2["source_config_snapshot_id"]

    # Exactly 1 row in cp_source_config_snapshots
    with cp.db.conn:
        row = cp.db.conn.execute("SELECT COUNT(*) FROM cp_source_config_snapshots").fetchone()
        assert row is not None and row[0] == 1
    cp.close()


def test_change_detection_against_latest_success(tmp_path: Path) -> None:
    """Verify change detection only compares against latest SUCCESS runs."""
    cp = ControlPlane(str(tmp_path), "change_test.sqlite")
    cp.open()
    cp.ensure_schema()

    cfg_a = get_shan_baseline_source_configuration()
    fp_a = compute_source_config_fingerprint(cfg_a)

    # 1. No runs yet -> False
    assert not cp.runs.has_source_config_changed_since_last_success(fp_a.content_hash)

    # 2. Run 1 starts with cfg_a and FAILS
    run1 = cp.runs.start_run(source_config=cfg_a)
    cp.runs.finish_run(run1, "FAILED")

    # Still no successful run -> False
    assert not cp.runs.has_source_config_changed_since_last_success(fp_a.content_hash)

    # 3. Run 2 starts with cfg_a and SUCCEEDS
    run2 = cp.runs.start_run(source_config=cfg_a)
    cp.runs.finish_run(run2, "SUCCESS")

    assert (
        cp.runs.get_latest_successful_run_source_config_snapshot_id()
        == f"snap_src_{fp_a.content_hash}"
    )
    # Comparing same hash -> False
    assert not cp.runs.has_source_config_changed_since_last_success(fp_a.content_hash)

    # 4. Modified config B
    cfg_b = SourceConfiguration(
        sources=cfg_a.sources,
        datasets=cfg_a.datasets,
        capabilities=CapabilitySelection(enabled=(CapabilityId.TAX,)),
    )
    fp_b = compute_source_config_fingerprint(cfg_b)
    assert fp_b.content_hash != fp_a.content_hash

    # Comparing different hash -> True
    assert cp.runs.has_source_config_changed_since_last_success(fp_b.content_hash)

    # 5. Run 3 starts with cfg_b and SUCCEEDS
    run3 = cp.runs.start_run(source_config=cfg_b)
    cp.runs.finish_run(run3, "SUCCESS")

    # Now latest success is cfg_b -> comparing cfg_b is False, comparing cfg_a is True
    assert not cp.runs.has_source_config_changed_since_last_success(fp_b.content_hash)
    assert cp.runs.has_source_config_changed_since_last_success(fp_a.content_hash)
    cp.close()


def test_lifecycle_coordinator_provenance_integration(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator attaches fingerprint to context and emits events."""
    settings = Settings(
        TARGET_DB_BASE_PATH=str(tmp_path),
        TARGET_DB_NAME="test_duckdb.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_control.sqlite",
    )
    db_manager = DuckDBManager(str(tmp_path), "test_duckdb.duckdb")

    emitter = ObservabilityEmitter()
    sink = CapturingSink()
    emitter.register_sink(sink)

    cfg_a = get_shan_baseline_source_configuration()
    fp_a = compute_source_config_fingerprint(cfg_a)

    # Run 1: initial run
    coord1 = RunLifecycleCoordinator(
        cfg=settings,
        status_queue=NullEventQueue(),
        db_manager=db_manager,
        rules=None,
        emitter=emitter,
        source_config=cfg_a,
    )

    cp, run_id, _ = coord1.initialize()
    assert cp is not None
    assert run_id
    ctx = get_current_context()
    assert ctx.source_config_fingerprint == fp_a.fingerprint

    # Check emitted events
    event_codes = [e.event_code for e in sink.events]
    assert EventCode.SYSTEM_CONFIG_FINGERPRINT in event_codes
    assert EventCode.SYSTEM_SOURCE_CONFIG_FINGERPRINT in event_codes
    assert EventCode.SYSTEM_SOURCE_CONFIG_CHANGED not in event_codes

    coord1.commit()
    coord1.teardown()

    # Now create Run 2 with modified source config
    sink.events.clear()
    cfg_b = SourceConfiguration(
        sources=cfg_a.sources,
        datasets=cfg_a.datasets,
        capabilities=CapabilitySelection(enabled=(CapabilityId.TAX,)),
    )
    fp_b = compute_source_config_fingerprint(cfg_b)

    coord2 = RunLifecycleCoordinator(
        cfg=settings,
        status_queue=NullEventQueue(),
        db_manager=db_manager,
        rules=None,
        emitter=emitter,
        source_config=cfg_b,
    )

    coord2.initialize()
    ctx2 = get_current_context()
    assert ctx2.source_config_fingerprint == fp_b.fingerprint

    event_codes_2 = [e.event_code for e in sink.events]
    assert EventCode.SYSTEM_SOURCE_CONFIG_FINGERPRINT in event_codes_2
    assert EventCode.SYSTEM_SOURCE_CONFIG_CHANGED in event_codes_2

    coord2.commit()
    coord2.teardown()
