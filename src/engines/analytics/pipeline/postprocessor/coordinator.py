from datetime import date

import polars as pl

from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.postprocessor.analytics import AdvancedAnalyticsCalculator
from src.engines.analytics.pipeline.postprocessor.gains import RealizedGainsCalculator
from src.engines.analytics.pipeline.postprocessor.group_processor import (
    PORTFOLIO_COL_RENAMES,
    GroupProcessor,
)
from src.engines.analytics.pipeline.postprocessor.harvest import HarvestRecommendationCalculator
from src.engines.analytics.pipeline.postprocessor.weights import PortfolioWeightsCalculator
from src.engines.analytics.pipeline.postprocessor.xirr import PortfolioXIRRCalculator
from src.types.pipeline import PipelineExecutionResult


class PostProcessor:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.xirr_calc = PortfolioXIRRCalculator()
        self.analytics_calc = AdvancedAnalyticsCalculator(ctx.fy_table, ctx.rules)
        self.weights_calc = PortfolioWeightsCalculator()
        self.gains_calc = RealizedGainsCalculator(ctx)
        self.harvest_calc = HarvestRecommendationCalculator()
        self.group_calc = GroupProcessor(self.analytics_calc)

    def run(
        self,
        lazy_df: pl.LazyFrame,
        unique_dates: list[date],
        pipeline_res: PipelineExecutionResult,
    ) -> dict[str, pl.LazyFrame]:
        """
        Calculates portfolio metrics and lazily attaches them to the lot-level DataFrame.
        """
        df_port = self.xirr_calc.calculate(
            unique_dates, pipeline_res.global_cf, pipeline_res.global_pt
        )
        df_port = self.analytics_calc.calculate(df_port, unique_dates, pipeline_res.global_pt)
        lazy_df = lazy_df.join(df_port.lazy(), on="Closing_Date", how="left")

        lazy_df = self.weights_calc.calculate(lazy_df)
        lazy_df = self.gains_calc.calculate(lazy_df, unique_dates, pipeline_res.global_re)
        lazy_df = self.harvest_calc.calculate(lazy_df, rules=self.ctx.rules)

        # 1. Process Class Level
        df_class = self.group_calc.run(
            unique_dates, pipeline_res.class_cf, pipeline_res.class_pt, "INSTRUMENT_CLASS"
        )
        # 2. Process Subtype Level
        df_subtype = self.group_calc.run(
            unique_dates,
            pipeline_res.subtype_cf,
            pipeline_res.subtype_pt,
            "INSTRUMENT_CLASS",
            "INSTRUMENT_SUBTYPE",
        )

        # 3. Create the Port, Class, and Subtype final aggregated tables
        # Since df_port doesn't have the standard columns (Total_Invested_Value, etc)
        # we will aggregate lazy_df to get those and join them.

        # We need INSTRUMENT_CLASS and INSTRUMENT_SUBTYPE for aggregation
        master_records = [{"ISIN": k, **v} for k, v in self.ctx.isin_master.items()]
        master_cols = pl.LazyFrame(master_records).select(
            ["ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"]
        )
        lazy_df_agg = lazy_df.join(master_cols, on="ISIN", how="left")

        def _aggregate_level(group_cols: list[str]) -> pl.LazyFrame:
            return (
                lazy_df_agg.select(
                    list(
                        set(
                            group_cols
                            + [
                                "Buy_Value",
                                "Close_Value",
                                "Unrealized_LTCG",
                                "Unrealized_STCG",
                                "Unrealized_Gain",
                                "Unrealized_LTCL",
                                "Unrealized_STCL",
                                "Unrealized_Loss",
                                "LTCG_Tax_If_Sold",
                                "STCG_Tax_If_Sold",
                                "FY_Realized_LTCG",
                                "FY_Realized_STCG",
                                "FY_Realized_Gain",
                                "FY_Realized_LTCL",
                                "FY_Realized_STCL",
                                "FY_Realized_Loss",
                                "FY_Realized_Net_PnL",
                            ]
                        )
                    )
                )
                .group_by(group_cols)
                .agg(
                    pl.col("Buy_Value").sum().alias("Total_Invested_Value"),
                    pl.col("Close_Value").sum().alias("Total_Current_Value"),
                    pl.col("Unrealized_LTCG").sum().alias("Unrealized_LTCG"),
                    pl.col("Unrealized_STCG").sum().alias("Unrealized_STCG"),
                    pl.col("Unrealized_Gain").sum().alias("Unrealized_Gain"),
                    pl.col("Unrealized_LTCL").sum().alias("Unrealized_LTCL"),
                    pl.col("Unrealized_STCL").sum().alias("Unrealized_STCL"),
                    pl.col("Unrealized_Loss").sum().alias("Unrealized_Loss"),
                    pl.col("LTCG_Tax_If_Sold").sum().alias("LTCG_Tax_If_Sold"),
                    pl.col("STCG_Tax_If_Sold").sum().alias("STCG_Tax_If_Sold"),
                    pl.col("FY_Realized_LTCG").sum().alias("FY_Realized_LTCG"),
                    pl.col("FY_Realized_STCG").sum().alias("FY_Realized_STCG"),
                    pl.col("FY_Realized_Gain").sum().alias("FY_Realized_Gain"),
                    pl.col("FY_Realized_LTCL").sum().alias("FY_Realized_LTCL"),
                    pl.col("FY_Realized_STCL").sum().alias("FY_Realized_STCL"),
                    pl.col("FY_Realized_Loss").sum().alias("FY_Realized_Loss"),
                    pl.col("FY_Realized_Net_PnL").sum().alias("FY_Realized_Net_PnL"),
                )
                .with_columns(
                    (pl.col("Total_Current_Value") - pl.col("Total_Invested_Value")).alias(
                        "Unrealized_PL"
                    )
                )
                .with_columns(
                    pl.when(pl.col("Total_Invested_Value") > 0)
                    .then(pl.col("Unrealized_PL") / pl.col("Total_Invested_Value"))
                    .otherwise(0.0)
                    .alias("Absolute_Return_%")
                )
            )

        f_tf_isin = _aggregate_level(["Closing_Date", "ISIN"]).join(
            lazy_df_agg.select(
                [
                    "Closing_Date",
                    "ISIN",
                    "XIRR",
                    "After_Tax_XIRR",
                    "BM_XIRR",
                    "Active_Return",
                    "CAGR",
                    "BM_CAGR",
                    "Is_Lagging_Benchmark",
                    "Beta",
                    "Tracking_Error",
                    "Information_Ratio",
                    "Upside_Capture",
                    "Downside_Capture",
                    "Outperformance_Probability",
                    # Per-ISIN risk-adjusted ratios
                    "Sharpe_Ratio",
                    "Sortino_Ratio",
                    "Calmar_Ratio",
                    "Max_Drawdown",
                    "BM_Sharpe_Ratio",
                    "BM_Sortino_Ratio",
                    "BM_Calmar_Ratio",
                    "BM_Max_Drawdown",
                    "Sharpe_Alpha",
                    "Sortino_Alpha",
                    "Calmar_Alpha",
                ]
            ).unique(),
            on=["Closing_Date", "ISIN"],
            how="left",
        )

        f_tf_class = (
            _aggregate_level(["Closing_Date", "INSTRUMENT_CLASS"]).join(
                df_class.lazy(), on=["Closing_Date", "INSTRUMENT_CLASS"], how="left"
            )
            if not df_class.is_empty()
            else _aggregate_level(["Closing_Date", "INSTRUMENT_CLASS"])
        )
        f_tf_subtype = (
            _aggregate_level(["Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"]).join(
                df_subtype.lazy(),
                on=["Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"],
                how="left",
            )
            if not df_subtype.is_empty()
            else _aggregate_level(["Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"])
        )
        f_tf_port = _aggregate_level(["Closing_Date"]).join(
            df_port.lazy().rename(PORTFOLIO_COL_RENAMES),
            on=["Closing_Date"],
            how="left",
        )

        # Portfolio Weight logic (window sum over Closing_Date)
        for lf, g in [
            (f_tf_isin, "ISIN"),
            (f_tf_subtype, "INSTRUMENT_SUBTYPE"),
            (f_tf_class, "INSTRUMENT_CLASS"),
        ]:
            lf = lf.with_columns(
                (
                    pl.col("Total_Current_Value")
                    / pl.col("Total_Current_Value").sum().over("Closing_Date")
                ).alias("Weight_%")
            )
            if g == "ISIN":
                f_tf_isin = lf
            elif g == "INSTRUMENT_SUBTYPE":
                f_tf_subtype = lf
            else:
                f_tf_class = lf

        f_tf_port = f_tf_port.with_columns(pl.lit(1.0).alias("Weight_%"))

        return {
            "df_f_tf_investment_analytics_lot": lazy_df,
            "df_f_tf_investment_analytics_isin": f_tf_isin,
            "df_f_tf_investment_analytics_subtype": f_tf_subtype,
            "df_f_tf_investment_analytics_class": f_tf_class,
            "df_f_tf_investment_analytics_portfolio": f_tf_port,
        }
