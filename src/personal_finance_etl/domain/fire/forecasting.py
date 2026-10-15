"""Budget and cashflow forecasting models.

Owns
----
- calculate_budget_forecast: Calculates forward budget forecast for next month (M+1) based on target percentages.

Does not own
-------------
- Budget variance and actuals calculation (owned by domain.household.budget).
- Monte Carlo simulation (owned by domain.fire.simulation).
"""

from __future__ import annotations

import polars as pl

__all__ = ["calculate_budget_forecast"]


def calculate_budget_forecast(
    lf: pl.LazyFrame,
    core_pct: float,
    non_core_pct: float,
    investment_pct: float,
    buffer_pct: float,
) -> pl.LazyFrame:
    """Calculate the forward budget forecast for the next month (M+1) based on target percentages.

    Parameters
    ----------
    lf : pl.LazyFrame
        LazyFrame containing `Budget_Income` column.
    core_pct : float
        Target allocation percentage for core expenses.
    non_core_pct : float
        Target allocation percentage for non-core/discretionary expenses.
    investment_pct : float
        Target allocation percentage for investments.
    buffer_pct : float
        Target allocation percentage for emergency/buffer savings.

    Returns
    -------
    pl.LazyFrame
        LazyFrame enriched with forward-looking budget forecasts.
    """
    return lf.with_columns(
        pl.col("Budget_Income").alias("NextMonth_Budget_Income_Forecast"),
    ).with_columns(
        (pl.col("NextMonth_Budget_Income_Forecast") * core_pct).alias("NextMonth_Core_Budget"),
        (pl.col("NextMonth_Budget_Income_Forecast") * non_core_pct).alias(
            "NextMonth_NonCore_Budget"
        ),
        (pl.col("NextMonth_Budget_Income_Forecast") * investment_pct).alias(
            "NextMonth_Investment_Budget"
        ),
        (pl.col("NextMonth_Budget_Income_Forecast") * non_core_pct).alias(
            "NextMonth_Discretionary_Pool"
        ),
        (pl.col("NextMonth_Budget_Income_Forecast") * buffer_pct).alias(
            "NextMonth_Recommended_Savings"
        ),
    )
