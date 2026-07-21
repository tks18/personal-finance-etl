from datetime import date

import polars as pl


class WealthPresentationEngine:
    """
    Presentation Engine for Wealth & Cashflow metrics.
    Consumes LazyFrames and produces aggregated summary tables suitable for BI dashboards.
    """

    def __init__(self):
        pass

    def run(self, dfs: dict[str, pl.DataFrame]) -> dict[str, pl.LazyFrame]:
        """
        Takes collected DataFrames from the primary ETL, converts them to LazyFrames,
        performs presentation-tier aggregations, and returns them to be collected.
        """
        # Convert to LazyFrames for efficient query planning
        f_open = dfs.get("df_f_opening_balances")
        f_inc = dfs.get("df_f_income_transactions")
        f_exp = dfs.get("df_f_expense_transactions")
        f_trn = dfs.get("df_f_transfer_transactions")
        d_cal = dfs.get("df_d_calendar")
        d_asset = dfs.get("df_d_asset_subcategory")
        d_cat = dfs.get("df_d_expense_category")

        if (
            f_open is None
            or f_inc is None
            or f_exp is None
            or f_trn is None
            or d_cal is None
            or d_asset is None
            or d_cat is None
        ):
            return {}

        lf_open = f_open.lazy()
        lf_inc = f_inc.lazy()
        lf_exp = f_exp.lazy()
        lf_trn = f_trn.lazy()
        lf_cal = d_cal.lazy().rename({"Date": "DATE", "Year": "YEAR", "Month": "MONTH"})
        lf_asset = d_asset.lazy()

        results = {}

        # Group by Month Start and End, dropping any future months beyond the active one
        lf_months = (
            lf_cal.group_by(["YEAR", "MONTH"])
            .agg(
                [
                    pl.col("DATE").min().alias("MONTH_START_DATE"),
                    pl.col("DATE").max().alias("MONTH_END_DATE"),
                ]
            )
            .filter(pl.col("MONTH_START_DATE") <= pl.lit(date.today()))
            .sort(["YEAR", "MONTH"])
        )

        # We will build f_net_worth_monthly_summary
        # A full cross-join of all assets and all months
        lf_assets_months = lf_months.join(
            lf_asset.select([pl.col("UID").alias("ASSET_SUBCATEGORY_ID")]), how="cross"
        )

        # Aggregate Opening Balances by Asset
        # ZTXDATESTR is the date
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

        # Aggregate Incomes by Month and Asset
        lf_inc_agg = lf_inc.with_columns(
            pl.col("DATE").str.to_date("%Y-%m-%d", strict=False)
        ).select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("AMOUNT_ACCOUNT").alias("INCOME"),
                pl.col("DATE"),
            ]
        )

        # Aggregate Expenses by Month and Asset
        lf_exp_agg = lf_exp.with_columns(
            pl.col("DATE").str.to_date("%Y-%m-%d", strict=False)
        ).select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("AMOUNT_ACCOUNT").alias("EXPENSE"),
                pl.col("CATEGORY_ID"),
                pl.col("DATE"),
            ]
        )

        # The transfer table already contains two line items per transaction (In and Out).
        # We simply map ASSET_ID and use the pre-signed AMOUNT_PROPER column.
        lf_trn_agg = lf_trn.with_columns(
            pl.col("DATE").str.to_date("%Y-%m-%d", strict=False)
        ).select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("AMOUNT_PROPER").alias("TRANSFER"),
                pl.col("DATE"),
            ]
        )

        # To calculate running balances, it's easier to concat everything into a single ledger
        lf_ledger = pl.concat(
            [
                lf_open_agg.with_columns(pl.lit("OPENING").alias("TYPE")),
                lf_inc_agg.rename({"INCOME": "AMOUNT"}).with_columns(
                    pl.lit("INCOME").alias("TYPE")
                ),
                lf_exp_agg.select(["ASSET_SUBCATEGORY_ID", "EXPENSE", "DATE"])
                .rename({"EXPENSE": "AMOUNT"})
                .with_columns(pl.lit("EXPENSE").alias("TYPE")),
                lf_trn_agg.rename({"TRANSFER": "AMOUNT"}).with_columns(
                    pl.lit("TRANSFER").alias("TYPE")
                ),
            ],
            how="diagonal",
        )

        # Now we join this ledger to the assets_months table
        # We want to aggregate activities *within* the month
        lf_activity = (
            lf_ledger.join(lf_months, how="cross")
            .filter(
                (pl.col("DATE") >= pl.col("MONTH_START_DATE"))
                & (pl.col("DATE") <= pl.col("MONTH_END_DATE"))
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

        # For closing balance, we need cumulative sum of ALL amounts up to MONTH_END_DATE
        # We can just sum where DATE <= MONTH_END_DATE
        # But wait, expense amounts are positive in the ledger? Let's check:
        # We should make expense negative for balance calculation
        lf_ledger_balance = lf_ledger.with_columns(
            pl.when(pl.col("TYPE") == "EXPENSE")
            .then(pl.col("AMOUNT") * -1)
            .otherwise(pl.col("AMOUNT"))
            .alias("NET_AMOUNT")
        )

        lf_balances = (
            lf_ledger_balance.join(lf_months, how="cross")
            .filter(pl.col("DATE") <= pl.col("MONTH_END_DATE"))
            .group_by(["MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"])
            .agg(pl.col("NET_AMOUNT").sum().fill_null(0.0).alias("Closing_Balance"))
        )

        lf_balances_open = (
            lf_ledger_balance.join(lf_months, how="cross")
            .filter(pl.col("DATE") < pl.col("MONTH_START_DATE"))
            .group_by(["MONTH_START_DATE", "ASSET_SUBCATEGORY_ID"])
            .agg(pl.col("NET_AMOUNT").sum().fill_null(0.0).alias("Opening_Balance"))
        )

        # Join everything together
        lf_nw_summary = (
            lf_assets_months.join(
                lf_activity,
                on=["MONTH_START_DATE", "MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"],
                how="left",
            )
            .join(lf_balances, on=["MONTH_END_DATE", "ASSET_SUBCATEGORY_ID"], how="left")
            .join(lf_balances_open, on=["MONTH_START_DATE", "ASSET_SUBCATEGORY_ID"], how="left")
            .with_columns(
                [
                    pl.col("Income_Inflow").fill_null(0.0),
                    pl.col("Expense_Outflow").fill_null(0.0),
                    pl.col("Net_Transfers").fill_null(0.0),
                    pl.col("Closing_Balance").fill_null(0.0),
                    pl.col("Opening_Balance").fill_null(0.0),
                ]
            )
            .with_columns(
                (
                    pl.col("Income_Inflow") - pl.col("Expense_Outflow") + pl.col("Net_Transfers")
                ).alias("Net_Cashflow_Month")
            )
            .with_columns(
                (
                    pl.col("Closing_Balance")
                    - (pl.col("Opening_Balance") + pl.col("Net_Cashflow_Month"))
                ).alias("Organic_Growth_Value")
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
                pl.when(pl.col("Opening_Balance") != 0)
                .then(
                    (
                        pl.col("Income_Inflow")
                        + pl.col("Expense_Outflow")
                        + pl.col("Net_Transfers").abs()
                    )
                    / pl.col("Opening_Balance")
                )
                .otherwise(0.0)
                .alias("Asset_Velocity_%"),
            )
        )

        # Calculate 3M Averages and YoY using window functions
        lf_nw_summary = (
            lf_nw_summary.sort(["ASSET_SUBCATEGORY_ID", "MONTH_START_DATE"])
            .with_columns(
                [
                    pl.col("Expense_Outflow")
                    .rolling_mean(window_size=3)
                    .over("ASSET_SUBCATEGORY_ID")
                    .alias("3M_Avg_Expense"),
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

        results["df_p_tf_net_worth_monthly_summary"] = lf_nw_summary

        # 2. Financial Ratios Monthly
        # Aggregate totals per month
        lf_monthly_totals = (
            lf_nw_summary.group_by(["MONTH_START_DATE", "MONTH_END_DATE"])
            .agg(
                [
                    pl.col("Income_Inflow").sum().alias("Total_Income"),
                    pl.col("Expense_Outflow").sum().alias("Total_Expense"),
                    pl.col("Closing_Balance")
                    .filter(pl.col("Closing_Balance") >= 0)
                    .sum()
                    .alias("Total_Assets"),
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
        )

        # Compute 3M averages for ratios
        lf_monthly_totals = lf_monthly_totals.sort("MONTH_START_DATE").with_columns(
            [
                pl.col("Total_Expense")
                .rolling_mean(window_size=3)
                .alias("3M_Avg_Total_Expense"),
                pl.col("Total_Income")
                .rolling_mean(window_size=3)
                .alias("3M_Avg_Total_Income"),
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
        ).select(
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
            ]
        )

        results["df_p_tf_financial_ratios_monthly"] = lf_ratios

        # 3. Category Inflation Trends
        # Group expenses by Month and Parent Category
        # From f_exp_agg, we already have CATEGORY_ID
        lf_cat_agg = (
            lf_exp_agg.join(lf_months, how="cross")
            .filter(
                (pl.col("DATE") >= pl.col("MONTH_START_DATE"))
                & (pl.col("DATE") <= pl.col("MONTH_END_DATE"))
            )
            .group_by(["MONTH_START_DATE", "MONTH_END_DATE", "CATEGORY_ID"])
            .agg(
                [
                    pl.col("EXPENSE").sum().fill_null(0.0).alias("Total_Monthly_Spend"),
                    pl.col("EXPENSE").mean().fill_null(0.0).alias("Average_Transaction_Value"),
                ]
            )
            .sort(["CATEGORY_ID", "MONTH_START_DATE"])
        )

        lf_cat_inflation = (
            lf_cat_agg.with_columns(
                [
                    pl.col("Total_Monthly_Spend")
                    .shift(1)
                    .over("CATEGORY_ID")
                    .alias("Prev_Month_Spend"),
                    pl.col("Total_Monthly_Spend")
                    .shift(12)
                    .over("CATEGORY_ID")
                    .alias("Prev_Year_Spend"),
                ]
            )
            .with_columns(
                [
                    pl.when(pl.col("Prev_Month_Spend") > 0)
                    .then(
                        (pl.col("Total_Monthly_Spend") - pl.col("Prev_Month_Spend"))
                        / pl.col("Prev_Month_Spend")
                    )
                    .otherwise(0.0)
                    .alias("MoM_Spend_Growth_%"),
                    pl.when(pl.col("Prev_Year_Spend") > 0)
                    .then(
                        (pl.col("Total_Monthly_Spend") - pl.col("Prev_Year_Spend"))
                        / pl.col("Prev_Year_Spend")
                    )
                    .otherwise(0.0)
                    .alias("YoY_Spend_Growth_%"),
                ]
            )
            .drop(["Prev_Month_Spend", "Prev_Year_Spend"])
        )

        results["df_p_tf_category_inflation_trends"] = lf_cat_inflation

        return results
