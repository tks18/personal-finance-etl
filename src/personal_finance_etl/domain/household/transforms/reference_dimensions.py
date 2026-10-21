"""Household reference dimension transformations (Currency, Benchmark, Macro).

Owns
----
- Transformation of currency master table (transform_d_currency).
- Transformation of investment benchmark master table (transform_d_investment_benchmark_master).
- Transformation of macro parameters table (transform_d_macro_parameters).

Does not own
-------------
- Income, expense, or asset dimensions.
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

__all__ = [
    "transform_d_currency",
    "transform_d_investment_benchmark_master",
    "transform_d_macro_parameters",
]


def transform_d_currency(
    df_lazy: pl.LazyFrame,
    column_mapping: dict[str, str],
    mapping_lazy: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
    """Execute the PQ logic for the Currency Master table."""
    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "UID",
                "CURRENCY_NAME",
                "ISO",
                "MAIN_ISO",
                "ORDER_SEQUENCE",
                "RATE",
                "SYMBOL",
                "INSERT_TYPE",
                "SYMBOL_POSITION",
                "IS_MAIN_CURRENCY",
                "IS_SHOW",
                "MODIFY_DATE",
                "DECIMAL_POINT",
            ]
        )
    )

    if mapping_lazy is not None:
        mapping_lazy = mapping_lazy.select(
            ["UID", "Target_Currency_Code", "yF_Ticker", "Is_Active"]
        )
        if "Is_Active" in mapping_lazy.collect_schema().names():
            mapping_lazy = mapping_lazy.with_columns(
                pl.col("Is_Active").cast(pl.Boolean).fill_null(False)
            )
        return df_transformed.join(mapping_lazy, on="UID", how="left")

    return df_transformed.with_columns(
        pl.lit(None).cast(pl.String).alias("Target_Currency_Code"),
        pl.lit(None).cast(pl.String).alias("yF_Ticker"),
        pl.lit(False).alias("Is_Active"),
    )


def transform_d_investment_benchmark_master(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Execute the PQ logic for the Benchmark Master table."""
    return raw_data.rename({"Currency": "CURRENCY_ID"}).select(
        [
            "__file_name__",
            "__folder_path__",
            "ID",
            "Benchmark_Name",
            "yF_Ticker",
            "CURRENCY_ID",
        ]
    )


def transform_d_macro_parameters(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Execute the PQ logic for the Macro Parameters table."""
    return raw_data.with_columns(
        (
            pl.col("FY").str.extract(r"(20\d{2})", 1).cast(pl.Int64).cast(pl.String)
            + "-"
            + (pl.col("FY").str.extract(r"(20\d{2})", 1).cast(pl.Int64) + 1)
            .cast(pl.String)
            .str.slice(2, 2)
        ).alias("FY")
    ).select(
        [
            "FY",
            "__file_name__",
            "__folder_path__",
            "FY_Start_Date",
            "FY_End_Date",
            "Debt_MF_Cutoff_Date",
            "Inflation_Rate",
            "Risk_Free_Rate",
            "Equity_Listed_LTCG",
            "Equity_Listed_STCG",
            "Equity_Unlisted_LTCG",
            "Equity_Unlisted_STCG",
            "Gold_LTCG",
            "Gold_STCG",
            "Debt_MF_Pre_Cutoff_LTCG",
            "Debt_MF_Pre_Cutoff_STCG",
            "Debt_MF_Post_Cutoff_LTCG",
            "Debt_MF_Post_Cutoff_STCG",
            "Other_Debt_LTCG",
            "Other_Debt_STCG",
            "Default_LTCG",
            "Default_STCG",
            "Estimated_Ordinary_Income_Tax_Rate",
            "Equity_LTCG_Exemption",
            "Remarks",
        ]
    )
