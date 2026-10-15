"""Financial health scoring and budget stress indicators.

Owns
----
- calculate_budget_health_score: Evaluates savings rate health (0-100), letter grade (A+ to F), and budget stress score.
- HealthScorer: Namespace wrapper for budget health calculation functions.

Does not own
-------------
- Budget target rules configuration (owned by config.financial_rules.household).
- Net worth calculation (owned by domain.wealth.net_worth).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

__all__ = ["HealthScorer", "calculate_budget_health_score"]


def calculate_budget_health_score(lf: pl.LazyFrame, investment_pct: float) -> pl.LazyFrame:
    """Calculate the Savings Rate Health Score (0-100) and assign a Grade and Stress Score.

    Parameters
    ----------
    lf : pl.LazyFrame
        LazyFrame containing budget target and variance columns.
    investment_pct : float
        Configured target investment percentage of income.

    Returns
    -------
    pl.LazyFrame
        LazyFrame with `Savings_Rate_Health_Score`, `Savings_Rate_Grade`, and `Budget_Stress_Score`.
    """
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
                pl.when(pl.col("Actual_NonCore_Expense") <= pl.col("Budget_NonCore_Expense_Target"))
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
    return lf


class HealthScorer:
    """Namespace for budget health and financial resilience scoring."""

    score_budget = staticmethod(calculate_budget_health_score)
