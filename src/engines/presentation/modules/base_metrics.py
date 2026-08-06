from collections.abc import Mapping
from datetime import date
from typing import Any, cast

import polars as pl

from src.utils.helpers import ensure_date_col


class BaseMetricsBuilder:
    """
    Constructs the foundational lazy frames required by downstream analytical presentation models.
    """

    def __init__(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], rules):
        self.dfs = dfs
        self.rules = rules

    def build(self) -> dict[str, Any]:
        f_open = self.dfs.get("df_f_opening_balances")
        f_inc = self.dfs.get("df_f_income_transactions")
        f_exp = self.dfs.get("df_f_expense_transactions")
        f_trn = self.dfs.get("df_f_transfer_transactions")
        d_cal = self.dfs.get("df_d_calendar")
        d_asset = self.dfs.get("df_d_asset_subcategory")
        d_macro = self.dfs.get("df_d_macro_parameters")

        if (
            f_open is None
            or f_inc is None
            or f_exp is None
            or f_trn is None
            or d_cal is None
            or d_asset is None
        ):
            return {}

        lf_open = cast(pl.LazyFrame, f_open.lazy() if isinstance(f_open, pl.DataFrame) else f_open)
        lf_inc = cast(pl.LazyFrame, f_inc.lazy() if isinstance(f_inc, pl.DataFrame) else f_inc)
        lf_exp = cast(pl.LazyFrame, f_exp.lazy() if isinstance(f_exp, pl.DataFrame) else f_exp)
        lf_trn = cast(pl.LazyFrame, f_trn.lazy() if isinstance(f_trn, pl.DataFrame) else f_trn)
        lf_cal = cast(
            pl.LazyFrame, (d_cal.lazy() if isinstance(d_cal, pl.DataFrame) else d_cal)
        ).rename({"Date": "DATE", "Year": "YEAR", "Month": "MONTH"})
        lf_asset = cast(
            pl.LazyFrame, d_asset.lazy() if isinstance(d_asset, pl.DataFrame) else d_asset
        )

        lf_macro = cast(
            pl.LazyFrame, d_macro.lazy() if isinstance(d_macro, pl.DataFrame) else d_macro
        ).select(pl.col("FY_Start_Date").cast(pl.Date), pl.col("Inflation_Rate").cast(pl.Float64))

        if isinstance(f_open, pl.DataFrame):
            min_open_date = f_open.select(pl.col("ZTXDATESTR").min()).item()
        else:
            min_open_date = f_open.select(pl.col("ZTXDATESTR").min()).collect().item()

        if min_open_date is None:
            min_open_date = date(2000, 1, 1)

        lf_months = (
            lf_cal.group_by(["YEAR", "MONTH"])
            .agg(
                [
                    pl.col("DATE").min().alias("MONTH_START_DATE"),
                    pl.col("DATE").max().alias("MONTH_END_DATE"),
                ]
            )
            .filter(
                (pl.col("MONTH_START_DATE") <= pl.lit(date.today()))
                & (pl.col("MONTH_END_DATE") >= pl.lit(min_open_date))
            )
            .sort(["YEAR", "MONTH"])
        )

        lf_inflation = (
            lf_months.sort("MONTH_START_DATE")
            .join_asof(
                lf_macro.sort("FY_Start_Date"),
                left_on="MONTH_START_DATE",
                right_on="FY_Start_Date",
                strategy="backward",
            )
            .with_columns(
                pl.col("Inflation_Rate")
                .fill_null(
                    self.rules.assumptions.macro.fallback_inflation_rate
                )
                .alias("INFLATION_YOY_PCT")
            )
            .with_columns(
                ((pl.col("INFLATION_YOY_PCT") + 1.0).pow(1.0 / 12.0)).alias("monthly_factor")
            )
            .with_columns((pl.col("monthly_factor").cum_prod() * 100.0).alias("CPI_INDEX"))
            .select(["MONTH_START_DATE", "INFLATION_YOY_PCT", "CPI_INDEX"])
        )

        try:
            cpi_latest_df = (
                lf_inflation.sort("MONTH_START_DATE").tail(1).select("CPI_INDEX").collect()
            )
            if not cpi_latest_df.is_empty():
                cpi_latest = cpi_latest_df.item()
            else:
                cpi_latest = 100.0
        except Exception:
            cpi_latest = 100.0

        lf_assets_months = lf_months.join(
            lf_asset.select(
                [pl.col("UID").alias("ASSET_SUBCATEGORY_ID"), pl.col("Is_Liquid").fill_null(True)]
            ),
            how="cross",
        )

        lf_open_agg = (
            lf_open.sort("ZUTIME")
            .group_by("ZASSETUID")
            .last()
            .select(
                [
                    pl.col("ZASSETUID").alias("ASSET_SUBCATEGORY_ID"),
                    pl.col("ZAMOUNTACCOUNT").alias("AMOUNT"),
                    pl.col("ZTXDATESTR").alias("DATE"),
                ]
            )
        )

        lf_inc_agg = ensure_date_col(lf_inc, "DATE").select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("BASE_AMOUNT").alias("INCOME"),
                pl.col("CATEGORY_ID"),
                pl.col("DATE"),
                pl.col("Is_Active_Income"),
                pl.col("Is_Dividend_Income"),
                pl.col("Is_Interest_Income"),
            ]
        )

        lf_exp_agg = ensure_date_col(lf_exp, "DATE").select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("BASE_AMOUNT").alias("EXPENSE"),
                pl.col("CATEGORY_ID"),
                pl.col("DATE"),
                pl.col("Is_Core_Expense"),
            ]
        )

        d_exp_subcat = self.dfs.get("df_d_expense_subcategory")
        d_exp_cat = self.dfs.get("df_d_expense_category")
        if d_exp_subcat is not None and d_exp_cat is not None:
            lf_exp_subcat = cast(
                pl.LazyFrame,
                d_exp_subcat.lazy() if isinstance(d_exp_subcat, pl.DataFrame) else d_exp_subcat,
            )
            lf_exp_cat = cast(
                pl.LazyFrame, d_exp_cat.lazy() if isinstance(d_exp_cat, pl.DataFrame) else d_exp_cat
            )

            lf_exp_agg = (
                lf_exp_agg.join(
                    lf_exp_subcat.select(["UID", "CATEGORY_ID"]).rename(
                        {"CATEGORY_ID": "PARENT_ID", "UID": "CATEGORY_ID"}
                    ),
                    on="CATEGORY_ID",
                    how="left",
                )
                .join(
                    lf_exp_cat.select(
                        [
                            pl.col("UID").alias("PARENT_ID"),
                            pl.col("CATEGORY_NAME").alias("CATEGORY_GROUPS"),
                        ]
                    ),
                    on="PARENT_ID",
                    how="left",
                )
                .drop("PARENT_ID")
            )

        # Removed the legacy regex-based Is_Core_Expense logic.
        # Is_Core_Expense is now pre-calculated in facts.py via the FinancialRules Engine.

        lf_trn_agg = ensure_date_col(lf_trn, "DATE").select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("AMOUNT_PROPER").alias("TRANSFER"),
                pl.col("DATE"),
            ]
        )

        lf_ledger = pl.concat(
            [
                lf_open_agg.with_columns(pl.lit("OPENING").alias("TYPE")),
                lf_inc_agg.rename({"INCOME": "AMOUNT"}).with_columns(
                    pl.lit("INCOME").alias("TYPE")
                ),
                lf_exp_agg.select(["ASSET_SUBCATEGORY_ID", "EXPENSE", "DATE", "Is_Core_Expense"])
                .rename({"EXPENSE": "AMOUNT"})
                .with_columns(pl.lit("EXPENSE").alias("TYPE")),
                lf_trn_agg.rename({"TRANSFER": "AMOUNT"}).with_columns(
                    pl.lit("TRANSFER").alias("TYPE")
                ),
            ],
            how="diagonal",
        )

        lf_activity = (
            lf_ledger.with_columns(
                pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("DATE").dt.month_end().alias("MONTH_END_DATE"),
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"])
            .agg(
                [
                    pl.col("AMOUNT")
                    .filter(pl.col("TYPE") == "INCOME")
                    .sum()
                    .fill_null(0.0)
                    .alias("Income_Inflow"),
                    pl.col("AMOUNT")
                    .filter(
                        (pl.col("TYPE") == "EXPENSE") & pl.col("Is_Core_Expense").fill_null(True)
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("Core_Expense_Outflow"),
                    pl.col("AMOUNT")
                    .filter(pl.col("TYPE") == "EXPENSE")
                    .sum()
                    .fill_null(0.0)
                    .alias("Expense_Outflow"),
                    pl.col("AMOUNT")
                    .filter(pl.col("TYPE") == "TRANSFER")
                    .sum()
                    .fill_null(0.0)
                    .alias("Net_Transfers"),
                ]
            )
        )

        lf_ledger_balance = lf_ledger.with_columns(
            pl.when(pl.col("TYPE") == "EXPENSE")
            .then(pl.col("AMOUNT") * -1)
            .otherwise(pl.col("AMOUNT"))
            .alias("NET_AMOUNT"),
            pl.col("DATE").dt.month_end().alias("MONTH_END_DATE"),
        )

        lf_balances = lf_ledger_balance.group_by(["ASSET_SUBCATEGORY_ID", "MONTH_END_DATE"]).agg(
            pl.col("NET_AMOUNT").sum().fill_null(0.0).alias("MONTHLY_NET_CHANGE")
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

        lf_monthly_totals = lf_monthly_totals.join(
            lf_inflation, on="MONTH_START_DATE", how="left"
        ).with_columns(
            pl.col("INFLATION_YOY_PCT").fill_null(0.0),
            (pl.col("Total_Net_Worth") * (pl.lit(cpi_latest) / pl.col("CPI_INDEX"))).alias(
                "Total_Net_Worth_Real"
            ),
        )

        return {
            "lf_nw_summary": lf_nw_summary.drop("Is_Liquid"),
            "lf_monthly_totals": lf_monthly_totals,
            "lf_exp_agg": lf_exp_agg,
            "lf_inc_agg": lf_inc_agg,
            "lf_months": lf_months,
            "cpi_latest": cpi_latest,
        }
