from collections.abc import Mapping
from datetime import date

import polars as pl


class BaseMetricsBuilder:
    """
    Constructs the foundational lazy frames required by downstream analytical presentation models.
    """

    def __init__(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]):
        self.dfs = dfs

    def build(self) -> dict[str, pl.LazyFrame]:
        f_open = self.dfs.get("df_f_opening_balances")
        f_inc = self.dfs.get("df_f_income_transactions")
        f_exp = self.dfs.get("df_f_expense_transactions")
        f_trn = self.dfs.get("df_f_transfer_transactions")
        d_cal = self.dfs.get("df_d_calendar")
        d_asset = self.dfs.get("df_d_asset_subcategory")

        if (
            f_open is None
            or f_inc is None
            or f_exp is None
            or f_trn is None
            or d_cal is None
            or d_asset is None
        ):
            return {}

        from typing import cast
        lf_open = cast(pl.LazyFrame, f_open.lazy() if isinstance(f_open, pl.DataFrame) else f_open)
        lf_inc = cast(pl.LazyFrame, f_inc.lazy() if isinstance(f_inc, pl.DataFrame) else f_inc)
        lf_exp = cast(pl.LazyFrame, f_exp.lazy() if isinstance(f_exp, pl.DataFrame) else f_exp)
        lf_trn = cast(pl.LazyFrame, f_trn.lazy() if isinstance(f_trn, pl.DataFrame) else f_trn)
        lf_cal = cast(pl.LazyFrame, (d_cal.lazy() if isinstance(d_cal, pl.DataFrame) else d_cal)).rename(
            {"Date": "DATE", "Year": "YEAR", "Month": "MONTH"}
        )
        lf_asset = cast(pl.LazyFrame, d_asset.lazy() if isinstance(d_asset, pl.DataFrame) else d_asset)

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

        lf_assets_months = lf_months.join(
            lf_asset.select([pl.col("UID").alias("ASSET_SUBCATEGORY_ID")]), how="cross"
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

        lf_inc_agg = lf_inc.with_columns(
            pl.col("DATE").str.to_date("%Y-%m-%d", strict=False)
        ).select(
            [
                pl.col("ASSET_ID").alias("ASSET_SUBCATEGORY_ID"),
                pl.col("AMOUNT_ACCOUNT").alias("INCOME"),
                pl.col("CATEGORY_ID"),
                pl.col("DATE"),
            ]
        )

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

        lf_trn_agg = lf_trn.with_columns(
            pl.col("DATE").str.to_date("%Y-%m-%d", strict=False)
        ).select(
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
                lf_exp_agg.select(["ASSET_SUBCATEGORY_ID", "EXPENSE", "DATE"])
                .rename({"EXPENSE": "AMOUNT"})
                .with_columns(pl.lit("EXPENSE").alias("TYPE")),
                lf_trn_agg.rename({"TRANSFER": "AMOUNT"}).with_columns(
                    pl.lit("TRANSFER").alias("TYPE")
                ),
            ],
            how="diagonal",
        )

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

        lf_ledger_balance = lf_ledger.with_columns(
            pl.when(pl.col("TYPE") == "EXPENSE")
            .then(pl.col("AMOUNT") * -1)
            .otherwise(pl.col("AMOUNT"))
            .alias("NET_AMOUNT")
        )

        lf_balances = (
            lf_ledger_balance.join(lf_months, how="cross")
            .filter(pl.col("DATE") <= pl.col("MONTH_END_DATE"))
            .group_by(["ASSET_SUBCATEGORY_ID", "MONTH_END_DATE"])
            .agg(pl.col("NET_AMOUNT").sum().fill_null(0.0).alias("Closing_Balance"))
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
                pl.col("Net_Transfers").fill_null(0.0),
                pl.col("Closing_Balance").fill_null(0.0),
            )
            .sort(["ASSET_SUBCATEGORY_ID", "MONTH_START_DATE"])
        )

        lf_nw_summary = lf_nw_summary.with_columns(
            pl.col("Closing_Balance")
            .shift(1)
            .over("ASSET_SUBCATEGORY_ID")
            .fill_null(0.0)
            .alias("Opening_Balance")
        )

        lf_nw_summary = (
            lf_nw_summary.with_columns(
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

        return {
            "lf_nw_summary": lf_nw_summary,
            "lf_monthly_totals": lf_monthly_totals,
            "lf_exp_agg": lf_exp_agg,
            "lf_inc_agg": lf_inc_agg,
            "lf_months": lf_months,
        }
