"""Parquet partition collection and post-processing orchestrator.

Owns
----
- PostProcessingPipeline: Scans spilled intermediate Parquet partitions and executes post-processing graphs.

Does not own
-------------
- Aggregation calculation logic (owned by application.investments.aggregation_service).
- Realized and reconciliation event conversion (owned by application.investments.aggregation_events).
- ISIN simulation (owned by application.investments.isin_service).
"""

from __future__ import annotations

import os

import polars as pl

from personal_finance_etl.application.investments.aggregation_service.service import PostProcessor
from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.logging import StatusQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.domain.investments.contracts import PipelineExecutionResult
from personal_finance_etl.infrastructure.logging.setup import logger

__all__ = ["PostProcessingPipeline"]


class PostProcessingPipeline:
    """Handles reading spilled parquet files and running final aggregations.

    Parameters
    ----------
    ctx : RunContext
        Analytics run context containing configuration and shared tables.
    tmp_dir : str
        Directory containing intermediate per-ISIN Parquet partitions.
    status_queue : StatusQueue | None, optional
        Status queue for reporting pipeline progress.
    """

    def __init__(
        self,
        ctx: RunContext,
        tmp_dir: str,
        status_queue: StatusQueue | None = None,
    ) -> None:
        self.ctx = ctx
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue
        self.postprocessor = PostProcessor(ctx)

    def _report_step(self, progress: float) -> None:
        """Report incremental step progress to status queue."""
        if self.status_queue:
            self.status_queue.put(
                ObservabilityEvent.create(
                    event_code=EventCode.TRANSFORMATION_STAGE,
                    message="",
                    progress=progress,
                    severity=DiagnosticSeverity.INFO,
                    outcome=EventOutcome.COMPLETED,
                    presentation_kind=PresentationKind.PROGRESS,
                    stage=EngineStage.ANALYZING,
                )
            )

    def run(
        self,
        pipeline_res: PipelineExecutionResult,
    ) -> dict[str, pl.DataFrame]:
        """Scan spilled parquet partitions and execute aggregation pipeline.

        Parameters
        ----------
        pipeline_res : PipelineExecutionResult
            Aggregated terminal values, cash flows, and realized events from worker pool.

        Returns
        -------
        dict[str, pl.DataFrame]
            Collected dictionary of final analytics tables.
        """
        logger.debug("Post-processing: Scanning temporary parquet files...")
        self._report_step(0.86)

        lazy_df = pl.scan_parquet(os.path.join(self.tmp_dir, "*.parquet"))

        # Materialization Boundary: SCALAR_EXTRACTION
        # Extract unique closing dates series to construct ordered temporal spine for group calculations
        unique_dates_df = lazy_df.select("Closing_Date").unique().collect()
        unique_dates = unique_dates_df["Closing_Date"].sort().to_list()

        logger.debug("Post-processing: Aggregating portfolio metrics...")
        self._report_step(0.90)

        res_dict = self.postprocessor.run(lazy_df, unique_dates, pipeline_res)

        logger.debug("Post-processing: Collecting final output...")
        self._report_step(0.95)

        # Materialization Boundary: PUBLICATION_BOUNDARY
        # Materialize calculated presentation marts from Polars query graphs for DuckDB registration
        final_res: dict[str, pl.DataFrame] = {k: v.collect() for k, v in res_dict.items()}
        return final_res
