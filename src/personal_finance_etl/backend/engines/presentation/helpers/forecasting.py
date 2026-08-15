import polars as pl


def calculate_budget_forecast(
    lf: pl.LazyFrame, core_pct: float, non_core_pct: float, investment_pct: float, buffer_pct: float
) -> pl.LazyFrame:
    """Calculates the forward budget forecast for the next month (M+1) based on target percentages."""
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
