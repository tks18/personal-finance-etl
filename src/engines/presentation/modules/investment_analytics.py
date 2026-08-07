from collections.abc import Mapping
from typing import Any

import polars as pl


class InvestmentAnalyticsBuilder:
    """
    Constructs p_tf_Investment_Analytics.
    Unifies Rebalancing (drift), Sector Allocation (weights), Performance Attribution (returns),
    and Tax Harvesting (unrealized losses) into a single cohesive ISIN-level table.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        f_market_data = self.dfs.get("df_f_tf_investment_analytics_lot")
        d_inv_master = self.dfs.get("df_d_tf_investment_master")
        df_inv_port = self.dfs.get("df_f_tf_investment_analytics_portfolio")

        if f_market_data is None or d_inv_master is None or df_inv_port is None:
            return pl.LazyFrame()

        lf_market_data = (
            f_market_data.lazy() if isinstance(f_market_data, pl.DataFrame) else f_market_data
        )
        lf_inv_master = (
            d_inv_master.lazy() if isinstance(d_inv_master, pl.DataFrame) else d_inv_master
        )

        lf_market_data = lf_market_data.with_columns(
            pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
        )

        df_monthly_base = (
            lf_market_data.filter(
                pl.col("Closing_Date") == pl.col("Closing_Date").max().over("MONTH_START_DATE")
            )
            .with_columns(pl.col("Closing_Date").alias("Max_Closing_Date"))
            .join(
                lf_inv_master.select(
                    [
                        "ISIN",
                        "INSTRUMENT_NAME",
                        "INSTRUMENT_CLASS",
                        "INSTRUMENT_TYPE",
                        "INSTRUMENT_SUBTYPE",
                        "SECTOR",
                    ]
                ),
                on="ISIN",
                how="left",
            )
        ).with_columns(
            pl.col("INSTRUMENT_CLASS").fill_null("Unknown"),
            pl.col("INSTRUMENT_TYPE").fill_null("Unknown"),
            pl.col("INSTRUMENT_SUBTYPE").fill_null("Unknown"),
            pl.col("SECTOR").fill_null("Unknown"),
        )

        # 1. Base ISIN Aggregation
        lf_isin_agg = df_monthly_base.group_by(
            [
                "MONTH_START_DATE",
                "Max_Closing_Date",
                "ISIN",
                "INSTRUMENT_NAME",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE",
                "INSTRUMENT_SUBTYPE",
                "SECTOR",
            ]
        ).agg(
            pl.col("Close_Value").sum().fill_null(0.0).alias("ISIN_Market_Value"),
            pl.col("Buy_Value").sum().fill_null(0.0).alias("ISIN_Book_Value"),
            pl.col("P/L").sum().fill_null(0.0).alias("ISIN_Unrealized_PnL"),
            pl.when(pl.col("P/L") < 0)
            .then(pl.col("P/L"))
            .otherwise(0.0)
            .sum()
            .alias("ISIN_Harvestable_Loss"),
        )

        # 2. Portfolio Weights & Allocation
        lf_isin_agg = lf_isin_agg.with_columns(
            pl.col("ISIN_Market_Value")
            .sum()
            .over("MONTH_START_DATE")
            .alias("Total_Portfolio_Value"),
            pl.col("ISIN_Market_Value")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_Market_Value"),
            pl.col("ISIN_Market_Value")
            .sum()
            .over(["MONTH_START_DATE", "SECTOR"])
            .alias("Sector_Market_Value"),
        ).with_columns(
            pl.when(pl.col("Total_Portfolio_Value") > 0)
            .then(pl.col("ISIN_Market_Value") / pl.col("Total_Portfolio_Value"))
            .otherwise(0.0)
            .alias("ISIN_Weight"),
            pl.when(pl.col("Total_Portfolio_Value") > 0)
            .then(pl.col("Class_Market_Value") / pl.col("Total_Portfolio_Value"))
            .otherwise(0.0)
            .alias("Class_Weight"),
            pl.when(pl.col("Total_Portfolio_Value") > 0)
            .then(pl.col("Sector_Market_Value") / pl.col("Total_Portfolio_Value"))
            .otherwise(0.0)
            .alias("Sector_Weight"),
        )

        # 3. Target Allocations & Drift
        if self.rules and getattr(self.rules.assumptions, "target_allocations", None):
            alloc_data = [
                {"INSTRUMENT_CLASS": str(k), "Class_Target_Weight": float(v)}
                for k, v in self.rules.assumptions.target_allocations.items()
            ]
            lf_target_allocs = pl.LazyFrame(alloc_data)
            lf_isin_agg = lf_isin_agg.join(
                lf_target_allocs, on="INSTRUMENT_CLASS", how="left"
            ).with_columns(pl.col("Class_Target_Weight").fill_null(0.0))
        else:
            lf_isin_agg = lf_isin_agg.with_columns(pl.lit(0.0).alias("Class_Target_Weight"))

        lf_isin_agg = lf_isin_agg.with_columns(
            (pl.col("Class_Weight") - pl.col("Class_Target_Weight")).alias("Class_Drift"),
            (pl.col("Class_Target_Weight") * pl.col("Total_Portfolio_Value")).alias(
                "Class_Target_Value"
            ),
        ).with_columns(
            pl.when(pl.col("Class_Drift").abs() > 0.05)
            .then(True)
            .otherwise(False)
            .alias("Rebalance_Required")
        )

        # 4. Returns & Performance Attribution (MoM Change)
        lf_isin_agg = lf_isin_agg.sort(["ISIN", "MONTH_START_DATE"]).with_columns(
            pl.when(pl.col("ISIN_Market_Value").shift(1).over("ISIN") > 0)
            .then(
                (pl.col("ISIN_Market_Value") - pl.col("ISIN_Market_Value").shift(1).over("ISIN"))
                / pl.col("ISIN_Market_Value").shift(1).over("ISIN")
            )
            .otherwise(0.0)
            .alias("ISIN_Monthly_Return")
        )

        # 5. Tax Harvesting Priority
        lf_isin_agg = lf_isin_agg.with_columns(
            pl.when(pl.col("ISIN_Harvestable_Loss") < 0)
            .then(
                (pl.col("ISIN_Harvestable_Loss").abs() / pl.col("ISIN_Book_Value")) * 0.5
                + (pl.col("ISIN_Harvestable_Loss").abs() / pl.col("Total_Portfolio_Value")) * 0.5
            )
            .otherwise(0.0)
            .alias("Tax_Harvesting_Priority_Score")
        )

        return lf_isin_agg.select(
            [
                "MONTH_START_DATE",
                "Max_Closing_Date",
                "ISIN",
                "INSTRUMENT_NAME",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE",
                "SECTOR",
                "ISIN_Market_Value",
                "ISIN_Book_Value",
                "ISIN_Unrealized_PnL",
                "ISIN_Harvestable_Loss",
                "ISIN_Weight",
                "Class_Weight",
                "Class_Target_Weight",
                "Class_Drift",
                "Rebalance_Required",
                "Sector_Weight",
                "ISIN_Monthly_Return",
                "Tax_Harvesting_Priority_Score",
            ]
        )
