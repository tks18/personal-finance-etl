from collections.abc import Mapping
from typing import Any

import polars as pl

class NetWorthBuilder:
    def __init__(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], inflation_res: dict[str, Any], ledger_res: dict[str, Any]):
        self.dfs = dfs
        self.inflation_res = inflation_res
        self.ledger_res = ledger_res

    def build(self) -> dict[str, Any]:
        d_asset = self.dfs.get("df_d_asset_subcategory")
        if d_asset is None:
            return {}

        lf_asset = d_asset.lazy() if isinstance(d_asset, pl.DataFrame) else d_asset
        
        lf_months = self.inflation_res["lf_months"]
        lf_inflation = self.inflation_res["lf_inflation"]
        cpi_latest = self.inflation_res["cpi_latest"]

        lf_activity = self.ledger_res["lf_activity"]
        lf_balances = self.ledger_res["lf_balances"]

        lf_assets_months = lf_months.join(
            lf_asset.select(
                [pl.col("UID").alias("ASSET_SUBCATEGORY_ID"), pl.col("Is_Liquid").fill_null(True)]
            ),
            how="cross",
        )

        lf_nw_summary = (
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
                pl.col("Expense_Outflow").fill_null(0.0),
                pl.col("Core_Expense_Outflow").fill_null(0.0),
                pl.col("Net_Transfers").fill_null(0.0),
                pl.col("MONTHLY_NET_CHANGE").fill_null(0.0),
            )
            .sort(["ASSET_SUBCATEGORY_ID", "MONTH_START_DATE"])
        )

        # Compute Closing Balance as cumulative sum of Net Changes
        lf_nw_summary = lf_nw_summary.with_columns(
            pl.col("MONTHLY_NET_CHANGE")
            .cum_sum()
            .over("ASSET_SUBCATEGORY_ID")
            .alias("Closing_Balance")
        )

        lf_nw_summary = lf_nw_summary.with_columns(
            pl.col("Closing_Balance")
            .shift(1)
            .over("ASSET_SUBCATEGORY_ID")
            .fill_null(0.0)
            .alias("Opening_Balance")
        ).drop("MONTHLY_NET_CHANGE")

        lf_nw_summary = (
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
                pl.when((pl.col("Opening_Balance") + pl.col("Closing_Balance")) > 0)
                .then(
                    (
                        pl.col("Income_Inflow")
                        + pl.col("Expense_Outflow")
                        + pl.col("Net_Transfers").abs()
                    )
                    / ((pl.col("Opening_Balance") + pl.col("Closing_Balance")) / 2.0)
                )
                .otherwise(0.0)
                .alias("Asset_Velocity_%"),
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
                pl.when(pl.col("Closing_Balance").sum().over("MONTH_START_DATE") > 0)
                .then(
                    pl.col("Closing_Balance")
                    / pl.col("Closing_Balance").sum().over("MONTH_START_DATE")
                )
                .otherwise(0.0)
                .alias("Balance_Concentration_%"),
            )
        )

        lf_nw_summary = (
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

        # Inject Market Values for assets if available
        df_inv_isin = self.dfs.get("df_f_tf_investment_analytics_isin")
        df_inv_master = self.dfs.get("df_d_tf_investment_master")

        if df_inv_isin is not None and df_inv_master is not None:
            lf_inv_isin = (
                df_inv_isin.lazy() if isinstance(df_inv_isin, pl.DataFrame) else df_inv_isin
            )
            lf_inv_master = (
                df_inv_master.lazy() if isinstance(df_inv_master, pl.DataFrame) else df_inv_master
            )

            # Map ISIN to ASSET_SUBCATEGORY_ID (CATEGORY_ID in master) and snap to month-end
            lf_inv_mapped = lf_inv_isin.join(
                lf_inv_master.select(["ISIN", "CATEGORY_ID"]), on="ISIN", how="left"
            ).with_columns(pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE"))

            lf_inv_latest_dates = lf_inv_mapped.group_by(["MONTH_END_DATE", "CATEGORY_ID"]).agg(
                pl.col("Closing_Date").max().alias("Max_Closing_Date")
            )

            lf_inv_agg = (
                lf_inv_mapped.join(lf_inv_latest_dates, on=["MONTH_END_DATE", "CATEGORY_ID"])
                .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
                .group_by(["MONTH_END_DATE", "CATEGORY_ID"])
                .agg(
                    pl.col("Total_Current_Value").sum().fill_null(0.0).alias("Asset_Market_Value"),
                    pl.col("Total_Invested_Value").sum().fill_null(0.0).alias("Asset_Book_Value"),
                )
                .rename({"CATEGORY_ID": "ASSET_SUBCATEGORY_ID"})
            )

            lf_nw_summary = (
                lf_nw_summary.join(
                    lf_inv_agg, on=["MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"], how="left"
                )
                .with_columns(
                    pl.col("Asset_Market_Value").fill_null(0.0),
                    pl.col("Asset_Book_Value").fill_null(0.0),
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
                .drop(["Asset_Market_Value", "Asset_Book_Value"])
            )
        else:
            lf_nw_summary = lf_nw_summary.with_columns(
                pl.col("Closing_Balance").alias("Closing_Balance_Market")
            )

        lf_nw_summary = (
            lf_nw_summary.join(lf_inflation, on="MONTH_START_DATE", how="left")
            .with_columns(
                pl.col("INFLATION_YOY_PCT").fill_null(0.0),
                (pl.col("Closing_Balance") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "Closing_Balance_Real"
                ),
                (
                    ((1 + pl.col("YoY_Balance_Growth_%")) / (1 + pl.col("INFLATION_YOY_PCT"))) - 1
                ).alias("YoY_Balance_Growth_%_Real"),
            )
            .with_columns(
                (pl.col("Organic_Growth_Value") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "Organic_Growth_Value_Real"
                ),
                (pl.col("Income_Inflow") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "Real_Income_Inflow"
                ),
                (pl.col("Expense_Outflow") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "Real_Expense_Outflow"
                ),
                (pl.col("3M_Avg_Core_Expense") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "3M_Avg_Core_Expense_Real"
                ),
                (
                    pl.col("Closing_Balance_Market") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))
                ).alias("Closing_Balance_Market_Real"),
            )
            .with_columns(
                pl.when(pl.col("3M_Avg_Core_Expense_Real") > 0)
                .then(pl.col("Closing_Balance_Real") / pl.col("3M_Avg_Core_Expense_Real"))
                .otherwise(0.0)
                .alias("Months_of_Runway_Real"),
                (((1 + pl.col("Organic_Yield_%")) / (1 + pl.col("INFLATION_YOY_PCT"))) - 1).alias(
                    "Organic_Yield_%_Real"
                ),
                (
                    (
                        (1 + pl.col("MoM_Balance_Growth_%"))
                        / ((1 + pl.col("INFLATION_YOY_PCT")).pow(1 / 12.0))
                    )
                    - 1
                ).alias("MoM_Balance_Growth_%_Real"),
                (
                    pl.col("Closing_Balance_Real")
                    - pl.col("Closing_Balance_Real").shift(1).over("ASSET_SUBCATEGORY_ID")
                ).alias("Balance_MoM_Real"),
            )
            .drop("CPI_INDEX")
        )

        lf_monthly_totals = (
            lf_nw_summary.group_by(["MONTH_START_DATE", "MONTH_END_DATE"])
            .agg(
                [
                    pl.col("Income_Inflow").sum().alias("Total_Income"),
                    pl.col("Expense_Outflow").sum().alias("Total_Expense"),
                    pl.col("Core_Expense_Outflow").sum().alias("Total_Core_Expense"),
                    pl.col("Real_Income_Inflow").sum().alias("Total_Real_Income"),
                    pl.col("Real_Expense_Outflow").sum().alias("Total_Real_Expense"),
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
                pl.col("MONTH_START_DATE").cum_count().alias("Months_Elapsed"),
            )
        )

        # Inject Total Market Value into Monthly Totals
        df_inv_port = self.dfs.get("df_f_tf_investment_analytics_portfolio")
        if df_inv_port is not None:
            lf_inv_port = (
                df_inv_port.lazy() if isinstance(df_inv_port, pl.DataFrame) else df_inv_port
            )
            lf_inv_port_mapped = lf_inv_port.with_columns(
                pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE")
            )
            lf_inv_port_latest = lf_inv_port_mapped.group_by("MONTH_END_DATE").agg(
                pl.col("Closing_Date").max().alias("Max_Closing_Date")
            )
            lf_inv_port_agg = (
                lf_inv_port_mapped.join(lf_inv_port_latest, on="MONTH_END_DATE")
                .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
                .select(
                    [
                        "MONTH_END_DATE",
                        pl.col("Total_Current_Value").alias("Port_Market_Value"),
                        pl.col("Total_Invested_Value").alias("Port_Book_Value"),
                    ]
                )
            )

            lf_monthly_totals = (
                lf_monthly_totals.join(
                    lf_inv_port_agg,
                    on="MONTH_END_DATE",
                    how="left",
                )
                .with_columns(
                    pl.col("Port_Market_Value").fill_null(0.0),
                    pl.col("Port_Book_Value").fill_null(0.0),
                )
                .with_columns(
                    pl.when(pl.col("Port_Book_Value") > 0)
                    .then(
                        pl.col("Total_Assets")
                        - pl.col("Port_Book_Value")
                        + pl.col("Port_Market_Value")
                    )
                    .otherwise(pl.col("Total_Assets"))
                    .alias("Total_Assets_Market"),
                    pl.when(pl.col("Port_Book_Value") > 0)
                    .then(
                        pl.col("Total_Net_Worth")
                        - pl.col("Port_Book_Value")
                        + pl.col("Port_Market_Value")
                    )
                    .otherwise(pl.col("Total_Net_Worth"))
                    .alias("Total_Net_Worth_Market"),
                    pl.when(pl.col("Port_Book_Value") > 0)
                    .then(
                        pl.col("Liquid_Assets")
                        - pl.col("Port_Book_Value")
                        + pl.col("Port_Market_Value")
                    )
                    .otherwise(pl.col("Liquid_Assets"))
                    .alias("Liquid_Assets_Market"),
                )
                .drop(["Port_Market_Value", "Port_Book_Value"])
            )
        else:
            lf_monthly_totals = lf_monthly_totals.with_columns(
                pl.col("Total_Assets").alias("Total_Assets_Market"),
                pl.col("Total_Net_Worth").alias("Total_Net_Worth_Market"),
                pl.col("Liquid_Assets").alias("Liquid_Assets_Market"),
            )

        lf_monthly_totals = (
            lf_monthly_totals.join(lf_inflation, on="MONTH_START_DATE", how="left")
            .sort("MONTH_START_DATE")
            .with_columns(
                pl.col("INFLATION_YOY_PCT").fill_null(0.0),
                (pl.col("Total_Net_Worth") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                    "Total_Net_Worth_Real"
                ),
            )
        )

        return {
            "lf_nw_summary": lf_nw_summary.drop("Is_Liquid"),
            "lf_monthly_totals": lf_monthly_totals,
        }
