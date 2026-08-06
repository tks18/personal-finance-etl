from collections.abc import Mapping
from typing import Any, cast

import polars as pl


class InvestmentSnapshotBuilder:
    """
    Builds two presentation tables:
      1. p_tf_Investment_Snapshot_ISIN     — MoM return at ISIN × Month grain
      2. p_tf_Investment_Snapshot_Portfolio — MoM return + cashflow context at Month grain

    MoM return is flow-corrected:
        MoM_Return = (MV_t - MV_{t-1} - Deployed_t + Redeemed_t) / MV_{t-1}
    This strips capital inflows/outflows so the metric reflects pure price/NAV appreciation.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _snap_to_month(self, lf: pl.LazyFrame, date_col: str = "Closing_Date") -> pl.LazyFrame:
        """Keep the latest snapshot row per ISIN×month (or just month for portfolio)."""
        return lf.with_columns(
            pl.col(date_col).dt.month_end().alias("MONTH_END_DATE"),
            pl.col(date_col).dt.month_start().alias("MONTH_START_DATE"),
        )

    def _latest_per_isin_month(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Deduplicate to one row per ISIN×MONTH_END_DATE (latest Closing_Date wins)."""
        latest = lf.group_by(["ISIN", "MONTH_END_DATE"]).agg(
            pl.col("Closing_Date").max().alias("_max_date")
        )
        return (
            lf.join(latest, on=["ISIN", "MONTH_END_DATE"], how="left")
            .filter(pl.col("Closing_Date") == pl.col("_max_date"))
            .drop("_max_date")
        )

    def _latest_per_month(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Deduplicate to one row per MONTH_END_DATE (portfolio level)."""
        latest = lf.group_by("MONTH_END_DATE").agg(
            pl.col("Closing_Date").max().alias("_max_date")
        )
        return (
            lf.join(latest, on="MONTH_END_DATE", how="left")
            .filter(pl.col("Closing_Date") == pl.col("_max_date"))
            .drop("_max_date")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ISIN-level snapshot
    # ─────────────────────────────────────────────────────────────────────────

    def build_isin(self) -> pl.LazyFrame:
        df_isin = self.dfs.get("df_f_tf_investment_analytics_isin")
        df_master = self.dfs.get("df_d_tf_investment_master")
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")
        df_benchmark = self.dfs.get("df_f_investment_benchmark_data")

        if df_isin is None:
            return pl.LazyFrame()

        lf_isin = cast(
            pl.LazyFrame, df_isin.lazy() if isinstance(df_isin, pl.DataFrame) else df_isin
        )

        # ── Snap to month-end and dedup ──────────────────────────────────────
        lf_isin = self._snap_to_month(lf_isin)
        lf_isin = self._latest_per_isin_month(lf_isin)

        # ── Join master for instrument metadata ──────────────────────────────
        if df_master is not None:
            lf_master = cast(
                pl.LazyFrame,
                df_master.lazy() if isinstance(df_master, pl.DataFrame) else df_master,
            )
            lf_isin = lf_isin.join(
                lf_master.select(
                    ["ISIN", "INSTRUMENT_NAME", "INSTRUMENT_CLASS", "INSTRUMENT_TYPE",
                     "INSTRUMENT_SUBTYPE", "SECTOR", "BENCHMARK_ID"]
                ),
                on="ISIN",
                how="left",
            )
        else:
            lf_isin = lf_isin.with_columns(
                pl.lit(None).alias("INSTRUMENT_NAME"),
                pl.lit(None).alias("INSTRUMENT_CLASS"),
                pl.lit(None).alias("INSTRUMENT_TYPE"),
                pl.lit(None).alias("INSTRUMENT_SUBTYPE"),
                pl.lit(None).alias("SECTOR"),
                pl.lit(None).alias("BENCHMARK_ID"),
            )

        # ── Monthly deployed (buys) per ISIN ─────────────────────────────────
        if df_buys is not None and "Date" in df_buys.columns:
            lf_buys = cast(
                pl.LazyFrame, df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            )
            lf_deployed = (
                lf_buys.with_columns(pl.col("Date").dt.month_end().alias("MONTH_END_DATE"))
                .group_by(["ISIN", "MONTH_END_DATE"])
                .agg(pl.col("Value").sum().fill_null(0.0).alias("Monthly_Deployed"))
            )
            lf_isin = lf_isin.join(lf_deployed, on=["ISIN", "MONTH_END_DATE"], how="left")
        else:
            lf_isin = lf_isin.with_columns(pl.lit(0.0).alias("Monthly_Deployed"))

        # ── Monthly redeemed (sells) per ISIN ────────────────────────────────
        if df_sells is not None and "Date" in df_sells.columns:
            lf_sells = cast(
                pl.LazyFrame, df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            )
            lf_redeemed = (
                lf_sells.with_columns(pl.col("Date").dt.month_end().alias("MONTH_END_DATE"))
                .group_by(["ISIN", "MONTH_END_DATE"])
                .agg(pl.col("Sell Value").sum().fill_null(0.0).alias("Monthly_Redeemed"))
            )
            lf_isin = lf_isin.join(lf_redeemed, on=["ISIN", "MONTH_END_DATE"], how="left")
        else:
            lf_isin = lf_isin.with_columns(pl.lit(0.0).alias("Monthly_Redeemed"))

        # ── Benchmark MoM price return ────────────────────────────────────────
        if df_benchmark is not None and "Date" in df_benchmark.columns and "BENCHMARK_ID" in (lf_isin.collect_schema().names()):
            lf_bm = cast(
                pl.LazyFrame,
                df_benchmark.lazy() if isinstance(df_benchmark, pl.DataFrame) else df_benchmark,
            )
            # Latest benchmark close per month
            lf_bm_monthly = (
                lf_bm.with_columns(pl.col("Date").dt.month_end().alias("MONTH_END_DATE"))
                .group_by(["ID", "MONTH_END_DATE"])
                .agg(pl.col("Close").last().alias("BM_Closing_Price"))
                .sort(["ID", "MONTH_END_DATE"])
                .with_columns(
                    pl.col("BM_Closing_Price")
                    .shift(1)
                    .over("ID", order_by="MONTH_END_DATE")
                    .alias("Prev_BM_Closing_Price")
                )
                .with_columns(
                    pl.when(pl.col("Prev_BM_Closing_Price") > 0)
                    .then(
                        (pl.col("BM_Closing_Price") - pl.col("Prev_BM_Closing_Price"))
                        / pl.col("Prev_BM_Closing_Price")
                    )
                    .otherwise(None)
                    .alias("BM_MoM_Return_Pct")
                )
                .rename({"ID": "BENCHMARK_ID"})
                .select(["BENCHMARK_ID", "MONTH_END_DATE", "BM_MoM_Return_Pct"])
            )
            lf_isin = lf_isin.join(lf_bm_monthly, on=["BENCHMARK_ID", "MONTH_END_DATE"], how="left")
        else:
            lf_isin = lf_isin.with_columns(pl.lit(None).cast(pl.Float64).alias("BM_MoM_Return_Pct"))

        # ── Fill nulls for flow columns ───────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.col("Monthly_Deployed").fill_null(0.0),
            pl.col("Monthly_Redeemed").fill_null(0.0),
        )

        # ── Sort FIRST — mandatory before any over()/shift() ─────────────────
        lf_isin = lf_isin.sort(["ISIN", "MONTH_START_DATE"])

        # ── Window computations ───────────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.col("Total_Current_Value")
            .shift(1)
            .over("ISIN", order_by="MONTH_START_DATE")
            .alias("Prev_Month_Market_Value"),
            pl.col("Total_Invested_Value")
            .shift(1)
            .over("ISIN", order_by="MONTH_START_DATE")
            .alias("Prev_Month_Invested_Value"),
        )

        # ── MoM return calculations ───────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            (pl.col("Total_Current_Value") - pl.col("Prev_Month_Market_Value")).alias(
                "Monthly_Value_Change"
            ),
            (pl.col("Monthly_Deployed") - pl.col("Monthly_Redeemed")).alias("Net_Monthly_Flow"),
            # Flow-corrected MoM (pure price return)
            pl.when(pl.col("Prev_Month_Market_Value") > 0)
            .then(
                (
                    pl.col("Total_Current_Value")
                    - pl.col("Prev_Month_Market_Value")
                    - pl.col("Monthly_Deployed")
                    + pl.col("Monthly_Redeemed")
                )
                / pl.col("Prev_Month_Market_Value")
            )
            .otherwise(None)
            .alias("MoM_Return_Pct"),
            # Naive MoM (includes SIP effect)
            pl.when(pl.col("Prev_Month_Market_Value") > 0)
            .then(
                (pl.col("Total_Current_Value") - pl.col("Prev_Month_Market_Value"))
                / pl.col("Prev_Month_Market_Value")
            )
            .otherwise(None)
            .alias("MoM_Return_Pct_Simple"),
        )

        # ── Rolling returns ───────────────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.when(pl.col("Total_Current_Value").shift(3).over("ISIN", order_by="MONTH_START_DATE") > 0)
            .then(
                pl.col("Total_Current_Value")
                / pl.col("Total_Current_Value").shift(3).over("ISIN", order_by="MONTH_START_DATE")
                - 1.0
            )
            .otherwise(None)
            .alias("Rolling_3M_Return_Pct"),
            pl.when(pl.col("Total_Current_Value").shift(6).over("ISIN", order_by="MONTH_START_DATE") > 0)
            .then(
                pl.col("Total_Current_Value")
                / pl.col("Total_Current_Value").shift(6).over("ISIN", order_by="MONTH_START_DATE")
                - 1.0
            )
            .otherwise(None)
            .alias("Rolling_6M_Return_Pct"),
            pl.when(pl.col("Total_Current_Value").shift(12).over("ISIN", order_by="MONTH_START_DATE") > 0)
            .then(
                pl.col("Total_Current_Value")
                / pl.col("Total_Current_Value").shift(12).over("ISIN", order_by="MONTH_START_DATE")
                - 1.0
            )
            .otherwise(None)
            .alias("Rolling_12M_Return_Pct"),
        )

        # ── Benchmark alpha ───────────────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.when(
                pl.col("MoM_Return_Pct").is_not_null()
                & pl.col("BM_MoM_Return_Pct").is_not_null()
            )
            .then(pl.col("MoM_Return_Pct") - pl.col("BM_MoM_Return_Pct"))
            .otherwise(None)
            .alias("MoM_Alpha"),
        )

        # ── Portfolio weight context ──────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.when(pl.col("Total_Current_Value").sum().over("MONTH_START_DATE") > 0)
            .then(
                pl.col("Total_Current_Value")
                / pl.col("Total_Current_Value").sum().over("MONTH_START_DATE")
            )
            .otherwise(0.0)
            .alias("Portfolio_Weight_Pct"),
        )

        # ── YEAR_MONTH ────────────────────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
        )

        # ── Flags ─────────────────────────────────────────────────────────────
        lf_isin = lf_isin.with_columns(
            (
                pl.col("Prev_Month_Market_Value").is_null()
                & (pl.col("Total_Current_Value") > 0)
            ).alias("Is_New_Position"),
            (
                (pl.col("Total_Current_Value") == 0)
                & pl.col("Prev_Month_Market_Value").is_not_null()
                & (pl.col("Prev_Month_Market_Value") > 0)
            ).alias("Is_Closed_Position"),
            (
                (pl.col("Monthly_Deployed") > 0) | (pl.col("Monthly_Redeemed") > 0)
            ).alias("Is_Active_Month"),
            pl.col("MoM_Return_Pct").is_not_null()
            .and_(pl.col("MoM_Return_Pct") > 0)
            .alias("Is_MoM_Positive"),
            pl.col("MoM_Alpha").is_not_null()
            .and_(pl.col("MoM_Alpha") > 0)
            .alias("Is_Beating_BM_MoM"),
        )

        return lf_isin.select(
            [
                "MONTH_START_DATE", "MONTH_END_DATE", "YEAR_MONTH",
                "ISIN", "INSTRUMENT_NAME", "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE", "INSTRUMENT_SUBTYPE", "SECTOR",
                # Position values
                pl.col("Total_Invested_Value").alias("Invested_Value"),
                pl.col("Total_Current_Value").alias("Market_Value"),
                "Unrealized_PL",
                pl.col("Absolute_Return_%").alias("Absolute_Return_Pct"),
                "Portfolio_Weight_Pct",
                # MoM
                "Prev_Month_Market_Value",
                "Monthly_Value_Change",
                "Monthly_Deployed",
                "Monthly_Redeemed",
                "Net_Monthly_Flow",
                "MoM_Return_Pct",
                "MoM_Return_Pct_Simple",
                # Trailing
                "Rolling_3M_Return_Pct",
                "Rolling_6M_Return_Pct",
                "Rolling_12M_Return_Pct",
                # Benchmark MoM
                "BM_MoM_Return_Pct",
                "MoM_Alpha",
                # Snapshot metrics (cumulative)
                "CAGR", "XIRR", "After_Tax_XIRR", "Active_Return",
                "Beta", "Tracking_Error", "Information_Ratio",
                # Tax context
                "Unrealized_LTCG", "Unrealized_STCG",
                "Unrealized_LTCL", "Unrealized_STCL",
                "LTCG_Tax_If_Sold", "STCG_Tax_If_Sold",
                # Flags
                "Is_New_Position", "Is_Closed_Position",
                "Is_Active_Month", "Is_MoM_Positive", "Is_Beating_BM_MoM",
            ]
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio-level snapshot
    # ─────────────────────────────────────────────────────────────────────────

    def build_portfolio(self) -> pl.LazyFrame:
        df_port = self.dfs.get("df_f_tf_investment_analytics_portfolio")
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")
        lf_monthly_totals = self.base_lf.get("lf_monthly_totals")

        if df_port is None:
            return pl.LazyFrame()

        lf_port = cast(
            pl.LazyFrame, df_port.lazy() if isinstance(df_port, pl.DataFrame) else df_port
        )

        # ── Snap to month-end and dedup ──────────────────────────────────────
        lf_port = self._snap_to_month(lf_port)
        lf_port = self._latest_per_month(lf_port)

        # ── Monthly deployed/redeemed (all ISINs combined) ───────────────────
        if df_buys is not None and "Date" in df_buys.columns:
            lf_buys = cast(
                pl.LazyFrame, df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            )
            lf_deployed_total = (
                lf_buys.with_columns(pl.col("Date").dt.month_end().alias("MONTH_END_DATE"))
                .group_by("MONTH_END_DATE")
                .agg(pl.col("Value").sum().fill_null(0.0).alias("Monthly_Deployed_Total"))
            )
            lf_port = lf_port.join(lf_deployed_total, on="MONTH_END_DATE", how="left")
        else:
            lf_port = lf_port.with_columns(pl.lit(0.0).alias("Monthly_Deployed_Total"))

        if df_sells is not None and "Date" in df_sells.columns:
            lf_sells = cast(
                pl.LazyFrame, df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            )
            lf_redeemed_total = (
                lf_sells.with_columns(pl.col("Date").dt.month_end().alias("MONTH_END_DATE"))
                .group_by("MONTH_END_DATE")
                .agg(pl.col("Sell Value").sum().fill_null(0.0).alias("Monthly_Redeemed_Total"))
            )
            lf_port = lf_port.join(lf_redeemed_total, on="MONTH_END_DATE", how="left")
        else:
            lf_port = lf_port.with_columns(pl.lit(0.0).alias("Monthly_Redeemed_Total"))

        lf_port = lf_port.with_columns(
            pl.col("Monthly_Deployed_Total").fill_null(0.0),
            pl.col("Monthly_Redeemed_Total").fill_null(0.0),
        )

        # ── Sort FIRST ────────────────────────────────────────────────────────
        lf_port = lf_port.sort("MONTH_START_DATE")

        # ── MoM return ────────────────────────────────────────────────────────
        lf_port = lf_port.with_columns(
            pl.col("Total_Current_Value").shift(1).alias("Prev_Month_Market_Value"),
        ).with_columns(
            (pl.col("Total_Current_Value") - pl.col("Prev_Month_Market_Value")).alias(
                "Portfolio_MoM_Value_Change"
            ),
            # Flow-corrected
            pl.when(pl.col("Prev_Month_Market_Value") > 0)
            .then(
                (
                    pl.col("Total_Current_Value")
                    - pl.col("Prev_Month_Market_Value")
                    - pl.col("Monthly_Deployed_Total")
                    + pl.col("Monthly_Redeemed_Total")
                )
                / pl.col("Prev_Month_Market_Value")
            )
            .otherwise(None)
            .alias("Portfolio_MoM_Return_Pct"),
            # Naive
            pl.when(pl.col("Prev_Month_Market_Value") > 0)
            .then(
                (pl.col("Total_Current_Value") - pl.col("Prev_Month_Market_Value"))
                / pl.col("Prev_Month_Market_Value")
            )
            .otherwise(None)
            .alias("Portfolio_MoM_Return_Pct_Simple"),
        )

        # ── Rolling returns ───────────────────────────────────────────────────
        lf_port = lf_port.with_columns(
            pl.when(pl.col("Total_Current_Value").shift(3) > 0)
            .then(pl.col("Total_Current_Value") / pl.col("Total_Current_Value").shift(3) - 1.0)
            .otherwise(None)
            .alias("Rolling_3M_Return_Pct"),
            pl.when(pl.col("Total_Current_Value").shift(6) > 0)
            .then(pl.col("Total_Current_Value") / pl.col("Total_Current_Value").shift(6) - 1.0)
            .otherwise(None)
            .alias("Rolling_6M_Return_Pct"),
            pl.when(pl.col("Total_Current_Value").shift(12) > 0)
            .then(pl.col("Total_Current_Value") / pl.col("Total_Current_Value").shift(12) - 1.0)
            .otherwise(None)
            .alias("Rolling_12M_Return_Pct"),
        ).with_columns(
            pl.when(pl.col("Rolling_3M_Return_Pct").is_not_null())
            .then(((1 + pl.col("Rolling_3M_Return_Pct")).pow(4.0)) - 1.0)
            .otherwise(None)
            .alias("Rolling_3M_Annualized_Return"),
        )


        # ── YEAR_MONTH ────────────────────────────────────────────────────────
        lf_port = lf_port.with_columns(
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
        )

        return lf_port.select(
            [
                "MONTH_START_DATE", "MONTH_END_DATE", "YEAR_MONTH",
                # Valuation
                pl.col("Total_Invested_Value"),
                pl.col("Total_Current_Value").alias("Total_Market_Value"),
                pl.col("Unrealized_PL").alias("Total_Unrealized_PL"),
                pl.col("Absolute_Return_%").alias("Absolute_Return_Pct"),
                # MoM
                "Prev_Month_Market_Value",
                "Portfolio_MoM_Return_Pct",
                "Portfolio_MoM_Return_Pct_Simple",
                "Portfolio_MoM_Value_Change",
                "Monthly_Deployed_Total",
                "Monthly_Redeemed_Total",
                # Rolling
                "Rolling_3M_Return_Pct",
                "Rolling_6M_Return_Pct",
                "Rolling_12M_Return_Pct",
                "Rolling_3M_Annualized_Return",
                # Quant
                "XIRR", "After_Tax_XIRR", "BM_XIRR",
                "Active_Return", "Sharpe_Ratio", "Sortino_Ratio", "Max_Drawdown",

                # Tax summary
                pl.col("Unrealized_LTCG").alias("Total_Unrealized_LTCG"),
                pl.col("Unrealized_STCG").alias("Total_Unrealized_STCG"),
                pl.col("Unrealized_LTCL").alias("Total_Unrealized_LTCL"),
                pl.col("Unrealized_STCL").alias("Total_Unrealized_STCL"),
                pl.col("LTCG_Tax_If_Sold").alias("Total_LTCG_Tax_If_Sold"),
                pl.col("STCG_Tax_If_Sold").alias("Total_STCG_Tax_If_Sold"),
                "FY_Realized_Net_PnL",
            ]
        )
