import tempfile
import traceback
from datetime import date

import polars as pl

from src.config.financial_rules import FinancialRules
from src.engines.analytics.context import AnalyticsContextManager
from src.engines.analytics.isin_pipeline import IsinPipeline
from src.engines.analytics.post_pipeline import PostProcessingPipeline
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, LogLevel


class InvestmentQuantEngine:
    """
    Orchestrates the quantitative engine pipeline.
    """

    def __init__(
        self,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame,
        df_b: pl.DataFrame | None,
        df_t: pl.DataFrame,
        status_queue: ILogger | None = None,
        rules: "FinancialRules | None" = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        self.df_p = df_p
        self.df_s = df_s
        self.df_m = df_m
        self.df_i = df_i
        self.df_b = df_b if df_b is not None else pl.DataFrame()
        self.df_t = df_t
        self.status_queue = status_queue
        self.rules = rules
        self.start_date = start_date
        self.end_date = end_date

    def run(self) -> dict[str, pl.DataFrame]:
        try:
            return self._run()
        except Exception as e:
            if self.status_queue is not None:
                self.status_queue.put(
                    EngineStatus(
                        msg=f"Error: {e}\n{traceback.format_exc()}",
                        data=None,
                        progress=0.0,
                        level=LogLevel.ERROR,
                    )
                )
            raise e

    def _run(self) -> dict[str, pl.DataFrame]:
        context_manager = AnalyticsContextManager(self.status_queue)
        ctx, isins = context_manager.initialize(
            self.df_p,
            self.df_s,
            self.df_m,
            self.df_i,
            self.df_b,
            self.df_t,
            self.start_date,
            self.end_date,
            self.rules,
        )

        min_market = ctx.df_m.select(pl.min("Date")).item() if not ctx.df_m.is_empty() else None
        max_market = ctx.df_m.select(pl.max("Date")).item() if not ctx.df_m.is_empty() else None
        logger.info(
            f"  -> Quant Engine initialized context spanning market dates {min_market} to {max_market} for {len(isins)} unique ISINs."
        )

        if not isins:
            empty_df = pl.DataFrame()
            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Processing Complete! (no valid ISINs found)",
                        data=empty_df,
                        progress=1.0,
                        level=LogLevel.SUCCESS,
                    )
                )
            return {"df_f_tf_investment_analytics_lot": empty_df}

        with tempfile.TemporaryDirectory() as tmp_dir:
            isin_pipeline = IsinPipeline(ctx, isins, tmp_dir, self.status_queue)
            pipeline_res = isin_pipeline.process_all()
            has_data = pipeline_res.has_data

            if not has_data:
                empty_df = pl.DataFrame()
                if self.status_queue:
                    self.status_queue.put(
                        EngineStatus(
                            msg="Processing Complete! (no output rows)",
                            data=empty_df,
                            progress=1.0,
                            level=LogLevel.SUCCESS,
                        )
                    )
                return {"df_f_tf_investment_analytics_lot": empty_df}

            post_pipeline = PostProcessingPipeline(ctx, tmp_dir, self.status_queue)
            final_dfs = post_pipeline.run(pipeline_res)

            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg=f"✅  Processing Complete — generated {len(final_dfs)} analytics tables.",
                        data=None,
                        progress=1.0,
                        level=LogLevel.SUCCESS,
                    )
                )

            return final_dfs
