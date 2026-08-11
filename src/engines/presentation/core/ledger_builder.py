from collections.abc import Mapping
from typing import Any

import polars as pl

from src.config.financial_rules import FinancialRules
from src.utils.helpers import ensure_date_col


class LedgerBuilder:
    def __init__(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], rules: FinancialRules):
        self.dfs = dfs
        self.rules = rules

    def build(self) -> dict[str, Any]:
        f_open = self.dfs.get("df_f_opening_balances")
        f_inc = self.dfs.get("df_f_income_transactions")
        f_exp = self.dfs.get("df_f_expense_transactions")
        f_trn = self.dfs.get("df_f_transfer_transactions")

        if f_open is None or f_inc is None or f_exp is None or f_trn is None:
            return {}

        lf_open = f_open.lazy() if isinstance(f_open, pl.DataFrame) else f_open
        lf_inc = f_inc.lazy() if isinstance(f_inc, pl.DataFrame) else f_inc
        lf_exp = f_exp.lazy() if isinstance(f_exp, pl.DataFrame) else f_exp
        lf_trn = f_trn.lazy() if isinstance(f_trn, pl.DataFrame) else f_trn

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
            lf_exp_subcat = (
                d_exp_subcat.lazy() if isinstance(d_exp_subcat, pl.DataFrame) else d_exp_subcat
            )
            lf_exp_cat = d_exp_cat.lazy() if isinstance(d_exp_cat, pl.DataFrame) else d_exp_cat

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

        return {
            "lf_exp_agg": lf_exp_agg,
            "lf_inc_agg": lf_inc_agg,
            "lf_activity": lf_activity,
            "lf_balances": lf_balances,
        }
