from collections.abc import Mapping
from typing import Any

import polars as pl


class SectorAllocationBuilder:
    """
    Constructs AE3: Sector Rotation Analytics (Using Granular Hierarchy).
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules=None
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

        df_monthly_sector = df_monthly_base.group_by(
            [
                "MONTH_START_DATE",
                "Max_Closing_Date",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE",
                "INSTRUMENT_SUBTYPE",
                "SECTOR",
            ]
        ).agg(pl.col("Close_Value").sum().fill_null(0.0).alias("Sector_Total_Value"))

        df_concentration = (
            df_monthly_sector.sort("MONTH_START_DATE")
            .with_columns(
                pl.col("Sector_Total_Value")
                .sum()
                .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
                .alias("Class_Total_Value"),
                pl.col("Sector_Total_Value")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Total_Portfolio_Value"),
            )
            .with_columns(
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then(pl.col("Class_Total_Value") / pl.col("Total_Portfolio_Value"))
                .otherwise(0.0)
                .alias("Class_Weight"),
                pl.when(pl.col("Class_Total_Value") > 0)
                .then(pl.col("Sector_Total_Value") / pl.col("Class_Total_Value"))
                .otherwise(0.0)
                .alias("Weight_In_Class"),
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then(pl.col("Sector_Total_Value") / pl.col("Total_Portfolio_Value"))
                .otherwise(0.0)
                .alias("Portfolio_Weight"),
            )
            .with_columns(
                pl.col("Portfolio_Weight").pow(2).alias("Squared_Portfolio_Weight"),
                (
                    pl.col("Portfolio_Weight")
                    - pl.col("Portfolio_Weight")
                    .shift(1)
                    .over(["INSTRUMENT_CLASS", "INSTRUMENT_TYPE", "INSTRUMENT_SUBTYPE", "SECTOR"])
                ).alias("Weight_Change_MoM"),
            )
            .with_columns(
                pl.col("Squared_Portfolio_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Sector_HHI_Concentration_Index")
            )
            .with_columns(
                (1.0 / pl.col("Sector_HHI_Concentration_Index")).alias("Effective_Diversification")
            )
        )

        if self.rules and getattr(self.rules.assumptions, "target_allocations", None):
            alloc_data = [
                {"INSTRUMENT_CLASS": str(k), "Class_Target_Weight": float(v)}
                for k, v in self.rules.assumptions.target_allocations.items()
            ]
            lf_target_allocs = pl.LazyFrame(alloc_data)
            df_concentration = df_concentration.join(
                lf_target_allocs, on="INSTRUMENT_CLASS", how="left"
            ).with_columns(pl.col("Class_Target_Weight").fill_null(0.0))
            df_concentration = df_concentration.with_columns(
                (pl.col("Class_Weight") > pl.col("Class_Target_Weight")).alias("Is_Overweight"),
                (pl.col("Class_Weight") - pl.col("Class_Target_Weight")).alias(
                    "Benchmark_Deviation"
                ),
            )
        else:
            df_concentration = df_concentration.with_columns(
                pl.lit(0.0).alias("Class_Target_Weight"),
                pl.lit(False).alias("Is_Overweight"),
                pl.lit(0.0).alias("Benchmark_Deviation"),
            )

        class_hhi_lf = (
            df_concentration.select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_Weight"])
            .unique()
            .with_columns(pl.col("Class_Weight").pow(2).alias("Squared_Class_Weight"))
            .with_columns(
                pl.col("Squared_Class_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Class_HHI_Concentration_Index")
            )
            .select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_HHI_Concentration_Index"])
            .unique()
        )

        class_risk_lf = (
            df_concentration.select(
                [
                    "MONTH_START_DATE",
                    "INSTRUMENT_CLASS",
                    "Class_Weight",
                    "Total_Portfolio_Value",
                    "Class_Total_Value",
                ]
            )
            .unique()
            .sort(["INSTRUMENT_CLASS", "MONTH_START_DATE"])
            .with_columns(
                (
                    pl.col("Class_Total_Value")
                    / pl.col("Class_Total_Value").shift(1).over("INSTRUMENT_CLASS")
                    - 1.0
                ).alias("Class_Monthly_Return"),
                (
                    pl.col("Total_Portfolio_Value")
                    / pl.col("Total_Portfolio_Value").shift(1).over("INSTRUMENT_CLASS")
                    - 1.0
                ).alias("Portfolio_Monthly_Return"),
            )
            .with_columns(
                pl.col("Class_Monthly_Return").fill_null(0.0),
                pl.col("Portfolio_Monthly_Return").fill_null(0.0),
            )
            .with_columns(
                (pl.col("Class_Monthly_Return") * pl.col("Portfolio_Monthly_Return")).alias("Ri_Rp")
            )
            .with_columns(
                pl.col("Class_Monthly_Return")
                .rolling_mean(12)
                .over("INSTRUMENT_CLASS")
                .alias("E_Ri"),
                pl.col("Portfolio_Monthly_Return")
                .rolling_mean(12)
                .over("INSTRUMENT_CLASS")
                .alias("E_Rp"),
                pl.col("Ri_Rp").rolling_mean(12).over("INSTRUMENT_CLASS").alias("E_RiRp"),
                pl.col("Portfolio_Monthly_Return")
                .rolling_var(12)
                .over("INSTRUMENT_CLASS")
                .alias("Var_Rp"),
            )
            .with_columns(
                ((pl.col("E_RiRp") - (pl.col("E_Ri") * pl.col("E_Rp"))) * 12.0 / 11.0).alias(
                    "Cov_Ri_Rp"
                )
            )
            .with_columns(
                pl.when(pl.col("Var_Rp") > 0)
                .then(pl.col("Class_Weight") * pl.col("Cov_Ri_Rp") / pl.col("Var_Rp"))
                .otherwise(0.0)
                .alias("Marginal_Risk_Contribution")
            )
            .select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Marginal_Risk_Contribution"])
            .unique()
        )

        df_concentration = (
            df_concentration.join(
                class_hhi_lf, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left"
            )
            .join(class_risk_lf, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left")
            .with_columns(pl.col("Marginal_Risk_Contribution").fill_null(0.0))
        )

        f_class_data = self.dfs.get("df_f_tf_investment_analytics_class")
        if f_class_data is not None:
            lf_class = (
                f_class_data.lazy() if isinstance(f_class_data, pl.DataFrame) else f_class_data
            )
            lf_class = lf_class.with_columns(
                pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
            )
            lf_class_agg = lf_class.group_by(["MONTH_START_DATE", "INSTRUMENT_CLASS"]).agg(
                pl.col("XIRR").last().alias("Class_CAGR")
            )
            df_concentration = df_concentration.join(
                lf_class_agg, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left"
            )
        else:
            df_concentration = df_concentration.with_columns(pl.lit(0.0).alias("Class_CAGR"))

        return df_concentration.select(
            [
                "MONTH_START_DATE",
                pl.col("Max_Closing_Date").alias("As_Of_Date"),
                "INSTRUMENT_CLASS",
                "INSTRUMENT_TYPE",
                "INSTRUMENT_SUBTYPE",
                "SECTOR",
                "Total_Portfolio_Value",
                "Class_Total_Value",
                "Sector_Total_Value",
                "Class_Target_Weight",
                "Class_Weight",
                "Weight_In_Class",
                "Portfolio_Weight",
                "Weight_Change_MoM",
                "Class_HHI_Concentration_Index",
                "Sector_HHI_Concentration_Index",
                "Effective_Diversification",
                "Marginal_Risk_Contribution",
                "Class_CAGR",
                "Benchmark_Deviation",
                "Is_Overweight",
            ]
        ).sort(
            ["MONTH_START_DATE", "INSTRUMENT_CLASS", "Portfolio_Weight"],
            descending=[False, False, True],
        )
