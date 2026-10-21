"""Indian domestic equity and ETF transformations.

Owns
----
- Transformation and strict validation of monthly stock holdings.
- Aggregation of Indian stock market data reference (implied prices and unit PnL).
- Ingestion and date/numeric parsing of raw broker trade orders.
- Filtering and price computation of stock buy and sell trades.
- Indian stock instrument master reference extraction (stg_StockMasterRef).

Does not own
-------------
- Excel broker parsing (owned by infrastructure.providers.files.excel).
- FIFO queue allocation (owned by domain.investments.lots.fifo).
"""

import polars as pl

from personal_finance_etl.domain.common.dates import validate_and_parse_dates
from personal_finance_etl.domain.common.validation import validate_and_parse_numerics


def _filter_active_stock_holdings(df_combined: pl.LazyFrame) -> pl.LazyFrame:
    """Filter out empty placeholder rows before strict numeric validation."""
    stock_clean = pl.col("Stock name").cast(pl.String).str.strip_chars()
    return df_combined.filter(
        stock_clean.is_not_null()
        & (stock_clean != "")
        & (
            ~stock_clean.str.to_uppercase().is_in(
                ["NO HOLDINGS FOUND", "NO DATA FOUND", "NO HOLDING FOUND"]
            )
        )
    )


def _resolve_unrealised_pnl(df: pl.LazyFrame, has_typo: bool, has_proper: bool) -> pl.LazyFrame:
    """Standardize Unrealised P&L column naming across statements."""
    if has_typo and has_proper:
        return df.with_columns(
            pl.coalesce([pl.col("Unrealised P&L"), pl.col("Unealised P&L")]).alias("Unrealised P&L")
        ).drop("Unealised P&L")
    if has_typo and not has_proper:
        return df.rename({"Unealised P&L": "Unrealised P&L"})
    if not has_proper and not has_typo:
        return df.with_columns(pl.lit(None).cast(pl.Float64).alias("Unrealised P&L"))
    return df


def get_stg_stock_market_data(raw_data: pl.LazyFrame, default_currency_id: str) -> pl.LazyFrame:
    """Apply final PQ and DAX transformations to raw stock market data.

    Returns a LazyFrame.
    """
    df_combined = raw_data
    available_cols = df_combined.collect_schema().names()

    df_transformed = _filter_active_stock_holdings(df_combined)

    has_typo = "Unealised P&L" in available_cols
    has_proper = "Unrealised P&L" in available_cols

    num_cols = ["Quantity", "Buy price", "Buy value", "Closing price", "Closing value"]
    optional_cols = {"Buy price", "Buy value", "Unrealised P&L", "Unealised P&L"}

    if has_proper:
        num_cols.append("Unrealised P&L")
    if has_typo:
        num_cols.append("Unealised P&L")

    df_transformed = validate_and_parse_numerics(
        df_transformed,
        num_cols,
        optional_cols=optional_cols,
        source_col="__file_name__",
    )
    df_transformed = validate_and_parse_dates(
        df_transformed,
        {
            "Buy date": ["%d-%m-%Y", "%Y-%m-%d"],
            "Closing date": ["%d-%m-%Y", "%Y-%m-%d"],
        },
        optional_cols={"Buy date"},
        source_col="__file_name__",
    )

    df_transformed = _resolve_unrealised_pnl(df_transformed, has_typo, has_proper)

    df_transformed = (
        df_transformed
        # DAX: Calculated Columns
        .with_columns(
            pl.when(pl.col("ISIN").str.contains("INF"))
            .then(pl.lit("ETFs"))
            .otherwise(pl.lit("Direct Stocks"))
            .alias("STOCKS_CLASS"),
            pl.lit(default_currency_id).alias("CURRENCY_ID"),
        )
        # Power Query: Reordered Columns (Select)
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "__file_category__",
                "Month Date",
                "Stock name",
                "ISIN",
                "Quantity",
                "Buy date",
                "Buy price",
                "Buy value",
                "Closing date",
                "Closing price",
                "Closing value",
                "Unrealised P&L",
                "Remark",
                "STOCKS_CLASS",
                "CURRENCY_ID",
            ]
        )
    )

    return df_transformed


def get_stg_stock_market_data_ref(stg_stock_market_data_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """Translate DAX SUMMARIZE + CALCULATE(SUM) for Stocks.

    Groups by Date, ISIN, Instrument Name, Closing Price, and Buy Price,
    then sums the Quantity and calculates the values.
    """
    df_grouped = (
        stg_stock_market_data_lazy
        # SUMMARIZE (Group By)
        .group_by(
            [
                "__file_category__",
                pl.col("Month Date").alias("Date"),
                "ISIN",
                pl.col("Stock name").alias("Instrument Name"),
                pl.col("Closing price").alias("Closing_Price"),
                pl.col("Buy price").alias("Buy_Price"),
                "CURRENCY_ID",
            ]
        )
        # CALCULATE(SUM(Quantity))
        .agg(pl.col("Quantity").sum().alias("Quantity"))
        # Add DAX Calculated Columns
        .with_columns(
            [
                (pl.col("Quantity") * pl.col("Closing_Price")).alias("Closing_Value"),
                (pl.col("Quantity") * pl.col("Buy_Price")).alias("Buy_Value"),
                (pl.col("Closing_Price") - pl.col("Buy_Price")).alias("Unit_PnL"),
            ]
        )
        .with_columns((pl.col("Quantity") * pl.col("Unit_PnL")).alias("Total_PnL"))
    )
    return df_grouped


def get_base_stock_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Acts as the STOCK_TRANSACTIONS helper query.

    Returns a single LazyFrame containing both Buys and Sells.
    """
    stock_clean = pl.col("Stock name").cast(pl.String).str.strip_chars()
    df_transformed = (
        raw_data.filter(
            stock_clean.is_not_null()
            & (stock_clean != "")
            & (
                ~stock_clean.str.to_uppercase().is_in(
                    ["NO TRANSACTIONS FOUND", "NO DATA FOUND", "NO TRANSACTION FOUND"]
                )
            )
        )
        # Select required columns
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "__file_category__",
                "Stock name",
                "Symbol",
                "ISIN",
                "Type",
                "Quantity",
                "Value",
                "Exchange",
                "Exchange Order Id",
                "Execution date and time",
                "Order status",
            ]
        )
    )

    df_transformed = validate_and_parse_numerics(
        df_transformed,
        ["Quantity", "Value"],
        source_col="__file_name__",
    )
    df_transformed = validate_and_parse_dates(
        df_transformed,
        {
            "Execution date and time": [
                "%d-%m-%Y %I:%M %p",
                "%d-%m-%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%d-%m-%Y",
                "%Y-%m-%d",
            ]
        },
        source_col="__file_name__",
    )

    return df_transformed


def transform_stg_stock_trades(
    base_stock_orders_lazy: pl.LazyFrame, trade_type: str
) -> pl.LazyFrame:
    """Branches the base orders into BUY or SELL tables and applies DAX calcs.

    trade_type must be "BUY" or "SELL".
    """
    df_transformed = (
        base_stock_orders_lazy
        # PQ: Filtered Rows ([Type] = "BUY" / "SELL")
        .filter(pl.col("Type") == trade_type)
        # DAX: Price = DIVIDE(Value, Quantity, 0)
        .with_columns(
            pl.when(pl.col("Quantity") == 0)
            .then(0.0)
            .otherwise(pl.col("Value") / pl.col("Quantity"))
            .alias("Price")
        )
    )

    return df_transformed


def get_stg_stock_master_ref(
    stg_stock_market_data_lazy: pl.LazyFrame, d_asset_subcategory_lazy: pl.LazyFrame
) -> pl.LazyFrame:
    """Translate stg_StockMasterRef dimensional data.

    Groups by ISIN, Name, and Class, and adds static Stock attributes.
    """
    # We lazily fetch Category ID
    stock_category_lazy = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Stocks & ETFs"
    ).select(pl.col("UID").alias("CATEGORY_ID"))

    df_grouped = (
        stg_stock_market_data_lazy.select(
            [
                "ISIN",
                pl.col("Stock name").alias("INSTRUMENT_NAME"),
                pl.col("STOCKS_CLASS").alias("INSTRUMENT_CLASS"),
                "CURRENCY_ID",
            ]
        )
        .unique()
        # Add DAX Calculated Columns
        .with_columns(
            [
                pl.col("INSTRUMENT_NAME").alias("INSTRUMENT_HOUSE"),
                pl.lit("Equity").alias("INSTRUMENT_TYPE"),
                pl.col("INSTRUMENT_CLASS").alias("INSTRUMENT_SUBTYPE"),
            ]
        )
        .join(stock_category_lazy, how="cross")
    )
    return df_grouped
