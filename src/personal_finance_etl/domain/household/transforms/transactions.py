"""Household financial transactions transformation.

Owns
----
- Ingestion and base normalization of household INOUTCOME transactions.
- Classification of income facts (active, dividend, interest, non-cash).
- Classification of expense facts (core vs non-core).
- Normalization of transfer facts (in/out, directional amounts, adjusted dates).
- Transformation of opening balances with strict date/numeric parsing.

Does not own
-------------
- Extraction of raw SQLite rows (owned by infrastructure.providers.files.sqlite).
- Physical insertion into DuckDB warehouse (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import validate_and_parse_dates
from personal_finance_etl.domain.common.validation import validate_and_parse_numerics

__all__ = [
    "BASE_TRANSACTION_COLS",
    "get_base_transactions",
    "transform_f_expense_transactions",
    "transform_f_income_transactions",
    "transform_f_opening_balances",
    "transform_f_transfer_transactions",
]

BASE_TRANSACTION_COLS = [
    "__file_name__",
    "__folder_path__",
    "S_NO",
    "UID",
    "ASSET_ID",
    "CARDDIVIDMONTH",
    "CATEGORY_ID",
    "TO_ASSET_ID",
    "DESCRIPTION",
    "TIMESTAMP",
    "DATE",
    "TIME",
    "PAID",
    "TRANSACTION_TYPE",
    "BASE_AMOUNT",
    "TRANSFER_UID",
    "FEES_NOTES",
    "LOCAL_AMOUNT",
    "MARK",
    "TRANSFER_FEES",
    "UPDATED_TIME",
    "CURRENCY_ID",
    "AMOUNT_ACCOUNT",
    "EXCH_RATE",
]


def _validate_monetary_invariants(df_renamed: pl.LazyFrame, raw_columns: set[str]) -> None:
    """Validate source monetary values before casting, raising immediately on malformed strings."""
    active_row = pl.col("IS_DEL").cast(pl.String).fill_null("0") == "0"
    base_amount = pl.col("BASE_AMOUNT").cast(pl.Float64, strict=False)
    invalid_conditions = [base_amount.is_null() | ~base_amount.is_finite()]

    for optional_field in ("LOCAL_AMOUNT", "AMOUNT_ACCOUNT"):
        if optional_field not in raw_columns:
            continue
        raw_value = pl.col(optional_field)
        raw_text = raw_value.cast(pl.String).str.strip_chars()
        populated = raw_value.is_not_null() & (raw_text != "")
        parsed = raw_value.cast(pl.Float64, strict=False)
        invalid_conditions.append(populated & (parsed.is_null() | ~parsed.is_finite()))

    invalid_rows = (
        df_renamed.filter(active_row & pl.any_horizontal(invalid_conditions))
        .select(
            [
                c
                for c in ("UID", "DATE", "BASE_AMOUNT", "LOCAL_AMOUNT", "AMOUNT_ACCOUNT")
                if c in raw_columns
            ]
        )
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 20) of invalid monetary rows for structured diagnostics
        .limit(20)
        .collect()
    )
    if not invalid_rows.is_empty():
        raise ValueError(
            "Invalid required or populated monetary value(s) in active INOUTCOME "
            "transaction(s). BASE_AMOUNT is required; populated LOCAL_AMOUNT and "
            "AMOUNT_ACCOUNT values must be finite numbers. "
            f"Examples: {invalid_rows.to_dicts()}"
        )


def get_base_transactions(df_lazy: pl.LazyFrame, column_mapping: dict[str, str]) -> pl.LazyFrame:
    """Acts as the TRANSACTIONS helper query.

    Reads INOUTCOME once, renames columns, and filters deleted rows.
    """
    df_renamed = df_lazy.rename(column_mapping)
    raw_columns = set(df_renamed.collect_schema().names())
    required_columns = {"IS_DEL", "UID", "BASE_AMOUNT"}
    missing_columns = sorted(required_columns - raw_columns)
    if missing_columns:
        raise ValueError(f"INOUTCOME is missing required transaction columns: {missing_columns}")

    _validate_monetary_invariants(df_renamed, raw_columns)

    return (
        df_renamed.with_columns(
            [
                pl.col("IS_DEL").cast(pl.String),
                pl.col("BASE_AMOUNT").cast(pl.Float64, strict=False),
                pl.col("LOCAL_AMOUNT").cast(pl.Float64, strict=False),
                pl.col("AMOUNT_ACCOUNT").cast(pl.Float64, strict=False),
                pl.col("TRANSACTION_TYPE").cast(pl.Int64, strict=False),
                pl.col("CARDDIVIDMONTH").cast(pl.Int64, strict=False),
                pl.col("TIMESTAMP").cast(pl.Int64, strict=False),
                pl.col("UPDATED_TIME").cast(pl.Int64, strict=False),
                pl.col("S_NO").cast(pl.Int64, strict=False),
            ]
        )
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .with_columns(
            pl.when(pl.col("LOCAL_AMOUNT").abs() < 1e-10)
            .then(0.0)
            .otherwise(pl.col("BASE_AMOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )
    )


def _classify_income_transaction_rules(
    df: pl.LazyFrame, rules: FinancialRules, d_subcat: pl.LazyFrame
) -> pl.LazyFrame:
    """Join subcategory hierarchy and flag active, dividend, interest, and non-cash income."""
    df_with_parent = df.join(
        d_subcat.select(
            [pl.col("UID").alias("CATEGORY_ID"), pl.col("CATEGORY_ID").alias("PARENT_ID")]
        ),
        on="CATEGORY_ID",
        how="left",
    )
    active_cat = [uid.upper() for uid in rules.income.active.category_ids]
    active_sub = [uid.upper() for uid in rules.income.active.sub_category_ids]
    div_cat = [uid.upper() for uid in rules.income.dividends.category_ids]
    div_sub = [uid.upper() for uid in rules.income.dividends.sub_category_ids]
    int_cat = [uid.upper() for uid in rules.income.interest.category_ids]
    int_sub = [uid.upper() for uid in rules.income.interest.sub_category_ids]
    non_cash_cat = [uid.upper() for uid in rules.income.non_cash.category_ids]
    non_cash_sub = [uid.upper() for uid in rules.income.non_cash.sub_category_ids]

    return df_with_parent.with_columns(
        pl.when(
            pl.col("CATEGORY_ID").str.to_uppercase().is_in(active_sub)
            | pl.col("PARENT_ID").str.to_uppercase().is_in(active_cat)
        )
        .then(True)
        .otherwise(False)
        .alias("Is_Active_Income"),
        pl.when(
            pl.col("CATEGORY_ID").str.to_uppercase().is_in(div_sub)
            | pl.col("PARENT_ID").str.to_uppercase().is_in(div_cat)
        )
        .then(True)
        .otherwise(False)
        .alias("Is_Dividend_Income"),
        pl.when(
            pl.col("CATEGORY_ID").str.to_uppercase().is_in(int_sub)
            | pl.col("PARENT_ID").str.to_uppercase().is_in(int_cat)
        )
        .then(True)
        .otherwise(False)
        .alias("Is_Interest_Income"),
        pl.when(
            pl.col("CATEGORY_ID").str.to_uppercase().is_in(non_cash_sub)
            | pl.col("PARENT_ID").str.to_uppercase().is_in(non_cash_cat)
        )
        .then(True)
        .otherwise(False)
        .alias("Is_Non_Cash_Income"),
    ).drop("PARENT_ID")


def transform_f_income_transactions(
    base_transactions_lazy: pl.LazyFrame,
    rules: FinancialRules | None = None,
    d_subcat: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
    """Branches off the base transactions for Income (TYPE = 0) and applies classification."""
    df_transformed = base_transactions_lazy.filter(pl.col("TRANSACTION_TYPE") == 0).select(
        BASE_TRANSACTION_COLS
    )

    if rules and d_subcat is not None:
        return _classify_income_transaction_rules(df_transformed, rules, d_subcat)

    return df_transformed.with_columns(
        pl.lit(False).alias("Is_Active_Income"),
        pl.lit(False).alias("Is_Dividend_Income"),
        pl.lit(False).alias("Is_Interest_Income"),
        pl.lit(False).alias("Is_Non_Cash_Income"),
    )


def transform_f_expense_transactions(
    base_transactions_lazy: pl.LazyFrame,
    rules: FinancialRules | None = None,
    d_subcat: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
    """Branches off the base transactions for Expenses (TYPE = 1) and applies the EXCH_RATE calculation."""
    df_transformed = base_transactions_lazy.filter(pl.col("TRANSACTION_TYPE") == 1).select(
        BASE_TRANSACTION_COLS
    )

    if rules and d_subcat is not None:
        df_transformed = df_transformed.join(
            d_subcat.select(
                [pl.col("UID").alias("CATEGORY_ID"), pl.col("CATEGORY_ID").alias("PARENT_ID")]
            ),
            on="CATEGORY_ID",
            how="left",
        )
        core_cat = [uid.upper() for uid in rules.expense.core.category_ids]
        core_sub = [uid.upper() for uid in rules.expense.core.sub_category_ids]

        df_transformed = df_transformed.with_columns(
            pl.when(
                pl.col("CATEGORY_ID").str.to_uppercase().is_in(core_sub)
                | pl.col("PARENT_ID").str.to_uppercase().is_in(core_cat)
            )
            .then(True)
            .otherwise(False)
            .alias("Is_Core_Expense")
        ).drop("PARENT_ID")
    else:
        df_transformed = df_transformed.with_columns(pl.lit(False).alias("Is_Core_Expense"))

    return df_transformed


def transform_f_transfer_transactions(
    base_transactions_lazy: pl.LazyFrame,
    df_d_asset_subcategory_lazy: pl.LazyFrame,
    df_d_asset_category_lazy: pl.LazyFrame,
) -> pl.LazyFrame:
    """Branches off base transactions for Transfers (TYPE = 3 or 4).

    Applies RELATED() logic via joins, plus temporal shifts for EDATE().
    """
    df_joined_sub = base_transactions_lazy.join(
        df_d_asset_subcategory_lazy.select([pl.col("UID").alias("SUB_UID"), "ASSET_GROUP_ID"]),
        left_on="ASSET_ID",
        right_on="SUB_UID",
        how="left",
    )

    df_joined_cat = df_joined_sub.join(
        df_d_asset_category_lazy.select([pl.col("UID").alias("CAT_UID"), "ASSET_GROUP"]),
        left_on="ASSET_GROUP_ID",
        right_on="CAT_UID",
        how="left",
    )

    return (
        df_joined_cat.filter((pl.col("TRANSACTION_TYPE") == 3) | (pl.col("TRANSACTION_TYPE") == 4))
        .select(BASE_TRANSACTION_COLS + ["ASSET_GROUP"])
        .with_columns(
            pl.when(pl.col("TRANSACTION_TYPE") == 3)
            .then(pl.lit("Out"))
            .otherwise(pl.lit("In"))
            .alias("TRANSFER_TYPE")
        )
        .with_columns(
            pl.when(pl.col("TRANSFER_TYPE") == "Out")
            .then(pl.col("BASE_AMOUNT") * -1)
            .otherwise(pl.col("BASE_AMOUNT"))
            .alias("AMOUNT_PROPER"),
            pl.when(pl.col("ASSET_GROUP") == "Investments")
            .then(pl.col("DATE").cast(pl.Date, strict=False).dt.offset_by("-1mo"))
            .otherwise(pl.col("DATE").cast(pl.Date, strict=False))
            .alias("ADJUSTED_DATE_FOR_ANALYSIS"),
        )
        .drop("ASSET_GROUP")
    )


def _parse_opening_balance_fields(df: pl.LazyFrame) -> pl.LazyFrame:
    """Validate numerics, dates, and types for opening balances."""
    df_parsed = validate_and_parse_numerics(
        df,
        ["ZAMOUNT", "ZAMOUNTACCOUNT", "ZAMOUNTSUB", "ZDATE"],
        optional_cols={"ZAMOUNTACCOUNT", "ZAMOUNTSUB", "ZDATE"},
        source_col="__file_name__",
    )
    df_parsed = validate_and_parse_dates(
        df_parsed,
        {
            "ZTXDATESTR": [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
            ]
        },
        optional_cols={"ZTXDATESTR"},
        source_col="__file_name__",
    )
    return df_parsed.with_columns(
        [
            pl.col("Z_PK").cast(pl.Int64),
            pl.col("ZUTIME").cast(pl.Int64),
            pl.col("ZDO_TYPE").cast(pl.Int64),
        ]
    )


def transform_f_opening_balances(
    raw_data: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Execute the PQ logic for Opening Balances."""
    df_transformed = raw_data.rename(column_mapping).select(
        [
            "__file_name__",
            "__folder_path__",
            "Z_PK",
            "ZUTIME",
            "ZDATE",
            "ZAMOUNT",
            "ZAMOUNTACCOUNT",
            "ZAMOUNTSUB",
            "ZCONTENT",
            "ZDO_TYPE",
            "ZASSETUID",
            "ZCATEGORYUID",
            "ZCURRENCYUID",
            "ZTOASSETUID",
            "ZTXDATESTR",
            "ZTXUIDFEE",
            "ZTXUIDTRANS",
            "ZUID",
        ]
    )
    return _parse_opening_balance_fields(df_transformed)
