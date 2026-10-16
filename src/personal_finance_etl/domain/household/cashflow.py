"""Household Cashflow Statement and Monthly Cashflow Summary builders.

Owns
----
- CashflowStatementBuilder: Reconciles direct method cashflows across CASH_POOL assets.
- MonthlyCashflowSummaryBuilder: Consolidates income, expense, and investment deployments into monthly surplus and savings rates.

Does not own
-------------
- Budget target rules configuration (owned by config.financial_rules.household).
- FIFO queue processing (owned by domain.investments.lots.fifo).
- Presentation layer dispatching (owned by application.wealth.wealth_service).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import ensure_date_col
from personal_finance_etl.domain.common.polars import pct_growth, rolling_avg, safe_divide

__all__ = ["CashflowStatementBuilder", "MonthlyCashflowSummaryBuilder"]


class CashflowStatementBuilder:
    """Constructs the Cashflow_Statement presentation model.

    Direct Method cash flow statement that reconciles opening and closing
    balances of CASH_POOL assets.
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

    def build(self) -> pl.LazyFrame:
        """Build the Cashflow Statement LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Cashflow Statement schema.
        """
        d_asset = self.dfs.get("df_d_asset_subcategory")
        if d_asset is None:
            return pl.LazyFrame()

        lf_asset = d_asset.lazy() if isinstance(d_asset, pl.DataFrame) else d_asset
        lf_asset = lf_asset.select(
            ["UID", "is_cash_pool", "cashflow_activity_type", "is_non_cash_pnl"]
        )

        lf_inc_df = self.dfs.get("df_f_income_transactions")
        lf_exp_df = self.dfs.get("df_f_expense_transactions")
        lf_trn_df = self.dfs.get("df_f_transfer_transactions")

        lf_months_raw = self.base_lf.get("lf_months")
        if (
            lf_inc_df is None
            or lf_exp_df is None
            or lf_trn_df is None
            or not isinstance(lf_months_raw, pl.LazyFrame)
        ):
            return pl.LazyFrame()
        lf_months: pl.LazyFrame = lf_months_raw

        lf_inc = ensure_date_col(
            lf_inc_df.lazy() if isinstance(lf_inc_df, pl.DataFrame) else lf_inc_df, "DATE"
        )
        lf_exp = ensure_date_col(
            lf_exp_df.lazy() if isinstance(lf_exp_df, pl.DataFrame) else lf_exp_df, "DATE"
        )
        lf_trn = ensure_date_col(
            lf_trn_df.lazy() if isinstance(lf_trn_df, pl.DataFrame) else lf_trn_df, "DATE"
        )

        lf_balances_raw = self.base_lf.get("lf_nw_summary")
        lf_balances: pl.LazyFrame | None = (
            lf_balances_raw if isinstance(lf_balances_raw, pl.LazyFrame) else None
        )

        # 1. Opening and Closing Cash Balances
        if lf_balances is not None:
            lf_cash_balances = (
                lf_balances.join(
                    lf_asset, left_on="ASSET_SUBCATEGORY_ID", right_on="UID", how="left"
                )
                .filter(pl.col("is_cash_pool").fill_null(False))
                .group_by("MONTH_END_DATE")
                .agg(
                    pl.col("Closing_Balance").sum().fill_null(0.0).alias("Closing_Cash_Balance"),
                    pl.col("Opening_Balance").sum().fill_null(0.0).alias("Opening_Cash_Balance"),
                )
                .sort("MONTH_END_DATE")
                .with_columns(
                    (pl.col("Closing_Cash_Balance") - pl.col("Opening_Cash_Balance")).alias(
                        "Net_Cash_Movement"
                    )
                )
            )
        else:
            lf_cash_balances = lf_months.with_columns(
                pl.lit(0.0).alias("Opening_Cash_Balance"),
                pl.lit(0.0).alias("Closing_Cash_Balance"),
                pl.lit(0.0).alias("Net_Cash_Movement"),
            )

        # 2. Income (Operating Inflows)
        lf_cash_inc = (
            lf_inc.join(lf_asset, left_on="ASSET_ID", right_on="UID", how="left")
            .filter(pl.col("is_cash_pool").fill_null(False))
            .with_columns(pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"))
            .group_by("MONTH_START_DATE")
            .agg(pl.col("BASE_AMOUNT").sum().fill_null(0.0).alias("Cash_Inflow_Operating_Inc"))
        )

        # 3. Expenses (Operating Outflows)
        lf_cash_exp = (
            lf_exp.join(lf_asset, left_on="ASSET_ID", right_on="UID", how="left")
            .filter(pl.col("is_cash_pool").fill_null(False))
            .with_columns(pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"))
            .group_by("MONTH_START_DATE")
            .agg(pl.col("BASE_AMOUNT").sum().fill_null(0.0).alias("Cash_Outflow_Operating_Exp"))
        )

        # Monthly expense totals
        lf_monthly_totals_raw = self.base_lf.get("lf_monthly_totals")
        lf_monthly_totals: pl.LazyFrame | None = (
            lf_monthly_totals_raw if isinstance(lf_monthly_totals_raw, pl.LazyFrame) else None
        )
        if lf_monthly_totals is not None:
            lf_expense_totals = lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    pl.col("Total_Cash_Expense").alias("Total_Cash_Expenses"),
                    pl.col("Total_Non_Cash_Expense").alias("Total_Non_Cash_Expenses"),
                ]
            )
        else:
            lf_expense_totals = lf_months.with_columns(
                pl.lit(0.0).alias("Total_Cash_Expenses"),
                pl.lit(0.0).alias("Total_Non_Cash_Expenses"),
            ).select(["MONTH_START_DATE", "Total_Cash_Expenses", "Total_Non_Cash_Expenses"])

        # 4. Transfers
        lf_cash_trn = lf_trn.join(
            lf_asset.select(["UID", "is_cash_pool"]), left_on="ASSET_ID", right_on="UID", how="left"
        ).filter(pl.col("is_cash_pool").fill_null(False))

        lf_cash_trn = lf_cash_trn.join(
            lf_asset.select(["UID", "cashflow_activity_type"]).rename(
                {"cashflow_activity_type": "counterparty_type"}
            ),
            left_on="TO_ASSET_ID",
            right_on="UID",
            how="left",
        ).with_columns(
            pl.col("counterparty_type").fill_null("UNCLASSIFIED"),
            pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
        )

        lf_trn_agg = lf_cash_trn.group_by("MONTH_START_DATE").agg(
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "OPERATING") & (pl.col("AMOUNT_PROPER") > 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Inflow_Operating_Trn"),
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "OPERATING") & (pl.col("AMOUNT_PROPER") < 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Outflow_Operating_Trn"),
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "INVESTING") & (pl.col("AMOUNT_PROPER") > 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Inflow_Investing"),
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "INVESTING") & (pl.col("AMOUNT_PROPER") < 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Outflow_Investing"),
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "FINANCING") & (pl.col("AMOUNT_PROPER") > 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Inflow_Financing"),
            pl.col("AMOUNT_PROPER")
            .filter((pl.col("counterparty_type") == "FINANCING") & (pl.col("AMOUNT_PROPER") < 0))
            .sum()
            .fill_null(0.0)
            .alias("Cash_Outflow_Financing"),
            pl.col("AMOUNT_PROPER")
            .filter(
                (pl.col("counterparty_type") == "INTERNAL_TRANSFER") & (pl.col("AMOUNT_PROPER") > 0)
            )
            .sum()
            .fill_null(0.0)
            .alias("Internal_Transfer_Inflow"),
            pl.col("AMOUNT_PROPER")
            .filter(
                (pl.col("counterparty_type") == "INTERNAL_TRANSFER") & (pl.col("AMOUNT_PROPER") < 0)
            )
            .sum()
            .fill_null(0.0)
            .alias("Internal_Transfer_Outflow"),
        )

        # 5. Assemble statement
        lf_statement = (
            lf_months.join(lf_cash_balances, on="MONTH_END_DATE", how="left")
            .join(lf_cash_inc, on="MONTH_START_DATE", how="left")
            .join(lf_cash_exp, on="MONTH_START_DATE", how="left")
            .join(lf_expense_totals, on="MONTH_START_DATE", how="left")
            .join(lf_trn_agg, on="MONTH_START_DATE", how="left")
            .fill_null(0.0)
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
            )
        )

        # 6. Totals and Reconciliations
        lf_statement = (
            lf_statement.with_columns(
                (pl.col("Cash_Inflow_Operating_Inc") + pl.col("Cash_Inflow_Operating_Trn")).alias(
                    "Cash_Inflow_Operating"
                ),
                (
                    pl.col("Cash_Outflow_Operating_Exp")
                    + pl.col("Cash_Outflow_Operating_Trn").abs()
                ).alias("Cash_Outflow_Operating"),
                pl.col("Cash_Outflow_Investing").abs().alias("Cash_Outflow_Investing"),
                pl.col("Cash_Outflow_Financing").abs().alias("Cash_Outflow_Financing"),
                pl.col("Internal_Transfer_Outflow").abs().alias("Internal_Transfer_Outflow"),
            )
            .with_columns(
                (pl.col("Cash_Inflow_Operating") - pl.col("Cash_Outflow_Operating")).alias(
                    "Net_Cashflow_Operating"
                ),
                (pl.col("Cash_Inflow_Investing") - pl.col("Cash_Outflow_Investing")).alias(
                    "Net_Cashflow_Investing"
                ),
                (pl.col("Cash_Inflow_Financing") - pl.col("Cash_Outflow_Financing")).alias(
                    "Net_Cashflow_Financing"
                ),
                (pl.col("Internal_Transfer_Inflow") - pl.col("Internal_Transfer_Outflow")).alias(
                    "Net_Internal_Transfers"
                ),
            )
            .with_columns(
                (
                    pl.col("Cash_Inflow_Operating")
                    + pl.col("Cash_Inflow_Investing")
                    + pl.col("Cash_Inflow_Financing")
                    + pl.col("Internal_Transfer_Inflow")
                ).alias("Total_Cash_Inflow"),
                (
                    pl.col("Cash_Outflow_Operating")
                    + pl.col("Cash_Outflow_Investing")
                    + pl.col("Cash_Outflow_Financing")
                    + pl.col("Internal_Transfer_Outflow")
                ).alias("Total_Cash_Outflow"),
                (
                    pl.col("Net_Cashflow_Operating")
                    + pl.col("Net_Cashflow_Investing")
                    + pl.col("Net_Cashflow_Financing")
                    + pl.col("Net_Internal_Transfers")
                ).alias("Calculated_Net_Cashflow"),
            )
            .with_columns(
                (pl.col("Net_Cash_Movement") - pl.col("Calculated_Net_Cashflow")).alias(
                    "Unreconciled_Difference"
                )
            )
        )

        return lf_statement.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "Opening_Cash_Balance",
                "Closing_Cash_Balance",
                "Net_Cash_Movement",
                "Cash_Inflow_Operating",
                "Cash_Outflow_Operating",
                "Net_Cashflow_Operating",
                "Cash_Inflow_Investing",
                "Cash_Outflow_Investing",
                "Net_Cashflow_Investing",
                "Cash_Inflow_Financing",
                "Cash_Outflow_Financing",
                "Net_Cashflow_Financing",
                "Internal_Transfer_Inflow",
                "Internal_Transfer_Outflow",
                "Net_Internal_Transfers",
                "Total_Cash_Expenses",
                "Total_Non_Cash_Expenses",
                "Total_Cash_Inflow",
                "Total_Cash_Outflow",
                "Calculated_Net_Cashflow",
                "Unreconciled_Difference",
            ]
        )


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
        lf_monthly: pl.LazyFrame = lf_monthly_raw

        # Step 1: Income bifurcation from lf_inc_agg
        lf_inc_raw = self.base_lf.get("lf_inc_agg")
        lf_inc_agg: pl.LazyFrame | None = (
            lf_inc_raw if isinstance(lf_inc_raw, pl.LazyFrame) else None
        )

        if lf_inc_agg is not None:
            lf_inc_split = (
                lf_inc_agg.with_columns(
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
            lf_monthly = lf_monthly.join(lf_inc_split, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            lf_monthly = lf_monthly.with_columns(
                pl.col("Active_Income").fill_null(0.0),
                pl.col("Dividend_Income").fill_null(0.0),
                pl.col("Interest_Income").fill_null(0.0),
                pl.col("Passive_Income").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(
                pl.lit(0.0).alias("Active_Income"),
                pl.lit(0.0).alias("Passive_Income"),
                pl.lit(0.0).alias("Dividend_Income"),
                pl.lit(0.0).alias("Interest_Income"),
            )

        # Step 2: Expense bifurcation
        lf_monthly = lf_monthly.with_columns(
            (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias("NonCore_Expense"),
            pl.col("Total_Core_Expense").alias("Core_Expense"),
        )

        # Step 3: Investment activity from purchase/sale facts
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")
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
            lf_monthly = lf_monthly.with_columns(
                pl.col("Total_Investment_Deployed").fill_null(0.0),
                pl.col("Equity_Deployed").fill_null(0.0),
                pl.col("Stocks_Deployed").fill_null(0.0),
                pl.col("ETFs_Deployed").fill_null(0.0),
                pl.col("MF_Deployed").fill_null(0.0),
                pl.col("Other_Deployed").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(
                pl.lit(0.0).alias("Total_Investment_Deployed"),
                pl.lit(0.0).alias("Equity_Deployed"),
                pl.lit(0.0).alias("Stocks_Deployed"),
                pl.lit(0.0).alias("ETFs_Deployed"),
                pl.lit(0.0).alias("MF_Deployed"),
                pl.lit(0.0).alias("Other_Deployed"),
            )

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
            lf_monthly = lf_monthly.with_columns(
                pl.col("Total_Investment_Redeemed").fill_null(0.0),
                pl.col("Redemption_Gain_Loss_Value").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(
                pl.lit(0.0).alias("Total_Investment_Redeemed"),
                pl.lit(0.0).alias("Redemption_Gain_Loss_Value"),
            )

        # Step 4: Net investment flow & surplus
        lf_monthly = lf_monthly.with_columns(
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

        # Step 5: MoM deltas
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

        # Step 6: Trailing averages (3M)
        lf_monthly = lf_monthly.with_columns(
            rolling_avg("Total_Cash_Income", 3).alias("Trailing_3M_Avg_Income"),
            rolling_avg("Total_Expense", 3).alias("Trailing_3M_Avg_Expense"),
            rolling_avg("Net_Investment_Flow", 3).alias("Trailing_3M_Avg_Investment"),
            rolling_avg("Savings_Rate_Pct", 3).alias("Trailing_3M_Avg_Savings_Rate"),
            rolling_avg("Investment_Rate_Pct", 3).alias("Trailing_3M_Avg_Investment_Rate"),
        )

        # Step 7: Financial Ratios Integration
        lf_monthly = lf_monthly.with_columns(
            [
                rolling_avg("Total_Core_Expense", 12).alias("12M_Avg_Total_Core_Expense"),
                pl.col("Total_Net_Worth_Market").shift(12).alias("Prev_Year_NW_Market"),
            ]
        )

        lf_monthly = lf_monthly.with_columns(
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
        )

        # Step 8: YEAR_MONTH, flags & derived ratios
        lf_monthly = lf_monthly.with_columns(
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
