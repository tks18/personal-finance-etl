"""Portfolio aggregation and post-processing orchestration service.

Owns
----
- PostProcessor: Constructs aggregated multi-asset analytics tables across 10 dimensions
  (Lot, ISIN, Class, Subtype, Instrument Type, Sector, Industry, Geo, Country, Currency, Portfolio)
  plus realized gain events and reconciliation events.

Does not own
-------------
- Chronological per-ISIN daily simulation (owned by application.investments.isin_service).
- FIFO lot accounting and matching algorithms (owned by domain.investments.lots.fifo).
- Realized and reconciliation event conversion (owned by application.investments.aggregation_events).
- Post-processing pipeline scanning (owned by application.investments.aggregation_pipeline).
- Presentation layer report synthesis (owned by presentation).
"""

from __future__ import annotations

from datetime import date

import polars as pl

from personal_finance_etl.application.investments.aggregation_service.events import (
    build_realized_events,
    build_reconciliation_events,
)
from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.domain.investments.contracts import PipelineExecutionResult
from personal_finance_etl.domain.investments.performance.attribution import (
    RealizedGainsCalculator,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator,
)
from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PORTFOLIO_COL_RENAMES,
    GroupProcessor,
    PortfolioWeightsCalculator,
)
from personal_finance_etl.domain.investments.portfolio.analytics import (
    AdvancedAnalyticsCalculator,
    HarvestRecommendationCalculator,
)

__all__ = ["PostProcessor"]


class PostProcessor:
    """Aggregates lot-level stream partitions into hierarchical portfolio tables.

    Owns
    ----
    - Portfolio-level and group-level XIRR / analytics calculations.
    - Projection of 13 canonical analytical tables.
    """

    def __init__(self, ctx: RunContext) -> None:
        self.ctx = ctx
        self.xirr_calc = PortfolioXIRRCalculator()
        self.analytics_calc = AdvancedAnalyticsCalculator(ctx.fy_table, ctx.rules)
        self.weights_calc = PortfolioWeightsCalculator()
        self.gains_calc = RealizedGainsCalculator(ctx)
        self.harvest_calc = HarvestRecommendationCalculator()
        self.group_calc = GroupProcessor(self.analytics_calc)

    _FX_LOCAL_COLUMNS: tuple[str, ...] = (
        "Total_Invested_Value_Local",
        "Total_Current_Value_Local",
        "Blended_FX_Buy_Rate",
        "Current_FX_Rate",
        "Currency_Appreciation_Pct",
        "XIRR_Local",
        "BM_XIRR_Local",
        "Active_Return_Local",
        "FX_XIRR_Impact",
    )

    def _compute_portfolio_level(
        self,
        unique_dates: list[date],
        pipeline_res: PipelineExecutionResult,
    ) -> pl.DataFrame:
        """Calculate portfolio-level XIRR and extended risk/performance analytics."""
        df_port = self.xirr_calc.calculate(
            unique_dates, pipeline_res.global_cf, pipeline_res.global_pt
        )
        return self.analytics_calc.calculate(
            df_port, unique_dates, pipeline_res.global_pt, pipeline_res.global_cf
        )

    def _compute_group_analytics(
        self,
        unique_dates: list[date],
        pipeline_res: PipelineExecutionResult,
    ) -> dict[str, pl.DataFrame]:
        """Compute non-additive performance and return metrics across 9 portfolio dimensions."""
        return {
            "isin": self.group_calc.run(
                unique_dates, pipeline_res.isin_cf, pipeline_res.isin_pt, "ISIN"
            ),
            "class": self.group_calc.run(
                unique_dates, pipeline_res.class_cf, pipeline_res.class_pt, "INSTRUMENT_CLASS"
            ),
            "subtype": self.group_calc.run(
                unique_dates,
                pipeline_res.subtype_cf,
                pipeline_res.subtype_pt,
                "INSTRUMENT_CLASS",
                "INSTRUMENT_SUBTYPE",
            ),
            "inst_type": self.group_calc.run(
                unique_dates,
                pipeline_res.instrument_type_cf,
                pipeline_res.instrument_type_pt,
                "INSTRUMENT_TYPE",
            ),
            "sector": self.group_calc.run(
                unique_dates, pipeline_res.sector_cf, pipeline_res.sector_pt, "SECTOR"
            ),
            "industry": self.group_calc.run(
                unique_dates, pipeline_res.industry_cf, pipeline_res.industry_pt, "INDUSTRY"
            ),
            "geo": self.group_calc.run(
                unique_dates, pipeline_res.geo_cf, pipeline_res.geo_pt, "GEO"
            ),
            "country": self.group_calc.run(
                unique_dates, pipeline_res.country_cf, pipeline_res.country_pt, "COUNTRY"
            ),
            "currency": self.group_calc.run(
                unique_dates, pipeline_res.currency_cf, pipeline_res.currency_pt, "CURRENCY_ID"
            ),
        }

    def _build_master_metadata(self) -> pl.LazyFrame:
        """Construct LazyFrame of instrument metadata with sanitized null defaults."""
        master_records = [{"ISIN": k, **v} for k, v in self.ctx.isin_master.items()]
        return (
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

    @staticmethod
    def _level_aggregation_expressions() -> list[pl.Expr]:
        return [
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
        ]

    def _aggregate_level(
        self,
        lazy_df_agg: pl.LazyFrame,
        group_cols: list[str],
    ) -> pl.LazyFrame:
        """Roll up active lot positions into additive group-level financial metrics."""
        select_cols = list(
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
        base = (
            lazy_df_agg.select(select_cols)
            .group_by(group_cols)
            .agg(self._level_aggregation_expressions())
            .with_columns(
                (pl.col("Total_Current_Value") - pl.col("Total_Invested_Value")).alias(
                    "Unrealized_PL"
                )
            )
        )
        return base.with_columns(
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
        ).with_columns(
            pl.when(pl.col("Blended_FX_Buy_Rate") > 0)
            .then((pl.col("Current_FX_Rate") / pl.col("Blended_FX_Buy_Rate")) - 1.0)
            .otherwise(0.0)
            .alias("Currency_Appreciation_Pct")
        )

    def _apply_weights_and_prune(
        self,
        lf: pl.LazyFrame,
        group_col: str,
    ) -> pl.LazyFrame:
        """Calculate relative portfolio weight and prune local FX columns for non-currency dimensions."""
        lf = lf.with_columns(
            (
                pl.col("Total_Current_Value")
                / pl.col("Total_Current_Value").sum().over("Closing_Date")
            ).alias("Weight")
        ).drop(["annualized_twr", "bm_annualized_twr"], strict=False)

        if group_col not in ("ISIN", "CURRENCY_ID", "COUNTRY"):
            lf = lf.drop(list(self._FX_LOCAL_COLUMNS), strict=False)

        return lf

    def _build_isin_table(
        self,
        lazy_df_agg: pl.LazyFrame,
        group_isin: pl.DataFrame,
    ) -> pl.LazyFrame:
        """Construct ISIN-level aggregated analytical table."""
        metrics = (
            lazy_df_agg.select(
                [
                    "Closing_Date",
                    "ISIN",
                    "CAGR",
                    "BM_CAGR",
                    "Is_Lagging_Benchmark",
                    "LTCG_Tax_If_Sold",
                    "STCG_Tax_If_Sold",
                    "Unrealized_LTCG",
                    "Unrealized_STCG",
                    "Unrealized_LTCL",
                    "Unrealized_STCL",
                    "Outperforming_Lot_Ratio",
                ]
            )
            .group_by(["Closing_Date", "ISIN"])
            .agg(
                pl.col("CAGR").first(),
                pl.col("BM_CAGR").first(),
                pl.col("Is_Lagging_Benchmark").first(),
                pl.col("LTCG_Tax_If_Sold").sum(),
                pl.col("STCG_Tax_If_Sold").sum(),
                pl.col("Unrealized_LTCG").sum(),
                pl.col("Unrealized_STCG").sum(),
                pl.col("Unrealized_LTCL").sum(),
                pl.col("Unrealized_STCL").sum(),
                pl.col("Outperforming_Lot_Ratio").first(),
            )
        )
        base = (
            self._aggregate_level(lazy_df_agg, ["Closing_Date", "ISIN"])
            .join(metrics, on=["Closing_Date", "ISIN"], how="left")
            .join(group_isin.lazy(), on=["Closing_Date", "ISIN"], how="left")
        )
        return self._apply_weights_and_prune(base, "ISIN")

    def _build_dimensional_tables(
        self,
        lazy_df_agg: pl.LazyFrame,
        groups: dict[str, pl.DataFrame],
    ) -> dict[str, pl.LazyFrame]:
        """Construct 8 aggregated dimensional slice tables."""

        def _build_dim(
            dim_df: pl.DataFrame, group_cols: list[str], weight_key: str
        ) -> pl.LazyFrame:
            base = self._aggregate_level(lazy_df_agg, group_cols)
            if not dim_df.is_empty():
                base = base.join(dim_df.lazy(), on=group_cols, how="left")
            return self._apply_weights_and_prune(base, weight_key)

        return {
            "class": _build_dim(
                groups["class"], ["Closing_Date", "INSTRUMENT_CLASS"], "INSTRUMENT_CLASS"
            ),
            "subtype": _build_dim(
                groups["subtype"],
                ["Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"],
                "INSTRUMENT_SUBTYPE",
            ),
            "inst_type": _build_dim(
                groups["inst_type"], ["Closing_Date", "INSTRUMENT_TYPE"], "INSTRUMENT_TYPE"
            ),
            "sector": _build_dim(groups["sector"], ["Closing_Date", "SECTOR"], "SECTOR"),
            "industry": _build_dim(groups["industry"], ["Closing_Date", "INDUSTRY"], "INDUSTRY"),
            "geo": _build_dim(groups["geo"], ["Closing_Date", "GEO"], "GEO"),
            "country": _build_dim(groups["country"], ["Closing_Date", "COUNTRY"], "COUNTRY"),
            "currency": _build_dim(
                groups["currency"], ["Closing_Date", "CURRENCY_ID"], "CURRENCY_ID"
            ),
        }

    def _build_portfolio_table(
        self,
        lazy_df_agg: pl.LazyFrame,
        df_port: pl.DataFrame,
    ) -> pl.LazyFrame:
        """Construct portfolio-wide aggregate table."""
        return (
            self._aggregate_level(lazy_df_agg, ["Closing_Date"])
            .join(
                df_port.lazy().rename(PORTFOLIO_COL_RENAMES),
                on=["Closing_Date"],
                how="left",
            )
            .with_columns(pl.lit(1.0).alias("Weight"))
            .drop(list(self._FX_LOCAL_COLUMNS), strict=False)
        )

    def run(
        self,
        lazy_df: pl.LazyFrame,
        unique_dates: list[date],
        pipeline_res: PipelineExecutionResult,
    ) -> dict[str, pl.LazyFrame]:
        """Calculate portfolio metrics and lazily attach them to the lot-level DataFrame.

        Parameters
        ----------
        lazy_df : pl.LazyFrame
            LazyFrame scanning intermediate lot partitions.
        unique_dates : list[date]
            Sorted list of all unique valuation dates across the run.
        pipeline_res : PipelineExecutionResult
            Aggregated terminal values, cash flows, and realized events from worker pool.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary containing 13 lazy analytical tables.
        """
        df_port = self._compute_portfolio_level(unique_dates, pipeline_res)

        lazy_df = self.weights_calc.calculate(lazy_df)
        lazy_df = self.gains_calc.calculate(lazy_df, unique_dates, pipeline_res.global_re)
        lazy_df = self.harvest_calc.calculate(lazy_df, rules=self.ctx.rules)

        groups = self._compute_group_analytics(unique_dates, pipeline_res)

        master_cols = self._build_master_metadata()
        # Compose master metadata join into lazy pipeline without eager round-trip materialization
        lazy_df_agg = lazy_df.join(master_cols, on="ISIN", how="left")

        f_tf_isin = self._build_isin_table(lazy_df_agg, groups["isin"])
        dim_tables = self._build_dimensional_tables(lazy_df_agg, groups)
        f_tf_port = self._build_portfolio_table(lazy_df_agg, df_port)

        df_re = build_realized_events(pipeline_res)
        df_recon = build_reconciliation_events(pipeline_res, self.ctx.run_id)

        return {
            "df_f_investment_analytics_lot": lazy_df,
            "df_f_investment_realized_events": df_re,
            "df_f_investment_reconciliation_events": df_recon,
            "df_f_investment_analytics_isin": f_tf_isin,
            "df_f_investment_analytics_subtype": dim_tables["subtype"],
            "df_f_investment_analytics_class": dim_tables["class"],
            "df_f_investment_analytics_instrument_type": dim_tables["inst_type"],
            "df_f_investment_analytics_sector": dim_tables["sector"],
            "df_f_investment_analytics_industry": dim_tables["industry"],
            "df_f_investment_analytics_geo": dim_tables["geo"],
            "df_f_investment_analytics_country": dim_tables["country"],
            "df_f_investment_analytics_currency": dim_tables["currency"],
            "df_f_investment_analytics_portfolio": f_tf_port,
        }
