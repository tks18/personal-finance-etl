"""Household Monthly Cashflow Summary analytical builder.

Owns
----
- MonthlyCashflowSummaryBuilder: Consolidates income, expense, and investment deployments into monthly surplus and savings rates.

Does not own
-------------
- Direct method cashflow statement reconciliation (owned by domain.household.cashflow.statement).
- Budget target rules configuration (owned by config.financial_rules.household).
- Presentation layer dispatching (owned by application.wealth.wealth_service).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.polars import pct_growth, rolling_avg, safe_divide

__all__ = ["MonthlyCashflowSummaryBuilder"]


class MonthlyCashflowSummaryBuilder:
    """Builds p_tf_Monthly_Cashflow_Summary.

    A single wide row per month that consolidates income, expenses,
    investment flows, surplus, savings rates, and financial health ratios.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: Mapping[str, pl.LazyFrame],
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def _enrich_income_streams(self, lf_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Bifurcate income into active, dividend, interest, and passive components."""
        lf_inc_raw = self.base_lf.get("lf_inc_agg")
        if isinstance(lf_inc_raw, pl.LazyFrame):
            lf_inc_split = (
                lf_inc_raw.with_columns(
                    pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                )
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.col("INCOME").sum().fill_null(0.0).alias("Total_Income_Check"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Active_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Active_Income"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Dividend_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Dividend_Income"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Interest_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Interest_Income"),
                )
                .with_columns(
                    (pl.col("Dividend_Income") + pl.col("Interest_Income")).alias("Passive_Income"),
                )
            )
            lf_joined = lf_monthly.join(lf_inc_split, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            return lf_joined.with_columns(
                pl.col("Active_Income").fill_null(0.0),
                pl.col("Dividend_Income").fill_null(0.0),
                pl.col("Interest_Income").fill_null(0.0),
                pl.col("Passive_Income").fill_null(0.0),
            )

        return lf_monthly.with_columns(
            pl.lit(0.0).alias("Active_Income"),
            pl.lit(0.0).alias("Passive_Income"),
            pl.lit(0.0).alias("Dividend_Income"),
            pl.lit(0.0).alias("Interest_Income"),
        )

    def _calculate_investments_deployed(self, lf_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Aggregate purchases into equity, stocks, ETFs, and MF deployed categories."""
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_master = self.dfs.get("df_d_investment_master")
        if df_buys is not None and df_master is not None:
            lf_buys = df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            lf_master = df_master.lazy() if isinstance(df_master, pl.DataFrame) else df_master
            lf_buys_enriched = lf_buys.join(
                lf_master.select(["ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_TYPE"]),
                on="ISIN",
                how="left",
            ).with_columns(
                pl.col("Date").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("INSTRUMENT_CLASS").fill_null("Unknown"),
                pl.col("INSTRUMENT_TYPE").fill_null("Unknown"),
            )

            lf_inv_deployed = (
                lf_buys_enriched.group_by("MONTH_START_DATE")
                .agg(
                    pl.col("Value").sum().fill_null(0.0).alias("Total_Investment_Deployed"),
                    pl.col("Value")
                    .filter(
                        pl.col("INSTRUMENT_CLASS")
                        .str.to_lowercase()
                        .str.contains("(?i)stocks|etfs")
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("Equity_Deployed"),
                    pl.col("Value")
                    .filter(
                        pl.col("INSTRUMENT_CLASS")
                        .str.to_lowercase()
                        .str.contains("(?i)direct|stock")
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("Stocks_Deployed"),
                    pl.col("Value")
                    .filter(pl.col("INSTRUMENT_CLASS").str.to_lowercase().str.contains("etf"))
                    .sum()
                    .fill_null(0.0)
                    .alias("ETFs_Deployed"),
                    pl.col("Value")
                    .filter(
                        pl.col("INSTRUMENT_CLASS")
                        .str.to_lowercase()
                        .str.contains("(?i)mutual|fund")
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("MF_Deployed"),
                )
                .with_columns(
                    (
                        pl.col("Total_Investment_Deployed")
                        - pl.col("Equity_Deployed")
                        - pl.col("MF_Deployed")
                    )
                    .clip(lower_bound=0.0)
                    .alias("Other_Deployed"),
                )
            )
            lf_monthly = lf_monthly.join(lf_inv_deployed, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            return lf_monthly.with_columns(
                pl.col("Total_Investment_Deployed").fill_null(0.0),
                pl.col("Equity_Deployed").fill_null(0.0),
                pl.col("Stocks_Deployed").fill_null(0.0),
                pl.col("ETFs_Deployed").fill_null(0.0),
                pl.col("MF_Deployed").fill_null(0.0),
                pl.col("Other_Deployed").fill_null(0.0),
            )

        return lf_monthly.with_columns(
            pl.lit(0.0).alias("Total_Investment_Deployed"),
            pl.lit(0.0).alias("Equity_Deployed"),
            pl.lit(0.0).alias("Stocks_Deployed"),
            pl.lit(0.0).alias("ETFs_Deployed"),
            pl.lit(0.0).alias("MF_Deployed"),
            pl.lit(0.0).alias("Other_Deployed"),
        )

    def _calculate_investments_redeemed(self, lf_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Aggregate sales and capital gains into redemption metrics."""
        df_sells = self.dfs.get("df_f_tf_inv_sale")
        if df_sells is not None:
            lf_sells = df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            lf_inv_redeemed = (
                lf_sells.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.col("Sell_Value").sum().fill_null(0.0).alias("Total_Investment_Redeemed"),
                    pl.col("Total_PnL").sum().fill_null(0.0).alias("Redemption_Gain_Loss_Value"),
                )
            )
            lf_monthly = lf_monthly.join(lf_inv_redeemed, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            return lf_monthly.with_columns(
                pl.col("Total_Investment_Redeemed").fill_null(0.0),
                pl.col("Redemption_Gain_Loss_Value").fill_null(0.0),
            )

        return lf_monthly.with_columns(
            pl.lit(0.0).alias("Total_Investment_Redeemed"),
            pl.lit(0.0).alias("Redemption_Gain_Loss_Value"),
        )

    def _compute_surplus_and_rates(self, lf_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Compute surplus, investment flows, and budget allocation share percentages."""
        return lf_monthly.with_columns(
            (pl.col("Total_Investment_Deployed") - pl.col("Total_Investment_Redeemed")).alias(
                "Net_Investment_Flow"
            ),
            (pl.col("Total_Cash_Income") - pl.col("Total_Expense")).alias("Gross_Surplus"),
        ).with_columns(
            (pl.col("Gross_Surplus") - pl.col("Net_Investment_Flow")).alias(
                "Net_Surplus_After_Invest"
            ),
            safe_divide("Gross_Surplus", "Total_Cash_Income").alias("Savings_Rate_Pct"),
            safe_divide("Net_Investment_Flow", "Total_Cash_Income").alias("Investment_Rate_Pct"),
            safe_divide("Active_Income", "Total_Cash_Income").alias("Active_Income_Share_Pct"),
            safe_divide("Passive_Income", "Total_Cash_Income").alias("Passive_Income_Share_Pct"),
            safe_divide("Total_Core_Expense", "Total_Expense").alias("Core_Expense_Share_Pct"),
            safe_divide("NonCore_Expense", "Total_Expense").alias("NonCore_Expense_Share_Pct"),
            safe_divide("Equity_Deployed", "Total_Investment_Deployed").alias(
                "Equity_Pct_of_Deployed"
            ),
            safe_divide("MF_Deployed", "Total_Investment_Deployed").alias("MF_Pct_of_Deployed"),
        )

    def _compute_trailing_and_ratios(self, lf_monthly: pl.LazyFrame) -> pl.LazyFrame:
        """Compute MoM changes, 3M trailing averages, and wealth health ratios."""
        lf_monthly = lf_monthly.sort("MONTH_START_DATE").with_columns(
            (pl.col("Total_Cash_Income") - pl.col("Total_Cash_Income").shift(1)).alias(
                "Income_MoM_Delta"
            ),
            (pl.col("Total_Expense") - pl.col("Total_Expense").shift(1)).alias("Expense_MoM_Delta"),
            (pl.col("Net_Investment_Flow") - pl.col("Net_Investment_Flow").shift(1)).alias(
                "Investment_MoM_Delta"
            ),
            pct_growth("Total_Cash_Income", 1, None).alias("Income_MoM_Pct"),
            pct_growth("Total_Expense", 1, None).alias("Expense_MoM_Pct"),
        )

        lf_monthly = lf_monthly.with_columns(
            rolling_avg("Total_Cash_Income", 3).alias("Trailing_3M_Avg_Income"),
            rolling_avg("Total_Expense", 3).alias("Trailing_3M_Avg_Expense"),
            rolling_avg("Net_Investment_Flow", 3).alias("Trailing_3M_Avg_Investment"),
            rolling_avg("Savings_Rate_Pct", 3).alias("Trailing_3M_Avg_Savings_Rate"),
            rolling_avg("Investment_Rate_Pct", 3).alias("Trailing_3M_Avg_Investment_Rate"),
            rolling_avg("Total_Core_Expense", 12).alias("12M_Avg_Total_Core_Expense"),
            pl.col("Total_Net_Worth_Market").shift(12).alias("Prev_Year_NW_Market"),
        )

        return lf_monthly.with_columns(
            [
                safe_divide("Liquid_Assets_Market", "Trailing_3M_Avg_Expense").alias(
                    "Liquidity_Ratio_Months"
                ),
                safe_divide("Total_Liabilities", "Total_Assets_Market").alias(
                    "Debt_to_Asset_Ratio_Pct"
                ),
                pct_growth("Total_Net_Worth_Market", 12).alias("YoY_Net_Worth_Growth_Pct"),
                safe_divide("Total_Expense", "Total_Net_Worth_Market").alias("Expense_to_NW_Ratio"),
                safe_divide("Liquid_Assets_Market", "12M_Avg_Total_Core_Expense").alias(
                    "Emergency_Fund_Coverage"
                ),
            ]
        ).with_columns(
            (
                ((1 + pl.col("YoY_Net_Worth_Growth_Pct")) / (1 + pl.col("INFLATION_YOY_PCT"))) - 1
            ).alias("YoY_Net_Worth_Growth_Pct_Real"),
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
            (pl.col("Gross_Surplus") > 0).alias("Is_Surplus_Month"),
            (
                pl.col("Net_Investment_Flow")
                >= pl.col("Total_Cash_Income") * self.rules.budget.income_allocation.investment_pct
            ).alias("Is_Investment_Target_Met"),
            pl.col("Total_Net_Worth").shift(1).fill_null(0.0).alias("Opening_Balance_Asset"),
            pl.col("Total_Net_Worth").alias("Closing_Balance_Asset"),
            pl.col("Total_Net_Worth_Market").alias("Closing_Balance_Asset_Market"),
        )

    def build(self) -> pl.LazyFrame:
        """Build the Monthly Cashflow Summary LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Monthly Cashflow Summary schema.
        """
        lf_monthly_raw = self.base_lf.get("lf_monthly_totals")
        if not isinstance(lf_monthly_raw, pl.LazyFrame):
            return pl.LazyFrame()

        lf_monthly = self._enrich_income_streams(lf_monthly_raw)
        lf_monthly = lf_monthly.with_columns(
            (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias("NonCore_Expense"),
            pl.col("Total_Core_Expense").alias("Core_Expense"),
        )
        lf_monthly = self._calculate_investments_deployed(lf_monthly)
        lf_monthly = self._calculate_investments_redeemed(lf_monthly)
        lf_monthly = self._compute_surplus_and_rates(lf_monthly)
        lf_monthly = self._compute_trailing_and_ratios(lf_monthly)

        return lf_monthly.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "Total_Income",
                "Total_Cash_Income",
                "Total_Non_Cash_Income",
                "Total_Expense",
                "Active_Income",
                "Passive_Income",
                "Dividend_Income",
                "Interest_Income",
                "Core_Expense",
                "NonCore_Expense",
                "Total_Cash_Expense",
                "Total_Non_Cash_Expense",
                "Total_Investment_Deployed",
                "Total_Investment_Redeemed",
                "Redemption_Gain_Loss_Value",
                "Net_Investment_Flow",
                "Gross_Surplus",
                "Net_Surplus_After_Invest",
                "Savings_Rate_Pct",
                "Investment_Rate_Pct",
                "Active_Income_Share_Pct",
                "Passive_Income_Share_Pct",
                "Core_Expense_Share_Pct",
                "NonCore_Expense_Share_Pct",
                "Income_MoM_Delta",
                "Expense_MoM_Delta",
                "Investment_MoM_Delta",
                "Income_MoM_Pct",
                "Expense_MoM_Pct",
                "Trailing_3M_Avg_Income",
                "Trailing_3M_Avg_Expense",
                "Trailing_3M_Avg_Investment",
                "Trailing_3M_Avg_Savings_Rate",
                "Trailing_3M_Avg_Investment_Rate",
                "Is_Surplus_Month",
                "Is_Investment_Target_Met",
                "Liquidity_Ratio_Months",
                "Debt_to_Asset_Ratio_Pct",
                "YoY_Net_Worth_Growth_Pct",
                "YoY_Net_Worth_Growth_Pct_Real",
                "Expense_to_NW_Ratio",
                "Emergency_Fund_Coverage",
            ]
        )
