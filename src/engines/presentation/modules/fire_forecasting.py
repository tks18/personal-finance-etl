import polars as pl


class FireForecastingBuilder:
    """
    Constructs the FIRE & Wealth Forecasting presentation model.
    """

    def __init__(self, base_lf: dict[str, pl.LazyFrame]):
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Income",
                    "Total_Expense",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Income") - pl.col("Total_Expense")).alias("Net_Savings"),
            )
            .sort("MONTH_START_DATE")
        )

        lf_fire_forecast = (
            lf_fire_base.with_columns(
                pl.col("Total_Expense").rolling_mean(window_size=3).alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Expense").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Expense").rolling_sum(window_size=12).alias("Trailing_12M_Spend"),
                pl.col("Net_Savings").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Savings"),
            )
            .with_columns((pl.col("Trailing_12M_Spend") * 25.0).alias("Target_FI_Number"))
            .with_columns(
                pl.when(pl.col("Target_FI_Number") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Target_FI_Number"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct"),
                pl.when(
                    (pl.col("Trailing_6M_Avg_Savings") > 0)
                    & (pl.col("Target_FI_Number") > pl.col("Total_Net_Worth"))
                )
                .then(
                    (pl.col("Target_FI_Number") - pl.col("Total_Net_Worth"))
                    / pl.col("Trailing_6M_Avg_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI"),
                pl.when(pl.col("Trailing_3M_Avg_Spend") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Trailing_3M_Avg_Spend"))
                .otherwise(0.0)
                .alias("Runway_Months"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "Total_Net_Worth",
                    "Trailing_6M_Avg_Spend",
                    "Trailing_6M_Avg_Savings",
                    "Target_FI_Number",
                    "Current_FI_Coverage_Pct",
                    "Estimated_Months_To_FI",
                    "Runway_Months",
                ]
            )
        )
        return lf_fire_forecast
