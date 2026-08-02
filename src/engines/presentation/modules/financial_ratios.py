from typing import Any

import polars as pl


class FinancialRatiosBuilder:
    """
    Constructs the Financial Ratios Monthly presentation model.
    """

    def __init__(self, base_lf: dict[str, Any], rules=None):
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]
        cpi_base = self.base_lf.get("cpi_base", 151.4)
        swr = 25.0
        if self.rules and self.rules.assumptions:
            swr = self.rules.assumptions.fire.swr_multiplier

        # Compute 3M averages for ratios
        lf_monthly_totals = lf_monthly_totals.sort("MONTH_START_DATE").with_columns(
            [
                pl.col("Total_Expense").rolling_mean(window_size=3).alias("3M_Avg_Total_Expense"),
                pl.col("Total_Core_Expense")
                .rolling_mean(window_size=3)
                .alias("3M_Avg_Total_Core_Expense"),
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
                .then(pl.col("Total_Assets") / (swr * 12 * pl.col("3M_Avg_Total_Core_Expense")))
                .alias("FIRE_Progress_%"),
                pl.when(pl.col("Total_Net_Worth") > 0)
                .then(pl.col("Total_Expense") / pl.col("Total_Net_Worth"))
                .otherwise(0.0)
                .alias("Expense_to_NW_Ratio"),
                pl.when(pl.col("Total_Liabilities") > 0)
                .then(pl.col("Total_Income") / pl.col("Total_Liabilities"))
                .otherwise(999.0)
                .alias("Debt_Service_Coverage"),
                pl.when(pl.col("Months_Elapsed") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Months_Elapsed"))
                .otherwise(0.0)
                .alias("Net_Worth_per_Month_Age"),
                pl.when(pl.col("3M_Avg_Total_Expense") > 0)
                .then(pl.col("Total_Net_Worth") / (pl.col("3M_Avg_Total_Expense") * 4))
                .otherwise(0.0)
                .alias("Net_Worth_to_Annual_Expense_Ratio"),
                pl.when(pl.col("Total_Income") > 0)
                .then(
                    (pl.col("Total_Income") - pl.col("Total_Core_Expense")) / pl.col("Total_Income")
                )
                .otherwise(0.0)
                .alias("Income_Surplus_Rate_%"),
                pl.when(pl.col("Total_Liabilities") > 0)
                .then(pl.col("Total_Assets") / pl.col("Total_Liabilities"))
                .otherwise(999.0)
                .alias("Liability_Coverage_Ratio"),
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
                / (
                    swr
                    * 12
                    * (
                        pl.col("3M_Avg_Total_Core_Expense")
                        / (pl.col("CPI_INDEX") / pl.lit(cpi_base))
                    )
                )
            ).alias("FIRE_Progress_%_Real"),
            pl.when(pl.col("Total_Real_Income") > 0)
            .then(
                (pl.col("Total_Real_Income") - pl.col("Total_Real_Expense"))
                / pl.col("Total_Real_Income")
            )
            .otherwise(0.0)
            .alias("Real_Savings_Rate_%"),
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
                "Total_Assets_Market",
                "Total_Liabilities",
                "Total_Net_Worth",
                "Total_Net_Worth_Market",
                "YoY_Net_Worth_Growth_%_Real",
                "FIRE_Progress_%_Real",
                "Expense_to_NW_Ratio",
                "Debt_Service_Coverage",
                "Emergency_Fund_Coverage",
                "Net_Worth_per_Month_Age",
                "Real_Savings_Rate_%",
                "Net_Worth_to_Annual_Expense_Ratio",
                "Income_Surplus_Rate_%",
                "Liability_Coverage_Ratio",
            ]
        )
        return lf_ratios
