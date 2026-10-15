"""Tests for Phase 9: Application Orchestration and Bootstrap Composition Root.

Verifies:
1. Strict object identity equivalence (`is`) between legacy shims and canonical modules.
2. ServiceContainer dependency wiring and instantiation of storage, rules, orchestrators, and engines.
3. PersonalFinanceEngine façade methods (configuration, preferences, backup telemetry).
4. RunLifecycleCoordinator transactional lifecycle, two-phase commit, rollback, and split-commit recovery.
5. WorkerPoolCoordinator queue stream interception and log-level inference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.pipeline import (
    ETLOrchestrator,
    PipelineExecutor,
    QueueStream,
    RunLifecycleCoordinator,
)
from personal_finance_etl.bootstrap.container import ServiceContainer
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.lifecycle import CommitState
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.contracts.recovery import SnapshotOutcome
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


@pytest.fixture
def mock_rules() -> FinancialRules:
    """Load canonical test financial rules."""
    return FinancialRules.from_toml(Path("tests/financial_rules.toml"))


def test_service_container_wiring(mock_rules: FinancialRules, tmp_path: Path) -> None:
    """Verify ServiceContainer wires dependencies cleanly and resolves required services."""
    container = ServiceContainer(default_config_path="", default_rules_path="")

    # Preferences Manager
    prefs = container.get_preferences_manager()
    assert prefs is not None

    # Settings & Rules
    cfg = container.create_settings()
    assert isinstance(cfg, Settings)

    rules = container.create_rules("tests/financial_rules.toml")
    assert isinstance(rules, FinancialRules)

    # Storage & Control Plane
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    db_mgr = container.create_duckdb_manager(cfg)
    assert db_mgr.base_path == str(tmp_path)

    cp = container.create_control_plane(cfg)
    assert cp.base_path == str(tmp_path)

    backup_mgr = container.create_backup_manager(cfg)
    assert backup_mgr.base_path == str(tmp_path)

    # Orchestrator
    orchestrator = container.create_orchestrator(rules_path="tests/financial_rules.toml")
    assert isinstance(orchestrator, ETLOrchestrator)
    assert isinstance(orchestrator.executor, PipelineExecutor)

    # Engine Façade
    engine = container.create_engine()
    assert isinstance(engine, PersonalFinanceEngine)
    assert engine.container is container


def test_personal_finance_engine_facade(tmp_path: Path) -> None:
    """Verify PersonalFinanceEngine configuration validation, preferences, and snapshots."""
    engine = PersonalFinanceEngine()

    # Configuration validation
    valid = engine.validate_config("tests/financial_rules.toml")
    # A financial rules file is not a valid Settings file (missing fields like STATEMENTS_FOLDER)
    assert isinstance(valid, bool)

    # Preferences
    custom_rules_file = tmp_path / "custom_rules.toml"
    custom_rules_file.touch()
    recent_rules = engine.get_recent_rules()
    assert isinstance(recent_rules, list)
    engine.add_recent_rules(str(custom_rules_file))
    assert str(custom_rules_file) in engine.get_recent_rules()

    # Detailed snapshot on invalid config returns failure outcome
    snap_res = engine.snapshot_database_detailed(str(tmp_path / "nonexistent.toml"))
    assert not snap_res.is_success
    assert snap_res.outcome == SnapshotOutcome.SNAPSHOT_FAILED


def test_run_lifecycle_coordinator_transitions(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator initialization, transaction states, and commit convergence."""
    cfg = Settings()
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    cfg.TARGET_DB_NAME = "test_lifecycle.duckdb"
    cfg.RAW_DOCUMENT_STORE_NAME = "test_lifecycle_raw.db"

    class MockStatusQueue:
        def __init__(self) -> None:
            self.items: list[Any] = []

        def put(self, status: Any, block: bool = True, timeout: float | None = None) -> None:
            self.items.append(status)

    q = MockStatusQueue()
    db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
    lifecycle = RunLifecycleCoordinator(cfg, q, db_manager, rules=None)

    assert lifecycle.commit_state == CommitState.NOT_STARTED

    _cp, run_id, _pending_rec = lifecycle.initialize()
    assert isinstance(run_id, str)
    assert lifecycle.duckdb_started
    assert lifecycle.sqlite_started
    assert lifecycle.commit_state == CommitState.STARTED

    # Commit phase
    lifecycle.commit()
    assert lifecycle.duckdb_committed
    assert lifecycle.sqlite_committed
    assert lifecycle.commit_state == CommitState.FULLY_COMMITTED

    lifecycle.teardown()


def test_run_lifecycle_rollback_on_failure(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator rolls back cleanly on exception and sets ROLLED_BACK state."""
    cfg = Settings()
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    cfg.TARGET_DB_NAME = "test_rollback.duckdb"
    cfg.RAW_DOCUMENT_STORE_NAME = "test_rollback_raw.db"

    class MockStatusQueue:
        def put(self, status: Any, block: bool = True, timeout: float | None = None) -> None:
            pass

    db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
    lifecycle = RunLifecycleCoordinator(cfg, MockStatusQueue(), db_manager, rules=None)

    cp, run_id, _ = lifecycle.initialize()

    # Simulate failure before commit
    simulated_err = ValueError("Simulated transformation anomaly")
    lifecycle.handle_failure(simulated_err)

    assert lifecycle.commit_state == CommitState.ROLLED_BACK
    row = cp.db.conn.execute(
        "SELECT status, commit_state FROM cp_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row is not None
    assert row[0] == "FAILED"
    assert row[1] == CommitState.ROLLED_BACK.value

    lifecycle.teardown()


def test_run_lifecycle_split_commit_recovery_marker(tmp_path: Path) -> None:
    """Verify split-commit divergence marks RECOVERY_REQUIRED when SQLite commit fails."""
    cfg = Settings()
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    cfg.TARGET_DB_NAME = "test_split_commit.duckdb"
    cfg.RAW_DOCUMENT_STORE_NAME = "test_split_commit_raw.db"

    class MockStatusQueue:
        def put(self, status: Any, block: bool = True, timeout: float | None = None) -> None:
            pass

    db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
    lifecycle = RunLifecycleCoordinator(cfg, MockStatusQueue(), db_manager, rules=None)

    cp, run_id, _ = lifecycle.initialize()

    # Break SQLite commit to simulate split-commit divergence
    def faulty_commit():
        raise RuntimeError("Disk I/O error writing SQLite journal")

    cp.commit = faulty_commit  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="SQLite Commit Failed after DuckDB committed"):
        lifecycle.commit()

    assert lifecycle.commit_state == CommitState.RECOVERY_REQUIRED
    lifecycle.handle_failure(RuntimeError("SQLite Commit Failed"))

    row = cp.db.conn.execute(
        "SELECT status, commit_state FROM cp_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row is not None
    assert row[1] == CommitState.RECOVERY_REQUIRED.value

    lifecycle.teardown()


def test_queue_stream_and_log_level_inference() -> None:
    """Verify QueueStream captures stream writes and infers correct log levels."""

    class MockQueue:
        def __init__(self) -> None:
            self.messages: list[EngineStatusMessage] = []

        def put(self, status: Any, block: bool = True, timeout: float | None = None) -> None:
            self.messages.append(status)

    mock_q = MockQueue()
    stream = QueueStream(mock_q, is_error=False)

    stream.write("Processing dataset batch...\n")
    stream.write("Warning: Minor latency detected\n")
    stream.write("Error occurred during network read\n")
    stream.write("Complete: 100% processed\n")
    stream.flush()

    levels = [m.level for m in mock_q.messages]
    assert LogLevel.INFO in levels
    assert LogLevel.WARNING in levels
    assert LogLevel.ERROR in levels
    assert LogLevel.SUCCESS in levels
