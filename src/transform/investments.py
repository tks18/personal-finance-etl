import polars as pl


def get_purchase_reference(
    df_lazy: pl.LazyFrame, instrument_col: str, date_col: str, price_col: str, qty_col: str
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Purchases.
    Groups by Instrument, ISIN, Date, and Price, then sums the Quantity.
    Returns: ISIN, Date, Price, Quantity, Value
    """
    df_grouped = (
        df_lazy
        # SUMMARIZE equivalent
        .group_by(
            [
                "__file_name__",
                "__folder_path__",
                "ISIN",
                pl.col(instrument_col).alias("Instrument name"),
                pl.col(date_col).alias("Date"),
                pl.col(price_col).alias("Price"),
            ]
        )
        # CALCULATE(SUM(Quantity)) equivalent
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        # DAX: Value = Quantity * Price
        .with_columns((pl.col("Quantity") * pl.col("Price")).alias("Value"))
    )
    return df_grouped


def get_sale_reference(
    df_sale_lazy: pl.LazyFrame,
    df_purchase_ref_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Sales.
    Also calculates the Rolling Average Buy Price based on historical purchases.
    """

    # Step 1: Base Sale Aggregation (SUMMARIZE + SUM(Quantity))
    df_sale_grouped = (
        df_sale_lazy.group_by(
            [
                "__file_name__",
                "__folder_path__",
                "ISIN",
                pl.col(instrument_col).alias("Instrument name"),
                pl.col(date_col).alias("Date"),
                pl.col(price_col).alias("Sell Price"),
            ]
        )
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        .with_columns((pl.col("Quantity") * pl.col("Sell Price")).alias("Sell Value"))
    )

    # Step 2: Cumulative Sum of Purchases (Rolling calculation for DAX VAR Qty & VAR Val)
    # We sort by ISIN and Date, then calculate rolling sums to get total historical buys up to each date
    df_purchase_rolling = (
        df_purchase_ref_lazy.select(["ISIN", "Date", "Quantity", "Value"])
        .sort(["ISIN", "Date"])
        .with_columns(
            [
                pl.col("Quantity").cum_sum().over("ISIN").alias("Cum_Buy_Qty"),
                pl.col("Value").cum_sum().over("ISIN").alias("Cum_Buy_Val"),
            ]
        )
    )

    # Step 3: ASOF Join (Replicating FILTER(Date <= Sale Date))
    # join_asof perfectly matches each sale to the most recent historical purchase state
    df_final = (
        df_sale_grouped.sort(["ISIN", "Date"])  # Both frames must be sorted by the join keys
        .with_columns(pl.col("Date"))
        .join_asof(
            df_purchase_rolling.sort(["ISIN", "Date"]),
            on="Date",
            by="ISIN",
            strategy="backward",  # Matches the closest date <= Sale Date
        )
        # Calculate final DAX columns
        .with_columns(
            # Buy Price = DIVIDE(Cum_Buy_Val, Cum_Buy_Qty, 0)
            pl.when(pl.col("Cum_Buy_Qty").is_null() | (pl.col("Cum_Buy_Qty") == 0))
            .then(0.0)
            .otherwise(pl.col("Cum_Buy_Val") / pl.col("Cum_Buy_Qty"))
            .alias("Buy Price")
        )
        .with_columns(
            [
                (pl.col("Quantity") * pl.col("Buy Price")).alias("Buy Value"),
                (pl.col("Sell Price") - pl.col("Buy Price")).alias("Unit P/L"),
            ]
        )
        .with_columns((pl.col("Unit P/L") * pl.col("Quantity")).alias("Total P/L"))
        # Keep only required columns
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "ISIN",
                "Instrument name",
                "Date",
                "Quantity",
                "Sell Price",
                "Sell Value",
                "Buy Price",
                "Buy Value",
                "Unit P/L",
                "Total P/L",
            ]
        )
    )

    return df_final


def transform_stg_investment_market_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """
    Translates DAX UNION + SUMMARIZE.
    Concatenates the aggregated tables and selects the final columns.
    """

    # Ensure both frames have the exact same columns in the exact same order for UNION
    select_cols = [
        "__file_name__",
        "__folder_path__",
        "Date",
        "ISIN",
        "Quantity",
        "Closing Price",
        "Buy Price",
        "Closing Value",
        "Buy Value",
        "Unit P/L",
        "Total P/L",
    ]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    # The outer SUMMARIZE in DAX acts as a distinct/group by on the unioned result.
    df_final = (
        df_union.group_by(select_cols)
        .agg([])
        .sort(["ISIN", "Date", "Quantity", "Buy Price", "Closing Price"])
    )

    return df_final


def get_f_tf_investment_purchase_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Purchases."""
    select_cols = ["__file_name__", "__folder_path__", "ISIN", "Date", "Price", "Quantity", "Value"]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    df_final = (
        df_union.group_by(select_cols)
        .agg([])  # SUMMARIZE (distinct)
        .sort(["ISIN", "Date", "Quantity", "Price"])
        # DAX calculated col
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final


def get_f_tf_investment_sale_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Sales."""
    select_cols = [
        "__file_name__",
        "__folder_path__",
        "ISIN",
        "Date",
        "Quantity",
        "Sell Price",
        "Sell Value",
        "Buy Price",
        "Buy Value",
        "Unit P/L",
        "Total P/L",
    ]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    df_final = (
        df_union.group_by(select_cols)
        .agg([])  # SUMMARIZE (distinct)
        .sort(["ISIN", "Date", "Quantity", "Sell Price"])
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final


def get_d_tf_investment_master(
    master_refs: list[pl.LazyFrame], stg_benchmark_mapping_lazy: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Translates d_tf_InvestmentMaster.
    Unions the References into a single distinct dimension table,
    then joins the Benchmark Mapping to pull in Sector, Industry, Tax flags, etc.
    """

    # Define common schema to ensure clean union
    select_cols = [
        "ISIN",
        "INSTRUMENT_NAME",
        "INSTRUMENT_HOUSE",
        "INSTRUMENT_CLASS",
        "INSTRUMENT_TYPE",
        "INSTRUMENT_SUBTYPE",
        "CATEGORY_ID",
    ]

    # Union the References
    df_master_union = pl.concat([ref.select(select_cols) for ref in master_refs]).unique(
        subset=["ISIN"]
    )  # Ensure one row per ISIN

    # Replicate DAX LOOKUPVALUE by joining the Benchmark Mapping
    df_final = df_master_union.join(stg_benchmark_mapping_lazy, on="ISIN", how="left").select(
        [
            "ISIN",
            "INSTRUMENT_NAME",
            "INSTRUMENT_HOUSE",
            "INSTRUMENT_CLASS",
            "INSTRUMENT_TYPE",
            "INSTRUMENT_SUBTYPE",
            "CATEGORY_ID",
            # Rename columns to match DAX output if needed
            pl.col("Sector").alias("SECTOR"),
            pl.col("Industry").alias("INDUSTRY"),
            pl.col("Benchmark_ID").alias("BENCHMARK_ID"),
            # Ensure these match the actual headers in BENCHMARK_MAPPING.csv
            pl.col("Tax_Instrument_Type").alias("TAX_TYPE"),
            pl.col("Tax_Instrument_Subtype").alias("TAX_SUBTYPE"),
        ]
    )

    return df_final
