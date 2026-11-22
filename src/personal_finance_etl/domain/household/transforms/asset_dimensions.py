"""Household asset dimension transformations.

Owns
----
- Transformation of asset groups/categories with ledger role and cashflow activity (transform_d_asset_category).
- Transformation of asset accounts/subcategories with liquidity classification (transform_d_asset_subcategory).

Does not own
-------------
- Income or expense dimensions (owned by income_dimensions.py and expense_dimensions.py).
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules

__all__ = [
    "transform_d_asset_category",
    "transform_d_asset_subcategory",
]


def _classify_asset_category_roles(df: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
    """Classify asset groups into ledger roles and cashflow activities."""
    digital_cats = rules.assets.digital.category_ids
    cash_pools = rules.assets.cashflow.cash_pools
    non_cash_pnl = rules.assets.cashflow.non_cash_pnl_sources
    working_capital = rules.assets.cashflow.working_capital_conduits
    investing = rules.assets.cashflow.investing_activities
    financing = rules.assets.cashflow.financing_liabilities

    return df.with_columns(
        pl.when(pl.col("UID").is_in(digital_cats))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("Is_Digital_Asset"),
        pl.when(pl.col("UID").is_in(cash_pools))
        .then(pl.lit("CASH_POOL"))
        .when(pl.col("UID").is_in(non_cash_pnl))
        .then(pl.lit("NON_CASH_PNL"))
        .when(pl.col("UID").is_in(working_capital))
        .then(pl.lit("WORKING_CAPITAL_CONDUIT"))
        .when(pl.col("UID").is_in(investing))
        .then(pl.lit("INVESTING_ASSET"))
        .when(pl.col("UID").is_in(financing))
        .then(pl.lit("FINANCING_LIABILITY"))
        .otherwise(pl.lit("UNCLASSIFIED"))
        .alias("ledger_role"),
        pl.when(pl.col("UID").is_in(cash_pools))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("is_cash_pool"),
        pl.when(pl.col("UID").is_in(non_cash_pnl))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("is_non_cash_pnl"),
    ).with_columns(
        pl.when(pl.col("ledger_role") == "CASH_POOL")
        .then(pl.lit("INTERNAL_TRANSFER"))
        .when(pl.col("ledger_role").is_in(["NON_CASH_PNL", "WORKING_CAPITAL_CONDUIT"]))
        .then(pl.lit("OPERATING"))
        .when(pl.col("ledger_role") == "INVESTING_ASSET")
        .then(pl.lit("INVESTING"))
        .when(pl.col("ledger_role") == "FINANCING_LIABILITY")
        .then(pl.lit("FINANCING"))
        .otherwise(pl.lit(None).cast(pl.String))
        .alias("cashflow_activity_type"),
        pl.when(pl.col("ledger_role") == "CASH_POOL")
        .then(pl.lit("IMMEDIATE_CASH"))
        .when(
            pl.col("ledger_role").is_in(
                [
                    "NON_CASH_PNL",
                    "WORKING_CAPITAL_CONDUIT",
                    "INVESTING_ASSET",
                    "FINANCING_LIABILITY",
                ]
            )
        )
        .then(pl.lit("DEFERRED_ACCRUAL"))
        .otherwise(pl.lit(None).cast(pl.String))
        .alias("settlement_timing"),
    )


def transform_d_asset_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
) -> pl.LazyFrame:
    """Execute the PQ logic for Asset Categories (ASSETGROUP)."""
    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "DEVICE_ID",
                "UID",
                "USE_TIME",
                "ASSET_GROUP",
                "TYPE",
                "ORDER_SEQUENCE",
            ]
        )
    )

    if rules:
        return _classify_asset_category_roles(df_transformed, rules)

    return df_transformed.with_columns(
        pl.lit(False).alias("Is_Digital_Asset"),
        pl.lit("UNCLASSIFIED").alias("ledger_role"),
        pl.lit(False).alias("is_cash_pool"),
        pl.lit(False).alias("is_non_cash_pnl"),
        pl.lit(None).cast(pl.String).alias("cashflow_activity_type"),
        pl.lit(None).cast(pl.String).alias("settlement_timing"),
    )


def _classify_asset_subcategory_roles(df: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
    """Classify individual asset subcategories into liquidity, digital, and cashflow categories."""
    illiquid_cats = rules.assets.illiquid.category_ids
    illiquid_subcats = rules.assets.illiquid.sub_category_ids
    digital_cats = rules.assets.digital.category_ids
    cash_pools = rules.assets.cashflow.cash_pools
    non_cash_pnl = rules.assets.cashflow.non_cash_pnl_sources
    working_capital = rules.assets.cashflow.working_capital_conduits
    investing = rules.assets.cashflow.investing_activities
    financing = rules.assets.cashflow.financing_liabilities

    return (
        df.with_columns(
            pl.when(
                pl.col("ASSET_GROUP_ID").is_in(illiquid_cats)
                | pl.col("UID").is_in(illiquid_subcats)
            )
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Illiquid"),
            pl.when(pl.col("ASSET_GROUP_ID").is_in(digital_cats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Digital_Asset"),
            pl.when(pl.col("ASSET_GROUP_ID").is_in(cash_pools))
            .then(pl.lit("CASH_POOL"))
            .when(pl.col("ASSET_GROUP_ID").is_in(non_cash_pnl))
            .then(pl.lit("NON_CASH_PNL"))
            .when(pl.col("ASSET_GROUP_ID").is_in(working_capital))
            .then(pl.lit("WORKING_CAPITAL_CONDUIT"))
            .when(pl.col("ASSET_GROUP_ID").is_in(investing))
            .then(pl.lit("INVESTING_ASSET"))
            .when(pl.col("ASSET_GROUP_ID").is_in(financing))
            .then(pl.lit("FINANCING_LIABILITY"))
            .otherwise(pl.lit("UNCLASSIFIED"))
            .alias("ledger_role"),
            pl.when(pl.col("ASSET_GROUP_ID").is_in(cash_pools))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("is_cash_pool"),
            pl.when(pl.col("ASSET_GROUP_ID").is_in(non_cash_pnl))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("is_non_cash_pnl"),
        )
        .with_columns((~pl.col("Is_Illiquid")).alias("Is_Liquid"))
        .with_columns(
            pl.when(pl.col("ledger_role") == "CASH_POOL")
            .then(pl.lit("INTERNAL_TRANSFER"))
            .when(pl.col("ledger_role").is_in(["NON_CASH_PNL", "WORKING_CAPITAL_CONDUIT"]))
            .then(pl.lit("OPERATING"))
            .when(pl.col("ledger_role") == "INVESTING_ASSET")
            .then(pl.lit("INVESTING"))
            .when(pl.col("ledger_role") == "FINANCING_LIABILITY")
            .then(pl.lit("FINANCING"))
            .otherwise(pl.lit(None).cast(pl.String))
            .alias("cashflow_activity_type"),
            pl.when(pl.col("ledger_role") == "CASH_POOL")
            .then(pl.lit("IMMEDIATE_CASH"))
            .when(
                pl.col("ledger_role").is_in(
                    [
                        "NON_CASH_PNL",
                        "WORKING_CAPITAL_CONDUIT",
                        "INVESTING_ASSET",
                        "FINANCING_LIABILITY",
                    ]
                )
            )
            .then(pl.lit("DEFERRED_ACCRUAL"))
            .otherwise(pl.lit(None).cast(pl.String))
            .alias("settlement_timing"),
        )
    )


def transform_d_asset_subcategory(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
) -> pl.LazyFrame:
    """Execute the PQ logic for Asset Subcategories (ASSETS)."""
    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "CARD_STATEMENT_DATE",
                "CARD_PAYMENT_DATE",
                "ASSET_NAME",
                "ORDER_SEQUENCE",
                "ASSET_DESCRIPTION",
                "NOTES",
                "TRANSFER_EXPENSE",
                "CARD_AUTOPAY",
                "ADDED_TIME",
                "UID",
                "CURRENCY_ID",
                "AUTOPAY_ASSET_ID",
                "ASSET_GROUP_ID",
            ]
        )
    )

    if rules:
        return _classify_asset_subcategory_roles(df_transformed, rules)

    return df_transformed.with_columns(
        pl.lit(False).alias("Is_Illiquid"),
        pl.lit(True).alias("Is_Liquid"),
        pl.lit(False).alias("Is_Digital_Asset"),
        pl.lit("UNCLASSIFIED").alias("ledger_role"),
        pl.lit(False).alias("is_cash_pool"),
        pl.lit(False).alias("is_non_cash_pnl"),
        pl.lit(None).cast(pl.String).alias("cashflow_activity_type"),
        pl.lit(None).cast(pl.String).alias("settlement_timing"),
    )
