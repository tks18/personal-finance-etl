from collections.abc import Mapping
from typing import Any

import polars as pl

from src.config.financial_rules import FinancialRules
from src.engines.presentation.helpers.forecasting import calculate_budget_forecast
from src.engines.presentation.helpers.scoring import calculate_budget_health_score
from src.utils.polars_expressions import rolling_avg, rolling_std, safe_divide


class BudgetForecastBuilder:
    """
    Constructs the Budget Forecast Monthly presentation model.

    Driven by financial_rules.budget config (40/20/30+10 rule):
      - Core Expense  = 40% of smoothed income
      - Non-Core      = 20% of smoothed income (Total - Core)
      - Investment    = 30% of smoothed income (Net Transfers to investment accounts)
      - Buffer        = 10% implicit remainder

    Produces actuals-vs-targets variance, Z-score anomaly detection,
    trend/momentum signals, Lifestyle Creep Index, a 0-100 health score,
    and a 3-month rolling income-weighted forward budget plan.
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
        lf = self.base_lf.get("lf_monthly_totals")
        if lf is None:
            return pl.LazyFrame()

        # --- Config ---
        budget = self.rules.budget
        core_pct = budget.income_allocation.core_expense_pct
        non_core_pct = budget.income_allocation.non_core_expense_pct
        investment_pct = budget.income_allocation.investment_pct
        buffer_pct = 1.0 - core_pct - non_core_pct - investment_pct
        emergency_months = budget.alerts.emergency_fund_target_months

        # Sort is MANDATORY before any window/rolling function (Polars join order is not stable)
        lf = lf.sort("MONTH_START_DATE")

        # ── Step 1: Derive raw actuals ───────────────────────────────────────────
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
                .agg(pl.col("Sell Value").sum().fill_null(0.0).alias("Investment_Redeemed"))
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
            pl.col("Total_Income").alias("Actual_Income"),
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
            ).alias("Actual_Savings"),
        )

        # ── Step 2: Rolling statistics ───────────────────────────────────────────
        lf = lf.with_columns(
            pl.col("Actual_Income").shift(1).alias("Inc_T1"),
            pl.col("Actual_Income").shift(2).alias("Inc_T2"),
            pl.col("Actual_Income").shift(3).alias("Inc_T3"),
            rolling_avg("Actual_Income", 3).alias("Income_3M_Mean"),
            rolling_avg("Actual_Income", 6).alias("Income_6M_Mean"),
            rolling_std("Actual_Income", 6).alias("Income_6M_Std"),
            rolling_avg("Actual_Core_Expense", 3).alias("Core_3M_Mean"),
            rolling_avg("Actual_Core_Expense", 6).alias("Core_6M_Mean"),
            rolling_std("Actual_Core_Expense", 6).alias("Core_6M_Std"),
            rolling_avg("Actual_NonCore_Expense", 3).alias("NonCore_3M_Mean"),
            rolling_avg("Actual_NonCore_Expense", 6).alias("NonCore_6M_Mean"),
            rolling_std("Actual_NonCore_Expense", 6).alias("NonCore_6M_Std"),
        )

        # ── Step 3: Smoothed budget base (recency-biased 3M weighted avg) ────────
        # Weight: 3×T-1 + 2×T-2 + 1×T-3 / 6  →  falls back gracefully
        lf = lf.with_columns(
            pl.when(
                pl.col("Inc_T1").is_not_null()
                & pl.col("Inc_T2").is_not_null()
                & pl.col("Inc_T3").is_not_null()
            )
            .then((3 * pl.col("Inc_T1") + 2 * pl.col("Inc_T2") + 1 * pl.col("Inc_T3")) / 6.0)
            .when(pl.col("Inc_T1").is_not_null() & pl.col("Inc_T2").is_not_null())
            .then((2 * pl.col("Inc_T1") + 1 * pl.col("Inc_T2")) / 3.0)
            .when(pl.col("Inc_T1").is_not_null())
            .then(pl.col("Inc_T1"))
            .otherwise(pl.col("Actual_Income"))
            .alias("Budget_Income"),
        )

        # ── Step 4: Income volatility & regime ───────────────────────────────────
        lf = lf.with_columns(
            safe_divide("Income_6M_Std", "Income_6M_Mean").alias("Income_Volatility_Pct"),
            pl.col("Actual_Income").shift(1).alias("Prev_Income"),
        ).with_columns(
            pl.when(pl.col("Income_Volatility_Pct") > 0.20)
            .then(pl.lit("Volatile"))
            .when(
                pl.col("Prev_Income").is_not_null()
                & (pl.col("Actual_Income") > pl.col("Prev_Income") * 1.05)
            )
            .then(pl.lit("Growing"))
            .otherwise(pl.lit("Stable"))
            .alias("Income_Regime"),
        )

        # ── Step 5: Rule-based budget targets ────────────────────────────────────
        lf = lf.with_columns(
            pl.lit(core_pct).alias("Rule_Core_Pct_Budget"),
            pl.lit(non_core_pct).alias("Rule_NonCore_Pct_Budget"),
            pl.lit(investment_pct).alias("Rule_Investment_Pct_Budget"),
            (pl.col("Budget_Income") * core_pct).alias("Budget_Core_Expense_Target"),
            (pl.col("Budget_Income") * non_core_pct).alias("Budget_NonCore_Expense_Target"),
            (pl.col("Budget_Income") * investment_pct).alias("Budget_Investment_Target"),
        ).with_columns(
            (pl.col("Budget_Core_Expense_Target") + pl.col("Budget_NonCore_Expense_Target")).alias(
                "Budget_Total_Expense_Target"
            ),
            (pl.col("Budget_Income") * buffer_pct).alias("Budget_Surplus_Buffer"),
        )

        # ── Step 6: Actuals vs targets (variance) ────────────────────────────────
        lf = lf.with_columns(
            (pl.col("Actual_Core_Expense") - pl.col("Budget_Core_Expense_Target")).alias(
                "Core_Expense_Variance"
            ),
            (pl.col("Actual_NonCore_Expense") - pl.col("Budget_NonCore_Expense_Target")).alias(
                "NonCore_Expense_Variance"
            ),
            (pl.col("Budget_Investment_Target") - pl.col("Actual_Investment")).alias(
                "Investment_Shortfall"
            ),
            (
                (pl.col("Actual_Core_Expense") + pl.col("Actual_NonCore_Expense"))
                - pl.col("Budget_Total_Expense_Target")
            ).alias("Total_Budget_Variance"),
        )

        # ── Step 7: Actual allocation percentages ────────────────────────────────
        lf = lf.with_columns(
            safe_divide("Actual_Core_Expense", "Actual_Income").alias("Actual_Core_Pct_of_Income"),
            safe_divide("Actual_NonCore_Expense", "Actual_Income").alias(
                "Actual_NonCore_Pct_of_Income"
            ),
            safe_divide("Actual_Investment", "Actual_Income").alias(
                "Actual_Investment_Pct_of_Income"
            ),
            safe_divide("Actual_Savings", "Actual_Income").alias("Actual_Savings_Pct_of_Income"),
        )

        # ── Step 8: Z-Score anomaly detection (6M rolling baseline) ──────────────
        lf = lf.with_columns(
            safe_divide(
                pl.col("Actual_Core_Expense") - pl.col("Core_6M_Mean"), "Core_6M_Std"
            ).alias("Core_Expense_ZScore"),
            safe_divide(
                pl.col("Actual_NonCore_Expense") - pl.col("NonCore_6M_Mean"), "NonCore_6M_Std"
            ).alias("NonCore_Expense_ZScore"),
            safe_divide(pl.col("Actual_Income") - pl.col("Income_6M_Mean"), "Income_6M_Std").alias(
                "Income_ZScore"
            ),
        )

        # ── Step 9: Trend signals (rolling mean slope proxy) ─────────────────────
        lf = lf.with_columns(
            (pl.col("Core_3M_Mean") - pl.col("Core_3M_Mean").shift(1)).alias(
                "Core_Expense_3M_Trend"
            ),
            (pl.col("NonCore_3M_Mean") - pl.col("NonCore_3M_Mean").shift(1)).alias(
                "NonCore_Expense_3M_Trend"
            ),
            (pl.col("Income_3M_Mean") - pl.col("Income_3M_Mean").shift(1)).alias("Income_3M_Trend"),
        )

        # Savings rate trend signal
        lf = (
            lf.with_columns(
                safe_divide(
                    pl.col("Actual_Income")
                    - pl.col("Actual_Core_Expense")
                    - pl.col("Actual_NonCore_Expense"),
                    "Actual_Income",
                ).alias("Curr_Savings_Rate"),
            )
            .with_columns(
                pl.col("Curr_Savings_Rate").shift(1).alias("Prev_Savings_Rate"),
            )
            .with_columns(
                pl.when(pl.col("Curr_Savings_Rate") > pl.col("Prev_Savings_Rate") + 0.02)
                .then(pl.lit("Improving"))
                .when(pl.col("Curr_Savings_Rate") < pl.col("Prev_Savings_Rate") - 0.02)
                .then(pl.lit("Deteriorating"))
                .otherwise(pl.lit("Stable"))
                .alias("Savings_Rate_Trend_Signal"),
            )
        )

        # ── Step 11: Health Score (0–100) ────────────────────────────────────────
        lf = calculate_budget_health_score(lf, investment_pct)

        # ── Step 12: Runway metrics ───────────────────────────────────────────────
        lf = lf.with_columns(
            safe_divide("Liquid_Assets_Market", "Actual_Core_Expense").alias(
                "Zero_Income_Runway_Months"
            ),
            (
                pl.col("Core_6M_Mean").fill_null(pl.col("Actual_Core_Expense")) * emergency_months
                - pl.col("Liquid_Assets_Market")
            ).alias("Emergency_Fund_Gap"),
        )

        # ── Step 13: Forward Budget Forecast (M+1) ───────────────────────────────
        lf = calculate_budget_forecast(lf, core_pct, non_core_pct, investment_pct, buffer_pct)

        # ── Step 14: Boolean flags ────────────────────────────────────────────────
        lf = lf.with_columns(
            (pl.col("Actual_Core_Expense") > pl.col("Budget_Core_Expense_Target")).alias(
                "Is_Core_Overspent"
            ),
            (pl.col("Actual_NonCore_Expense") > pl.col("Budget_NonCore_Expense_Target")).alias(
                "Is_NonCore_Overspent"
            ),
            (pl.col("Actual_Investment") < pl.col("Budget_Investment_Target")).alias(
                "Is_Investment_Underfunded"
            ),
            (pl.col("Income_Volatility_Pct") > 0.20).alias("Is_Income_Volatile"),
            (
                (pl.col("Core_Expense_ZScore").abs() > 2.0)
                | (pl.col("NonCore_Expense_ZScore").abs() > 2.0)
            ).alias("Is_Expense_Anomaly"),
        ).with_columns(
            (
                ~(
                    pl.col("Is_Core_Overspent")
                    | pl.col("Is_NonCore_Overspent")
                    | pl.col("Is_Investment_Underfunded")
                )
            ).alias("Is_Budget_Month_Healthy"),
        )

        # ── Final select ──────────────────────────────────────────────────────────
        return lf.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                # Income anchor
                "Actual_Income",
                "Budget_Income",
                "Income_Volatility_Pct",
                "Income_Regime",
                # Rule targets
                "Rule_Core_Pct_Budget",
                "Rule_NonCore_Pct_Budget",
                "Rule_Investment_Pct_Budget",
                "Budget_Core_Expense_Target",
                "Budget_NonCore_Expense_Target",
                "Budget_Investment_Target",
                "Budget_Surplus_Buffer",
                "Budget_Total_Expense_Target",
                # Actuals
                "Actual_Core_Expense",
                "Actual_NonCore_Expense",
                "Investment_Deployed",
                "Investment_Redeemed",
                "Actual_Investment",
                "Actual_Savings",
                # Actual % of income
                "Actual_Core_Pct_of_Income",
                "Actual_NonCore_Pct_of_Income",
                "Actual_Investment_Pct_of_Income",
                "Actual_Savings_Pct_of_Income",
                # Variance
                "Core_Expense_Variance",
                "NonCore_Expense_Variance",
                "Investment_Shortfall",
                "Total_Budget_Variance",
                # Statistical signals
                "Core_Expense_3M_Trend",
                "NonCore_Expense_3M_Trend",
                "Income_3M_Trend",
                "Core_Expense_ZScore",
                "NonCore_Expense_ZScore",
                "Income_ZScore",
                "Savings_Rate_Trend_Signal",
                # Composite scores
                "Savings_Rate_Health_Score",
                "Savings_Rate_Grade",
                "Budget_Stress_Score",
                # Runway
                "Zero_Income_Runway_Months",
                "Emergency_Fund_Gap",
                # M+1 forecast
                "NextMonth_Budget_Income_Forecast",
                "NextMonth_Core_Budget",
                "NextMonth_NonCore_Budget",
                "NextMonth_Investment_Budget",
                "NextMonth_Discretionary_Pool",
                "NextMonth_Recommended_Savings",
                # Flags
                "Is_Core_Overspent",
                "Is_NonCore_Overspent",
                "Is_Investment_Underfunded",
                "Is_Income_Volatile",
                "Is_Budget_Month_Healthy",
                "Is_Expense_Anomaly",
            ]
        )
