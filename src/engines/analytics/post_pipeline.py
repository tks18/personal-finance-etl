import os

import polars as pl

from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.postprocessor import PostProcessor
from src.types.pipeline import PipelineExecutionResult
from src.utils.interfaces import ILogger
from src.utils.logger import logger
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
        pipeline_res: PipelineExecutionResult,
    ) -> dict[str, pl.DataFrame]:

        if self.status_queue:
            logger.info("Post-processing: Scanning temporary parquet files...")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=0.86,
                    level=LogLevel.STEP,
                )
            )

        lazy_df = pl.scan_parquet(os.path.join(self.tmp_dir, "*.parquet"))

        unique_dates_df = lazy_df.select("Closing_Date").unique().collect()
        unique_dates = unique_dates_df["Closing_Date"].sort().to_list()

        if self.status_queue:
            logger.info("Post-processing: Aggregating portfolio metrics...")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=0.90,
                    level=LogLevel.STEP,
                )
            )
        res_dict = self.postprocessor.run(lazy_df, unique_dates, pipeline_res)

        if self.status_queue:
            logger.info("Post-processing: Collecting final output...")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=0.95,
                    level=LogLevel.STEP,
                )
            )
        final_res: dict[str, pl.DataFrame] = {k: v.collect() for k, v in res_dict.items()}
        return final_res
