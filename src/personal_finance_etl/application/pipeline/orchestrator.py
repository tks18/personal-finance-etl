"""Orchestrator coordinating the execution of the quantitative ETL pipeline.

Owns
----
- ETLOrchestrator: High-level use-case coordinator driving the 5 pipeline phases.
- Delegating transaction management, logging, and split-commit recovery to RunLifecycleCoordinator.
- Delegating evidence extraction, transformations, and warehouse loading to PipelineExecutor.

Does not own
-------------
- Concrete DuckDB/SQLite database mechanics (owned by infrastructure.warehouse and infrastructure.control_plane).
- Financial algorithms or calculation formulas (owned by domain.*).
- Multiprocessing child process supervision (owned by application.pipeline.worker).
"""

from __future__ import annotations

import time
from typing import Any, cast

import polars as pl

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.logging import ILogger, LogLevel, NullStatusQueue
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.logging.setup import logger
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager

__all__ = ["ETLOrchestrator"]


class ETLOrchestrator:
    """High-level application coordinator driving end-to-end quantitative ETL execution."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: ILogger | None = None,
        rules: FinancialRules | None = None,
    ) -> None:
        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue or NullStatusQueue()
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.executor = PipelineExecutor(cfg, self.status_queue, self.db_manager, rules)

    @property
    def dfs(self) -> dict[str, pl.DataFrame]:
        """Active collection of transformed datasets."""
        return self.executor.dfs

    @dfs.setter
    def dfs(self, value: dict[str, pl.DataFrame]) -> None:
        self.executor.dfs = value

    def _extract(
        self,
        cp: ControlPlane,
        actionable_files: dict[str, list[str]] | None = None,
    ) -> ExtractionResult:
        """Legacy pass-through extraction step."""
        return self.executor.extract(cp, actionable_files)

    def _transform(self, extracted_data: ExtractionResult) -> None:
        """Legacy pass-through transformation step."""
        self.executor.transform(extracted_data)

    def _process_benchmark(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Legacy pass-through benchmark processing step."""
        self.executor.process_benchmark(cp, bronze)

    def _process_currency(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Legacy pass-through currency processing step."""
        self.executor.process_currency(cp, bronze)

    def _process_us_market_data(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Legacy pass-through US market processing step."""
        self.executor.process_us_market_data(cp, bronze)

    def _run_engines(self, cp: ControlPlane | None, run_id: str) -> None:
        """Legacy pass-through presentation and quant engine execution step."""
        self.executor.run_engines(cp, run_id)

    def run(self) -> None:
        """Run the end-to-end quantitative ETL pipeline."""
        start_time = time.perf_counter()
        lifecycle = RunLifecycleCoordinator(self.cfg, self.status_queue, self.db_manager, self.rules)

        try:
            cp, run_id, _ = lifecycle.initialize()
            self.status_queue.put(
                cast(
                    Any,
                    EngineStatusMessage(
                        msg="Initializing Master Engine...",
                        progress=0.0,
                        level=LogLevel.STEP,
                    ),
                )
            )

            self.executor.execute_phases(cp, run_id)
            lifecycle.commit()

            self.status_queue.put(
                cast(
                    Any,
                    EngineStatusMessage(
                        msg="Pipeline Execution Successful",
                        progress=1.0,
                        level=LogLevel.SUCCESS,
                    ),
                )
            )
            total_time = time.perf_counter() - start_time
            logger.info(
                f"✅ Pipeline Execution Successful in {total_time:.2f} seconds. Total Nodes: {len(self.dfs)}"
            )
        except Exception as e:
            lifecycle.handle_failure(e)
            raise e
        finally:
            lifecycle.teardown()
