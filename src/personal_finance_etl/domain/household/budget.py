"""Household Budget Forecast and Spend Analytics builders.

Owns
----
- BudgetForecastBuilder: Driven by financial_rules.budget config (40/20/30+10 allocation rule).
- SpendAnalyticsBuilder: Monthly category-level spend analytics, trend variances, creep detection, and discretionary tags.

Does not own
-------------
- Raw transaction stage ingestion (owned by domain.household.transforms).
- Household policy configuration models (owned by config.financial_rules.household).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.polars import rolling_avg, rolling_std, safe_divide

__all__ = ["BudgetForecastBuilder", "SpendAnalyticsBuilder"]


class SpendAnalyticsBuilder:
    """Constructs the Category Spend Analytics presentation model."""

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        """Build the Category Spend Analytics LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Spend Analytics schema.
        """
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
                    pl.col("EXPENSE")
                    .filter(~pl.col("is_non_cash_pnl").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Cash_Spend"),
                    pl.col("EXPENSE")
                    .filter(pl.col("is_non_cash_pnl").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Non_Cash_Spend"),
                    pl.col("EXPENSE").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                    pl.len().alias("Transaction_Count"),
                ]
            )
        )

        lf_months = self.base_lf["lf_months"]
        lf_grid = lf_months.join(lf_exp_agg.select("CATEGORY_ID").unique(), how="cross")

        lf_cat_agg = (
            lf_grid.join(
                lf_cat_agg, on=["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"], how="left"
            )
            .sort(["CATEGORY_ID", "MONTH_START_DATE"])
            .with_columns(
                pl.col("Total_Monthly_Spend").fill_null(0.0),
                pl.col("Average_Transaction_Value").fill_null(0.0),
                pl.col("Transaction_Count").fill_null(0).cast(pl.Int64),
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
            )
        )

        if d_subcat is not None and d_exp_cat is not None:
            lf_subcat = d_subcat.lazy() if isinstance(d_subcat, pl.DataFrame) else d_subcat
            lf_exp_cat = d_exp_cat.lazy() if isinstance(d_exp_cat, pl.DataFrame) else d_exp_cat

            lf_cat_agg = (
                lf_cat_agg.join(
                    lf_subcat.select(
                        ["UID", "CATEGORY_NAME", "CATEGORY_ID", "Is_Core_Expense"]
                    ).rename({"CATEGORY_ID": "PARENT_ID", "UID": "CATEGORY_ID"}),
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
                pl.lit(None).alias("CATEGORY_NAME"),
                pl.lit(None).alias("CATEGORY_GROUPS"),
                pl.lit(False).alias("Is_Core_Expense"),
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

        return lf_spend_analytics.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "CATEGORY_ID",
                "CATEGORY_NAME",
                "CATEGORY_GROUPS",
                "Total_Monthly_Spend",
                "Cash_Spend",
                "Non_Cash_Spend",
                "Trailing_3M_Avg_Spend",
                "Cumulative_YTD_Spend",
                "Is_Investment",
                "Spend_Type",
                "Is_Discretionary",
                "Is_Core_Expense",
            ]
        )


class BudgetForecastBuilder:
    """Constructs the Budget Forecast Monthly presentation model.

    Driven by financial_rules.budget config (40/20/30+10 rule):
      - Core Expense  = 40% of smoothed income
      - Non-Core      = 20% of smoothed income (Total - Core)
      - Investment    = 30% of smoothed income (Net Transfers to investment accounts)
      - Buffer        = 10% implicit remainder
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        """Build the Budget Forecast LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Budget Forecast schema.
        """
        lf = self.base_lf.get("lf_monthly_totals")
        if lf is None:
            return pl.LazyFrame()

        budget = self.rules.budget
        core_pct = budget.income_allocation.core_expense_pct
        non_core_pct = budget.income_allocation.non_core_expense_pct
        investment_pct = budget.income_allocation.investment_pct
        buffer_pct = 1.0 - core_pct - non_core_pct - investment_pct
        emergency_months = budget.alerts.emergency_fund_target_months

        lf = lf.sort("MONTH_START_DATE")

        # Step 1: Derive raw actuals
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")

        if df_buys is not None:
            lf_buys = df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            lf_inv_buys = (
                lf_buys.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(pl.col("Value").sum().fill_null(0.0).alias("Investment_Deployed"))
            )
            lf = lf.join(lf_inv_buys, on="MONTH_START_DATE", how="left").sort("MONTH_START_DATE")
            lf = lf.with_columns(pl.col("Investment_Deployed").fill_null(0.0))
        else:
            lf = lf.with_columns(pl.lit(0.0).alias("Investment_Deployed"))

        if df_sells is not None:
            lf_sells = df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            lf_inv_sells = (
                lf_sells.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(pl.col("Sell_Value").sum().fill_null(0.0).alias("Investment_Redeemed"))
            )
            lf = lf.join(lf_inv_sells, on="MONTH_START_DATE", how="left").sort("MONTH_START_DATE")
            lf = lf.with_columns(pl.col("Investment_Redeemed").fill_null(0.0))
        else:
            lf = lf.with_columns(pl.lit(0.0).alias("Investment_Redeemed"))

        lf = lf.with_columns(
            (pl.col("Investment_Deployed") - pl.col("Investment_Redeemed")).alias(
                "Actual_Investment"
            )
        )

        lf = lf.with_columns(
            pl.col("Total_Cash_Income").alias("Actual_Income"),
            pl.col("Total_Core_Expense").alias("Actual_Core_Expense"),
            (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias(
                "Actual_NonCore_Expense"
            ),
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
        ).with_columns(
            (
                pl.col("Actual_Income")
                - pl.col("Actual_Core_Expense")
                - pl.col("Actual_NonCore_Expense")
                - pl.col("Actual_Investment")
            ).alias("Actual_Buffer"),
        )

        # Step 2: Income smoothing
        lf = lf.with_columns(
            rolling_avg("Actual_Income", 3).alias("Income_Smoothed_3M"),
            rolling_avg("Actual_Income", 6).alias("Income_Smoothed_6M"),
        ).with_columns(
            pl.coalesce(["Income_Smoothed_6M", "Income_Smoothed_3M", "Actual_Income"]).alias(
                "Income_Baseline"
            ),
        )

        # Step 3: Compute targets
        lf = lf.with_columns(
            (pl.col("Income_Baseline") * core_pct).alias("Target_Core_Expense"),
            (pl.col("Income_Baseline") * non_core_pct).alias("Target_NonCore_Expense"),
            (pl.col("Income_Baseline") * investment_pct).alias("Target_Investment"),
            (pl.col("Income_Baseline") * buffer_pct).alias("Target_Buffer"),
        )

        # Step 4: Variances
        lf = lf.with_columns(
            (pl.col("Actual_Core_Expense") - pl.col("Target_Core_Expense")).alias(
                "Variance_Core_Expense"
            ),
            (pl.col("Actual_NonCore_Expense") - pl.col("Target_NonCore_Expense")).alias(
                "Variance_NonCore_Expense"
            ),
            (pl.col("Actual_Investment") - pl.col("Target_Investment")).alias(
                "Variance_Investment"
            ),
            (pl.col("Actual_Buffer") - pl.col("Target_Buffer")).alias("Variance_Buffer"),
        ).with_columns(
            safe_divide("Variance_Core_Expense", "Target_Core_Expense").alias(
                "Variance_Core_Expense_Pct"
            ),
            safe_divide("Variance_NonCore_Expense", "Target_NonCore_Expense").alias(
                "Variance_NonCore_Expense_Pct"
            ),
            safe_divide("Variance_Investment", "Target_Investment").alias(
                "Variance_Investment_Pct"
            ),
        )

        # Step 5: Rolling actuals & z-scores
        lf = lf.with_columns(
            rolling_avg("Actual_Core_Expense", 12).alias("Rolling_12M_Mean_Core"),
            rolling_std("Actual_Core_Expense", 12).alias("Rolling_12M_Std_Core"),
            rolling_avg("Actual_NonCore_Expense", 12).alias("Rolling_12M_Mean_NonCore"),
            rolling_std("Actual_NonCore_Expense", 12).alias("Rolling_12M_Std_NonCore"),
            rolling_avg("Actual_Income", 12).alias("Rolling_12M_Mean_Income"),
        ).with_columns(
            safe_divide(
                pl.col("Actual_Core_Expense") - pl.col("Rolling_12M_Mean_Core"),
                "Rolling_12M_Std_Core",
            ).alias("Z_Score_Core_Expense"),
            safe_divide(
                pl.col("Actual_NonCore_Expense") - pl.col("Rolling_12M_Mean_NonCore"),
                "Rolling_12M_Std_NonCore",
            ).alias("Z_Score_NonCore_Expense"),
        )

        # Step 6: Trend & lifestyle creep
        lf = lf.with_columns(
            (
                safe_divide("Actual_NonCore_Expense", "Actual_Income")
                / safe_divide("Rolling_12M_Mean_NonCore", "Rolling_12M_Mean_Income")
            ).alias("Lifestyle_Creep_Index"),
            safe_divide(
                pl.col("Actual_Core_Expense") - pl.col("Actual_Core_Expense").shift(3),
                pl.col("Actual_Core_Expense").shift(3),
            ).alias("Core_Expense_3M_Trend_Pct"),
            safe_divide(
                pl.col("Actual_NonCore_Expense") - pl.col("Actual_NonCore_Expense").shift(3),
                pl.col("Actual_NonCore_Expense").shift(3),
            ).alias("NonCore_Expense_3M_Trend_Pct"),
            safe_divide("Liquid_Assets_Market", pl.col("Actual_Core_Expense") * emergency_months).alias(
                "Emergency_Fund_Health_Ratio"
            ),
        )

        # Step 7: Scoring
        core_score = (
            pl.when(pl.col("Variance_Core_Expense_Pct") <= 0.0)
            .then(35.0)
            .when(pl.col("Variance_Core_Expense_Pct") <= 0.10)
            .then(25.0)
            .when(pl.col("Variance_Core_Expense_Pct") <= 0.20)
            .then(15.0)
            .otherwise(0.0)
        )
        non_core_score = (
            pl.when(pl.col("Variance_NonCore_Expense_Pct") <= 0.0)
            .then(20.0)
            .when(pl.col("Variance_NonCore_Expense_Pct") <= 0.15)
            .then(12.0)
            .when(pl.col("Variance_NonCore_Expense_Pct") <= 0.30)
            .then(6.0)
            .otherwise(0.0)
        )
        invest_score = (
            pl.when(pl.col("Variance_Investment_Pct") >= 0.0)
            .then(35.0)
            .when(pl.col("Variance_Investment_Pct") >= -0.15)
            .then(25.0)
            .when(pl.col("Variance_Investment_Pct") >= -0.30)
            .then(15.0)
            .otherwise(0.0)
        )
        buffer_score = (
            pl.when(pl.col("Actual_Buffer") >= 0.0).then(10.0).otherwise(0.0)
        )

        lf = lf.with_columns(
            (core_score + non_core_score + invest_score + buffer_score).alias("Budget_Health_Score")
        ).with_columns(
            pl.when(pl.col("Budget_Health_Score") >= 80.0)
            .then(pl.lit("EXCELLENT"))
            .when(pl.col("Budget_Health_Score") >= 60.0)
            .then(pl.lit("GOOD"))
            .when(pl.col("Budget_Health_Score") >= 40.0)
            .then(pl.lit("FAIR"))
            .otherwise(pl.lit("POOR"))
            .alias("Budget_Health_Tier")
        )

        # Step 8: Forward budget plan
        lf = lf.with_columns(
            (pl.col("Income_Smoothed_3M") * core_pct).alias("Plan_Forward_Core_Expense"),
            (pl.col("Income_Smoothed_3M") * non_core_pct).alias("Plan_Forward_NonCore_Expense"),
            (pl.col("Income_Smoothed_3M") * investment_pct).alias("Plan_Forward_Investment"),
            (pl.col("Income_Smoothed_3M") * buffer_pct).alias("Plan_Forward_Buffer"),
        )

        return lf.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "Actual_Income",
                "Income_Baseline",
                "Actual_Core_Expense",
                "Target_Core_Expense",
                "Variance_Core_Expense",
                "Variance_Core_Expense_Pct",
                "Actual_NonCore_Expense",
                "Target_NonCore_Expense",
                "Variance_NonCore_Expense",
                "Variance_NonCore_Expense_Pct",
                "Actual_Investment",
                "Target_Investment",
                "Variance_Investment",
                "Variance_Investment_Pct",
                "Actual_Buffer",
                "Target_Buffer",
                "Variance_Buffer",
                "Z_Score_Core_Expense",
                "Z_Score_NonCore_Expense",
                "Lifestyle_Creep_Index",
                "Core_Expense_3M_Trend_Pct",
                "NonCore_Expense_3M_Trend_Pct",
                "Emergency_Fund_Health_Ratio",
                "Budget_Health_Score",
                "Budget_Health_Tier",
                "Plan_Forward_Core_Expense",
                "Plan_Forward_NonCore_Expense",
                "Plan_Forward_Investment",
                "Plan_Forward_Buffer",
            ]
        )
