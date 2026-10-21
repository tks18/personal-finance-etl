"""Household expense dimension transformations.

Owns
----
- Transformation of expense categories (transform_d_expense_category).
- Transformation of expense subcategories with core classification (transform_d_expense_subcategory).

Does not own
-------------
- Income or asset dimensions (owned by income_dimensions.py and asset_dimensions.py).
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules

__all__ = [
    "transform_d_expense_category",
    "transform_d_expense_subcategory",
]


def transform_d_expense_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Execute the PQ logic for Expense Categories (TYPE = 1)."""
    return (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .filter(
            (pl.col("TYPE") == 1)
            & (pl.col("CATEGORY_ID").is_null() | (pl.col("CATEGORY_ID").str.len_chars() < 1))
        )
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
            ]
        )
    )


def transform_d_expense_subcategory(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
) -> pl.LazyFrame:
    """Execute the PQ logic for Expense Subcategories."""
    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .filter(
            (pl.col("TYPE") == 1)
            & pl.col("CATEGORY_ID").is_not_null()
            & (pl.col("CATEGORY_ID").str.len_chars() > 0)
        )
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
                "CATEGORY_ID",
            ]
        )
    )

    if rules:
        core_cats = rules.expense.core.category_ids
        core_subcats = rules.expense.core.sub_category_ids

        return df_transformed.with_columns(
            pl.when(pl.col("CATEGORY_ID").is_in(core_cats) | pl.col("UID").is_in(core_subcats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Core_Expense")
        )

    return df_transformed.with_columns(pl.lit(False).alias("Is_Core_Expense"))
