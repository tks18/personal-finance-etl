from collections.abc import Mapping
from typing import Any

import polars as pl


class PortfolioRebalancingBuilder:
    """
    Constructs AE8: Actionable Portfolio Rebalancing Robo-Advisor (Granular).
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

        if f_market_data is None or d_inv_master is None:
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

        latest_month_dates = lf_market_data.group_by("MONTH_START_DATE").agg(
            pl.col("Closing_Date").max().alias("Max_Closing_Date")
        )

        df_monthly_base = (
            lf_market_data.join(latest_month_dates, on="MONTH_START_DATE")
            .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
            .join(
                lf_inv_master.select(
                    ["ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_TYPE", "INSTRUMENT_SUBTYPE", "SECTOR"]
                ),
                on="ISIN",
                how="left",
            )
        ).with_columns(
            pl.col("INSTRUMENT_TYPE").fill_null("Unknown"),
            pl.col("INSTRUMENT_SUBTYPE").fill_null("Unknown"),
            pl.col("SECTOR").fill_null("Unknown"),
        )

        # Aggregate at Sector level
        df_sector_agg = df_monthly_base.group_by(
            [
                "MONTH_START_DATE",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE",
                "INSTRUMENT_SUBTYPE",
                "SECTOR",
            ]
        ).agg(
            pl.col("Close_Value").sum().fill_null(0.0).alias("Sector_Value"),
            pl.when(pl.col("P/L") < 0)
            .then(pl.col("P/L"))
            .otherwise(0.0)
            .sum()
            .alias("Sector_Unrealized_Loss"),
        )

        # Calculate macro Class values
        df_portfolio = df_sector_agg.with_columns(
            pl.col("Sector_Value")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_Total_Value"),
            pl.col("Sector_Value").sum().over("MONTH_START_DATE").alias("Total_Portfolio_Value"),
        ).with_columns(
            pl.when(pl.col("Total_Portfolio_Value") > 0)
            .then(pl.col("Class_Total_Value") / pl.col("Total_Portfolio_Value"))
            .otherwise(0.0)
            .alias("Class_Actual_Weight")
        )

        # Merge with macro target allocations
        if self.rules and getattr(self.rules.assumptions, "target_allocations", None):
            alloc_data = [
                {"INSTRUMENT_CLASS": str(k), "Class_Target_Weight": float(v)}
                for k, v in self.rules.assumptions.target_allocations.items()
            ]
            lf_target_allocs = pl.LazyFrame(alloc_data)

            df_rebalance = df_portfolio.join(
                lf_target_allocs, on="INSTRUMENT_CLASS", how="left"
            ).with_columns(pl.col("Class_Target_Weight").fill_null(0.0))
        else:
            df_rebalance = df_portfolio.with_columns(pl.lit(0.0).alias("Class_Target_Weight"))

        return (
            df_rebalance.with_columns(
                (pl.col("Class_Actual_Weight") - pl.col("Class_Target_Weight")).alias(
                    "Class_Deviation"
                ),
                (pl.col("Class_Target_Weight") * pl.col("Total_Portfolio_Value")).alias(
                    "Target_Fiat_Value"
                ),
            )
            .with_columns(
                (pl.col("Class_Total_Value") - pl.col("Target_Fiat_Value")).alias("Fiat_Deviation")
            )
            .with_columns(
                pl.when(pl.col("Class_Deviation").abs() > 0.05)  # 5% rebalance threshold
                .then(True)
                .otherwise(False)
                .alias("Is_Rebalance_Required"),
                pl.when(pl.col("Fiat_Deviation") > 0)
                .then(pl.lit("SELL"))
                .when(pl.col("Fiat_Deviation") < 0)
                .then(pl.lit("BUY"))
                .otherwise(pl.lit("HOLD"))
                .alias("Class_Rebalance_Action"),
                pl.col("Fiat_Deviation").abs().alias("Class_Order_Value"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "INSTRUMENT_CLASS",
                    "INSTRUMENT_TYPE",
                    "INSTRUMENT_SUBTYPE",
                    "SECTOR",
                    "Class_Target_Weight",
                    "Class_Actual_Weight",
                    "Class_Deviation",
                    "Class_Rebalance_Action",
                    "Class_Order_Value",
                    "Sector_Value",
                    "Sector_Unrealized_Loss",
                    "Is_Rebalance_Required",
                ]
            )
        )
