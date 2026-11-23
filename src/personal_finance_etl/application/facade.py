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

import json
import multiprocessing
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from tomlkit.toml_document import TOMLDocument

from personal_finance_etl.application.operator import (
    DoctorReport,
    OperatorService,
    SystemInfo,
    SystemStatus,
)
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.worker import WorkerPoolCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.configuration.toml_store import (
    TomlRulesStore,
    TomlSettingsStore,
)
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager

__all__ = ["ContainerProtocol", "PersonalFinanceEngine"]


class ContainerProtocol(Protocol):
    """Structural protocol for bootstrap container dependency resolution."""

    def create_orchestrator(
        self,
        config_path: str | None = None,
        rules_path: str | None = None,
        status_queue: EventQueue | None = None,
        settings: Settings | None = None,
    ) -> ETLOrchestrator:
        """Create and wire an ETLOrchestrator with configuration and observability."""
        ...

    def create_operator_service(
        self,
        config_path: str | None = None,
        rules_path: str | None = None,
    ) -> OperatorService:
        """Create and wire an OperatorService with an OperatorInspector."""
        ...


class PersonalFinanceEngine:
    """Unified Façade for the entire Personal Finance Backend and Presentation boundary."""

    def __init__(self, container: ContainerProtocol | None = None) -> None:
        self.container = container
        self._prefs = PreferencesManager()
        self._toml_store = TomlSettingsStore()
        self._rules_store = TomlRulesStore()

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

    def load_settings_document(self, filepath: str) -> tuple[Settings, TOMLDocument]:
        """Load a configuration TOML file into a Settings instance and TOMLDocument AST."""
        return self._toml_store.load_document(filepath)

    def save_settings_document(
        self,
        filepath: str,
        settings: Settings,
        original_doc: TOMLDocument | None = None,
    ) -> None:
        """Atomically persist validated Settings to disk and add to recent configs."""
        self._toml_store.save_document(filepath, settings, original_doc=original_doc)
        self.add_recent_config(filepath)

    def save_settings_document_as(
        self,
        target_filepath: str,
        settings: Settings,
        source_filepath: str | None = None,
    ) -> None:
        """Save settings to a new destination, optionally copying structure from source."""
        original_doc: TOMLDocument | None = None
        if source_filepath and os.path.isfile(source_filepath):
            _, original_doc = self._toml_store.load_document(source_filepath)
        self.save_settings_document(target_filepath, settings, original_doc=original_doc)

    def validate_settings_model(self, settings: Settings) -> None:
        """Perform full validation on a Settings model, verifying path existence."""
        settings.validate_config()

    def load_financial_rules_document(self, filepath: str) -> tuple[FinancialRules, TOMLDocument]:
        """Load a financial rules TOML file into a FinancialRules instance and TOMLDocument AST."""
        return self._rules_store.load_document(filepath)

    def save_financial_rules_document(
        self,
        filepath: str,
        rules: FinancialRules,
        original_doc: TOMLDocument | None = None,
    ) -> None:
        """Atomically persist validated FinancialRules to disk and add to recent rules."""
        self._rules_store.save_document(filepath, rules, original_doc=original_doc)
        self.add_recent_rules(filepath)

    def save_financial_rules_document_as(
        self,
        target_filepath: str,
        rules: FinancialRules,
        source_filepath: str | None = None,
    ) -> None:
        """Save rules to a new destination, optionally copying structure from source."""
        original_doc: TOMLDocument | None = None
        if source_filepath and os.path.isfile(source_filepath):
            _, original_doc = self._rules_store.load_document(source_filepath)
        self.save_financial_rules_document(target_filepath, rules, original_doc=original_doc)

    def validate_financial_rules_model(self, rules: FinancialRules) -> None:
        """Validate in-memory FinancialRules model integrity."""
        FinancialRules.model_validate(rules.model_dump())

    # --- Operator Services ---

    def get_system_status(self, config_path: str | None = None) -> SystemStatus:
        """Query system status, lock state, and latest run telemetry read-only."""
        if self.container is not None and hasattr(self.container, "create_operator_service"):
            op = self.container.create_operator_service(config_path=config_path)
        else:
            op = OperatorService(config_path=config_path)
        return op.get_status()

    def get_system_info(self, config_path: str | None = None) -> SystemInfo:
        """Inspect runtime environment, configured paths, and warehouse table inventory."""
        if self.container is not None and hasattr(self.container, "create_operator_service"):
            op = self.container.create_operator_service(config_path=config_path)
        else:
            op = OperatorService(config_path=config_path)
        return op.get_info()

    def run_doctor(
        self, config_path: str | None = None, rules_path: str | None = None
    ) -> DoctorReport:
        """Execute actionable system health checks without raising unhandled exceptions."""
        if self.container is not None and hasattr(self.container, "create_operator_service"):
            op = self.container.create_operator_service(
                config_path=config_path, rules_path=rules_path
            )
        else:
            op = OperatorService(config_path=config_path, rules_path=rules_path)
        return op.run_doctor()

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
            cfg.database.target_db_base_path,
            sqlite_db_name=cfg.database.raw_document_store_name,
            duckdb_name=cfg.database.target_db_name,
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
            cfg.database.target_db_base_path,
            sqlite_db_name=cfg.database.raw_document_store_name,
            duckdb_name=cfg.database.target_db_name,
        )
        return backup_mgr.restore_snapshot(backup_zip_path)

    # --- Pipeline Execution ---

    def run_pipeline_async(
        self,
        config_path: str,
        rules_path: str,
        on_status: Callable[[ObservabilityEvent], None],
    ) -> threading.Thread:
        """Spawn the multiprocessing ETL pipeline and stream status updates to on_status."""
        if config_path:
            self.add_recent_config(config_path)
        if rules_path:
            self.add_recent_rules(rules_path)
        status_queue: multiprocessing.Queue[ObservabilityEvent] = multiprocessing.Queue()
        process = WorkerPoolCoordinator.spawn_process(status_queue, config_path, rules_path)
        return WorkerPoolCoordinator.monitor_queue(process, status_queue, on_status)

    def run_pipeline_sync(
        self,
        config_path: str = "config.toml",
        rules_path: str = "",
        status_queue: EventQueue | None = None,
    ) -> None:
        """Execute the ETL pipeline synchronously in the current thread (ideal for profiling/testing)."""
        if config_path:
            self.add_recent_config(config_path)
        if rules_path:
            self.add_recent_rules(rules_path)
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

    # --- Forensic Observability and Logs ---

    def get_logs_directory(self, config_path: str | None = None) -> Path:
        """Resolve the active logs directory from configuration or default fallback."""
        if config_path and os.path.exists(config_path):
            try:
                cfg = Settings.from_toml(config_path)
                return cfg.resolve_logs_dir()
            except Exception:
                pass
        return Path("outputs/logs")

    def discover_log_files(self, config_path: str | None = None) -> list[Path]:
        """Discover available JSONL forensic log files sorted newest first."""
        log_dir = self.get_logs_directory(config_path)
        if not log_dir.is_dir():
            return []
        try:
            files = [p for p in log_dir.glob("*.jsonl") if p.is_file()]
            runs_sub = log_dir / "runs"
            if runs_sub.is_dir():
                files.extend([p for p in runs_sub.glob("*.jsonl") if p.is_file()])
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return files
        except Exception:
            return []

    def read_jsonl_log(
        self, file_path: Path | str, limit: int = 1000
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Safely parse lines from a JSONL log file without throwing unhandled exceptions.

        Returns
        -------
        tuple[list[dict[str, Any]], str | None]
            List of parsed event dictionaries (including structured warning rows for malformed lines)
            and the detected run_id if discovered.
        """
        p = Path(file_path)
        if not p.is_file():
            return [], None

        events: list[dict[str, Any]] = []
        detected_run_id: str | None = None

        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f):
                    if len(events) >= limit:
                        break
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        record: Any = json.loads(stripped)
                        if isinstance(record, dict):
                            record_dict = cast("dict[str, Any]", record)
                            events.append(record_dict)
                            if detected_run_id is None:
                                raw_ctx = record_dict.get("context")
                                if isinstance(raw_ctx, dict):
                                    ctx_dict = cast("dict[str, object]", raw_ctx)
                                    run_id_val = ctx_dict.get("run_id")
                                    if run_id_val is not None:
                                        detected_run_id = str(run_id_val)
                        else:
                            events.append(
                                self._create_malformed_event_row(
                                    stripped, line_idx, "Not a JSON object"
                                )
                            )
                    except Exception as err:
                        events.append(
                            self._create_malformed_event_row(stripped, line_idx, str(err))
                        )
        except Exception as file_err:
            events.append(
                self._create_malformed_event_row(str(p), 0, f"Failed to read file: {file_err}")
            )

        return events, detected_run_id

    @staticmethod
    def _create_malformed_event_row(raw_text: str, line_no: int, error_msg: str) -> dict[str, Any]:
        """Construct a structured warning row for truncated or malformed JSONL rows."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_code": "LOG_PARSE_WARNING",
            "severity": "WARNING",
            "presentation_kind": "WARNING",
            "outcome": "FAILED",
            "message": f"Malformed or truncated JSONL line {line_no + 1}: {raw_text[:120]}...",
            "context": {
                "stage": "OBSERVABILITY",
                "component": "JsonlReader",
                "operation": "parse_line",
                "line_number": line_no + 1,
            },
            "error": {
                "exception_type": "JSONDecodeError",
                "exception_message": error_msg,
                "failure_domain": "SYSTEM",
                "traceback_summary": "",
                "retryable": False,
                "remediation_hint": "Check if write operation was abruptly interrupted.",
                "context_variables": {"raw_snippet": raw_text[:200]},
            },
        }
