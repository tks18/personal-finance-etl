import os
from datetime import date

import polars as pl

from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.postprocessor import PostProcessor
from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class PostProcessingPipeline:
    """Handles reading spilled parquet files and running final aggregations."""

    def __init__(self, ctx: RunContext, tmp_dir: str, status_queue: ILogger | None = None):
        self.ctx = ctx
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue
        self.postprocessor = PostProcessor(ctx)

    def run(
        self,
        global_cashflows: list[dict],
        portfolio_terminals: dict[date, dict[str, float]],
        realized_events: list[dict],
    ) -> pl.DataFrame:
        if self.status_queue:
            self.status_queue.put(
                EngineStatus(
                    msg="Post-processing: Scanning temporary parquet files...",
                    data=None,
                    progress=0.86,
                    level=LogLevel.STEP,
                )
            )

        lazy_df = pl.scan_parquet(os.path.join(self.tmp_dir, "*.parquet"))

        unique_dates_df = lazy_df.select("Closing_Date").unique().collect()
        unique_dates = unique_dates_df["Closing_Date"].sort().to_list()

        if self.status_queue:
            self.status_queue.put(
                EngineStatus(
                    msg="Post-processing: Aggregating portfolio metrics...",
                    data=None,
                    progress=0.90,
                    level=LogLevel.STEP,
                )
            )
        lazy_df = self.postprocessor.run(
            lazy_df, unique_dates, global_cashflows, portfolio_terminals, realized_events
        )

        if self.status_queue:
            self.status_queue.put(
                EngineStatus(
                    msg="Post-processing: Collecting final output...",
                    data=None,
                    progress=0.95,
                    level=LogLevel.STEP,
                )
            )
        return lazy_df.collect()
