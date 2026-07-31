from collections.abc import Mapping
from typing import cast

import polars as pl


class SpendAnalyticsBuilder:
    """
    Constructs the Category Spend Analytics presentation model.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, pl.LazyFrame]
    ):
        self.dfs = dfs
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_exp_agg = self.base_lf["lf_exp_agg"]

        d_subcat = self.dfs.get("df_d_expense_subcategory")
        d_exp_cat = self.dfs.get("df_d_expense_category")

        lf_cat_agg = (
            lf_exp_agg
            .with_columns(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("DATE").dt.month_end().alias("MONTH_END_DATE")
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                [
                    pl.col("EXPENSE").sum().fill_null(0.0).alias("Total_Monthly_Spend"),
                    pl.col("EXPENSE").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                ]
            )
        )

        lf_months = self.base_lf["lf_months"]
        lf_grid = lf_months.join(
            lf_exp_agg.select("CATEGORY_ID").unique(), how="cross"
        )
        
        lf_cat_agg = (
            lf_grid.join(lf_cat_agg, on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"], how="left")
            .with_columns(
                pl.col("Total_Monthly_Spend").fill_null(0.0),
                pl.col("Average_Transaction_Value").fill_null(0.0),
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH")
            )
        )

        if d_subcat is not None and d_exp_cat is not None:
            lf_subcat = cast(
                pl.LazyFrame, d_subcat.lazy() if isinstance(d_subcat, pl.DataFrame) else d_subcat
            )
            lf_exp_cat = cast(
                pl.LazyFrame, d_exp_cat.lazy() if isinstance(d_exp_cat, pl.DataFrame) else d_exp_cat
            )

            lf_cat_agg = (
                lf_cat_agg.join(
                    lf_subcat.select(["UID", "CATEGORY_NAME", "CATEGORY_ID"]).rename(
                        {"CATEGORY_ID": "PARENT_ID", "UID": "CATEGORY_ID"}
                    ),
                    on="CATEGORY_ID",
                    how="left",
                )
                .join(
                    lf_exp_cat.select(
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
            lf_cat_agg = lf_cat_agg.with_columns(
                pl.lit(None).alias("CATEGORY_NAME"), pl.lit(None).alias("CATEGORY_GROUPS")
            )

        lf_spend_analytics = (
            lf_cat_agg.sort(["CATEGORY_ID", "MONTH_START_DATE"])
            .with_columns(
                pl.col("Total_Monthly_Spend")
                .rolling_mean(window_size=3)
                .over("CATEGORY_ID")
                .alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Monthly_Spend")
                .rolling_mean(window_size=6)
                .over("CATEGORY_ID")
                .alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Monthly_Spend")
                .shift(1)
                .over("CATEGORY_ID")
                .alias("Prev_Month_Spend"),
                pl.col("Total_Monthly_Spend")
                .shift(12)
                .over("CATEGORY_ID")
                .alias("Prev_Year_Spend"),
                pl.col("Total_Monthly_Spend").mean().over("CATEGORY_ID").alias("Cat_Mean"),
                pl.col("Total_Monthly_Spend").std().over("CATEGORY_ID").alias("Cat_Std"),
                pl.col("Total_Monthly_Spend")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Total_Month_All_Categories_Spend"),
            )
            .with_columns(
                pl.when(pl.col("Prev_Month_Spend") > 0)
                .then(
                    (pl.col("Total_Monthly_Spend") - pl.col("Prev_Month_Spend"))
                    / pl.col("Prev_Month_Spend")
                )
                .otherwise(0.0)
                .alias("MoM_Variance_Pct"),
                pl.when(pl.col("Prev_Year_Spend") > 0)
                .then(
                    (pl.col("Total_Monthly_Spend") - pl.col("Prev_Year_Spend"))
                    / pl.col("Prev_Year_Spend")
                )
                .otherwise(0.0)
                .alias("YoY_Variance_Pct"),
                pl.when(pl.col("Cat_Std").is_not_null() & (pl.col("Cat_Std") > 0))
                .then((pl.col("Total_Monthly_Spend") - pl.col("Cat_Mean")) / pl.col("Cat_Std"))
                .otherwise(0.0)
                .alias("Spend_Intensity_Z_Score"),
                (pl.col("Total_Monthly_Spend") > (pl.col("Trailing_3M_Avg_Spend") * 1.15)).alias(
                    "Is_Category_Creep"
                ),
                pl.when(pl.col("Total_Month_All_Categories_Spend") > 0)
                .then(pl.col("Total_Monthly_Spend") / pl.col("Total_Month_All_Categories_Spend"))
                .otherwise(0.0)
                .alias("Spend_Share_Pct"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "CATEGORY_ID",
                    "CATEGORY_NAME",
                    "CATEGORY_GROUPS",
                    "Total_Monthly_Spend",
                    "Average_Transaction_Value",
                    "Trailing_3M_Avg_Spend",
                    "Trailing_6M_Avg_Spend",
                    "Spend_Share_Pct",
                    "MoM_Variance_Pct",
                    "YoY_Variance_Pct",
                    "Spend_Intensity_Z_Score",
                    "Is_Category_Creep",
                ]
            )
        )
        return lf_spend_analytics
