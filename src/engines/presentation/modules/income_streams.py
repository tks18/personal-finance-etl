from collections.abc import Mapping
from typing import Any, cast

import polars as pl


class IncomeStreamsBuilder:
    """
    Constructs the Income Streams presentation model.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules=None
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_inc_agg = self.base_lf["lf_inc_agg"]
        lf_months = self.base_lf["lf_months"]

        d_inc_subcat = self.dfs.get("df_d_income_subcategory")
        d_inc_cat = self.dfs.get("df_d_income_category")

        lf_inc_monthly = (
            lf_inc_agg.with_columns(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("DATE").dt.month_end().alias("MONTH_END_DATE"),
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                [
                    pl.col("INCOME").sum().fill_null(0.0).alias("Total_Monthly_Income"),
                    pl.col("INCOME").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                    pl.col("Is_Active_Income").first().alias("Is_Active_Income"),
                    pl.col("Is_Dividend_Income").first().alias("Is_Dividend_Income"),
                    pl.col("Is_Interest_Income").first().alias("Is_Interest_Income"),
                ]
            )
        )

        lf_grid = lf_months.join(lf_inc_agg.select("CATEGORY_ID").unique(), how="cross")

        lf_inc_monthly = lf_grid.join(
            lf_inc_monthly, on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"], how="left"
        ).with_columns(
            pl.col("Total_Monthly_Income").fill_null(0.0),
            pl.col("Average_Transaction_Value").fill_null(0.0),
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
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
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_3M_Avg_Income"),
                pl.col("Total_Monthly_Income")
                .rolling_mean(window_size=6)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_6M_Avg_Income"),
                pl.col("Total_Monthly_Income")
                .shift(1)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Prev_Month_Income"),
                pl.col("Total_Monthly_Income")
                .shift(12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Prev_Year_Income"),
                pl.col("Total_Monthly_Income")
                .rolling_mean(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_12M_Avg_Income"),
                pl.col("Total_Monthly_Income")
                .rolling_sum(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Trailing_12M_Total_Income"),
                pl.col("Total_Monthly_Income")
                .cum_sum()
                .over(
                    ["CATEGORY_ID", pl.col("MONTH_START_DATE").dt.year()],
                    order_by="MONTH_START_DATE",
                )
                .alias("Cumulative_YTD_Income"),
                pl.when(pl.col("Total_Monthly_Income") > 0)
                .then(pl.col("MONTH_START_DATE"))
                .otherwise(None)
                .forward_fill()
                .shift(1)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Last_Received_Date"),
                pl.col("Total_Monthly_Income")
                .rolling_mean(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Cat_Mean"),
                pl.col("Total_Monthly_Income")
                .rolling_std(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Cat_Std"),
                pl.col("Total_Monthly_Income")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Total_Month_All_Categories_Income"),
                pl.col("MONTH_START_DATE")
                .cum_count()
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Months_Since_First"),
                (pl.col("Total_Monthly_Income") > 0)
                .cast(pl.Int64)
                .rolling_sum(window_size=12)
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("Months_Active_TTM"),
            )
            .with_columns(
                pl.when(pl.col("Months_Since_First") == 12)
                .then(pl.col("Trailing_12M_Total_Income"))
                .otherwise(None)
                .forward_fill()
                .over("CATEGORY_ID", order_by="MONTH_START_DATE")
                .alias("First_12M_Total_Income"),
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
                pl.when(pl.col("Cat_Std").is_not_null() & (pl.col("Cat_Std") > 0))
                .then(
                    pl.when((pl.col("Cat_Mean") / pl.col("Cat_Std")) > 10.0)
                    .then(10.0)
                    .otherwise(pl.col("Cat_Mean") / pl.col("Cat_Std"))
                )
                .when((pl.col("Cat_Std") == 0) & (pl.col("Cat_Mean") == 0))
                .then(pl.lit(None))
                .otherwise(10.0)
                .alias("Income_Stability_Score"),
                pl.when(pl.col("Last_Received_Date").is_not_null())
                .then(
                    (
                        pl.col("MONTH_START_DATE").dt.year() * 12
                        + pl.col("MONTH_START_DATE").dt.month()
                    )
                    - (
                        pl.col("Last_Received_Date").dt.year() * 12
                        + pl.col("Last_Received_Date").dt.month()
                    )
                )
                .otherwise(None)
                .cast(pl.Int64)
                .alias("Months_Since_Last_Received"),
                (~pl.col("Is_Active_Income")).alias("Is_Passive_Income"),
                pl.when(
                    (pl.col("Months_Since_First") >= 12) & (pl.col("First_12M_Total_Income") > 0)
                )
                .then(
                    (pl.col("Trailing_12M_Total_Income") / pl.col("First_12M_Total_Income")).pow(
                        1.0 / (pl.col("Months_Since_First") / 12.0)
                    )
                    - 1.0
                )
                .otherwise(0.0)
                .alias("Income_CAGR"),
            )
            .with_columns(
                pl.when(pl.col("Income_Share_Pct").pow(2).sum().over("MONTH_START_DATE") > 0)
                .then(1.0 / pl.col("Income_Share_Pct").pow(2).sum().over("MONTH_START_DATE"))
                .otherwise(0.0)
                .alias("Income_Diversification_Score"),
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
            lf_income_streams = (
                lf_income_streams.join(lf_inflation, on="MONTH_START_DATE", how="left")
                .with_columns(
                    (
                        pl.col("Total_Monthly_Income") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))
                    ).alias("Real_Monthly_Income"),
                    pl.when(pl.col("Prev_Year_Income") > 0)
                    .then(
                        ((1 + pl.col("YoY_Variance_Pct")) / (1 + pl.col("INFLATION_YOY_PCT"))) - 1
                    )
                    .otherwise(0.0)
                    .alias("Real_YoY_Income_Growth"),
                )
                .drop(["INFLATION_YOY_PCT", "CPI_INDEX"])
            )
        else:
            lf_income_streams = lf_income_streams.with_columns(
                pl.lit(0.0).alias("Real_Monthly_Income"),
                pl.lit(0.0).alias("Real_YoY_Income_Growth"),
            )

        return lf_income_streams.select(
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
                "Trailing_12M_Avg_Income",
                "Trailing_12M_Total_Income",
                "Cumulative_YTD_Income",
                "Income_Share_Pct",
                "MoM_Variance_Pct",
                "YoY_Variance_Pct",
                "Income_Stability_Score",
                "Months_Since_Last_Received",
                "Is_Passive_Income",
                "Real_Monthly_Income",
                "Income_CAGR",
                "Real_YoY_Income_Growth",
                "Income_Diversification_Score",
                "Months_Active_TTM",
            ]
        )
