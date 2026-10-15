"""Unified application façade for personal finance ETL services.

Owns
----
- PersonalFinanceEngine: High-level entry point exposing configuration, database backup/restore,
  and asynchronous/synchronous pipeline execution workflows to CLI and GUI presentation layers.
- Translating cross-process status messages into presentation-compatible telemetry.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse).
- Financial algorithms or calculation formulas (owned by domain.*).
- Human-facing GUI widgets or CLI parsing (owned by presentation.*).
"""

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable
from typing import Any

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.worker import WorkerPoolCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.logging import ILogger
from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager

__all__ = ["PersonalFinanceEngine"]


class PersonalFinanceEngine:
    """Unified Façade for the entire Personal Finance Backend and Presentation boundary."""

    def __init__(self, container: Any | None = None) -> None:
        self.container = container
        self._prefs = PreferencesManager()

    # --- Configuration Management ---

    def get_recent_configs(self) -> list[str]:
        """Fetch list of recently opened configuration TOML paths."""
        return self._prefs.get_recent_configs()

    def get_recent_rules(self) -> list[str]:
        """Fetch list of recently opened financial rules TOML paths."""
        return self._prefs.get_recent_rules()

    def add_recent_rules(self, path: str) -> None:
        """Add a financial rules TOML path to the recent history."""
        self._prefs.add_recent_rules(path)

    def validate_config(self, path: str) -> bool:
        """Validate whether a configuration TOML file parses correctly."""
        try:
            Settings.from_toml(path)
            return True
        except Exception:
            return False

    # --- Database Operations ---

    def snapshot_database(self, config_path: str) -> str | None:
        """Create a coordinated backup snapshot archive of the DuckDB and SQLite instance."""
        try:
            res = self.snapshot_database_detailed(config_path)
            return res.zip_path if res.is_success else None
        except Exception:
            return None

    def snapshot_database_detailed(self, config_path: str) -> SnapshotResult:
        """Create a backup snapshot archive returning full outcome telemetry."""
        if not os.path.exists(config_path):
            return SnapshotResult(
                outcome=SnapshotOutcome.SNAPSHOT_FAILED,
                zip_path=None,
                error_message=f"Configuration file not found: {config_path}",
            )
        cfg = Settings.from_toml(config_path)
        backup_mgr = SystemBackupManager(
            cfg.TARGET_DB_BASE_PATH,
            sqlite_db_name=cfg.RAW_DOCUMENT_STORE_NAME,
            duckdb_name=cfg.TARGET_DB_NAME,
        )
        return backup_mgr.create_snapshot()

    def restore_database(self, config_path: str, backup_zip_path: str) -> bool:
        """Restore DuckDB and SQLite Raw Store from a coordinated backup zip."""
        try:
            res = self.restore_database_detailed(config_path, backup_zip_path)
            if not res.is_success and res.error_message and "in use" in res.error_message.lower():
                raise PermissionError(res.error_message)
            return res.is_success
        except PermissionError as pe:
            raise pe
        except Exception:
            return False

    def restore_database_detailed(self, config_path: str, backup_zip_path: str) -> RestoreResult:
        """Restore the database pair, returning full outcome telemetry and active state."""
        if not os.path.exists(config_path):
            return RestoreResult(
                outcome=RestoreOutcome.RESTORE_VALIDATION_FAILED,
                active_database_state=ActiveDatabaseState.PREVIOUS_PAIR_INTACT,
                error_message=f"Configuration file not found: {config_path}",
            )
        cfg = Settings.from_toml(config_path)
        backup_mgr = SystemBackupManager(
            cfg.TARGET_DB_BASE_PATH,
            sqlite_db_name=cfg.RAW_DOCUMENT_STORE_NAME,
            duckdb_name=cfg.TARGET_DB_NAME,
        )
        return backup_mgr.restore_snapshot(backup_zip_path)

    # --- Pipeline Execution ---

    def run_pipeline_async(
        self,
        config_path: str,
        rules_path: str,
        on_status: Callable[[Any], None],
    ) -> None:
        """Spawn the multiprocessing ETL pipeline and stream status updates to on_status."""
        status_queue: multiprocessing.Queue[Any] = multiprocessing.Queue()
        process = WorkerPoolCoordinator.spawn_process(status_queue, config_path, rules_path)
        WorkerPoolCoordinator.monitor_queue(process, status_queue, on_status)

    def run_pipeline_sync(
        self,
        config_path: str = "config.toml",
        rules_path: str = "",
        status_queue: ILogger | None = None,
    ) -> None:
        """Execute the ETL pipeline synchronously in the current thread (ideal for profiling/testing)."""
        if self.container is not None and hasattr(self.container, "create_orchestrator"):
            orchestrator = self.container.create_orchestrator(
                config_path=config_path,
                rules_path=rules_path,
                status_queue=status_queue,
            )
        else:
            cfg = Settings.from_toml(config_path) if config_path else Settings()
            rules = FinancialRules.from_toml(rules_path) if rules_path else None
            orchestrator = ETLOrchestrator(cfg, status_queue, rules)
        orchestrator.run()
