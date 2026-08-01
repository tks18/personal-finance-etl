import polars as pl
from typing import Any


class FinancialRatiosBuilder:
    """
    Constructs the Financial Ratios Monthly presentation model.
    """

    def __init__(self, base_lf: dict[str, Any]):
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]
        cpi_base = self.base_lf.get("cpi_base", 151.4)

        # Compute 3M averages for ratios
        lf_monthly_totals = lf_monthly_totals.sort("MONTH_START_DATE").with_columns(
            [
                pl.col("Total_Expense").rolling_mean(window_size=3).alias("3M_Avg_Total_Expense"),
                pl.col("Total_Core_Expense").rolling_mean(window_size=3).alias("3M_Avg_Total_Core_Expense"),
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
                pl.when(pl.col("3M_Avg_Total_Core_Expense") > 0)
                .then(pl.col("Total_Assets") / pl.col("3M_Avg_Total_Core_Expense"))
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
                pl.when(pl.col("3M_Avg_Total_Core_Expense") > 0)
                .then(pl.col("Total_Assets") / (25 * 12 * pl.col("3M_Avg_Total_Core_Expense")))
                .alias("FIRE_Progress_%"),
                pl.when(pl.col("Total_Net_Worth") > 0)
                .then(pl.col("Total_Expense") / pl.col("Total_Net_Worth"))
                .otherwise(0.0).alias("Expense_to_NW_Ratio"),
                pl.when(pl.col("Total_Liabilities") > 0)
                .then(pl.col("Total_Income") / pl.col("Total_Liabilities"))
                .otherwise(999.0).alias("Debt_Service_Coverage"),
                pl.when(pl.col("Months_Elapsed") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Months_Elapsed"))
                .otherwise(0.0).alias("Net_Worth_per_Month_Age"),
                (pl.col("Total_Income") * 0.1 / pl.col("Total_Expense")).alias("Passive_Income_Ratio"),  # Proxy since passive income not fully joined
                (pl.col("Total_Income") * 0.1 / pl.col("Total_Core_Expense")).alias("Financial_Freedom_Ratio"),
            ]
        )

        # Add real metrics
        lf_ratios = lf_ratios.with_columns(
            pl.col("Liquidity_Ratio_Months").alias("Emergency_Fund_Coverage"),
            (
                (
                    (1 + pl.col("YoY_Net_Worth_Growth_%"))
                    / (1 + (pl.col("INFLATION_YOY_PCT") / 100.0))
                )
                - 1
            ).alias("YoY_Net_Worth_Growth_%_Real"),
            (
                (pl.col("Total_Assets") / (pl.col("CPI_INDEX") / pl.lit(cpi_base)))
                / (25 * 12 * pl.col("3M_Avg_Total_Core_Expense"))
            ).alias("FIRE_Progress_%_Real"),
            pl.col("Savings_Rate_%").alias("Real_Savings_Rate_%"),
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
                "Expense_to_NW_Ratio",
                "Debt_Service_Coverage",
                "Emergency_Fund_Coverage",
                "Net_Worth_per_Month_Age",
                "Passive_Income_Ratio",
                "Financial_Freedom_Ratio",
                "Real_Savings_Rate_%",
            ]
        )
        return lf_ratios
