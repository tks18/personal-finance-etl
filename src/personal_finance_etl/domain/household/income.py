"""Household Income Streams analytics builder.

Owns
----
- IncomeStreamsBuilder: Analyzes recurring income streams, stability scores, diversification, and active/passive shares.

Does not own
-------------
- Raw transaction stage ingestion (owned by domain.household.transforms).
- Income policy rules models (owned by config.financial_rules.household).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules

__all__ = ["IncomeStreamsBuilder"]


class IncomeStreamsBuilder:
    """Constructs the Income Streams presentation model."""

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: Mapping[str, pl.LazyFrame],
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def _build_monthly_category_grid(
        self, lf_inc_agg: pl.LazyFrame, lf_months: pl.LazyFrame
    ) -> pl.LazyFrame:
        """Aggregate monthly income per category across full calendar months grid.

        Parameters
        ----------
        lf_inc_agg : pl.LazyFrame
            Aggregated raw income transaction stream.
        lf_months : pl.LazyFrame
            Spine of continuous calendar month intervals.

        Returns
        -------
        pl.LazyFrame
            Monthly grid frame with null-filled total income and transaction averages.
        """
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
                ]
            )
        )

        lf_grid = lf_months.join(lf_inc_agg.select("CATEGORY_ID").unique(), how="cross")

        return lf_grid.join(
            lf_inc_monthly,
            on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"],
            how="left",
        ).with_columns(
            pl.col("Total_Monthly_Income").fill_null(0.0),
            pl.col("Average_Transaction_Value").fill_null(0.0),
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
        )

    def _enrich_income_dimensions(self, lf_inc_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Join income category metadata, parent groupings, and classification flags.

        Parameters
        ----------
        lf_inc_monthly : pl.LazyFrame
            Monthly category income grid frame.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with category names, group descriptors, and active/passive flags.
        """
        d_inc_subcat = self.dfs.get("df_d_income_subcategory")
        d_inc_cat = self.dfs.get("df_d_income_category")

        if d_inc_subcat is not None and d_inc_cat is not None:
            lf_inc_subcat = (
                d_inc_subcat.lazy() if isinstance(d_inc_subcat, pl.DataFrame) else d_inc_subcat
            )
            lf_inc_cat = d_inc_cat.lazy() if isinstance(d_inc_cat, pl.DataFrame) else d_inc_cat

            return (
                lf_inc_monthly.join(
                    lf_inc_subcat.select(
                        [
                            "UID",
                            "CATEGORY_NAME",
                            "CATEGORY_ID",
                            "Is_Active_Income",
                            "Is_Passive_Income",
                            "Is_Dividend_Income",
                            "Is_Interest_Income",
                            "Is_Non_Cash_Income",
                        ]
                    ).rename({"CATEGORY_ID": "PARENT_ID", "UID": "CATEGORY_ID"}),
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

        return lf_inc_monthly.with_columns(
            pl.lit(None).alias("CATEGORY_NAME"),
            pl.lit(None).alias("CATEGORY_GROUPS"),
            pl.lit(False).alias("Is_Active_Income"),
            pl.lit(False).alias("Is_Passive_Income"),
            pl.lit(False).alias("Is_Dividend_Income"),
            pl.lit(False).alias("Is_Interest_Income"),
            pl.lit(False).alias("Is_Non_Cash_Income"),
        )

    def _calculate_rolling_income_metrics(self, lf_inc_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate trailing averages, cumulative totals, stability, and diversification scores.

        Parameters
        ----------
        lf_inc_monthly : pl.LazyFrame
            Dimension-enriched monthly income frame.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with trailing metrics, MoM/YoY growth, and stability indices.
        """
        return (
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

    def _project_income_streams_schema(self, lf_income_streams: pl.LazyFrame) -> pl.LazyFrame:
        """Select and order columns matching presentation-tier Income Streams schema.

        Parameters
        ----------
        lf_income_streams : pl.LazyFrame
            Fully evaluated income streams LazyFrame.

        Returns
        -------
        pl.LazyFrame
            Final schema projected income streams model.
        """
        return lf_income_streams.select(
            *[
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "CATEGORY_ID",
                "CATEGORY_NAME",
                "CATEGORY_GROUPS",
                "Total_Monthly_Income",
                "Trailing_3M_Avg_Income",
                "Cumulative_YTD_Income",
                "Is_Active_Income",
                "Is_Passive_Income",
                "Is_Dividend_Income",
                "Is_Interest_Income",
                "Is_Non_Cash_Income",
            ]
        )

    def build(self) -> pl.LazyFrame:
        """Build the Income Streams LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Income Streams schema.
        """
        lf_inc_agg: pl.LazyFrame = self.base_lf["lf_inc_agg"]
        lf_months: pl.LazyFrame = self.base_lf["lf_months"]

        lf_inc_monthly = self._build_monthly_category_grid(lf_inc_agg, lf_months)
        lf_inc_enriched = self._enrich_income_dimensions(lf_inc_monthly)
        lf_income_streams = self._calculate_rolling_income_metrics(lf_inc_enriched)
        return self._project_income_streams_schema(lf_income_streams)
