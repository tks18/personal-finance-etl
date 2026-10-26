"""ServiceContainer composition root assembling dependencies across layers.

Owns
----
- ServiceContainer: Factory and composition root wiring configuration, storage, control plane,
  backup managers, pipeline orchestrators, and application façades.
- Providing standardized dependency injection for headless tests, CLI, and GUI presentation.

Does not own
-------------
- Financial calculations or business rules (owned by domain.*).
- Execution lifecycle or pipeline stage coordination (owned by application.pipeline).
- Direct UI interaction or rendering (owned by presentation.*).
"""

from __future__ import annotations

import queue
from typing import cast

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.logging import ILogger
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager

__all__ = ["ServiceContainer"]


class _NullLoggerQueue:
    """Fallback in-memory queue satisfying ILogger protocol when no queue is provided."""

    def __init__(self) -> None:
        self._q: queue.Queue[ObservabilityEvent] = queue.Queue()

    def put(
        self,
        status: ObservabilityEvent,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Enqueue status message into fallback internal queue."""
        self._q.put(status, block=block, timeout=timeout)


class ServiceContainer:
    """Composition Root responsible for resolving and instantiating application dependencies."""

    def __init__(
        self,
        default_config_path: str = "config.toml",
        default_rules_path: str = "",
    ) -> None:
        self.default_config_path = default_config_path
        self.default_rules_path = default_rules_path
        self._prefs = PreferencesManager()

    def get_preferences_manager(self) -> PreferencesManager:
        """Resolve the active PreferencesManager."""
        return self._prefs

    def create_settings(self, config_path: str | None = None) -> Settings:
        """Resolve and parse Settings from TOML path."""
        target_path = config_path or self.default_config_path
        return Settings.from_toml(target_path) if target_path else Settings()

    def create_rules(self, rules_path: str | None = None) -> FinancialRules | None:
        """Resolve and parse FinancialRules from TOML path if provided."""
        target_path = rules_path or self.default_rules_path
        return FinancialRules.from_toml(target_path) if target_path else None

    def create_duckdb_manager(self, cfg: Settings) -> DuckDBManager:
        """Instantiate a DuckDBManager bound to the configured database path."""
        return DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)

    def create_control_plane(self, cfg: Settings) -> ControlPlane:
        """Instantiate a ControlPlane bound to the configured SQLite document store."""
        return ControlPlane(cfg.TARGET_DB_BASE_PATH, cfg.RAW_DOCUMENT_STORE_NAME)

    def create_backup_manager(self, cfg: Settings) -> SystemBackupManager:
        """Instantiate a SystemBackupManager bound to the active DuckDB and SQLite pair."""
        return SystemBackupManager(
            cfg.TARGET_DB_BASE_PATH,
            sqlite_db_name=cfg.RAW_DOCUMENT_STORE_NAME,
            duckdb_name=cfg.TARGET_DB_NAME,
        )

    def create_orchestrator(
        self,
        config_path: str | None = None,
        rules_path: str | None = None,
        status_queue: ILogger | None = None,
        settings: Settings | None = None,
    ) -> ETLOrchestrator:
        """Assemble an ETLOrchestrator with all required dependencies wired."""
        cfg = settings or self.create_settings(config_path)
        rules = self.create_rules(rules_path)
        active_queue: ILogger = status_queue or cast(ILogger, _NullLoggerQueue())
        return ETLOrchestrator(cfg, active_queue, rules)

    def create_engine(self) -> PersonalFinanceEngine:
        """Assemble a PersonalFinanceEngine application façade bound to this container."""
        return PersonalFinanceEngine(container=self)
