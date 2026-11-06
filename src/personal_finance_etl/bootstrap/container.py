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
from pathlib import Path
from typing import cast

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    CompiledSourcePlan,
    SourcePlanner,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager
from personal_finance_etl.infrastructure.warehouse import DuckDBManager, PreBronzeLayer

__all__ = ["ServiceContainer"]


class _NullEventQueue:
    """Fallback in-memory queue satisfying EventQueue protocol when no queue is provided."""

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
        default_sources_path: str = "sources.toml",
    ) -> None:
        self.default_config_path = default_config_path
        self.default_rules_path = default_rules_path
        self.default_sources_path = default_sources_path
        self._prefs = PreferencesManager()

    def get_preferences_manager(self) -> PreferencesManager:
        """Resolve the active PreferencesManager."""
        return self._prefs

    def create_settings(self, config_path: str | None = None) -> Settings:
        """Resolve and parse Settings from TOML path."""
        target_path = config_path or self.default_config_path
        if target_path:
            self._prefs.add_recent_config(target_path)
        return Settings.from_toml(target_path) if target_path else Settings()

    def create_rules(self, rules_path: str | None = None) -> FinancialRules | None:
        """Resolve and parse FinancialRules from TOML path if provided."""
        target_path = rules_path or self.default_rules_path
        if target_path:
            self._prefs.add_recent_rules(target_path)
        return FinancialRules.from_toml(target_path) if target_path else None

    def create_source_config(self, sources_path: str | None = None) -> SourceConfiguration:
        """Resolve and parse SourceConfiguration from TOML path or fallback to canonical Shan baseline.

        Parameters
        ----------
        sources_path : str | None, optional
            Path to the source configuration TOML file.

        Returns
        -------
        SourceConfiguration
            Parsed SourceConfiguration instance if file exists, or canonical Shan baseline.
        """
        target_path = sources_path or self.default_sources_path
        if target_path and Path(target_path).is_file():
            return SourceConfiguration.from_toml(target_path)
        return get_shan_baseline_source_configuration()

    def create_duckdb_manager(self, cfg: Settings) -> DuckDBManager:
        """Instantiate a DuckDBManager bound to the configured database path."""
        return DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)

    def create_pre_bronze_layer(
        self,
        db_manager: DuckDBManager,
        emitter: ObservabilityEmitter | None = None,
    ) -> PreBronzeLayer:
        """Instantiate a PreBronzeLayer bound to the active DuckDB warehouse manager.

        Parameters
        ----------
        db_manager : DuckDBManager
            Active DuckDB connection manager.
        emitter : ObservabilityEmitter | None, default=None
            Observability emitter for diagnostic logging and telemetry.

        Returns
        -------
        PreBronzeLayer
            Configured Pre-Bronze layer manager.
        """
        return PreBronzeLayer(db_manager, emitter=emitter)

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
        sources_path: str | None = None,
        status_queue: EventQueue | None = None,
        settings: Settings | None = None,
        source_config: SourceConfiguration | None = None,
        plan: ExecutionPlan | None = None,
    ) -> ETLOrchestrator:
        """Assemble an ETLOrchestrator with all required dependencies wired.

        Parameters
        ----------
        config_path : str | None, optional
            Path to settings TOML file.
        rules_path : str | None, optional
            Path to financial rules TOML file.
        sources_path : str | None, optional
            Path to source configuration TOML file.
        status_queue : EventQueue | None, optional
            Queue for event transport.
        settings : Settings | None, optional
            Pre-loaded Settings instance.
        source_config : SourceConfiguration | None, optional
            Pre-loaded SourceConfiguration instance.
        plan : ExecutionPlan | None, optional
            Pre-compiled ExecutionPlan instance.

        Returns
        -------
        ETLOrchestrator
            Wired execution orchestrator.
        """
        cfg = settings or self.create_settings(config_path)
        rules = self.create_rules(rules_path)
        src_cfg = source_config or self.create_source_config(sources_path)
        active_queue: EventQueue = status_queue or cast(EventQueue, _NullEventQueue())

        # If execution plan is not explicitly provided, resolve from source_config capability selection
        resolved_plan = plan
        if resolved_plan is None:
            requested_caps = src_cfg.capabilities.resolved_capabilities
            resolved_plan = CapabilityPlanner().create_plan(requested_capabilities=requested_caps)

        # Compile non-I/O source plan
        source_plan: CompiledSourcePlan = SourcePlanner(src_cfg, resolved_plan).compile_plan()

        return ETLOrchestrator(
            cfg,
            active_queue,
            rules,
            plan=resolved_plan,
            source_config=src_cfg,
            source_plan=source_plan,
        )

    def create_engine(self) -> PersonalFinanceEngine:
        """Assemble a PersonalFinanceEngine application façade bound to this container."""
        return PersonalFinanceEngine(container=self)
