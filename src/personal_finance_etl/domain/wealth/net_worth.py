"""Household and investment Net Worth aggregation and valuation builder.

Owns
----
- NetWorthBuilder: Calculates monthly net worth summaries across all asset categories.
- Mark-to-market valuation combining book values with live investment and portfolio valuations.
- Organic yield, cumulative savings, and liquid asset runway metrics.

Does not own
-------------
- Raw transaction ledger aggregation (owned by domain.household.ledger).
- Historical inflation series alignment (owned by domain.fire.inflation).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import polars as pl

from personal_finance_etl.domain.fire.inflation import InflationCalendarResult
from personal_finance_etl.domain.wealth.market_valuation import inject_portfolio_market_values

__all__ = ["NetWorthBuilder"]


class NetWorthBuilder:
    """Calculates monthly asset balances, market valuations, liabilities, and net worth."""

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        inflation_res: InflationCalendarResult | Mapping[str, object],
        ledger_res: Mapping[str, pl.LazyFrame],
        default_currency_id: str,
    ) -> None:
        self.dfs = dfs
        self.inflation_res = inflation_res
        self.ledger_res = ledger_res
        self.default_currency_id = default_currency_id

    def build(self) -> dict[str, pl.LazyFrame]:
        """Build Net Worth analytical LazyFrames.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary containing:
            - lf_nw_summary: Monthly asset subcategory balances, market values, and organic yields.
            - lf_monthly_totals: Portfolio-level monthly total assets, liabilities, and market net worth.
        """
        d_asset = self.dfs.get("df_d_asset_subcategory")
        if d_asset is None:
            return {}

        lf_asset = d_asset.lazy() if isinstance(d_asset, pl.DataFrame) else d_asset
        lf_months = cast(pl.LazyFrame, self.inflation_res["lf_months"])

        lf_nw_summary = self._build_nw_summary(lf_asset, lf_months)
        lf_monthly_totals = self._build_monthly_totals(lf_nw_summary)

        return {
            "lf_nw_summary": lf_nw_summary.drop("Is_Liquid"),
            "lf_monthly_totals": lf_monthly_totals,
        }

    def _join_ledger_activity(
        self,
        lf_asset: pl.LazyFrame,
        lf_months: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Cross-join assets with months and join monthly activity and balance streams."""
        lf_activity = self.ledger_res["lf_activity"]
        lf_balances = self.ledger_res["lf_balances"]

        lf_assets_months = lf_months.join(
            lf_asset.select(
                [pl.col("UID").alias("ASSET_SUBCATEGORY_ID"), pl.col("Is_Liquid").fill_null(True)]
            ),
            how="cross",
        )

        return (
            lf_assets_months.join(
                lf_activity,
                on=["MONTH_START_DATE", "MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"],
                how="left",
            )
            .join(
                lf_balances,
                on=["MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"],
                how="left",
            )
            .with_columns(
                pl.col("Income_Inflow").fill_null(0.0),
                pl.col("Cash_Income_Inflow").fill_null(0.0),
                pl.col("Non_Cash_Income_Inflow").fill_null(0.0),
                pl.col("Expense_Outflow").fill_null(0.0),
                pl.col("Core_Expense_Outflow").fill_null(0.0),
                pl.col("Cash_Expense_Outflow").fill_null(0.0),
                pl.col("Non_Cash_Expense_Outflow").fill_null(0.0),
                pl.col("Net_Transfers").fill_null(0.0),
                pl.col("MONTHLY_NET_CHANGE").fill_null(0.0),
                pl.col("DB_Opening_Balance").fill_null(0.0),
            )
            .sort(["ASSET_SUBCATEGORY_ID", "MONTH_START_DATE"])
        )

    def _compute_balances_and_growth(self, lf_nw_summary: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate cumulative balances, net cashflows, organic yields, and drawdowns."""
        lf_nw_summary = (
            lf_nw_summary.with_columns(
                pl.col("MONTHLY_NET_CHANGE")
                .cum_sum()
                .over("ASSET_SUBCATEGORY_ID")
                .alias("Closing_Balance")
            )
            .with_columns(
                (
                    pl.col("Closing_Balance").shift(1).over("ASSET_SUBCATEGORY_ID").fill_null(0.0)
                    + pl.col("DB_Opening_Balance").fill_null(0.0)
                ).alias("Opening_Balance")
            )
            .drop(
                ["MONTHLY_NET_CHANGE", "MONTHLY_NET_CHANGE_right", "DB_Opening_Balance"],
                strict=False,
            )
        )

        return (
            lf_nw_summary.with_columns(
                (
                    pl.col("Income_Inflow") - pl.col("Expense_Outflow") + pl.col("Net_Transfers")
                ).alias("Net_Cashflow_Month"),
                (pl.col("Income_Inflow") - pl.col("Expense_Outflow")).alias(
                    "Surplus_Deficit_Month"
                ),
            )
            .with_columns(
                pl.when(pl.col("Surplus_Deficit_Month") > 0)
                .then(pl.col("Net_Transfers") / pl.col("Surplus_Deficit_Month"))
                .otherwise(0.0)
                .alias("Investment_Contribution_Pct"),
                (
                    pl.col("Closing_Balance")
                    - (pl.col("Opening_Balance") + pl.col("Net_Cashflow_Month"))
                ).alias("Organic_Growth_Value"),
                pl.col("Net_Cashflow_Month")
                .cum_sum()
                .over("ASSET_SUBCATEGORY_ID")
                .alias("Cumulative_Net_Savings"),
                pl.col("Closing_Balance")
                .cum_max()
                .over("ASSET_SUBCATEGORY_ID")
                .alias("All_Time_High_Balance"),
            )
            .with_columns(
                pl.when(pl.col("Opening_Balance") != 0)
                .then(pl.col("Organic_Growth_Value") / pl.col("Opening_Balance"))
                .otherwise(0.0)
                .alias("Organic_Yield_%"),
                pl.when(pl.col("Opening_Balance") != 0)
                .then(
                    (pl.col("Closing_Balance") - pl.col("Opening_Balance"))
                    / pl.col("Opening_Balance")
                )
                .otherwise(0.0)
                .alias("MoM_Balance_Growth_%"),
                pl.when(pl.col("Closing_Balance") > 0)
                .then(pl.col("Cumulative_Net_Savings") / pl.col("Closing_Balance"))
                .otherwise(0.0)
                .alias("Savings_to_NW_Ratio"),
                pl.when(pl.col("All_Time_High_Balance") > 0)
                .then(
                    (pl.col("Closing_Balance") - pl.col("All_Time_High_Balance"))
                    / pl.col("All_Time_High_Balance")
                )
                .otherwise(0.0)
                .alias("Drawdown_From_Peak"),
            )
        )

    def _compute_runway_metrics(self, lf_nw_summary: pl.LazyFrame) -> pl.LazyFrame:
        """Compute rolling 3M averages, YoY balance growth, and runway months."""
        return (
            lf_nw_summary.sort(["ASSET_SUBCATEGORY_ID", "MONTH_START_DATE"])
            .with_columns(
                [
                    pl.col("Expense_Outflow")
                    .rolling_mean(window_size=3)
                    .over("ASSET_SUBCATEGORY_ID")
                    .alias("3M_Avg_Expense"),
                    pl.col("Core_Expense_Outflow")
                    .rolling_mean(window_size=3)
                    .over("ASSET_SUBCATEGORY_ID")
                    .alias("3M_Avg_Core_Expense"),
                    pl.col("Income_Inflow")
                    .rolling_mean(window_size=3)
                    .over("ASSET_SUBCATEGORY_ID")
                    .alias("3M_Avg_Income"),
                    pl.col("Closing_Balance")
                    .shift(12)
                    .over("ASSET_SUBCATEGORY_ID")
                    .alias("Prev_Year_Balance"),
                ]
            )
            .with_columns(
                pl.when(
                    pl.col("Prev_Year_Balance").is_not_null() & (pl.col("Prev_Year_Balance") != 0)
                )
                .then(
                    (pl.col("Closing_Balance") - pl.col("Prev_Year_Balance"))
                    / pl.col("Prev_Year_Balance")
                )
                .otherwise(0.0)
                .alias("YoY_Balance_Growth_%"),
                pl.when(pl.col("3M_Avg_Expense") > 0)
                .then(pl.col("Closing_Balance") / pl.col("3M_Avg_Expense"))
                .otherwise(0.0)
                .alias("Months_of_Runway"),
            )
            .drop(["Prev_Year_Balance", "YEAR", "MONTH"])
        )

    def _build_nw_summary(
        self,
        lf_asset: pl.LazyFrame,
        lf_months: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Construct full monthly net worth summary across all asset subcategories."""
        lf_nw_summary = self._join_ledger_activity(lf_asset, lf_months)
        lf_nw_summary = self._compute_balances_and_growth(lf_nw_summary)
        lf_nw_summary = self._compute_runway_metrics(lf_nw_summary)
        return self._inject_asset_market_values(lf_nw_summary)

    def _aggregate_isin_market_values(
        self,
        df_inv_isin: pl.DataFrame | pl.LazyFrame,
        df_inv_master: pl.DataFrame | pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Aggregate monthly investment closing values by ASSET_SUBCATEGORY_ID."""
        lf_inv_isin = df_inv_isin.lazy() if isinstance(df_inv_isin, pl.DataFrame) else df_inv_isin
        lf_inv_master = (
            df_inv_master.lazy() if isinstance(df_inv_master, pl.DataFrame) else df_inv_master
        )

        lf_inv_mapped = lf_inv_isin.join(
            lf_inv_master.select(["ISIN", "CATEGORY_ID"]), on="ISIN", how="left"
        ).with_columns(pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE"))

        lf_inv_latest_dates = lf_inv_mapped.group_by(["MONTH_END_DATE", "CATEGORY_ID"]).agg(
            pl.col("Closing_Date").max().alias("Max_Closing_Date")
        )

        return (
            lf_inv_mapped.join(lf_inv_latest_dates, on=["MONTH_END_DATE", "CATEGORY_ID"])
            .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
            .group_by(["MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                pl.col("Total_Current_Value").sum().fill_null(0.0).alias("Asset_Market_Value"),
                pl.col("Total_Invested_Value").sum().fill_null(0.0).alias("Asset_Book_Value"),
                pl.col("Asset_PnL").sum().fill_null(0.0).alias("Closing_Asset_PnL"),
                pl.col("Forex_PnL").sum().fill_null(0.0).alias("Closing_Forex_PnL"),
            )
            .rename({"CATEGORY_ID": "ASSET_SUBCATEGORY_ID"})
        )

    def _inject_asset_market_values(self, lf_nw_summary: pl.LazyFrame) -> pl.LazyFrame:
        """Enrich net worth monthly summary records with granular investment market valuations.

        Parameters
        ----------
        lf_nw_summary : pl.LazyFrame
            Monthly net worth summary LazyFrame.

        Returns
        -------
        pl.LazyFrame
            Enhanced LazyFrame incorporating mark-to-market valuations and unrealized PnL.
        """
        df_inv_isin = self.dfs.get("df_f_investment_analytics_isin")
        df_inv_master = self.dfs.get("df_d_investment_master")

        if df_inv_isin is not None and df_inv_master is not None:
            lf_inv_agg = self._aggregate_isin_market_values(df_inv_isin, df_inv_master)
            return (
                lf_nw_summary.join(
                    lf_inv_agg, on=["MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"], how="left"
                )
                .with_columns(
                    pl.col("Asset_Market_Value").fill_null(0.0),
                    pl.col("Asset_Book_Value").fill_null(0.0),
                    pl.col("Closing_Asset_PnL").fill_null(0.0),
                    pl.col("Closing_Forex_PnL").fill_null(0.0),
                )
                .with_columns(
                    pl.when(pl.col("Asset_Book_Value") > 0)
                    .then(
                        pl.col("Closing_Balance")
                        - pl.col("Asset_Book_Value")
                        + pl.col("Asset_Market_Value")
                    )
                    .otherwise(pl.col("Closing_Balance"))
                    .alias("Closing_Balance_Market")
                )
                .with_columns(
                    pl.when(pl.col("Is_Liquid"))
                    .then(pl.col("Closing_Balance"))
                    .otherwise(0.0)
                    .alias("Liquid_Assets"),
                    pl.when(pl.col("Is_Liquid"))
                    .then(pl.col("Closing_Balance_Market"))
                    .otherwise(0.0)
                    .alias("Liquid_Assets_Market"),
                )
                .drop(["Asset_Market_Value", "Asset_Book_Value"])
            )

        return lf_nw_summary.with_columns(
            pl.col("Closing_Balance").alias("Closing_Balance_Market"),
            pl.lit(0.0).alias("Closing_Asset_PnL"),
            pl.lit(0.0).alias("Closing_Forex_PnL"),
            pl.when(pl.col("Is_Liquid"))
            .then(pl.col("Closing_Balance"))
            .otherwise(0.0)
            .alias("Liquid_Assets"),
            pl.when(pl.col("Is_Liquid"))
            .then(pl.col("Closing_Balance"))
            .otherwise(0.0)
            .alias("Liquid_Assets_Market"),
        )

    def _aggregate_monthly_balance_totals(self, lf_nw_summary: pl.LazyFrame) -> pl.LazyFrame:
        """Roll up subcategory balances and cashflows into portfolio totals per month."""
        return (
            lf_nw_summary.group_by(["MONTH_START_DATE", "MONTH_END_DATE"])
            .agg(
                [
                    pl.col("Income_Inflow").sum().alias("Total_Income"),
                    pl.col("Cash_Income_Inflow").sum().alias("Total_Cash_Income"),
                    pl.col("Non_Cash_Income_Inflow").sum().alias("Total_Non_Cash_Income"),
                    pl.col("Expense_Outflow").sum().alias("Total_Expense"),
                    pl.col("Core_Expense_Outflow").sum().alias("Total_Core_Expense"),
                    pl.col("Cash_Expense_Outflow").sum().alias("Total_Cash_Expense"),
                    pl.col("Non_Cash_Expense_Outflow").sum().alias("Total_Non_Cash_Expense"),
                    pl.col("Net_Cashflow_Month").sum().alias("Net_Cashflow_Month"),
                    pl.col("Closing_Balance")
                    .filter(pl.col("Closing_Balance") >= 0)
                    .sum()
                    .alias("Total_Assets"),
                    pl.col("Closing_Balance")
                    .filter((pl.col("Closing_Balance") >= 0) & pl.col("Is_Liquid"))
                    .sum()
                    .alias("Liquid_Assets"),
                    pl.col("Closing_Balance")
                    .filter(pl.col("Closing_Balance") < 0)
                    .sum()
                    .alias("Total_Liabilities_Negative"),
                ]
            )
            .with_columns(
                pl.col("Total_Liabilities_Negative").abs().alias("Total_Liabilities"),
                (pl.col("Total_Assets") + pl.col("Total_Liabilities_Negative")).alias(
                    "Total_Net_Worth"
                ),
            )
            .sort("MONTH_START_DATE")
            .with_columns(
                pl.col("MONTH_START_DATE").cum_count().alias("Months_Elapsed"),
            )
        )

    def _build_monthly_totals(self, lf_nw_summary: pl.LazyFrame) -> pl.LazyFrame:
        """Construct portfolio-level net worth and balance totals per month."""
        lf_monthly_totals = self._aggregate_monthly_balance_totals(lf_nw_summary)
        lf_monthly_totals = inject_portfolio_market_values(
            lf_monthly_totals, self.dfs, self.default_currency_id
        )

        lf_monthly_totals = (
            lf_monthly_totals.sort("MONTH_START_DATE")
            .with_columns(
                pl.col("Total_Net_Worth").shift(1).fill_null(0.0).alias("Opening_Balance_Asset"),
                pl.col("Total_Net_Worth_Market")
                .shift(1)
                .fill_null(0.0)
                .alias("Opening_Balance_Asset_Market"),
                pl.col("Closing_Investment_Book_Value")
                .shift(1)
                .fill_null(0.0)
                .alias("Opening_Investment_Book_Value"),
                pl.col("Closing_Investment_Market_Value")
                .shift(1)
                .fill_null(0.0)
                .alias("Opening_Investment_Market_Value"),
                pl.col("Closing_Investment_XIRR")
                .shift(1)
                .fill_null(0.0)
                .alias("Opening_Investment_XIRR"),
                pl.col("Closing_Unrealized_PL")
                .shift(1)
                .fill_null(0.0)
                .alias("Opening_Unrealized_PL"),
            )
            .with_columns(
                pl.col("Total_Net_Worth").alias("Closing_Balance_Asset"),
                pl.col("Total_Net_Worth_Market").alias("Closing_Balance_Asset_Market"),
                (pl.col("Total_Net_Worth") - pl.col("Opening_Balance_Asset")).alias("Asset_Delta"),
                (pl.col("Total_Net_Worth_Market") - pl.col("Opening_Balance_Asset_Market")).alias(
                    "Asset_Market_Delta"
                ),
                (
                    pl.col("Closing_Investment_Book_Value")
                    - pl.col("Opening_Investment_Book_Value")
                ).alias("Investment_Book_Value_Delta"),
                (
                    pl.col("Closing_Investment_Market_Value")
                    - pl.col("Opening_Investment_Market_Value")
                ).alias("Investment_Market_Value_Delta"),
            )
        )

        return lf_monthly_totals.join(
            cast(pl.LazyFrame, self.inflation_res["lf_inflation"]),
            on="MONTH_START_DATE",
            how="left",
        ).drop("Total_Liabilities_Negative", strict=False)
