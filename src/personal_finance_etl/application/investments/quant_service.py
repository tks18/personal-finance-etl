"""Investment quantitative analytics application service.

Owns
----
- InvestmentQuantEngine: Orchestrates the end-to-end investment pipeline:
  1. Ingests raw inputs into RunContext via AnalyticsContextManager.
  2. Runs concurrent per-ISIN processing and lot accounting via IsinPipeline.
  3. Executes multi-asset portfolio aggregation and post-processing via PostProcessingPipeline.
- QuantService: Canonical alias for InvestmentQuantEngine.

Does not own
-------------
- Chronological per-ISIN daily simulation (owned by application.investments.isin_service).
- Post-processing aggregation logic (owned by application.investments.aggregation_service).
- Ingestion extraction adapters (owned by application.investments.input_adapter).
"""

from __future__ import annotations

import tempfile
import traceback

import polars as pl

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessingPipeline,
)
from personal_finance_etl.application.investments.context import (
    AnalyticsContextManager,
    QuantDataFrames,
    QuantRunOptions,
)
from personal_finance_etl.application.investments.isin_service import (
    IsinPipeline,
)
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.infrastructure.logging.setup import logger

__all__ = ["InvestmentQuantEngine", "QuantService"]


class InvestmentQuantEngine:
    """Orchestrates the multi-process investment quantitative calculations."""

    def __init__(
        self,
        data: QuantDataFrames,
        options: QuantRunOptions,
        status_queue: StatusQueue | None = None,
    ) -> None:
        """Initialize InvestmentQuantEngine with structured typed parameter bundles.

        Parameters
        ----------
        data : QuantDataFrames
            Bundle of DataFrames for analysis.
        options : QuantRunOptions
            Execution options and boundaries.
        status_queue : StatusQueue | None, optional
            Queue for streaming engine progress events.
        """
        self.data = data
        self.options = options
        self.status_queue = status_queue

    def _report_status(
        self,
        msg: str,
        data: pl.DataFrame | None,
        progress: float,
        level: LogLevel,
    ) -> None:
        if self.status_queue is not None:
            self.status_queue.put(
                EngineStatusMessage(msg=msg, data=data, progress=progress, level=level)
            )

    def run(self) -> dict[str, pl.DataFrame]:
        """Execute the quantitative analysis engine.

        Returns
        -------
        dict[str, pl.DataFrame]
            Dictionary of 13 aggregated analytical tables.
        """
        try:
            return self._run()
        except Exception as e:
            err_msg = f"Error: {e}\n{traceback.format_exc()}"
            self._report_status(err_msg, None, 0.0, LogLevel.ERROR)
            raise e

    def _run(self) -> dict[str, pl.DataFrame]:
        context_manager = AnalyticsContextManager(self.status_queue)
        ctx, isins = context_manager.initialize(data=self.data, options=self.options)

        min_market = ctx.df_m.select(pl.min("Date")).item() if not ctx.df_m.is_empty() else None
        max_market = ctx.df_m.select(pl.max("Date")).item() if not ctx.df_m.is_empty() else None
        logger.info(
            f"  -> Quant Engine initialized context spanning market dates {min_market} to {max_market} for {len(isins)} unique ISINs."
        )

        if not isins:
            empty_df = pl.DataFrame()
            self._report_status(
                "Processing Complete! (no valid ISINs found)",
                empty_df,
                1.0,
                LogLevel.SUCCESS,
            )
            return {"df_f_investment_analytics_lot": empty_df}

        with tempfile.TemporaryDirectory() as tmp_dir:
            isin_pipeline = IsinPipeline(ctx, isins, tmp_dir, self.status_queue)
            pipeline_res = isin_pipeline.process_all()
            has_data = pipeline_res.has_data

            if not has_data:
                empty_df = pl.DataFrame()
                self._report_status(
                    "Processing Complete! (no output rows)",
                    empty_df,
                    1.0,
                    LogLevel.SUCCESS,
                )
                return {"df_f_investment_analytics_lot": empty_df}

            post_pipeline = PostProcessingPipeline(ctx, tmp_dir, self.status_queue)
            final_dfs = post_pipeline.run(pipeline_res)

            succ_msg = f"✅  Processing Complete — generated {len(final_dfs)} analytics tables."
            self._report_status(succ_msg, None, 1.0, LogLevel.SUCCESS)

            return final_dfs


QuantService = InvestmentQuantEngine
