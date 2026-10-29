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

import polars as pl

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue, NullEventQueue
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

__all__ = ["ETLOrchestrator"]

diagnostics = get_observability_diagnostics(__name__)


class ETLOrchestrator:
    """High-level application coordinator driving end-to-end quantitative ETL execution."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: EventQueue | None = None,
        rules: FinancialRules | None = None,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue or NullEventQueue()
        self.emitter = emitter or get_global_emitter()
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.executor = PipelineExecutor(
            cfg, self.status_queue, self.db_manager, rules, emitter=self.emitter
        )

    @property
    def dfs(self) -> dict[str, pl.DataFrame]:
        """Active collection of transformed datasets."""
        return self.executor.dfs

    @dfs.setter
    def dfs(self, value: dict[str, pl.DataFrame]) -> None:
        """Set the active collection of transformed datasets."""
        self.executor.dfs = value

    def run(self) -> None:
        """Run the end-to-end quantitative ETL pipeline."""
        start_time = time.perf_counter()
        lifecycle = RunLifecycleCoordinator(
            self.cfg,
            self.status_queue,
            self.db_manager,
            self.rules,
            emitter=self.emitter,
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

            self.executor.execute_phases(cp, run_id)
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
