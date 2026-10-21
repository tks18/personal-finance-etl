"""Household Cashflow Statement direct-method builder.

Owns
----
- CashflowStatementBuilder: Reconciles direct method cashflows across CASH_POOL assets.

Does not own
-------------
- Monthly cashflow summary or savings rate computations (owned by domain.household.cashflow.summary).
- Budget target rules configuration (owned by config.financial_rules.household).
- Presentation layer dispatching (owned by application.wealth.wealth_service).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import ensure_date_col

__all__ = ["CashflowStatementBuilder"]


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

    def _prepare_cash_balances(
        self,
        lf_balances: pl.LazyFrame | None,
        lf_asset: pl.LazyFrame,
        lf_months: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Calculate opening/closing cash pool balances and net cash movement."""
        if lf_balances is not None:
            return (
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
        return lf_months.with_columns(
            pl.lit(0.0).alias("Opening_Cash_Balance"),
            pl.lit(0.0).alias("Closing_Cash_Balance"),
            pl.lit(0.0).alias("Net_Cash_Movement"),
        )

    def _prepare_operating_flows(
        self,
        lf_inc: pl.LazyFrame,
        lf_exp: pl.LazyFrame,
        lf_asset: pl.LazyFrame,
    ) -> tuple[pl.LazyFrame, pl.LazyFrame]:
        """Aggregate monthly cash operating income inflows and expense outflows."""
        lf_cash_inc = (
            lf_inc.join(lf_asset, left_on="ASSET_ID", right_on="UID", how="left")
            .filter(pl.col("is_cash_pool").fill_null(False))
            .with_columns(pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"))
            .group_by("MONTH_START_DATE")
            .agg(pl.col("BASE_AMOUNT").sum().fill_null(0.0).alias("Cash_Inflow_Operating_Inc"))
        )

        lf_cash_exp = (
            lf_exp.join(lf_asset, left_on="ASSET_ID", right_on="UID", how="left")
            .filter(pl.col("is_cash_pool").fill_null(False))
            .with_columns(pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"))
            .group_by("MONTH_START_DATE")
            .agg(pl.col("BASE_AMOUNT").sum().fill_null(0.0).alias("Cash_Outflow_Operating_Exp"))
        )
        return lf_cash_inc, lf_cash_exp

    def _prepare_expense_totals(self, lf_months: pl.LazyFrame) -> pl.LazyFrame:
        """Extract total cash and non-cash expense series from monthly totals."""
        lf_monthly_totals_raw = self.base_lf.get("lf_monthly_totals")
        if isinstance(lf_monthly_totals_raw, pl.LazyFrame):
            return lf_monthly_totals_raw.select(
                [
                    "MONTH_START_DATE",
                    pl.col("Total_Cash_Expense").alias("Total_Cash_Expenses"),
                    pl.col("Total_Non_Cash_Expense").alias("Total_Non_Cash_Expenses"),
                ]
            )
        return lf_months.with_columns(
            pl.lit(0.0).alias("Total_Cash_Expenses"),
            pl.lit(0.0).alias("Total_Non_Cash_Expenses"),
        ).select(["MONTH_START_DATE", "Total_Cash_Expenses", "Total_Non_Cash_Expenses"])

    def _prepare_transfer_flows(
        self,
        lf_trn: pl.LazyFrame,
        lf_asset: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Aggregate monthly transfers by counterparty activity type."""
        lf_cash_trn = (
            lf_trn.join(
                lf_asset.select(["UID", "is_cash_pool"]),
                left_on="ASSET_ID",
                right_on="UID",
                how="left",
            )
            .filter(pl.col("is_cash_pool").fill_null(False))
            .join(
                lf_asset.select(["UID", "cashflow_activity_type"]).rename(
                    {"cashflow_activity_type": "counterparty_type"}
                ),
                left_on="TO_ASSET_ID",
                right_on="UID",
                how="left",
            )
            .with_columns(
                pl.col("counterparty_type").fill_null("UNCLASSIFIED"),
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
            )
        )

        return lf_cash_trn.group_by("MONTH_START_DATE").agg(
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

    def _assemble_statement(
        self,
        lf_months: pl.LazyFrame,
        lf_cash_balances: pl.LazyFrame,
        lf_cash_inc: pl.LazyFrame,
        lf_cash_exp: pl.LazyFrame,
        lf_expense_totals: pl.LazyFrame,
        lf_trn_agg: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Combine cash activity components and compute totals and reconciliations."""
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

        return (
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
            .select(
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
        )

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
        lf_balances = lf_balances_raw if isinstance(lf_balances_raw, pl.LazyFrame) else None

        lf_cash_balances = self._prepare_cash_balances(lf_balances, lf_asset, lf_months)
        lf_cash_inc, lf_cash_exp = self._prepare_operating_flows(lf_inc, lf_exp, lf_asset)
        lf_expense_totals = self._prepare_expense_totals(lf_months)
        lf_trn_agg = self._prepare_transfer_flows(lf_trn, lf_asset)

        return self._assemble_statement(
            lf_months,
            lf_cash_balances,
            lf_cash_inc,
            lf_cash_exp,
            lf_expense_totals,
            lf_trn_agg,
        )
