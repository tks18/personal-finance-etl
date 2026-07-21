import os
from datetime import datetime

import fastexcel
import polars as pl


def get_stg_stock_market_data(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """
    Applies the final PQ & DAX transformations.
    Returns a LazyFrame.
    """
    df_combined = raw_data
    available_cols = df_combined.collect_schema().names()

    # 3. Apply Final PQ & DAX Transformations
    df_transformed = df_combined.filter(pl.col("Stock name").is_not_null())

    # Power Query: Handle the typo in "Unrealised P&L" vs "Unealised P&L" dynamically
    if "Unealised P&L" in available_cols and "Unrealised P&L" in available_cols:
        df_transformed = (
            df_transformed.with_columns(
                [
                    pl.col("Unealised P&L").cast(pl.Float64).fill_null(0.0),
                    pl.col("Unrealised P&L").cast(pl.Float64).fill_null(0.0),
                ]
            )
            .with_columns(
                (pl.col("Unealised P&L") + pl.col("Unrealised P&L")).alias("Unrealised P&L_Final")
            )
            .drop(["Unealised P&L", "Unrealised P&L"])
            .rename({"Unrealised P&L_Final": "Unrealised P&L"})
        )
    elif "Unealised P&L" in available_cols and "Unrealised P&L" not in available_cols:
        df_transformed = df_transformed.rename({"Unealised P&L": "Unrealised P&L"})

    current_cols = df_transformed.collect_schema().names()
    num_cols = [
        "Quantity",
        "Buy price",
        "Buy value",
        "Closing price",
        "Closing value",
        "Unrealised P&L",
    ]

    df_transformed = (
        df_transformed.with_columns(  # Power Query: Change Types
            [
                pl.col(c)
                .cast(pl.String)
                .str.replace_all(",", "")
                .cast(pl.Float64, strict=False)
                .fill_null(0.0)
                for c in num_cols
                if c in current_cols
            ]
        )
        .with_columns(
            [
                # Using try_parse_dates on the string dates from Excel
                pl.col("Buy date").str.to_date("%d-%m-%Y", strict=False),
                pl.col("Closing date").str.to_date("%d-%m-%Y", strict=False),
            ]
        )
        # DAX: Calculated Columns
        .with_columns(
            pl.when(pl.col("ISIN").str.contains("INF"))
            .then(pl.lit("ETFs"))
            .otherwise(pl.lit("Direct Stocks"))
            .alias("STOCKS_CLASS"),
            pl.lit("INR_INR").alias("CURRENCY_ID"),
        )
        # Power Query: Reordered Columns (Select)
        .select(
            [
                "__file_name__",
                "__folder_path__",
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
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Stocks.
    Groups by Date, ISIN, Instrument Name, Closing Price, and Buy Price,
    then sums the Quantity and calculates the values.
    """
    df_grouped = (
        stg_stock_market_data_lazy
        # SUMMARIZE (Group By)
        .group_by(
            [
                "__file_name__",
                "__folder_path__",
                pl.col("Month Date").alias("Date"),
                "ISIN",
                pl.col("Stock name").alias("Instrument Name"),
                pl.col("Closing price").alias("Closing Price"),
                pl.col("Buy price").alias("Buy Price"),
            ]
        )
        # CALCULATE(SUM(Quantity))
        .agg(pl.col("Quantity").sum().alias("Quantity"))
        # Add DAX Calculated Columns
        .with_columns(
            [
                (pl.col("Quantity") * pl.col("Closing Price")).alias("Closing Value"),
                (pl.col("Quantity") * pl.col("Buy Price")).alias("Buy Value"),
                (pl.col("Closing Price") - pl.col("Buy Price")).alias("Unit P/L"),
            ]
        )
        .with_columns((pl.col("Quantity") * pl.col("Unit P/L")).alias("Total P/L"))
    )
    return df_grouped


def get_base_stock_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """
    Acts as the STOCK_TRANSACTIONS helper query.
    Returns a single LazyFrame containing both Buys and Sells.
    """
    df_combined = raw_data

    df_transformed = (
        df_combined
        # Power Query: Filter out empty strings in Stock Name
        .filter(pl.col("Stock name") != "")
        # Select required columns
        .select(
            [
                "__file_name__",
                "__folder_path__",
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
        # Power Query: Type Casting & Date Conversion
        .with_columns(
            [
                pl.col("Quantity").cast(pl.Float64),
                pl.col("Value").cast(pl.Float64),
                # PQ extracts just the Date from the DateTime string
                pl.col("Execution date and time")
                .str.to_datetime(format="%d-%m-%Y %I:%M %p", strict=False)
                .dt.date()
                .alias("Execution date and time"),
            ]
        )
    )

    return df_transformed


def transform_stg_stock_trades(
    base_stock_orders_lazy: pl.LazyFrame, trade_type: str
) -> pl.LazyFrame:
    """
    Branches the base orders into BUY or SELL tables and applies DAX calcs.
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
    """
    Translates stg_StockMasterRef.
    Groups by ISIN, Name, and Class, and adds static Stock attributes.
    """

    # DAX LOOKUPVALUE equivalent for CATEGORY_ID
    # We find the UID where ASSET_NAME == "Stocks & ETFs"
    category_id_df = (
        d_asset_subcategory_lazy.filter(pl.col("ASSET_NAME") == "Stocks & ETFs")
        .select("UID")
        .collect()
    )
    stock_category_id = category_id_df[0, 0] if not category_id_df.is_empty() else None

    df_grouped = (
        stg_stock_market_data_lazy
        # SUMMARIZE equivalent (distinct)
        .select(
            [
                "ISIN",
                pl.col("Stock name").alias("INSTRUMENT_NAME"),
                pl.col("STOCKS_CLASS").alias("INSTRUMENT_CLASS"),
            ]
        )
        .unique()
        # Add DAX Calculated Columns
        .with_columns(
            [
                pl.col("INSTRUMENT_NAME").alias("INSTRUMENT_HOUSE"),
                pl.lit("Equity").alias("INSTRUMENT_TYPE"),
                pl.col("INSTRUMENT_CLASS").alias("INSTRUMENT_SUBTYPE"),
                pl.lit(stock_category_id).alias("CATEGORY_ID"),
            ]
        )
    )
    return df_grouped

