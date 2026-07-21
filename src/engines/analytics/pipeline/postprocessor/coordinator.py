from datetime import date
import polars as pl

from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.postprocessor.xirr import PortfolioXIRRCalculator
from src.engines.analytics.pipeline.postprocessor.analytics import AdvancedAnalyticsCalculator
from src.engines.analytics.pipeline.postprocessor.weights import PortfolioWeightsCalculator
from src.engines.analytics.pipeline.postprocessor.gains import RealizedGainsCalculator
from src.engines.analytics.pipeline.postprocessor.harvest import HarvestRecommendationCalculator

class PostProcessor:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.xirr_calc = PortfolioXIRRCalculator()
        self.analytics_calc = AdvancedAnalyticsCalculator()
        self.weights_calc = PortfolioWeightsCalculator()
        self.gains_calc = RealizedGainsCalculator(ctx)
        self.harvest_calc = HarvestRecommendationCalculator()

    def run(
        self,
        lazy_df: pl.LazyFrame,
        unique_dates: list[date],
        global_cashflows: list[dict],
        portfolio_terminals: dict[date, dict],
        realized_events: list[dict],
    ) -> pl.LazyFrame:
        """
        Calculates portfolio metrics and lazily attaches them to the lot-level DataFrame.
        """
        df_port = self.xirr_calc.calculate(unique_dates, global_cashflows, portfolio_terminals)
        df_port = self.analytics_calc.calculate(df_port, unique_dates, portfolio_terminals)
        lazy_df = lazy_df.join(df_port.lazy(), on="Closing_Date", how="left")
        
        lazy_df = self.weights_calc.calculate(lazy_df)
        lazy_df = self.gains_calc.calculate(lazy_df, unique_dates, realized_events)
        lazy_df = self.harvest_calc.calculate(lazy_df)

        return lazy_df
