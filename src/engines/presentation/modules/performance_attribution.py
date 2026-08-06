from collections.abc import Mapping
from typing import Any

import polars as pl


class PerformanceAttributionBuilder:
    """
    Constructs AE10: Multi-Level Brinson-Fachler Institutional Performance Attribution.
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

        # Sector level returns
        df_sector_agg = (
            df_monthly_base.group_by(
                [
                    "MONTH_START_DATE",
                    "INSTRUMENT_CLASS",
                    "INSTRUMENT_TYPE",
                    "INSTRUMENT_SUBTYPE",
                    "SECTOR",
                ]
            )
            .agg(
                pl.col("Close_Value").sum().alias("Sector_Total_Value"),
                pl.col("Buy_Value").sum().alias("Sector_Buy_Value"),
                (pl.col("Buy_Value") * pl.col("Dietz_Day_Weight").fill_null(1.0))
                .sum()
                .alias("Sector_Dietz_Buy_Value"),
                (pl.col("Buy_Value") * pl.col("Lot_BM_Returns_%")).sum().alias("Sector_BM_Gain"),
            )
            .with_columns(
                pl.when(pl.col("Sector_Dietz_Buy_Value") > 0)
                .then(
                    (pl.col("Sector_Total_Value") - pl.col("Sector_Buy_Value"))
                    / pl.col("Sector_Dietz_Buy_Value")
                )
                .otherwise(0.0)
                .alias("Sector_Return")
            )
        )

        # Class level baseline
        df_portfolio = df_sector_agg.with_columns(
            pl.col("Sector_Total_Value")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_Total_Value"),
            pl.col("Sector_Buy_Value")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_Buy_Value"),
            pl.col("Sector_Dietz_Buy_Value")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_Dietz_Buy_Value"),
            pl.col("Sector_BM_Gain")
            .sum()
            .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
            .alias("Class_BM_Gain"),
            pl.col("Sector_Total_Value")
            .sum()
            .over("MONTH_START_DATE")
            .alias("Total_Portfolio_Value"),
        ).with_columns(
            pl.when(pl.col("Class_Dietz_Buy_Value") > 0)
            .then(pl.col("Class_BM_Gain") / pl.col("Class_Dietz_Buy_Value"))
            .otherwise(0.0)
            .alias("Class_Benchmark_Return"),
            pl.when(pl.col("Total_Portfolio_Value") > 0)
            .then(pl.col("Class_Total_Value") / pl.col("Total_Portfolio_Value"))
            .otherwise(0.0)
            .alias("Class_Actual_Weight"),
        )

        # Merge Targets
        if self.rules and getattr(self.rules.assumptions, "target_allocations", None):
            alloc_data = [
                {"INSTRUMENT_CLASS": str(k), "Class_Target_Weight": float(v)}
                for k, v in self.rules.assumptions.target_allocations.items()
            ]
            lf_target_allocs = pl.LazyFrame(alloc_data)
            df_attr = df_portfolio.join(
                lf_target_allocs, on="INSTRUMENT_CLASS", how="left"
            ).with_columns(pl.col("Class_Target_Weight").fill_null(0.0))
        else:
            df_attr = df_portfolio.with_columns(pl.lit(0.0).alias("Class_Target_Weight"))

        # Total Benchmark Return
        df_attr = df_attr.with_columns(
            (pl.col("Class_Target_Weight") * pl.col("Class_Benchmark_Return"))
            .sum()
            .over("MONTH_START_DATE")
            .alias("Total_Benchmark_Return")
        )

        # Brinson-Fachler Formulas
        return (
            df_attr.with_columns(
                (
                    (pl.col("Class_Actual_Weight") - pl.col("Class_Target_Weight"))
                    * (pl.col("Class_Benchmark_Return") - pl.col("Total_Benchmark_Return"))
                ).alias("Allocation_Effect"),
                (
                    pl.col("Class_Target_Weight")
                    * (pl.col("Sector_Return") - pl.col("Class_Benchmark_Return"))
                ).alias("Selection_Effect"),
                (
                    (pl.col("Class_Actual_Weight") - pl.col("Class_Target_Weight"))
                    * (pl.col("Sector_Return") - pl.col("Class_Benchmark_Return"))
                ).alias("Interaction_Effect"),
            )
            .with_columns(
                (
                    pl.col("Allocation_Effect")
                    + pl.col("Selection_Effect")
                    + pl.col("Interaction_Effect")
                ).alias("Total_Active_Return")
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
                    "Sector_Return",
                    "Class_Benchmark_Return",
                    "Allocation_Effect",
                    "Selection_Effect",
                    "Interaction_Effect",
                    "Total_Active_Return",
                ]
            )
        )
