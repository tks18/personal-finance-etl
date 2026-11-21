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
from typing import Protocol

from personal_finance_etl.application.diagnostics.service import DiagnosticService
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.worker import WorkerPoolCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.diagnostics import (
    AdmissionDryRunResult,
    ConfigValidationResult,
    IdentityPreviewResult,
    MappingPreviewResult,
    PlanPreviewResult,
    SourceCheckResult,
)
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager

__all__ = ["ContainerProtocol", "PersonalFinanceEngine"]


class ContainerProtocol(Protocol):
    """Structural protocol for bootstrap container dependency resolution."""

    def create_orchestrator(
        self,
        config_path: str | None = None,
        rules_path: str | None = None,
        sources_path: str | None = None,
        status_queue: EventQueue | None = None,
        settings: Settings | None = None,
        source_config: SourceConfiguration | None = None,
        plan: ExecutionPlan | None = None,
        skip_preflight: bool = False,
    ) -> ETLOrchestrator:
        """Create and wire an ETLOrchestrator with configuration and observability.

        Parameters
        ----------
        config_path : str | None, optional
            Path to application settings YAML.
        rules_path : str | None, optional
            Path to financial rules YAML.
        sources_path : str | None, optional
            Path to source configuration TOML.
        status_queue : EventQueue | None, optional
            Queue transport for canonical runtime events.
        settings : Settings | None, optional
            Pre-loaded settings instance.
        source_config : SourceConfiguration | None, optional
            Pre-loaded SourceConfiguration instance.
        plan : ExecutionPlan | None, optional
            Pre-compiled execution plan.
        skip_preflight : bool, default=False
            Whether to skip Phase 0 pre-flight health checks.

        Returns
        -------
        ETLOrchestrator
            Wired execution orchestrator.
        """
        ...


class PersonalFinanceEngine:
    """Unified Façade for the entire Personal Finance Backend and Presentation boundary."""

    def __init__(self, container: ContainerProtocol | None = None) -> None:
        self.container = container
        self._prefs = PreferencesManager()

    # --- Configuration Management ---

    def get_recent_configs(self) -> list[str]:
        """Fetch list of recently opened configuration TOML paths."""
        return self._prefs.get_recent_configs()

    def add_recent_config(self, path: str) -> None:
        """Add a configuration TOML path to the recent history."""
        self._prefs.add_recent_config(path)

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

    def validate_sources_config(self, path: str) -> bool:
        """Validate whether a source configuration TOML file parses and validates correctly.

        Parameters
        ----------
        path : str
            Filesystem path to source configuration TOML file.

        Returns
        -------
        bool
            True if the configuration is valid, False otherwise.
        """
        try:
            SourceConfiguration.from_toml(path)
            return True
        except Exception:
            return False

    # --- Configuration Diagnostics & Admission Previews ---

    def validate_all_configs(
        self,
        config_path: str = "config.toml",
        rules_path: str = "rules.toml",
        sources_path: str = "sources.toml",
    ) -> ConfigValidationResult:
        """Execute full tri-configuration validation across settings, sources, and rules."""
        diag_svc = DiagnosticService()
        return diag_svc.validate_configuration(
            config_path=config_path,
            rules_path=rules_path,
            sources_path=sources_path,
        )

    def check_sources(
        self,
        sources_path: str = "sources.toml",
        config_path: str | None = None,
    ) -> SourceCheckResult:
        """Check reachability and selectors across all configured evidence sources."""
        diag_svc = DiagnosticService()
        return diag_svc.check_sources(sources_path=sources_path, config_path=config_path)

    def preview_mapping(
        self,
        dataset_id: DatasetId | str,
        sources_path: str = "sources.toml",
    ) -> MappingPreviewResult:
        """Preview column mapping and normalization sequence for a target dataset."""
        diag_svc = DiagnosticService()
        return diag_svc.preview_mapping(dataset_id=dataset_id, sources_path=sources_path)

    def preview_identity(
        self,
        dataset_id: DatasetId | str,
        sources_path: str = "sources.toml",
        config_path: str | None = None,
        sample_limit: int = 10,
    ) -> IdentityPreviewResult:
        """Preview row identity derivation strategy, sample IDs, and collision diagnostics."""
        diag_svc = DiagnosticService()
        return diag_svc.preview_identity(
            dataset_id=dataset_id,
            sources_path=sources_path,
            config_path=config_path,
            sample_limit=sample_limit,
        )

    def preview_plan(
        self,
        config_path: str = "config.toml",
        sources_path: str = "sources.toml",
    ) -> PlanPreviewResult:
        """Preview resolved capability execution plan, active datasets, and stages."""
        diag_svc = DiagnosticService()
        return diag_svc.preview_plan(config_path=config_path, sources_path=sources_path)

    def dry_run_admission(
        self,
        dataset_selector: str | None = None,
        config_path: str = "config.toml",
        rules_path: str | None = None,
        sources_path: str = "sources.toml",
        emitter: ObservabilityEmitter | None = None,
    ) -> AdmissionDryRunResult:
        """Execute in-memory admission dry run without lakehouse or control plane mutation."""
        diag_svc = DiagnosticService(emitter=emitter)
        return diag_svc.dry_run_admission(
            dataset_selector=dataset_selector,
            config_path=config_path,
            rules_path=rules_path,
            sources_path=sources_path,
            emitter=emitter,
        )

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
        on_status: Callable[[ObservabilityEvent], None],
        skip_preflight: bool = False,
    ) -> None:
        """Spawn the multiprocessing ETL pipeline and stream status updates to on_status.

        Parameters
        ----------
        config_path : str
            Path to pipeline settings TOML configuration.
        rules_path : str
            Path to financial rules TOML configuration.
        on_status : Callable[[ObservabilityEvent], None]
            Callback invoked for each streamed observability event.
        skip_preflight : bool, default=False
            Whether to skip Phase 0 pre-flight health checks.
        """
        if config_path:
            self.add_recent_config(config_path)
        if rules_path:
            self.add_recent_rules(rules_path)
        status_queue: multiprocessing.Queue[ObservabilityEvent] = multiprocessing.Queue()
        process = WorkerPoolCoordinator.spawn_process(
            status_queue, config_path, rules_path, skip_preflight=skip_preflight
        )
        WorkerPoolCoordinator.monitor_queue(process, status_queue, on_status)

    def run_pipeline_sync(
        self,
        config_path: str = "config.toml",
        rules_path: str = "",
        status_queue: EventQueue | None = None,
        skip_preflight: bool = False,
    ) -> None:
        """Execute the ETL pipeline synchronously in the current thread (ideal for profiling/testing).

        Parameters
        ----------
        config_path : str, default="config.toml"
            Path to pipeline settings TOML configuration.
        rules_path : str, default=""
            Path to financial rules TOML configuration.
        status_queue : EventQueue | None, default=None
            Queue for transmitting observability events.
        skip_preflight : bool, default=False
            Whether to skip Phase 0 pre-flight health checks.
        """
        if config_path:
            self.add_recent_config(config_path)
        if rules_path:
            self.add_recent_rules(rules_path)
        if self.container is not None and hasattr(self.container, "create_orchestrator"):
            orchestrator = self.container.create_orchestrator(
                config_path=config_path,
                rules_path=rules_path,
                status_queue=status_queue,
                skip_preflight=skip_preflight,
            )
        else:
            cfg = Settings.from_toml(config_path) if config_path else Settings()
            rules = FinancialRules.from_toml(rules_path) if rules_path else None
            diag_svc = DiagnosticService()
            orchestrator = ETLOrchestrator(
                cfg,
                status_queue,
                rules,
                skip_preflight=skip_preflight,
                diagnostic_service=diag_svc,
            )
        orchestrator.run()
