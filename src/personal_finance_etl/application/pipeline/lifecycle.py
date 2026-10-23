"""Run lifecycle and transactional commit coordinator for the ETL pipeline.

Owns
----
- RunLifecycleCoordinator: Manages transactional lifecycles across DuckDB and SQLite Control Plane.
- Atomic two-phase commit coordination (DuckDB committed first, SQLite committed second).
- Split-commit detection, durable RECOVERY_REQUIRED marking, and prior run convergence.
- Run log lifecycle, log compression archiving into Control Plane, and connection teardown.
- Emitting canonical ObservabilityEvents across lifecycle transitions.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse).
- Domain calculations or transformations (owned by domain.*).
- Pipeline step execution or DAG traversal (owned by application.pipeline.execution).
"""

from __future__ import annotations

import gc
import logging
import traceback
from pathlib import Path

from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    get_global_emitter,
    set_current_context,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    classify_failure_domain,
)
from personal_finance_etl.contracts.logging import ILogger
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    ObservabilityContext,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.logging.setup import (
    logger,
    stop_worker_listener,
)
from personal_finance_etl.infrastructure.observability import (
    JsonlForensicSink,
    LogRetentionManager,
    archive_run_trace,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer

__all__ = ["RunLifecycleCoordinator"]


class RunLifecycleCoordinator:
    """Coordinates runtime transaction state, telemetry, and split-commit recovery."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: ILogger,
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

    def _dump_configuration_logs(self) -> None:
        """Dump formatted configuration and financial rules to debug logger and emitter."""
        logger.debug("=== ETL CONFIGURATION DUMP ===")
        cfg_str = (
            self.cfg.model_dump_json(indent=2)
            if hasattr(self.cfg, "model_dump_json")
            else str(self.cfg)
        )
        logger.debug(cfg_str)

        logger.debug("=== FINANCIAL RULES DUMP ===")
        rules_str = (
            self.rules.model_dump_json(indent=2)
            if self.rules is not None and hasattr(self.rules, "model_dump_json")
            else str(self.rules)
        )
        logger.debug(rules_str)
        logger.debug("==============================")

        self.emitter.emit_event(
            event_code=EventCode.SYSTEM_CONFIG_FINGERPRINT,
            message="Loaded ETL configuration and financial rules policies",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.DEBUG,
        )

    def initialize(self) -> tuple[ControlPlane, str, list[str]]:
        """Initialize logging, open database instances, begin transactions, and record run start.

        Returns
        -------
        tuple[ControlPlane, str, list[str]]
            Tuple of active ControlPlane instance, unique run_id string, and pending recovery run IDs.
        """
        logger.info("Initializing Personal Finance ETL...")
        self.emitter.emit_event(
            event_code=EventCode.RUN_START,
            message="Initializing Personal Finance ETL...",
            presentation_kind=PresentationKind.STEP,
            stage=EngineStage.INITIALIZING,
        )

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
        set_current_context(
            ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.INITIALIZING,
                component="lifecycle",
            )
        )

        logs_dir = self.cfg.resolve_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.forensic_file_path = logs_dir / f"trace_{run_id}.jsonl"
        self.forensic_sink = JsonlForensicSink(self.forensic_file_path)
        self.emitter.register_sink(self.forensic_sink)

        self._dump_configuration_logs()

        # Detect any prior runs left requiring recovery
        self.pending_recovery_runs = cp.runs.get_recovery_required_runs()
        if self.pending_recovery_runs:
            rec_msg = (
                f"Found {len(self.pending_recovery_runs)} prior run(s) requiring convergence: "
                f"{self.pending_recovery_runs}. Initiating state reconciliation."
            )
            logger.warning(rec_msg)
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
        logger.debug("Beginning DuckDB ACID transaction...")
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
            logger.debug("Committing DuckDB transaction...")
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
            logger.info(conv_msg)
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
                logger.debug("Rolling back DuckDB transaction...")
                self.db_manager.conn.execute("ROLLBACK")
                logger.warning("DuckDB transaction rolled back.")
                self.emitter.emit_event(
                    event_code=EventCode.DATABASE_ROLLBACK,
                    message="DuckDB transaction rolled back.",
                    presentation_kind=PresentationKind.RECOVERY,
                    severity=DiagnosticSeverity.WARNING,
                )
            except Exception as rollback_err:
                logger.error(f"Failed to rollback DuckDB transaction: {rollback_err}")
        elif self.duckdb_committed:
            logger.warning("DuckDB is already committed; cannot rollback DuckDB.")

        if self.cp is not None and self.sqlite_started and not self.sqlite_committed:
            try:
                self.cp.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback SQLite Raw Store transaction: {rollback_err}")

    def _log_failure_status(self) -> None:
        """Emit truthful rollback logging guarded strictly by commit state."""
        messages: dict[CommitState, tuple[int, str]] = {
            CommitState.ROLLED_BACK: (
                logging.WARNING,
                "Pipeline failed. All open transactions rolled back to maintain integrity (state: ROLLED_BACK).",
            ),
            CommitState.RECOVERY_REQUIRED: (
                logging.ERROR,
                "CRITICAL SPLIT-COMMIT DIVERGENCE: DuckDB committed successfully, but SQLite Raw Store commit failed. "
                "Transactions CANNOT be fully rolled back. DuckDB has durable changes. State: RECOVERY_REQUIRED. "
                "RECOVERY_REQUIRED marker will be persisted.",
            ),
            CommitState.FULLY_COMMITTED: (
                logging.WARNING,
                "Pipeline encountered post-commit failure. Transactions are already fully committed (state: FULLY_COMMITTED).",
            ),
            CommitState.COMMIT_STATE_UNKNOWN: (
                logging.ERROR,
                "Pipeline failed with uncertain transaction commit state (state: COMMIT_STATE_UNKNOWN).",
            ),
        }
        level, msg = messages.get(
            self.commit_state,
            (logging.ERROR, f"Pipeline failed with unexpected commit state ({self.commit_state})."),
        )
        logger.log(level, msg)

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
        logger.exception("CRITICAL PIPELINE FAILURE:")
        self.commit_state = self._resolve_commit_state()
        self._rollback_open_transactions()
        self._log_failure_status()
        try:
            self._persist_failure_telemetry(exc)
        except Exception as failure_log_err:
            logger.error(f"Failed to log run_failure to Control Plane: {failure_log_err}")

        domain = classify_failure_domain("Pipeline", type(exc).__name__ or str(exc))
        err_details = ErrorDetails(
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            failure_domain=domain,
            traceback_summary=traceback.format_exc(),
            retryable=False,
        )
        self.emitter.emit_event(
            event_code=EventCode.RUN_FAILED,
            message=f"Critical Pipeline Failure: {exc}",
            presentation_kind=PresentationKind.FAILURE,
            severity=DiagnosticSeverity.ERROR,
            error=err_details,
            stage=EngineStage.FAILED,
        )

    def teardown(self) -> None:
        """Teardown logging handlers, archive compressed execution log, and close database handles."""
        logger.info("Cleaning up database connections and WAL sidecars...")
        self.emitter.emit_event(
            event_code=EventCode.SYSTEM_TEARDOWN,
            message="Cleaning up database connections and WAL sidecars...",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.INFO,
        )
        stop_worker_listener()
        if self.forensic_sink is not None:
            self.forensic_sink.close()
            self.emitter.unregister_sink(self.forensic_sink)
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
            logger.debug("Log Retention: Non-fatal cleanup error: %s", retention_err)

        try:
            self.db_manager.close()
        finally:
            if self.cp is not None:
                self.cp.close()
            # Materialization Boundary: PROCESS_BOUNDARY
            # Explicit Python runtime garbage collection invocation between execution stages
            gc.collect()
