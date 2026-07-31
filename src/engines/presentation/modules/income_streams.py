from collections.abc import Mapping
from typing import cast

import polars as pl


class IncomeStreamsBuilder:
    """
    Constructs the Income Streams presentation model.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, pl.LazyFrame]
    ):
        self.dfs = dfs
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_inc_agg = self.base_lf["lf_inc_agg"]
        lf_months = self.base_lf["lf_months"]

        d_inc_subcat = self.dfs.get("df_d_income_subcategory")
        d_inc_cat = self.dfs.get("df_d_income_category")

        lf_inc_monthly = (
            lf_inc_agg
            .with_columns(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("DATE").dt.month_end().alias("MONTH_END_DATE")
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                [
                    pl.col("INCOME").sum().fill_null(0.0).alias("Total_Monthly_Income"),
                    pl.col("INCOME").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                ]
            )
        )

        lf_grid = lf_months.join(
            lf_inc_agg.select("CATEGORY_ID").unique(), how="cross"
        )
        
        lf_inc_monthly = (
            lf_grid.join(lf_inc_monthly, on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"], how="left")
            .with_columns(
                pl.col("Total_Monthly_Income").fill_null(0.0),
                pl.col("Average_Transaction_Value").fill_null(0.0),
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH")
            )
        )

        if d_inc_subcat is not None and d_inc_cat is not None:
            lf_inc_subcat = cast(
                pl.LazyFrame,
                d_inc_subcat.lazy() if isinstance(d_inc_subcat, pl.DataFrame) else d_inc_subcat,
            )
            lf_inc_cat = cast(
                pl.LazyFrame, d_inc_cat.lazy() if isinstance(d_inc_cat, pl.DataFrame) else d_inc_cat
            )

            lf_inc_monthly = (
                lf_inc_monthly.join(
                    lf_inc_subcat.select(["UID", "CATEGORY_NAME", "CATEGORY_ID"]).rename(
                        {"CATEGORY_ID": "PARENT_ID", "UID": "CATEGORY_ID"}
                    ),
                    on="CATEGORY_ID",
                    how="left",
                )
                .join(
                    lf_inc_cat.select(
                        [
                            pl.col("UID").alias("PARENT_ID"),
                            pl.col("CATEGORY_NAME").alias("CATEGORY_GROUPS"),
                        ]
                    ),
                    on="PARENT_ID",
                    how="left",
                )
                .drop("PARENT_ID")
            )
        else:
            lf_inc_monthly = lf_inc_monthly.with_columns(
                pl.lit(None).alias("CATEGORY_NAME"), pl.lit(None).alias("CATEGORY_GROUPS")
            )

        lf_income_streams = (
            lf_inc_monthly.sort(["CATEGORY_ID", "MONTH_START_DATE"])
            .with_columns(
                pl.col("Total_Monthly_Income")
                .rolling_mean(window_size=3)
                .over("CATEGORY_ID")
                .alias("Trailing_3M_Avg_Income"),
                pl.col("Total_Monthly_Income")
                .rolling_mean(window_size=6)
                .over("CATEGORY_ID")
                .alias("Trailing_6M_Avg_Income"),
                pl.col("Total_Monthly_Income")
                .shift(1)
                .over("CATEGORY_ID")
                .alias("Prev_Month_Income"),
                pl.col("Total_Monthly_Income")
                .shift(12)
                .over("CATEGORY_ID")
                .alias("Prev_Year_Income"),
                pl.col("Total_Monthly_Income")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Total_Month_All_Categories_Income"),
            )
            .with_columns(
                pl.when(pl.col("Prev_Month_Income") > 0)
                .then(
                    (pl.col("Total_Monthly_Income") - pl.col("Prev_Month_Income"))
                    / pl.col("Prev_Month_Income")
                )
                .otherwise(0.0)
                .alias("MoM_Variance_Pct"),
                pl.when(pl.col("Prev_Year_Income") > 0)
                .then(
                    (pl.col("Total_Monthly_Income") - pl.col("Prev_Year_Income"))
                    / pl.col("Prev_Year_Income")
                )
                .otherwise(0.0)
                .alias("YoY_Variance_Pct"),
                pl.when(pl.col("Total_Month_All_Categories_Income") > 0)
                .then(pl.col("Total_Monthly_Income") / pl.col("Total_Month_All_Categories_Income"))
                .otherwise(0.0)
                .alias("Income_Share_Pct"),
                pl.col("CATEGORY_GROUPS")
                .str.to_lowercase()
                .str.contains("(?i)invest|interest|dividend|capital|passive")
                .fill_null(False)
                .alias("Is_Passive_Income"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "CATEGORY_ID",
                    "CATEGORY_NAME",
                    "CATEGORY_GROUPS",
                    "Total_Monthly_Income",
                    "Average_Transaction_Value",
                    "Trailing_3M_Avg_Income",
                    "Trailing_6M_Avg_Income",
                    "Income_Share_Pct",
                    "MoM_Variance_Pct",
                    "YoY_Variance_Pct",
                    "Is_Passive_Income",
                ]
            )
        )
        return lf_income_streams
