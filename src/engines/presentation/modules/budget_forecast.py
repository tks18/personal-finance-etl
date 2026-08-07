from typing import Any

import polars as pl


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

    def __init__(self, base_lf: dict[str, Any], rules):
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
        # Actual_Investment = Net_Transfers reconstructed from ledger identity:
        #   Net_Cashflow_Month = Income - Expense + Net_Transfers
        lf = lf.with_columns(
            pl.col("Total_Income").alias("Actual_Income"),
            pl.col("Total_Core_Expense").alias("Actual_Core_Expense"),
            (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias(
                "Actual_NonCore_Expense"
            ),
            (pl.col("Net_Cashflow_Month") - pl.col("Total_Income") + pl.col("Total_Expense")).alias(
                "Actual_Investment"
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
            pl.col("Actual_Income").rolling_mean(window_size=3).alias("Income_3M_Mean"),
            pl.col("Actual_Income").rolling_mean(window_size=6).alias("Income_6M_Mean"),
            pl.col("Actual_Income").rolling_std(window_size=6).alias("Income_6M_Std"),
            pl.col("Actual_Core_Expense").rolling_mean(window_size=3).alias("Core_3M_Mean"),
            pl.col("Actual_Core_Expense").rolling_mean(window_size=6).alias("Core_6M_Mean"),
            pl.col("Actual_Core_Expense").rolling_std(window_size=6).alias("Core_6M_Std"),
            pl.col("Actual_NonCore_Expense").rolling_mean(window_size=3).alias("NonCore_3M_Mean"),
            pl.col("Actual_NonCore_Expense").rolling_mean(window_size=6).alias("NonCore_6M_Mean"),
            pl.col("Actual_NonCore_Expense").rolling_std(window_size=6).alias("NonCore_6M_Std"),
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
            pl.when(pl.col("Income_6M_Mean") > 0)
            .then(pl.col("Income_6M_Std") / pl.col("Income_6M_Mean"))
            .otherwise(0.0)
            .alias("Income_Volatility_Pct"),
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
            pl.when(pl.col("Actual_Income") > 0)
            .then(pl.col("Actual_Core_Expense") / pl.col("Actual_Income"))
            .otherwise(0.0)
            .alias("Actual_Core_Pct_of_Income"),
            pl.when(pl.col("Actual_Income") > 0)
            .then(pl.col("Actual_NonCore_Expense") / pl.col("Actual_Income"))
            .otherwise(0.0)
            .alias("Actual_NonCore_Pct_of_Income"),
            pl.when(pl.col("Actual_Income") > 0)
            .then(pl.col("Actual_Investment") / pl.col("Actual_Income"))
            .otherwise(0.0)
            .alias("Actual_Investment_Pct_of_Income"),
            pl.when(pl.col("Actual_Income") > 0)
            .then(pl.col("Actual_Savings") / pl.col("Actual_Income"))
            .otherwise(0.0)
            .alias("Actual_Savings_Pct_of_Income"),
        )

        # ── Step 8: Z-Score anomaly detection (6M rolling baseline) ──────────────
        lf = lf.with_columns(
            pl.when(pl.col("Core_6M_Std") > 0)
            .then((pl.col("Actual_Core_Expense") - pl.col("Core_6M_Mean")) / pl.col("Core_6M_Std"))
            .otherwise(0.0)
            .alias("Core_Expense_ZScore"),
            pl.when(pl.col("NonCore_6M_Std") > 0)
            .then(
                (pl.col("Actual_NonCore_Expense") - pl.col("NonCore_6M_Mean"))
                / pl.col("NonCore_6M_Std")
            )
            .otherwise(0.0)
            .alias("NonCore_Expense_ZScore"),
            pl.when(pl.col("Income_6M_Std") > 0)
            .then((pl.col("Actual_Income") - pl.col("Income_6M_Mean")) / pl.col("Income_6M_Std"))
            .otherwise(0.0)
            .alias("Income_ZScore"),
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
                pl.when(pl.col("Actual_Income") > 0)
                .then(
                    (
                        pl.col("Actual_Income")
                        - pl.col("Actual_Core_Expense")
                        - pl.col("Actual_NonCore_Expense")
                    )
                    / pl.col("Actual_Income")
                )
                .otherwise(0.0)
                .alias("Curr_Savings_Rate"),
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

        # ── Step 10: Lifestyle Creep Index & Efficiency ──────────────────────────
        lf = lf.with_columns(
            pl.when(pl.col("Income_3M_Trend").abs() > 0)
            .then(pl.col("Core_Expense_3M_Trend") / pl.col("Income_3M_Trend").abs())
            .otherwise(0.0)
            .alias("Marginal_Core_Efficiency"),
            pl.when(pl.col("Income_3M_Trend").abs() > 0)
            .then(pl.col("NonCore_Expense_3M_Trend") / pl.col("Income_3M_Trend").abs())
            .otherwise(0.0)
            .alias("Lifestyle_Creep_Index"),
        ).with_columns(
            pl.when(
                (pl.col("Actual_NonCore_Expense").shift(1) > 0)
                & (pl.col("Actual_Income").shift(1) > 0)
            )
            .then(
                (pl.col("Actual_NonCore_Expense") - pl.col("Actual_NonCore_Expense").shift(1))
                / pl.col("Actual_NonCore_Expense").shift(1)
                - (pl.col("Actual_Income") - pl.col("Actual_Income").shift(1))
                / pl.col("Actual_Income").shift(1)
            )
            .otherwise(0.0)
            .alias("Budget_Elasticity"),
        )

        # ── Step 11: Health Score (0–100) ────────────────────────────────────────
        # 4 equal components × 25 pts each
        lf = (
            lf.with_columns(
                # Comp 1: Actual savings rate vs investment_pct target
                pl.when(pl.col("Actual_Savings_Pct_of_Income") >= investment_pct)
                .then(pl.lit(25.0))
                .when(pl.col("Actual_Savings_Pct_of_Income") > 0)
                .then((pl.col("Actual_Savings_Pct_of_Income") / investment_pct) * 25.0)
                .otherwise(pl.lit(0.0))
                .alias("_score_savings"),
                # Comp 2: Investment fulfillment
                pl.when(pl.col("Budget_Investment_Target") > 0)
                .then(
                    (pl.col("Actual_Investment") / pl.col("Budget_Investment_Target") * 25.0).clip(
                        0.0, 25.0
                    )
                )
                .otherwise(pl.lit(0.0))
                .alias("_score_investment"),
                # Comp 3: Core expense control (full marks if under budget)
                pl.when(pl.col("Budget_Core_Expense_Target") > 0)
                .then(
                    pl.when(pl.col("Actual_Core_Expense") <= pl.col("Budget_Core_Expense_Target"))
                    .then(pl.lit(25.0))
                    .otherwise(
                        (
                            pl.lit(1.0)
                            - pl.col("Core_Expense_Variance") / pl.col("Budget_Core_Expense_Target")
                        ).clip(0.0, 1.0)
                        * 25.0
                    )
                )
                .otherwise(pl.lit(0.0))
                .alias("_score_core"),
                # Comp 4: Non-core discipline
                pl.when(pl.col("Budget_NonCore_Expense_Target") > 0)
                .then(
                    pl.when(
                        pl.col("Actual_NonCore_Expense") <= pl.col("Budget_NonCore_Expense_Target")
                    )
                    .then(pl.lit(25.0))
                    .otherwise(
                        (
                            pl.lit(1.0)
                            - pl.col("NonCore_Expense_Variance")
                            / pl.col("Budget_NonCore_Expense_Target")
                        ).clip(0.0, 1.0)
                        * 25.0
                    )
                )
                .otherwise(pl.lit(0.0))
                .alias("_score_noncore"),
            )
            .with_columns(
                (
                    pl.col("_score_savings")
                    + pl.col("_score_investment")
                    + pl.col("_score_core")
                    + pl.col("_score_noncore")
                ).alias("Savings_Rate_Health_Score"),
            )
            .with_columns(
                pl.when(pl.col("Savings_Rate_Health_Score") >= 90)
                .then(pl.lit("A+"))
                .when(pl.col("Savings_Rate_Health_Score") >= 80)
                .then(pl.lit("A"))
                .when(pl.col("Savings_Rate_Health_Score") >= 70)
                .then(pl.lit("B"))
                .when(pl.col("Savings_Rate_Health_Score") >= 60)
                .then(pl.lit("C"))
                .when(pl.col("Savings_Rate_Health_Score") >= 50)
                .then(pl.lit("D"))
                .otherwise(pl.lit("F"))
                .alias("Savings_Rate_Grade"),
                # Budget stress = % over-budget (0 = within budget)
                pl.when(pl.col("Budget_Total_Expense_Target") > 0)
                .then(
                    pl.when(pl.col("Total_Budget_Variance") > 0)
                    .then(
                        (pl.col("Total_Budget_Variance") / pl.col("Budget_Total_Expense_Target"))
                        * 100.0
                    )
                    .otherwise(pl.lit(0.0))
                )
                .otherwise(pl.lit(0.0))
                .alias("Budget_Stress_Score"),
            )
        )

        # ── Step 12: Runway metrics ───────────────────────────────────────────────
        lf = lf.with_columns(
            pl.when(pl.col("Actual_Core_Expense") > 0)
            .then(pl.col("Liquid_Assets_Market") / pl.col("Actual_Core_Expense"))
            .otherwise(0.0)
            .alias("Zero_Income_Runway_Months"),
            (
                pl.col("Core_6M_Mean").fill_null(pl.col("Actual_Core_Expense")) * emergency_months
                - pl.col("Liquid_Assets_Market")
            ).alias("Emergency_Fund_Gap"),
        )

        # ── Step 13: 3-Month Rolling Forward Budget Forecast ─────────────────────
        # M+1: current Budget_Income (3M weighted lag)
        # M+2: Budget_Income + 1× income trend slope
        # M+3: Budget_Income + 2× income trend slope
        lf = lf.with_columns(
            pl.col("Budget_Income").alias("NextMonth_Budget_Income_Forecast"),
            (pl.col("Budget_Income") + pl.col("Income_3M_Trend").fill_null(0.0)).alias(
                "Next2Month_Budget_Income_Forecast"
            ),
            (pl.col("Budget_Income") + 2.0 * pl.col("Income_3M_Trend").fill_null(0.0)).alias(
                "Next3Month_Budget_Income_Forecast"
            ),
        )

        for prefix, col in [
            ("NextMonth", "NextMonth_Budget_Income_Forecast"),
            ("Next2Month", "Next2Month_Budget_Income_Forecast"),
            ("Next3Month", "Next3Month_Budget_Income_Forecast"),
        ]:
            lf = lf.with_columns(
                (pl.col(col) * core_pct).alias(f"{prefix}_Core_Budget"),
                (pl.col(col) * non_core_pct).alias(f"{prefix}_NonCore_Budget"),
                (pl.col(col) * investment_pct).alias(f"{prefix}_Investment_Budget"),
                (pl.col(col) * non_core_pct).alias(f"{prefix}_Discretionary_Pool"),
                (pl.col(col) * buffer_pct).alias(f"{prefix}_Recommended_Savings"),
            )

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
                (pl.col("Lifestyle_Creep_Index") > 1.0) & (pl.col("NonCore_Expense_ZScore") > 1.0)
            ).alias("Is_Lifestyle_Creep"),
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
                # Lifestyle & efficiency
                "Marginal_Core_Efficiency",
                "Lifestyle_Creep_Index",
                "Budget_Elasticity",
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
                # M+2 forecast
                "Next2Month_Budget_Income_Forecast",
                "Next2Month_Core_Budget",
                "Next2Month_NonCore_Budget",
                "Next2Month_Investment_Budget",
                "Next2Month_Discretionary_Pool",
                "Next2Month_Recommended_Savings",
                # M+3 forecast
                "Next3Month_Budget_Income_Forecast",
                "Next3Month_Core_Budget",
                "Next3Month_NonCore_Budget",
                "Next3Month_Investment_Budget",
                "Next3Month_Discretionary_Pool",
                "Next3Month_Recommended_Savings",
                # Flags
                "Is_Core_Overspent",
                "Is_NonCore_Overspent",
                "Is_Investment_Underfunded",
                "Is_Income_Volatile",
                "Is_Budget_Month_Healthy",
                "Is_Lifestyle_Creep",
                "Is_Expense_Anomaly",
            ]
        )
