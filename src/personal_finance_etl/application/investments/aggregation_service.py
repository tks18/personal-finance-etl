"""Portfolio aggregation and post-processing orchestration service.

Owns
----
- PostProcessor: Constructs aggregated multi-asset analytics tables across 10 dimensions
  (Lot, ISIN, Class, Subtype, Instrument Type, Sector, Industry, Geo, Country, Currency, Portfolio)
  plus realized gain events and reconciliation events.
- PostProcessingPipeline: Scans intermediate per-ISIN Parquet partitions and executes
  the post-processing aggregation graph to produce collected DataFrames.

Does not own
-------------
- Chronological per-ISIN daily simulation (owned by application.investments.isin_service).
- FIFO lot accounting and matching algorithms (owned by domain.investments.lots.fifo).
- Presentation layer report synthesis (owned by presentation).
"""

from __future__ import annotations

import os
from datetime import date

import polars as pl

from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.domain.common.identity import generate_deterministic_id
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
from personal_finance_etl.infrastructure.logging.setup import logger

__all__ = ["PostProcessingPipeline", "PostProcessor"]


class PostProcessor:
    """Aggregates lot-level stream partitions into hierarchical portfolio tables.

    Owns
    ----
    - Portfolio-level and group-level XIRR / analytics calculations.
    - Deterministic ID generation for reconciliation groups and events.
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

    def _aggregate_level(
        self,
        lazy_df_agg: pl.LazyFrame,
        group_cols: list[str],
    ) -> pl.LazyFrame:
        """Roll up active lot positions into additive group-level financial metrics."""
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

    def _build_realized_events(
        self,
        pipeline_res: PipelineExecutionResult,
    ) -> pl.LazyFrame:
        """Construct LazyFrame of realized FIFO tax events with sanitized reconciliation rates."""
        re_schema = {
            "Realized_Event_ID": pl.String,
            "Sale_ID": pl.String,
            "Lot_ID": pl.String,
            "Purchase_ID": pl.String,
            "ISIN": pl.String,
            "Acquisition_Date": pl.Date,
            "Disposal_Date": pl.Date,
            "FY": pl.String,
            "Quantity_Disposed": pl.Float64,
            "Acquisition_Price": pl.Float64,
            "Disposed_Cost_Basis": pl.Float64,
            "Sale_Price": pl.Float64,
            "Sale_Proceeds": pl.Float64,
            "Realized_Gain_Loss": pl.Float64,
            "Holding_Type": pl.String,
            "Tax_Type": pl.String,
            "Tax_Subtype": pl.String,
            "Lot_Source_Type": pl.String,
            "Currency_ID": pl.String,
            "Asset_PnL_Local": pl.Float64,
            "Asset_PnL": pl.Float64,
            "Forex_PnL": pl.Float64,
            "Applied_Rate": pl.Float64,
            "Estimated_Tax": pl.Float64,
        }

        if not pipeline_res.global_re:
            return pl.LazyFrame(schema=re_schema)

        return (
            pl.LazyFrame(pipeline_res.global_re, schema_overrides=re_schema)
            .select(list(re_schema.keys()))
            .with_columns(
                pl.when(
                    pl.col("Lot_Source_Type").cast(pl.String).str.to_uppercase() == "RECONCILIATION"
                )
                .then(pl.lit(None, dtype=pl.Float64))
                .otherwise(pl.col("Applied_Rate"))
                .alias("Applied_Rate"),
                pl.when(
                    pl.col("Lot_Source_Type").cast(pl.String).str.to_uppercase() == "RECONCILIATION"
                )
                .then(pl.lit(None, dtype=pl.Float64))
                .otherwise(pl.col("Estimated_Tax"))
                .alias("Estimated_Tax"),
            )
        )

    def _build_reconciliation_events(
        self,
        pipeline_res: PipelineExecutionResult,
    ) -> pl.LazyFrame:
        """Assign deterministic group/event IDs and build reconciliation LazyFrame."""
        for re_event in pipeline_res.global_recon_events:
            re_event["Run_ID"] = self.ctx.run_id
            re_event["Reconciliation_Group_ID"] = generate_deterministic_id(
                "RECON_GROUP",
                {
                    "ISIN": re_event.get("ISIN"),
                    "Reconciliation_Date": re_event.get("Reconciliation_Date"),
                    "Adjustment_Type": re_event.get("Adjustment_Type"),
                    "Broker_Quantity": re_event.get("Broker_Quantity"),
                    "Reconstructed_Quantity": re_event.get("Reconstructed_Quantity"),
                    "Broker_Cost_Basis": re_event.get("Broker_Cost_Basis"),
                    "Reconstructed_Cost_Basis": re_event.get("Reconstructed_Cost_Basis"),
                },
            )
            re_event["Reconciliation_Event_ID"] = generate_deterministic_id(
                "RECON_EVENT",
                {
                    "Reconciliation_Group_ID": re_event["Reconciliation_Group_ID"],
                    "Lot_ID": re_event.get("Lot_ID"),
                    "Adjustment_Type": re_event.get("Adjustment_Type"),
                },
            )

        if pipeline_res.global_recon_events:
            return pl.LazyFrame(pipeline_res.global_recon_events)

        return pl.LazyFrame(
            schema={
                "Reconciliation_Group_ID": pl.String,
                "Reconciliation_Event_ID": pl.String,
                "Run_ID": pl.String,
                "ISIN": pl.String,
                "Reconciliation_Date": pl.Date,
                "Lot_ID": pl.String,
                "Purchase_ID": pl.String,
                "Adjustment_Type": pl.String,
                "Reason": pl.String,
                "Broker_Quantity": pl.Float64,
                "Reconstructed_Quantity": pl.Float64,
                "Quantity_Adjustment": pl.Float64,
                "Broker_Cost_Basis": pl.Float64,
                "Reconstructed_Cost_Basis": pl.Float64,
                "Cost_Basis_Adjustment": pl.Float64,
                "Original_Unit_Cost": pl.Float64,
                "Adjusted_Unit_Cost": pl.Float64,
            }
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
        # Materialize once so subsequent aggregation calls scan cached in-memory data
        lazy_df_agg = lazy_df.join(master_cols, on="ISIN", how="left").collect().lazy()

        f_tf_isin = (
            self._aggregate_level(lazy_df_agg, ["Closing_Date", "ISIN"])
            .join(
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
                ),
                on=["Closing_Date", "ISIN"],
                how="left",
            )
            .join(groups["isin"].lazy(), on=["Closing_Date", "ISIN"], how="left")
        )
        f_tf_isin = self._apply_weights_and_prune(f_tf_isin, "ISIN")

        def _build_dim(
            dim_df: pl.DataFrame, group_cols: list[str], weight_key: str
        ) -> pl.LazyFrame:
            base = self._aggregate_level(lazy_df_agg, group_cols)
            if not dim_df.is_empty():
                base = base.join(dim_df.lazy(), on=group_cols, how="left")
            return self._apply_weights_and_prune(base, weight_key)

        f_tf_class = _build_dim(
            groups["class"], ["Closing_Date", "INSTRUMENT_CLASS"], "INSTRUMENT_CLASS"
        )
        f_tf_subtype = _build_dim(
            groups["subtype"],
            ["Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"],
            "INSTRUMENT_SUBTYPE",
        )
        f_tf_inst_type = _build_dim(
            groups["inst_type"], ["Closing_Date", "INSTRUMENT_TYPE"], "INSTRUMENT_TYPE"
        )
        f_tf_sector = _build_dim(groups["sector"], ["Closing_Date", "SECTOR"], "SECTOR")
        f_tf_industry = _build_dim(groups["industry"], ["Closing_Date", "INDUSTRY"], "INDUSTRY")
        f_tf_geo = _build_dim(groups["geo"], ["Closing_Date", "GEO"], "GEO")
        f_tf_country = _build_dim(groups["country"], ["Closing_Date", "COUNTRY"], "COUNTRY")
        f_tf_currency = _build_dim(
            groups["currency"], ["Closing_Date", "CURRENCY_ID"], "CURRENCY_ID"
        )

        f_tf_port = (
            self._aggregate_level(lazy_df_agg, ["Closing_Date"])
            .join(
                df_port.lazy().rename(PORTFOLIO_COL_RENAMES),
                on=["Closing_Date"],
                how="left",
            )
            .with_columns(pl.lit(1.0).alias("Weight"))
            .drop(list(self._FX_LOCAL_COLUMNS), strict=False)
        )

        df_re = self._build_realized_events(pipeline_res)
        df_recon = self._build_reconciliation_events(pipeline_res)

        return {
            "df_f_investment_analytics_lot": lazy_df,
            "df_f_investment_realized_events": df_re,
            "df_f_investment_reconciliation_events": df_recon,
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


class PostProcessingPipeline:
    """Handles reading spilled parquet files and running final aggregations."""

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
        if self.status_queue:
            self.status_queue.put(
                EngineStatusMessage(msg="", progress=progress, level=LogLevel.STEP)
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

        unique_dates_df = lazy_df.select("Closing_Date").unique().collect()
        unique_dates = unique_dates_df["Closing_Date"].sort().to_list()

        logger.debug("Post-processing: Aggregating portfolio metrics...")
        self._report_step(0.90)

        res_dict = self.postprocessor.run(lazy_df, unique_dates, pipeline_res)

        logger.debug("Post-processing: Collecting final output...")
        self._report_step(0.95)

        final_res: dict[str, pl.DataFrame] = {k: v.collect() for k, v in res_dict.items()}
        return final_res
