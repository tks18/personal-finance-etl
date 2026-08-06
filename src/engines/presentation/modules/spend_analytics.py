from collections.abc import Mapping
from typing import Any, cast

import polars as pl


class SpendAnalyticsBuilder:
    """
    Constructs the Category Spend Analytics presentation model.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_exp_agg = self.base_lf["lf_exp_agg"]

        d_subcat = self.dfs.get("df_d_expense_subcategory")
        d_exp_cat = self.dfs.get("df_d_expense_category")

        lf_cat_agg = (
            lf_exp_agg.with_columns(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("DATE").dt.month_end().alias("MONTH_END_DATE"),
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                [
                    pl.col("EXPENSE").sum().fill_null(0.0).alias("Total_Monthly_Spend"),
                    pl.col("EXPENSE").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                    pl.len().alias("Transaction_Count"),
                    pl.col("Is_Core_Expense").first().alias("Is_Core_Expense"),
                ]
            )
        )

        lf_months = self.base_lf["lf_months"]
        lf_grid = lf_months.join(lf_exp_agg.select("CATEGORY_ID").unique(), how="cross")

        lf_cat_agg = lf_grid.join(
            lf_cat_agg, on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"], how="left"
        ).sort(["CATEGORY_ID", "MONTH_START_DATE"]).with_columns(
            pl.col("Total_Monthly_Spend").fill_null(0.0),
            pl.col("Average_Transaction_Value").fill_null(0.0),
            pl.col("Transaction_Count").fill_null(0).cast(pl.Int64),
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
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
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Monthly_Spend")
                .rolling_mean(window_size=6)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Monthly_Spend")
                .shift(1)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Prev_Month_Spend"),
                pl.col("Total_Monthly_Spend")
                .shift(12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Prev_Year_Spend"),
                pl.col("Total_Monthly_Spend")
                .rolling_mean(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_12M_Avg_Spend"),
                pl.col("Total_Monthly_Spend")
                .rolling_sum(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_12M_Total_Spend"),
                pl.col("Total_Monthly_Spend")
                .cum_sum()
                .over(
                    ["CATEGORY_ID", pl.col("MONTH_START_DATE").dt.year()],
                    order_by="MONTH_START_DATE",
                )
                .alias("Cumulative_YTD_Spend"),
                pl.col("Transaction_Count")
                .rolling_mean(window_size=3)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_3M_Avg_Frequency"),
                pl.col("Total_Monthly_Spend")
                .rolling_mean(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Cat_Mean"),
                pl.col("Total_Monthly_Spend")
                .rolling_std(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Cat_Std"),
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
                pl.when(
                    pl.col("CATEGORY_GROUPS").str.to_lowercase().str.contains("(?i)invest|saving")
                )
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .alias("Is_Investment"),
                pl.when(
                    pl.col("CATEGORY_GROUPS")
                    .str.to_lowercase()
                    .str.contains("(?i)fixed|utilities|rent|insurance|tax|emi|loan")
                )
                .then(pl.lit("Fixed"))
                .otherwise(pl.lit("Variable"))
                .alias("Spend_Type"),
                pl.when(pl.col("Prev_Year_Spend") > 0)
                .then(
                    (pl.col("Total_Monthly_Spend") - pl.col("Prev_Year_Spend"))
                    / pl.col("Prev_Year_Spend")
                )
                .otherwise(0.0)
                .alias("YoY_Variance_Pct"),
                pl.when(pl.col("Cat_Std").is_not_null() & (pl.col("Cat_Std") > 0))
                .then(
                    pl.when((pl.col("Cat_Mean") / pl.col("Cat_Std")) > 10.0)
                    .then(10.0)
                    .otherwise(pl.col("Cat_Mean") / pl.col("Cat_Std"))
                )
                .when((pl.col("Cat_Std") == 0) & (pl.col("Cat_Mean") == 0))
                .then(pl.lit(None))
                .otherwise(10.0)
                .alias("Spend_Consistency_Score"),
                (
                    (
                        (pl.col("Total_Monthly_Spend") > (pl.col("Trailing_3M_Avg_Spend") * 1.15))
                        & (
                            pl.col("Transaction_Count")
                            > (pl.col("Trailing_3M_Avg_Frequency") * 1.1)
                        )
                    )
                    | (pl.col("Total_Monthly_Spend") > (pl.col("Trailing_3M_Avg_Spend") * 1.5))
                ).alias("Is_Category_Creep"),
                pl.col("Total_Monthly_Spend")
                .rank("dense", descending=True)
                .over("MONTH_START_DATE")
                .alias("Rank_by_Spend"),
                pl.when(pl.col("Total_Month_All_Categories_Spend") > 0)
                .then(pl.col("Total_Monthly_Spend") / pl.col("Total_Month_All_Categories_Spend"))
                .otherwise(0.0)
                .alias("Spend_Share_Pct"),
                pl.when(pl.col("Transaction_Count") > 0)
                .then(30.4375 / pl.col("Transaction_Count"))
                .otherwise(None)
                .alias("Avg_Days_Between_Transactions"),
            )
            .with_columns(
                pl.when((pl.col("Spend_Type") == "Fixed") & (pl.col("Prev_Year_Spend") > 0))
                .then(
                    (pl.col("Total_Monthly_Spend") - pl.col("Prev_Year_Spend"))
                    / pl.col("Prev_Year_Spend")
                )
                .when(pl.col("Trailing_6M_Avg_Spend") > 0)
                .then(
                    (pl.col("Total_Monthly_Spend") - pl.col("Trailing_6M_Avg_Spend"))
                    / pl.col("Trailing_6M_Avg_Spend")
                )
                .otherwise(0.0)
                .alias("Budget_Variance_Pct"),
                ((pl.col("Spend_Type") == "Variable") & ~(pl.col("Is_Investment"))).alias(
                    "Is_Discretionary"
                ),
            )
        )

        f_inflation = self.dfs.get("df_f_inflation_rates")
        if f_inflation is not None:
            cpi_latest = self.base_lf.get("cpi_latest", 100.0)
            lf_inflation = (
                f_inflation.lazy() if isinstance(f_inflation, pl.DataFrame) else f_inflation
            ).select(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("INFLATION_YOY_PCT"),
                pl.col("CPI_INDEX"),
            )
            lf_spend_analytics = (
                lf_spend_analytics.join(lf_inflation, on="MONTH_START_DATE", how="left")
                .with_columns(
                    (
                        pl.col("Total_Monthly_Spend") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))
                    ).alias("Real_Monthly_Spend"),
                    pl.when(pl.col("Prev_Year_Spend") > 0)
                    .then(
                        ((1 + pl.col("YoY_Variance_Pct")) / (1 + pl.col("INFLATION_YOY_PCT"))) - 1
                    )
                    .otherwise(0.0)
                    .alias("YoY_Real_Variance_Pct"),
                    (pl.col("Real_Monthly_Spend") - pl.col("Total_Monthly_Spend")).alias(
                        "Category_Inflation_Contribution"
                    ),
                )
                .drop(["INFLATION_YOY_PCT", "CPI_INDEX"])
            )
        else:
            lf_spend_analytics = lf_spend_analytics.with_columns(
                pl.lit(0.0).alias("Real_Monthly_Spend"),
                pl.lit(0.0).alias("YoY_Real_Variance_Pct"),
                pl.lit(0.0).alias("Category_Inflation_Contribution"),
            )

        return lf_spend_analytics.select(
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
                "Trailing_12M_Avg_Spend",
                "Trailing_12M_Total_Spend",
                "Cumulative_YTD_Spend",
                "Spend_Share_Pct",
                "MoM_Variance_Pct",
                "YoY_Variance_Pct",
                "Spend_Consistency_Score",
                "Is_Category_Creep",
                "Is_Investment",
                "Spend_Type",
                "Rank_by_Spend",
                "Is_Discretionary",
                "Real_Monthly_Spend",
                "YoY_Real_Variance_Pct",
                "Budget_Variance_Pct",
                "Category_Inflation_Contribution",
                "Avg_Days_Between_Transactions",
            ]
        )
