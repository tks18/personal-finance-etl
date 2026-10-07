import polars as pl


def get_base_us_stock_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """
    Acts as the US_STOCK_TRANSACTIONS helper query.
    Returns a single LazyFrame containing both Buys and Sells with translation to INR.
    """
    df_transformed = (
        raw_data.filter(pl.col("Stock Name").is_not_null() & (pl.col("Stock Name") != ""))
        .select(
            [
                "__file_name__",
                "__folder_path__",
                pl.col("Stock Name").alias("Instrument Name"),
                "ISIN",
                pl.col("Yahoo Ticker").alias("yF_Ticker"),
                pl.coalesce(
                    pl.col("Order Date").cast(pl.Date, strict=False),
                    pl.col("Order Date").cast(pl.String).str.to_date("%d-%b-%y", strict=False),
                    pl.col("Order Date")
                    .cast(pl.String)
                    .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
                    .dt.date(),
                    pl.col("Order Date").cast(pl.String).str.to_date("%Y-%m-%d", strict=False),
                ).alias("Date"),
                pl.col("Transaction Type").alias("Type"),
                pl.col("Quantity").cast(pl.Float64),
                pl.col("Price ($)").cast(pl.Float64).alias("Price_Local"),
                pl.col("Order Amount ($)").cast(pl.Float64).alias("Value_Local"),
                pl.col("Exch Rate").cast(pl.Float64).alias("FX_Rate"),
                pl.col("Order Amount (INR)").cast(pl.Float64).alias("Value"),
                pl.col("Brokerage (INR)").cast(pl.Float64).alias("Brokerage_INR"),
            ]
        )
        .with_columns(
            [
                pl.lit("US Stocks").alias("FILE_CATEGORY"),
                pl.lit("INR_USD").alias("CURRENCY_ID"),
                (pl.col("Price_Local") * pl.col("FX_Rate")).alias("Price"),
            ]
        )
    )
    return df_transformed


def transform_stg_us_stock_trades(base_orders_lazy: pl.LazyFrame, trade_type: str) -> pl.LazyFrame:
    """
    Branches the base orders into BUY or SELL tables and calculates per unit prices.
    """
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
    """
    Translates stg_StockMasterRef for US Stocks from transactions.
    """
    stock_category_lazy = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Stocks & ETFs"
    ).select(pl.col("UID").alias("CATEGORY_ID"))

    df_grouped = (
        base_orders_lazy.select(["ISIN", pl.col("Instrument Name").alias("INSTRUMENT_NAME"), "CURRENCY_ID"])
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
