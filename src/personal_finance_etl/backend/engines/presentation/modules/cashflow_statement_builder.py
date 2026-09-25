from collections.abc import Mapping
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.utils.helpers import ensure_date_col


class CashflowStatementBuilder:
    """
    Constructs the Cashflow_Statement presentation model.
    Direct Method cash flow statement that reconciles opening and closing
    balances of CASH_POOL assets.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules: FinancialRules,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
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

        lf_months = self.base_lf.get("lf_months")
        if lf_inc_df is None or lf_exp_df is None or lf_trn_df is None or lf_months is None:
            return pl.LazyFrame()

        lf_inc = ensure_date_col(
            lf_inc_df.lazy() if isinstance(lf_inc_df, pl.DataFrame) else lf_inc_df, "DATE"
        )
        lf_exp = ensure_date_col(
            lf_exp_df.lazy() if isinstance(lf_exp_df, pl.DataFrame) else lf_exp_df, "DATE"
        )
        lf_trn = ensure_date_col(
            lf_trn_df.lazy() if isinstance(lf_trn_df, pl.DataFrame) else lf_trn_df, "DATE"
        )

        # We need balances from net_worth_res to get opening and closing cash
        lf_balances = self.base_lf.get("lf_nw_summary")

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
            # Fallback if no balances
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

        # We need monthly totals to get the consistent definition of cash/non-cash expenses
        lf_monthly_totals = self.base_lf.get("lf_monthly_totals")
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

        # 4. Transfers (Can be any activity type based on TO_ASSET_ID)
        # First filter to where the source (ASSET_ID) is a cash pool.
        lf_cash_trn = lf_trn.join(
            lf_asset.select(["UID", "is_cash_pool"]), left_on="ASSET_ID", right_on="UID", how="left"
        ).filter(pl.col("is_cash_pool").fill_null(False))

        # Then join TO_ASSET_ID to get the counterparty activity type
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

        # Aggregate transfers by counterparty type and AMOUNT_PROPER sign
        lf_trn_agg = lf_cash_trn.group_by("MONTH_START_DATE").agg(
            # Operating
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
            # Investing
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
            # Financing
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
            # Internal Transfers
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

        # 5. Assemble the final statement
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

        # 6. Calculate Totals and Reconciliations
        lf_statement = (
            lf_statement.with_columns(
                (pl.col("Cash_Inflow_Operating_Inc") + pl.col("Cash_Inflow_Operating_Trn")).alias(
                    "Cash_Inflow_Operating"
                ),
                # Outflows should be positive absolute numbers for display, but AMOUNT_PROPER is negative for outflows, so take abs()
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

        return lf_statement.select(  # type: ignore[no-any-return]
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
