"""US equity trade and reference transformations.

Owns
----
- Parsing and validation of US stock transaction reports (IND Money CSV).
- Currency translation from USD to INR using observed transaction exchange rates.
- Per-unit price calculation for US stock buys and sells.
- US stock instrument master reference extraction (stg_StockMasterRef for US).

Does not own
-------------
- Ingestion of raw CSV files (owned by infrastructure.providers.files.csv).
- Cross-asset continuous valuation spine (owned by domain.investments.valuation.market_state).
"""

import polars as pl

from personal_finance_etl.domain.common.dates import validate_and_parse_dates
from personal_finance_etl.domain.common.validation import validate_and_parse_numerics


def get_base_us_stock_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Acts as the US_STOCK_TRANSACTIONS helper query.

    Returns a single LazyFrame containing both Buys and Sells with translation to INR.
    """
    stock_clean = pl.col("Stock Name").cast(pl.String).str.strip_chars()
    df_filtered = raw_data.filter(
        stock_clean.is_not_null()
        & (stock_clean != "")
        & (
            ~stock_clean.str.to_uppercase().is_in(
                [
                    "NO TRANSACTIONS FOUND",
                    "NO DATA FOUND",
                    "NO TRANSACTION FOUND",
                    "NO HOLDINGS FOUND",
                ]
            )
        )
    )

    df_validated = validate_and_parse_dates(
        df_filtered,
        {
            "Order Date": [
                "%d-%b-%y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%d-%m-%Y",
            ]
        },
        source_col="__file_name__",
    )

    numeric_cols = [
        "Quantity",
        "Price ($)",
        "Order Amount ($)",
        "Exch Rate",
        "Order Amount (INR)",
        "Brokerage (INR)",
    ]
    df_validated = validate_and_parse_numerics(
        df_validated,
        numeric_cols,
        optional_cols={"Brokerage (INR)"},
        source_col="__file_name__",
    )

    df_transformed = (
        df_validated.select(
            [
                "__file_name__",
                "__folder_path__",
                pl.col("Stock Name").alias("Instrument Name"),
                "ISIN",
                pl.col("Yahoo Ticker").alias("yF_Ticker"),
                pl.col("Order Date").alias("Date"),
                pl.col("Transaction Type").alias("Type"),
                "Quantity",
                pl.col("Price ($)").alias("Price_Local"),
                pl.col("Order Amount ($)").alias("Value_Local"),
                pl.col("Exch Rate").alias("FX_Rate"),
                pl.col("Order Amount (INR)").alias("Value"),
                pl.col("Brokerage (INR)").alias("Brokerage_INR"),
                pl.col("Currency").alias("CURRENCY_ID"),
            ]
        )
        .with_columns(
            [
                pl.lit("US Stocks").alias("__file_category__"),
                (pl.col("Price_Local") * pl.col("FX_Rate")).alias("Price"),
            ]
        )
    )
    return df_transformed


def transform_stg_us_stock_trades(base_orders_lazy: pl.LazyFrame, trade_type: str) -> pl.LazyFrame:
    """Branches the base orders into BUY or SELL tables and calculates per unit prices."""
    df_transformed = base_orders_lazy.filter(pl.col("Type") == trade_type).with_columns(
        [
            pl.when(pl.col("Quantity") == 0)
            .then(0.0)
            .otherwise(pl.col("Value_Local") / pl.col("Quantity"))
            .alias("Price_Local"),
            pl.when(pl.col("Quantity") == 0)
            .then(0.0)
            .otherwise(pl.col("Value") / pl.col("Quantity"))
            .alias("Price"),
        ]
    )
    return df_transformed


def get_stg_us_stock_master_ref(
    base_orders_lazy: pl.LazyFrame, d_asset_subcategory_lazy: pl.LazyFrame
) -> pl.LazyFrame:
    """Translates stg_StockMasterRef for US Stocks from transactions."""
    stock_category_lazy = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Stocks & ETFs"
    ).select(pl.col("UID").alias("CATEGORY_ID"))

    df_grouped = (
        base_orders_lazy.select(
            ["ISIN", pl.col("Instrument Name").alias("INSTRUMENT_NAME"), "CURRENCY_ID"]
        )
        .unique()
        .with_columns(
            [
                pl.col("INSTRUMENT_NAME").alias("INSTRUMENT_HOUSE"),
                pl.lit("Equity").alias("INSTRUMENT_TYPE"),
                pl.lit("US Stocks").alias("INSTRUMENT_CLASS"),
                pl.lit("US Stocks").alias("INSTRUMENT_SUBTYPE"),
            ]
        )
        .join(stock_category_lazy, how="cross")
    )
    return df_grouped

