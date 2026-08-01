import polars as pl


class FinancialRatiosBuilder:
    """
    Constructs the Financial Ratios Monthly presentation model.
    """

    def __init__(self, base_lf: dict[str, pl.LazyFrame]):
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        # Compute 3M averages for ratios
        lf_monthly_totals = lf_monthly_totals.sort("MONTH_START_DATE").with_columns(
            [
                pl.col("Total_Expense").rolling_mean(window_size=3).alias("3M_Avg_Total_Expense"),
                pl.col("Total_Income").rolling_mean(window_size=3).alias("3M_Avg_Total_Income"),
                pl.col("Total_Net_Worth").shift(12).alias("Prev_Year_NW"),
            ]
        )

        lf_ratios = lf_monthly_totals.with_columns(
            [
                pl.when(pl.col("Total_Income") > 0)
                .then((pl.col("Total_Income") - pl.col("Total_Expense")) / pl.col("Total_Income"))
                .otherwise(0.0)
                .alias("Savings_Rate_%"),
                pl.when(pl.col("3M_Avg_Total_Expense") > 0)
                .then(pl.col("Total_Assets") / pl.col("3M_Avg_Total_Expense"))
                .otherwise(0.0)
                .alias("Liquidity_Ratio_Months"),
                pl.when(pl.col("Total_Assets") > 0)
                .then(pl.col("Total_Liabilities") / pl.col("Total_Assets"))
                .otherwise(0.0)
                .alias("Debt_to_Asset_Ratio_%"),
                pl.when((pl.col("Prev_Year_NW").is_not_null()) & (pl.col("Prev_Year_NW") != 0))
                .then((pl.col("Total_Net_Worth") - pl.col("Prev_Year_NW")) / pl.col("Prev_Year_NW"))
                .otherwise(0.0)
                .alias("YoY_Net_Worth_Growth_%"),
                pl.when(pl.col("3M_Avg_Total_Expense") > 0)
                .then(pl.col("Total_Assets") / (25 * 12 * pl.col("3M_Avg_Total_Expense")))
                .otherwise(0.0)
                .alias("FIRE_Progress_%"),
            ]
        )

        # Add real metrics
        lf_ratios = lf_ratios.with_columns(
            (
                (
                    (1 + pl.col("YoY_Net_Worth_Growth_%"))
                    / (1 + (pl.col("INFLATION_YOY_PCT") / 100.0))
                )
                - 1
            ).alias("YoY_Net_Worth_Growth_%_Real"),
            (
                pl.col("Total_Assets")
                / (
                    25
                    * 12
                    * (pl.col("3M_Avg_Total_Expense") * (pl.col("CPI_INDEX") / pl.lit(151.4)))
                )
            ).alias("FIRE_Progress_%_Real"),
        )

        lf_ratios = lf_ratios.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "Savings_Rate_%",
                "Liquidity_Ratio_Months",
                "Debt_to_Asset_Ratio_%",
                "FIRE_Progress_%",
                "YoY_Net_Worth_Growth_%",
                "Total_Assets",
                "Total_Liabilities",
                "Total_Net_Worth",
                "YoY_Net_Worth_Growth_%_Real",
                "FIRE_Progress_%_Real",
            ]
        )
        return lf_ratios
