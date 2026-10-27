"""Run lifecycle and transactional commit coordinator for the ETL pipeline.

Owns
----
- RunLifecycleCoordinator: Manages transactional lifecycles across DuckDB and SQLite Control Plane.
- Atomic two-phase commit coordination (DuckDB committed first, SQLite committed second).
- Split-commit detection, durable RECOVERY_REQUIRED marking, and prior run convergence.
- Forensic trace lifecycle, compressed Control Plane archival, and connection teardown.
- Emitting canonical ObservabilityEvents across lifecycle transitions.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse).
- Domain calculations or transformations (owned by domain.*).
- Pipeline step execution or DAG traversal (owned by application.pipeline.execution).
"""

from __future__ import annotations

import gc
import traceback
from pathlib import Path

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    classify_failure_domain,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    ObservabilityContext,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    AsyncObservabilityListener,
    JsonlForensicSink,
    LogRetentionManager,
    ObservabilityEmitter,
    ObservabilityQueueSink,
    archive_run_trace,
    create_forensic_pipeline,
    fingerprint_config,
    fingerprint_rules,
    get_global_emitter,
    set_current_context,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer

__all__ = ["RunLifecycleCoordinator"]

diagnostics = get_observability_diagnostics(__name__)


class RunLifecycleCoordinator:
    """Coordinates runtime transaction state, telemetry, and split-commit recovery."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: EventQueue,
        db_manager: DuckDBManager,
        rules: FinancialRules | None = None,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cfg = cfg
        self.status_queue = status_queue
        self.db_manager = db_manager
        self.rules = rules
        self.emitter = emitter or get_global_emitter()

        self.duckdb_started: bool = False
        self.sqlite_started: bool = False
        self.duckdb_committed: bool = False
        self.sqlite_committed: bool = False
        self.commit_state: CommitState = CommitState.NOT_STARTED
        self.pending_recovery_runs: list[str] = []
        self.cp: ControlPlane | None = None
        self.run_id: str | None = None
        self.forensic_file_path: Path | None = None
        self.forensic_sink: JsonlForensicSink | None = None
        self.async_listener: AsyncObservabilityListener | None = None
        self.queue_sink: ObservabilityQueueSink | None = None

    def _dump_configuration_logs(self) -> None:
        """Emit deterministic provenance fingerprint event and safe configuration summary."""
        settings_summary = fingerprint_config(self.cfg)
        rules_summary = fingerprint_rules(self.rules)

        diagnostics.info(
            "Configuration fingerprint: %s | Rules fingerprint: %s",
            settings_summary["config_hash"],
            rules_summary["rules_hash"],
        )

        self.emitter.emit_event(
            event_code=EventCode.SYSTEM_CONFIG_FINGERPRINT,
            message=(
                f"Configuration fingerprint: {settings_summary['config_hash']} | "
                f"Rules fingerprint: {rules_summary['rules_hash']}"
            ),
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.INFO,
            settings_fingerprint=settings_summary["config_hash"],
            rules_fingerprint=rules_summary["rules_hash"],
        )

    def initialize(self) -> tuple[ControlPlane, str, list[str]]:
        """Initialize observability, open databases, begin transactions, and record run start.

        Returns
        -------
        tuple[ControlPlane, str, list[str]]
            Tuple of active ControlPlane instance, unique run_id string, and pending recovery run IDs.
        """
        self.db_manager.open()
        self.db_manager.ensure_schemas()

        cp = ControlPlane(self.cfg.TARGET_DB_BASE_PATH, self.cfg.RAW_DOCUMENT_STORE_NAME)
        cp.open()
        cp.ensure_schema()
        self.cp = cp

        # 1. Authoritative SQLite State
        run_id = cp.runs.start_run(
            cfg_json=self.cfg.model_dump_json(),
            rules_json=self.rules.model_dump_json() if self.rules else None,
        )
        self.run_id = run_id
        cp.active_run_id = run_id
        cp.artifacts.active_run_id = run_id
        cp.file_sync.active_run_id = run_id

        # Bind ambient context for current execution run
        settings_summary = fingerprint_config(self.cfg)
        rules_summary = fingerprint_rules(self.rules)
        set_current_context(
            ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.INITIALIZING,
                component="lifecycle",
                settings_fingerprint=settings_summary["config_hash"],
                rules_fingerprint=rules_summary["rules_hash"],
            )
        )

        logs_dir = self.cfg.resolve_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.forensic_file_path = logs_dir / f"trace_{run_id}.jsonl"
        self.queue_sink, self.async_listener, self.forensic_sink = create_forensic_pipeline(
            self.forensic_file_path, buffer_size=50
        )
        self.async_listener.start()
        self.emitter.register_sink(self.queue_sink)

        self._dump_configuration_logs()

        # Detect any prior runs left requiring recovery
        self.pending_recovery_runs = cp.runs.get_recovery_required_runs()
        if self.pending_recovery_runs:
            rec_msg = (
                f"Found {len(self.pending_recovery_runs)} prior run(s) requiring convergence: "
                f"{self.pending_recovery_runs}. Initiating state reconciliation."
            )
            self.emitter.emit_event(
                event_code=EventCode.DATABASE_ROLLBACK,
                message=rec_msg,
                presentation_kind=PresentationKind.RECOVERY,
                severity=DiagnosticSeverity.WARNING,
                rows=len(self.pending_recovery_runs),
            )

        # 2. Mirror to DuckDB Analytics
        meta_layer = MetaLayer(self.db_manager, self.cfg, self.rules)
        meta_layer.heal_duckdb_registry(cp)

        # Start ACID Transaction for the entire ETL run
        self.emitter.emit_event(
            event_code=EventCode.DATABASE_COMMIT,
            message="Beginning DuckDB ACID transaction",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.DEBUG,
        )
        self.db_manager.conn.execute("BEGIN TRANSACTION")
        self.duckdb_started = True

        cp.begin_transaction()
        self.sqlite_started = True
        self.commit_state = CommitState.STARTED

        cp.runs.update_run_status(run_id, "RUNNING")
        return cp, run_id, self.pending_recovery_runs

    def commit(self) -> None:
        """Execute atomic two-phase commit across DuckDB and SQLite Control Plane."""
        if self.cp is None or self.run_id is None:
            raise RuntimeError("Cannot commit pipeline run before initialization.")

        cp = self.cp
        run_id = self.run_id

        cp.runs.update_run_status(run_id, "COMMITTING")

        # 1. Commit DuckDB
        try:
            self.emitter.emit_event(
                event_code=EventCode.DATABASE_COMMIT,
                message="Committing DuckDB transaction",
                presentation_kind=PresentationKind.INTERNAL,
                severity=DiagnosticSeverity.DEBUG,
            )
            self.db_manager.conn.execute("COMMIT")
            self.duckdb_committed = True
            self.commit_state = CommitState.DUCKDB_COMMITTED
            cp.runs.update_commit_state(run_id, CommitState.DUCKDB_COMMITTED)
        except Exception as duckdb_commit_err:
            self.commit_state = CommitState.ROLLED_BACK
            cp.runs.update_commit_state(run_id, CommitState.ROLLED_BACK)
            raise RuntimeError(f"DuckDB Commit Failed: {duckdb_commit_err}") from duckdb_commit_err

        # 2. Commit SQLite
        try:
            cp.commit()
            self.sqlite_committed = True
            self.commit_state = CommitState.FULLY_COMMITTED
            cp.runs.update_commit_state(run_id, CommitState.FULLY_COMMITTED)
        except Exception as sqlite_commit_err:
            self.commit_state = CommitState.RECOVERY_REQUIRED
            cp.runs.update_commit_state(run_id, CommitState.RECOVERY_REQUIRED)
            raise RuntimeError(
                f"SQLite Commit Failed after DuckDB committed: {sqlite_commit_err}"
            ) from sqlite_commit_err

        cp.runs.finish_run(run_id, "SUCCESS", commit_state=CommitState.FULLY_COMMITTED)

        if self.pending_recovery_runs:
            for rec_run_id in self.pending_recovery_runs:
                cp.runs.mark_recovery_converged(rec_run_id, run_id)
            conv_msg = (
                f"Successfully converged {len(self.pending_recovery_runs)} prior diverged run(s): "
                f"{self.pending_recovery_runs}."
            )
            self.emitter.emit_event(
                event_code=EventCode.DATABASE_COMMIT,
                message=conv_msg,
                presentation_kind=PresentationKind.SUCCESS,
                rows=len(self.pending_recovery_runs),
            )

    def _resolve_commit_state(self) -> CommitState:
        """Derive explicit commit state from component database transaction statuses."""
        match (self.duckdb_committed, self.sqlite_committed):
            case (True, False):
                return CommitState.RECOVERY_REQUIRED
            case (False, False):
                return CommitState.ROLLED_BACK
            case (True, True):
                return CommitState.FULLY_COMMITTED
            case _:
                return CommitState.COMMIT_STATE_UNKNOWN

    def _rollback_open_transactions(self) -> None:
        """Rollback open transactions across DuckDB and SQLite if not already committed."""
        if self.duckdb_started and not self.duckdb_committed:
            try:
                diagnostics.debug("Rolling back DuckDB transaction...")
                self.db_manager.conn.execute("ROLLBACK")
                self.emitter.emit_event(
                    event_code=EventCode.DATABASE_ROLLBACK,
                    message="DuckDB transaction rolled back.",
                    presentation_kind=PresentationKind.RECOVERY,
                    severity=DiagnosticSeverity.WARNING,
                )
            except Exception as rollback_err:
                diagnostics.error(f"Failed to rollback DuckDB transaction: {rollback_err}")
        elif self.duckdb_committed:
            diagnostics.warning("DuckDB is already committed; cannot rollback DuckDB.")

        if self.cp is not None and self.sqlite_started and not self.sqlite_committed:
            try:
                self.cp.rollback()
            except Exception as rollback_err:
                diagnostics.error(
                    f"Failed to rollback SQLite Raw Store transaction: {rollback_err}"
                )

    def _log_failure_status(self) -> None:
        """Emit truthful rollback diagnostics guarded strictly by commit state."""
        messages: dict[CommitState, tuple[DiagnosticSeverity, str]] = {
            CommitState.ROLLED_BACK: (
                DiagnosticSeverity.WARNING,
                "Pipeline failed. All open transactions rolled back to maintain integrity (state: ROLLED_BACK).",
            ),
            CommitState.RECOVERY_REQUIRED: (
                DiagnosticSeverity.ERROR,
                "CRITICAL SPLIT-COMMIT DIVERGENCE: DuckDB committed successfully, but SQLite Raw Store commit failed. "
                "Transactions CANNOT be fully rolled back. DuckDB has durable changes. State: RECOVERY_REQUIRED. "
                "RECOVERY_REQUIRED marker will be persisted.",
            ),
            CommitState.FULLY_COMMITTED: (
                DiagnosticSeverity.WARNING,
                "Pipeline encountered post-commit failure. Transactions are already fully committed (state: FULLY_COMMITTED).",
            ),
            CommitState.COMMIT_STATE_UNKNOWN: (
                DiagnosticSeverity.ERROR,
                "Pipeline failed with uncertain transaction commit state (state: COMMIT_STATE_UNKNOWN).",
            ),
        }
        level, msg = messages.get(
            self.commit_state,
            (
                DiagnosticSeverity.ERROR,
                f"Pipeline failed with unexpected commit state ({self.commit_state}).",
            ),
        )
        diagnostics.emit(level, msg)

    def _persist_failure_telemetry(self, exc: Exception) -> None:
        """Persist error telemetry, failure domains, and recovery markers into Control Plane."""
        if self.cp is None or self.run_id is None:
            return

        if self.commit_state == CommitState.RECOVERY_REQUIRED:
            divergence_msg = (
                f"Split-commit divergence: DuckDB committed, but SQLite commit failed: {exc}. "
                "duckdb_commit_state=COMMITTED, sqlite_commit_state=FAILED"
            )
            self.cp.runs.mark_recovery_required(
                run_id=self.run_id,
                error_message=divergence_msg,
                stage="COMMIT",
                traceback_log=traceback.format_exc(),
            )
            return

        self.cp.runs.update_commit_state(self.run_id, self.commit_state)
        exc_str = str(exc)
        if "ISIN_FAILURE" in exc_str:
            parts = exc_str.split("|")
            failed_isin = parts[1] if len(parts) >= 3 else None
            error_msg = parts[2] if len(parts) >= 3 else exc_str
            self.cp.runs.log_run_failure(
                run_id=self.run_id,
                failed_isin=failed_isin,
                stage="InvestmentQuantEngine",
                error_type="RuntimeError",
                error_message=error_msg,
                traceback_log=traceback.format_exc(),
                failure_domain=FailureDomain.FINANCIAL_INVARIANT,
            )
        else:
            domain = classify_failure_domain("Pipeline", type(exc).__name__ or exc_str)
            self.cp.runs.log_run_failure(
                run_id=self.run_id,
                failed_isin=None,
                stage="Pipeline",
                error_type=type(exc).__name__,
                error_message=exc_str,
                traceback_log=traceback.format_exc(),
                failure_domain=domain,
            )
        self.cp.runs.finish_run(self.run_id, "FAILED", commit_state=self.commit_state)

    def handle_failure(self, exc: Exception) -> None:
        """Rollback open transactions and persist truthful error telemetry into Control Plane."""
        diagnostics.exception("CRITICAL PIPELINE FAILURE:")
        self.commit_state = self._resolve_commit_state()
        self._rollback_open_transactions()
        self._log_failure_status()
        try:
            self._persist_failure_telemetry(exc)
        except Exception as failure_log_err:
            diagnostics.error(f"Failed to log run_failure to Control Plane: {failure_log_err}")

        domain = classify_failure_domain("Pipeline", type(exc).__name__ or str(exc))

        # Build actionable remediation guidance based on failure classification
        hint = ""
        exc_str = str(exc)
        if "ISIN_FAILURE" in exc_str:
            hint = "Verify purchase/sale dates and prices in statement files; ensure market data covers all holding dates."
        elif domain == FailureDomain.SOURCE_VALIDATION or "Gatekeeper" in exc_str:
            hint = (
                "Check column schema and data types in raw source files against column_master.csv."
            )
        elif isinstance(exc, FileNotFoundError) or "not found" in exc_str.lower():
            hint = "Check configured paths and ensure required input files exist in configured directories."
        elif isinstance(exc, PermissionError) or "database is locked" in exc_str.lower():
            hint = "Close any external DuckDB, SQLite, or Excel programs holding open locks on the files."
        elif "commit" in exc_str.lower() or domain in (
            FailureDomain.DUCKDB_COMMIT,
            FailureDomain.SQLITE_COMMIT,
        ):
            hint = "Inspect database file integrity and ensure sufficient disk space for transaction commits."

        ctx_vars: dict[str, str | int | float | bool] = {
            "commit_state": self.commit_state.value,
        }
        if self.forensic_file_path:
            ctx_vars["forensic_trace_path"] = str(self.forensic_file_path)

        err_details = ErrorDetails.create(
            exc=exc,
            failure_domain=domain,
            stage="PipelineLifecycle",
            hint=hint,
            retryable=False,
            context_variables=ctx_vars,
        )

        trace_hint = (
            f"\n  ↳ Forensic Trace: {self.forensic_file_path}" if self.forensic_file_path else ""
        )
        self.emitter.emit_event(
            event_code=EventCode.RUN_FAILED,
            message=f"Critical Pipeline Failure: {exc}{trace_hint}",
            presentation_kind=PresentationKind.FAILURE,
            severity=DiagnosticSeverity.ERROR,
            error=err_details,
            stage=EngineStage.FAILED,
            commit_state=self.commit_state,
        )

    def teardown(self) -> None:
        """Drain observability, archive the compressed trace, and close database handles."""
        self.emitter.emit_event(
            event_code=EventCode.SYSTEM_TEARDOWN,
            message="Cleaning up database connections and WAL sidecars...",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.INFO,
        )
        if self.queue_sink is not None:
            self.emitter.unregister_sink(self.queue_sink)
            self.queue_sink = None
        if self.async_listener is not None:
            self.async_listener.stop(timeout=5.0)
            self.async_listener = None
        self.forensic_sink = None

        if (
            self.cp is not None
            and self.run_id is not None
            and self.forensic_file_path is not None
            and self.forensic_file_path.exists()
        ):
            archive_run_trace(self.cp, self.run_id, str(self.forensic_file_path))

        try:
            logs_dir = self.cfg.resolve_logs_dir()
            retention_mgr = LogRetentionManager(
                logs_dir=logs_dir,
                retain_last_n_runs=self.cfg.RETAIN_LAST_N_RUNS,
            )
            retention_mgr.prune_expired_traces()
        except Exception as retention_err:
            diagnostics.debug("Log Retention: Non-fatal cleanup error: %s", retention_err)

        try:
            self.db_manager.close()
        finally:
            if self.cp is not None:
                self.cp.close()
            # Materialization Boundary: PROCESS_BOUNDARY
            # Explicit Python runtime garbage collection invocation between execution stages
            gc.collect()
