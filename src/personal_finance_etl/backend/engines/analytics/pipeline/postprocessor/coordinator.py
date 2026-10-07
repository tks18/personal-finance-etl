from datetime import date

import polars as pl

from personal_finance_etl.backend.engines.analytics.pipeline.context import RunContext
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.analytics import (
    AdvancedAnalyticsCalculator,
)
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.gains import (
    RealizedGainsCalculator,
)
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.group_processor import (
    PORTFOLIO_COL_RENAMES,
    GroupProcessor,
)
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.harvest import (
    HarvestRecommendationCalculator,
)
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.weights import (
    PortfolioWeightsCalculator,
)
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.xirr import (
    PortfolioXIRRCalculator,
)
from personal_finance_etl.backend.types.pipeline import PipelineExecutionResult


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
        df_port = self.analytics_calc.calculate(
            df_port, unique_dates, pipeline_res.global_pt, pipeline_res.global_cf
        )

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
        # 3. Process Instrument Type Level
        df_inst_type = self.group_calc.run(
            unique_dates,
            pipeline_res.instrument_type_cf,
            pipeline_res.instrument_type_pt,
            "INSTRUMENT_TYPE",
        )
        # 4. Process Sector Level
        df_sector = self.group_calc.run(
            unique_dates, pipeline_res.sector_cf, pipeline_res.sector_pt, "SECTOR"
        )
        # 5. Process Industry Level
        df_industry = self.group_calc.run(
            unique_dates, pipeline_res.industry_cf, pipeline_res.industry_pt, "INDUSTRY"
        )
        # 6. Process Geo Level
        df_geo = self.group_calc.run(unique_dates, pipeline_res.geo_cf, pipeline_res.geo_pt, "GEO")
        # 7. Process Country Level
        df_country = self.group_calc.run(
            unique_dates, pipeline_res.country_cf, pipeline_res.country_pt, "COUNTRY"
        )
        # 8. Process Currency Level
        df_currency = self.group_calc.run(
            unique_dates, pipeline_res.currency_cf, pipeline_res.currency_pt, "CURRENCY_ID"
        )

        # 3. Create the Port, Class, and Subtype final aggregated tables
        # Since df_port doesn't have the standard columns (Total_Invested_Value, etc)
        # we will aggregate lazy_df to get those and join them.

        # We need INSTRUMENT_CLASS and INSTRUMENT_SUBTYPE for aggregation
        master_records = [{"ISIN": k, **v} for k, v in self.ctx.isin_master.items()]
        master_cols = (
            pl.LazyFrame(master_records)
            .select(
                [
                    "ISIN",
                    "INSTRUMENT_CLASS",
                    "INSTRUMENT_SUBTYPE",
                    "INSTRUMENT_TYPE",
                    "SECTOR",
                    "INDUSTRY",
                    "GEO",
                    "COUNTRY",
                ]
            )
            .with_columns(
                pl.col("INSTRUMENT_TYPE").fill_null("Unknown"),
                pl.col("SECTOR").fill_null("Unknown"),
                pl.col("INDUSTRY").fill_null("Unknown"),
                pl.col("GEO").fill_null("Unknown"),
                pl.col("COUNTRY").fill_null("Unknown"),
            )
        )
        lazy_df_agg = lazy_df.join(master_cols, on="ISIN", how="left")

        def _aggregate_level(group_cols: list[str]) -> pl.LazyFrame:
            return (
                lazy_df_agg.select(
                    list(
                        set(
                            group_cols
                            + [
                                "ISIN",
                                "Quantity",
                                "Buy_Value",
                                "Close_Value",
                                "Buy_Value_Local",
                                "Close_Value_Local",
                                "Asset_PnL",
                                "Forex_PnL",
                                "Unrealized_Gain",
                                "Unrealized_Loss",
                                "FY_Realized_Gain",
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
                    pl.col("Buy_Value_Local").sum().alias("Total_Invested_Value_Local"),
                    pl.col("Close_Value_Local").sum().alias("Total_Current_Value_Local"),
                    pl.col("Asset_PnL").sum().alias("Asset_PnL"),
                    pl.col("Forex_PnL").sum().alias("Forex_PnL"),
                    pl.col("Quantity").sum().alias("Total_Quantity"),
                    pl.col("ISIN").n_unique().alias("Total_Stocks"),
                    pl.col("Unrealized_Gain").sum().alias("Unrealized_Gain"),
                    pl.col("Unrealized_Loss").sum().alias("Unrealized_Loss"),
                    pl.col("FY_Realized_Gain").sum().alias("FY_Realized_Gain"),
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
                    .alias("Absolute_Return"),
                    pl.when(pl.col("Unrealized_PL") != 0.0)
                    .then(pl.col("Forex_PnL") / pl.col("Unrealized_PL"))
                    .otherwise(0.0)
                    .alias("Forex_Contribution_Pct"),
                    pl.when(pl.col("Total_Invested_Value_Local") > 0)
                    .then(pl.col("Total_Invested_Value") / pl.col("Total_Invested_Value_Local"))
                    .otherwise(1.0)
                    .alias("Blended_FX_Buy_Rate"),
                    pl.when(pl.col("Total_Current_Value_Local") > 0)
                    .then(pl.col("Total_Current_Value") / pl.col("Total_Current_Value_Local"))
                    .otherwise(1.0)
                    .alias("Current_FX_Rate"),
                )
                .with_columns(
                    pl.when(pl.col("Blended_FX_Buy_Rate") > 0)
                    .then((pl.col("Current_FX_Rate") / pl.col("Blended_FX_Buy_Rate")) - 1.0)
                    .otherwise(0.0)
                    .alias("Currency_Appreciation_Pct")
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
                    "Max_Drawdown",
                    "XIRR_Local",
                    "FX_XIRR_Impact",
                    "BM_XIRR_Local",
                    "Active_Return_Local",
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
        f_tf_inst_type = (
            _aggregate_level(["Closing_Date", "INSTRUMENT_TYPE"]).join(
                df_inst_type.lazy(), on=["Closing_Date", "INSTRUMENT_TYPE"], how="left"
            )
            if not df_inst_type.is_empty()
            else _aggregate_level(["Closing_Date", "INSTRUMENT_TYPE"])
        )
        f_tf_sector = (
            _aggregate_level(["Closing_Date", "SECTOR"]).join(
                df_sector.lazy(), on=["Closing_Date", "SECTOR"], how="left"
            )
            if not df_sector.is_empty()
            else _aggregate_level(["Closing_Date", "SECTOR"])
        )
        f_tf_industry = (
            _aggregate_level(["Closing_Date", "INDUSTRY"]).join(
                df_industry.lazy(), on=["Closing_Date", "INDUSTRY"], how="left"
            )
            if not df_industry.is_empty()
            else _aggregate_level(["Closing_Date", "INDUSTRY"])
        )
        f_tf_geo = (
            _aggregate_level(["Closing_Date", "GEO"]).join(
                df_geo.lazy(), on=["Closing_Date", "GEO"], how="left"
            )
            if not df_geo.is_empty()
            else _aggregate_level(["Closing_Date", "GEO"])
        )
        f_tf_country = (
            _aggregate_level(["Closing_Date", "COUNTRY"]).join(
                df_country.lazy(), on=["Closing_Date", "COUNTRY"], how="left"
            )
            if not df_country.is_empty()
            else _aggregate_level(["Closing_Date", "COUNTRY"])
        )
        f_tf_currency = (
            _aggregate_level(["Closing_Date", "CURRENCY_ID"]).join(
                df_currency.lazy(), on=["Closing_Date", "CURRENCY_ID"], how="left"
            )
            if not df_currency.is_empty()
            else _aggregate_level(["Closing_Date", "CURRENCY_ID"])
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
            (f_tf_inst_type, "INSTRUMENT_TYPE"),
            (f_tf_sector, "SECTOR"),
            (f_tf_industry, "INDUSTRY"),
            (f_tf_geo, "GEO"),
            (f_tf_country, "COUNTRY"),
            (f_tf_currency, "CURRENCY_ID"),
        ]:
            lf = lf.with_columns(
                (
                    pl.col("Total_Current_Value")
                    / pl.col("Total_Current_Value").sum().over("Closing_Date")
                ).alias("Weight")
            ).drop(["annualized_twr", "bm_annualized_twr"], strict=False)
            if g == "ISIN":
                f_tf_isin = lf
            elif g == "INSTRUMENT_SUBTYPE":
                f_tf_subtype = lf
            elif g == "INSTRUMENT_CLASS":
                f_tf_class = lf
            elif g == "INSTRUMENT_TYPE":
                f_tf_inst_type = lf
            elif g == "SECTOR":
                f_tf_sector = lf
            elif g == "INDUSTRY":
                f_tf_industry = lf
            elif g == "GEO":
                f_tf_geo = lf
            elif g == "COUNTRY":
                f_tf_country = lf
            elif g == "CURRENCY_ID":
                f_tf_currency = lf

        f_tf_port = f_tf_port.with_columns(pl.lit(1.0).alias("Weight"))

        return {
            "df_f_investment_analytics_lot": lazy_df,
            "df_f_investment_analytics_isin": f_tf_isin,
            "df_f_investment_analytics_subtype": f_tf_subtype,
            "df_f_investment_analytics_class": f_tf_class,
            "df_f_investment_analytics_instrument_type": f_tf_inst_type,
            "df_f_investment_analytics_sector": f_tf_sector,
            "df_f_investment_analytics_industry": f_tf_industry,
            "df_f_investment_analytics_geo": f_tf_geo,
            "df_f_investment_analytics_country": f_tf_country,
            "df_f_investment_analytics_currency": f_tf_currency,
            "df_f_investment_analytics_portfolio": f_tf_port,
        }
