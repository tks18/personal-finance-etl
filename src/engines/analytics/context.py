from src.engines.analytics.pipeline.context import RunContext
from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class AnalyticsContextManager:
    """Manages the initialization of the tax engine context."""
    def __init__(self, status_queue: ILogger | None = None):
        self.status_queue = status_queue

    def initialize(
        self, df_p, df_s, df_m, df_i, df_b, df_t, start_date, end_date
    ) -> tuple[RunContext, list[str]]:
        if self.status_queue:
            self.status_queue.put(
                EngineStatus("Loading DataFrame memory structures...", None, 0.01, LogLevel.STEP)
            )

        ctx = RunContext.from_dataframes(
            df_p, df_s, df_m, df_i, df_b, df_t, start_date, end_date
        )

        if self.status_queue:
            self.status_queue.put(
                EngineStatus("Data loaded into Context successfully.", None, 0.05, LogLevel.INFO)
            )

        isins_p = ctx.df_p["ISIN"].unique().to_list() if "ISIN" in ctx.df_p.columns else []
        isins_s = ctx.df_s["ISIN"].unique().to_list() if "ISIN" in ctx.df_s.columns else []
        isins_m = ctx.df_m["ISIN"].unique().to_list() if "ISIN" in ctx.df_m.columns else []
        isins = sorted(set(isins_p + isins_s + isins_m))
        
        return ctx, isins
