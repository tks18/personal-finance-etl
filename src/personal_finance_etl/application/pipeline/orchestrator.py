"""Orchestrator coordinating the execution of the quantitative ETL pipeline.

Owns
----
- ETLOrchestrator: High-level use-case coordinator driving the 5 pipeline phases.
- Delegating transactions, observability, and split-commit recovery to RunLifecycleCoordinator.
- Delegating evidence extraction, transformations, and warehouse loading to PipelineExecutor.
- Emitting pipeline run start and completion events via central ObservabilityEmitter.

Does not own
-------------
- Concrete DuckDB/SQLite database mechanics (owned by infrastructure.warehouse and infrastructure.control_plane).
- Financial algorithms or calculation formulas (owned by domain.*).
- Multiprocessing child process supervision (owned by application.pipeline.worker).
"""

from __future__ import annotations

import time
from typing import Protocol

import polars as pl

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
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
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.diagnostics import (
    ConfigValidationResult,
    DiagnosticSeverity,
    PreflightCheckFailedError,
    SourceCheckResult,
    SourceReachabilityStatus,
)
from personal_finance_etl.contracts.event_transport import EventQueue, NullEventQueue
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import (
    EventCode,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager

__all__ = ["ETLOrchestrator", "PreflightDiagnosticProtocol"]

diagnostics = get_observability_diagnostics(__name__)


class PreflightDiagnosticProtocol(Protocol):
    """Protocol for executing pre-flight diagnostics without coupling to concrete services."""

    def validate_configuration(
        self,
        config_path: str = "config.toml",
        rules_path: str = "rules.toml",
        sources_path: str = "sources.toml",
        plan: ExecutionPlan | None = None,
        settings: Settings | None = None,
        rules: FinancialRules | None = None,
        sources: SourceConfiguration | None = None,
    ) -> ConfigValidationResult:
        """Validate multi-configuration models.

        Parameters
        ----------
        config_path : str, default "config.toml"
            Path to application settings TOML file.
        rules_path : str, default "rules.toml"
            Path to financial rules TOML file.
        sources_path : str, default "sources.toml"
            Path to source configuration TOML file.
        plan : ExecutionPlan | None, default None
            Pre-compiled ExecutionPlan instance to validate.
        settings : Settings | None, default None
            Pre-loaded Settings instance to validate.
        rules : FinancialRules | None, default None
            Pre-loaded FinancialRules instance to validate.
        sources : SourceConfiguration | None, default None
            Pre-loaded SourceConfiguration instance to validate.

        Returns
        -------
        ConfigValidationResult
            Validation outcome and structured diagnostic issues.
        """
        ...

    def check_sources(
        self,
        sources_path: str = "sources.toml",
        config_path: str | None = None,
        source_config: SourceConfiguration | None = None,
        source_plan: CompiledSourcePlan | None = None,
    ) -> SourceCheckResult:
        """Verify reachability of configured evidence sources and dataset selectors.

        Parameters
        ----------
        sources_path : str, default "sources.toml"
            Path to sources TOML file.
        config_path : str | None, default None
            Path to settings TOML file.
        source_config : SourceConfiguration | None, default None
            Pre-loaded SourceConfiguration instance to verify.
        source_plan : CompiledSourcePlan | None, default None
            Pre-compiled source plan to discover files against.

        Returns
        -------
        SourceCheckResult
            Reachability and file/table inspection outcomes.
        """
        ...


class ETLOrchestrator:
    """High-level application coordinator driving end-to-end quantitative ETL execution."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: EventQueue | None = None,
        rules: FinancialRules | None = None,
        emitter: ObservabilityEmitter | None = None,
        plan: ExecutionPlan | None = None,
        source_config: SourceConfiguration | None = None,
        source_plan: CompiledSourcePlan | None = None,
        skip_preflight: bool = False,
        diagnostic_service: PreflightDiagnosticProtocol | None = None,
    ) -> None:
        """Initialize the ETL orchestrator.

        Parameters
        ----------
        cfg : Settings
            Pipeline settings instance.
        status_queue : EventQueue | None, default None
            Queue transport for emitting status updates.
        rules : FinancialRules | None, default None
            Configured financial rules model.
        emitter : ObservabilityEmitter | None, default None
            Telemetry and forensic logging emitter.
        plan : ExecutionPlan | None, default None
            Pre-compiled capability execution plan.
        source_config : SourceConfiguration | None, default None
            Source configuration defining evidence datasets.
        source_plan : CompiledSourcePlan | None, default None
            Pre-compiled source plan.
        skip_preflight : bool, default False
            Whether to skip Phase 0 pre-flight validation.
        diagnostic_service : PreflightDiagnosticProtocol | None, default None
            Diagnostic service for executing pre-flight health checks.
        """
        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue or NullEventQueue()
        self.emitter = emitter or get_global_emitter()
        self.source_config = source_config or get_shan_baseline_source_configuration(settings=cfg)
        self.skip_preflight = skip_preflight
        self.diagnostic_service = diagnostic_service

        if plan is not None:
            self.plan = plan
        else:
            requested_caps = cfg.capabilities.resolved_capabilities
            self.plan = CapabilityPlanner().create_plan(requested_capabilities=requested_caps)

        if source_plan is not None:
            self.source_plan = source_plan
        else:
            self.source_plan = SourcePlanner(self.source_config, self.plan).compile_plan()

        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.executor = PipelineExecutor(
            cfg,
            self.status_queue,
            self.db_manager,
            rules,
            emitter=self.emitter,
            plan=self.plan,
            source_config=self.source_config,
            source_plan=self.source_plan,
        )

    @property
    def dfs(self) -> dict[str, pl.DataFrame]:
        """Active collection of transformed datasets."""
        return self.executor.dfs

    @dfs.setter
    def dfs(self, value: dict[str, pl.DataFrame]) -> None:
        """Set the active collection of transformed datasets."""
        self.executor.dfs = value

    def execute_preflight_check(self) -> None:
        """Execute Phase 0: Pre-Flight Health Check verifying tri-config and source reachability."""
        if self.diagnostic_service is None:
            return

        chk_start = time.perf_counter()
        self.emitter.emit_event(
            event_code=EventCode.PREFLIGHT_START,
            message="Phase 0/5 [Pre-Flight]: Executing configuration & source reachability health checks...",
            presentation_kind=PresentationKind.STEP,
            stage=EngineStage.INITIALIZING,
        )

        val_res = self.diagnostic_service.validate_configuration(
            settings=self.cfg,
            sources=self.source_config,
            rules=self.rules,
            plan=self.plan,
        )
        src_res = self.diagnostic_service.check_sources(
            source_config=self.source_config,
            source_plan=self.source_plan,
        )

        errors = [
            issue
            for issue in (*val_res.issues, *src_res.issues)
            if issue.severity == DiagnosticSeverity.ERROR
        ]
        required_source_ids = {
            b.source_id
            for b in self.source_config.datasets
            if b.dataset_id in self.plan.required_bronze_datasets
        }
        unreachable = [
            s
            for s in src_res.sources
            if s.status != SourceReachabilityStatus.REACHABLE and s.source_id in required_source_ids
        ]

        chk_duration_ms = (time.perf_counter() - chk_start) * 1000.0

        if errors or unreachable:
            error_msgs = [f"[{e.category}] {e.message}" for e in errors]
            for u in unreachable:
                error_msgs.append(
                    f"[Source] Required source '{u.source_id}' at '{u.location}' is unreachable."
                )
            summary = "; ".join(error_msgs)
            self.emitter.emit_event(
                event_code=EventCode.PREFLIGHT_FAILED,
                message=f"Phase 0 Failed - Pre-flight health check rejected configuration: {summary}",
                presentation_kind=PresentationKind.FAILURE,
                stage=EngineStage.FAILED,
            )
            raise PreflightCheckFailedError(
                "Pre-flight health check failed:\n" + "\n".join(f"- {m}" for m in error_msgs),
                issues=tuple(errors),
            )

        self.emitter.emit_event(
            event_code=EventCode.PREFLIGHT_SUCCESS,
            message=(
                f"Phase 0 Complete - Configuration & source reachability verified "
                f"({len(val_res.active_capabilities)} active capabilities, "
                f"{len(self.source_config.datasets)} dataset bindings) ({chk_duration_ms:.1f}ms)"
            ),
            presentation_kind=PresentationKind.SUCCESS,
            stage=EngineStage.INITIALIZING,
        )

    _execute_preflight_check = execute_preflight_check

    def run(self) -> None:
        """Run the end-to-end quantitative ETL pipeline."""
        start_time = time.perf_counter()

        if not self.skip_preflight and self.diagnostic_service is not None:
            self.execute_preflight_check()

        lifecycle = RunLifecycleCoordinator(
            self.cfg,
            self.status_queue,
            self.db_manager,
            self.rules,
            emitter=self.emitter,
            plan=self.plan,
            source_config=self.source_config,
        )

        try:
            cp, run_id, _ = lifecycle.initialize()
            short_id = run_id[:8]
            self.emitter.emit_event(
                event_code=EventCode.RUN_START,
                message=f"Pipeline execution started [Run: {short_id}].",
                presentation_kind=PresentationKind.STEP,
                progress=0.0,
                stage=EngineStage.INITIALIZING,
            )

            self.executor.execute_phases(cp, run_id, replay_plan=lifecycle.replay_plan)
            lifecycle.commit()

            total_time = time.perf_counter() - start_time
            self.emitter.emit_event(
                event_code=EventCode.RUN_COMPLETED,
                message=(
                    f"Pipeline Execution Successful in {total_time:.2f}s "
                    f"(Total Nodes: {len(self.dfs)}) [Run: {short_id}]."
                ),
                presentation_kind=PresentationKind.SUCCESS,
                duration_ms=total_time * 1000.0,
                rows=len(self.dfs),
                progress=1.0,
                stage=EngineStage.COMPLETED,
                commit_state=lifecycle.commit_state,
            )
        except Exception as e:
            lifecycle.handle_failure(e)
            raise e
        finally:
            lifecycle.teardown()
