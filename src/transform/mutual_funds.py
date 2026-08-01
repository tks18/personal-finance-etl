import polars as pl


def get_stg_mf_market_data(
    raw_data: pl.LazyFrame, stg_mf_isin_mapping_lazy: pl.LazyFrame, default_currency_id: str
) -> pl.LazyFrame:
    """
    Applies final PQ & DAX transformations (including LOOKUPVALUE).
    Returns a LazyFrame.
    """
    df_combined = raw_data

    # Apply PQ & DAX Transformations
    df_transformed = (
        df_combined
        # Replace "N/A" with "0" in XIRR before casting
        .with_columns(
            pl.col("XIRR").cast(pl.String).str.replace("N/A", "0", literal=True).fill_null("0")
        )
        # Power Query: Change Types
        .with_columns(
            [
                # Usually better as string if leading zeros matter, but cast to Int64 if preferred
                pl.col("Folio No.").cast(pl.String),
                pl.col("Units").cast(pl.Float64),
                pl.col("Invested Value").cast(pl.Float64),
                pl.col("Current Value").cast(pl.Float64),
                pl.col("Returns").cast(pl.Float64),
                pl.col("XIRR").cast(pl.Float64),
            ]
        )
        # Filter: Scheme Name <> "NO HOLDINGS FOUND"
        .filter(pl.col("Scheme Name") != "NO HOLDINGS FOUND")
        # DAX: CURRENCY_ID
        .with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
        # DAX: LOOKUPVALUE for ISIN
        # This replicates DAX by joining the MF_ISIN_MAPPING table
        .join(
            stg_mf_isin_mapping_lazy, left_on="Scheme Name", right_on="INSTRUMENT_NAME", how="left"
        )
        # Final Select (Ensure output matches your expected schema)
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "Month Date",
                "Scheme Name",
                "AMC",
                "Category",
                "Sub-category",
                "Folio No.",
                "Source",
                "Units",
                "Invested Value",
                "Current Value",
                "Returns",
                "XIRR",
                "CURRENCY_ID",
                "ISIN",
            ]
        )
    )

    return df_transformed


def get_stg_mf_market_data_ref(stg_mf_market_data_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Mutual Funds.
    Groups by Date, ISIN, and Instrument Name, sums the Units and Values,
    and back-calculates the implied prices.
    """
    df_grouped = (
        stg_mf_market_data_lazy
        # SUMMARIZE (Group By)
        .group_by(
            [
                "__file_name__",
                "__folder_path__",
                pl.col("Month Date").alias("Date"),
                "ISIN",
                pl.col("Scheme Name").alias("Instrument Name"),
            ]
        )
        # CALCULATE(SUM(Units)), SUM(Current Value), SUM(Invested Value)
        .agg(
            [
                pl.col("Units").sum().alias("Quantity"),
                pl.col("Current Value").sum().alias("Closing Value"),
                pl.col("Invested Value").sum().alias("Buy Value"),
            ]
        )
        # Add DAX Calculated Columns (with division by zero protection)
        .with_columns(
            [
                pl.when(pl.col("Quantity") == 0)
                .then(0.0)
                .otherwise(pl.col("Closing Value") / pl.col("Quantity"))
                .alias("Closing Price"),
                pl.when(pl.col("Quantity") == 0)
                .then(0.0)
                .otherwise(pl.col("Buy Value") / pl.col("Quantity"))
                .alias("Buy Price"),
            ]
        )
        .with_columns((pl.col("Closing Price") - pl.col("Buy Price")).alias("Unit P/L"))
        .with_columns((pl.col("Unit P/L") * pl.col("Quantity")).alias("Total P/L"))
    )
    return df_grouped


def get_base_mf_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """
    Acts as the MF_TRANSACTIONS helper query.
    Extracts complex dates, and parses binaries.
    """
    df_combined = raw_data

    df_transformed = df_combined.select(
        [
            "__file_name__",
            "__folder_path__",
            "Month Date",
            "Scheme Name",
            "Transaction Type",
            "Units",
            "NAV",
            "Amount",
            "Date",
        ]
    ).with_columns(
        [
            pl.col("Units").cast(pl.Float64),
            pl.col("NAV").cast(pl.Float64),
            pl.col("Amount").cast(pl.Float64),
            # Use strict=False as Excel dates might be dirty
            pl.col("Date").str.to_date("%d %b %Y", strict=False),
        ]
    )

    return df_transformed


def transform_stg_mf_trades(
    base_mf_orders_lazy: pl.LazyFrame,
    stg_mf_isin_mapping_lazy: pl.LazyFrame,
    scheme_mapping: dict[str, str],
    trade_type: str,
) -> pl.LazyFrame:
    """
    Branches into Purchase or Sale tables, applies DAX SWITCH logic for old names,
    and runs the ISIN LOOKUPVALUE join.
    trade_type must be "PURCHASE" or "REDEEM".
    """
    # 1. Filter for the specific transaction type
    df_filtered = base_mf_orders_lazy.filter(
        pl.col("Transaction Type").str.contains(f"(?i){trade_type}")
    )

    # 2. DAX SWITCH Logic (Fixing old Scheme Names via configuration)
    # The mapping is strictly provided via the config.toml file.
    if not scheme_mapping:
        scheme_mapping = {}

    # Replace strings natively if they exist in the dictionary, otherwise keep original
    df_mapped = df_filtered.with_columns(
        pl.col("Scheme Name")
        .replace_strict(scheme_mapping, default=pl.col("Scheme Name"))
        .alias("Final Scheme Name")
    )

    # 3. DAX LOOKUPVALUE logic for ISIN
    # Replicated by joining the ISIN mapping table
    df_transformed = df_mapped.join(
        stg_mf_isin_mapping_lazy,
        left_on="Final Scheme Name",
        right_on="INSTRUMENT_NAME",
        how="left",
    )

    return df_transformed


def get_stg_mf_master_ref(
    stg_mf_market_data_lazy: pl.LazyFrame,
    stg_mf_purchase_transactions_lazy: pl.LazyFrame,
    stg_mf_sale_transactions_lazy: pl.LazyFrame,
    d_asset_subcategory_lazy: pl.LazyFrame,
) -> pl.LazyFrame:
    """
    Translates stg_MFMasterRef.
    Unions unique ISINs across MF tables, then looks up attributes from Market Data.
    """

    mf_category_lazy = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Mutual Funds"
    ).select(pl.col("UID").alias("CATEGORY_ID"))

    # Step 1: UNION of ISIN and Name across the 3 MF tables
    df_union = pl.concat(
        [
            stg_mf_market_data_lazy.select(
                ["ISIN", pl.col("Scheme Name").alias("INSTRUMENT_NAME")]
            ),
            stg_mf_purchase_transactions_lazy.select(
                ["ISIN", pl.col("Final Scheme Name").alias("INSTRUMENT_NAME")]
            ),
            stg_mf_sale_transactions_lazy.select(
                ["ISIN", pl.col("Final Scheme Name").alias("INSTRUMENT_NAME")]
            ),
        ]
    ).unique()

    # Step 2: To replicate the CALCULATE(MAX()) and LOOKUPVALUE from Market Data,
    # we get a distinct list of attributes from the Market Data table and join them back.
    mf_attributes = (
        stg_mf_market_data_lazy.select(["ISIN", "AMC", "Category", "Sub-category"])
        .group_by("ISIN")
        .agg(
            [
                pl.col("AMC").first().alias("INSTRUMENT_HOUSE"),
                pl.col("Category").max().alias("INSTRUMENT_TYPE"),
                pl.col("Sub-category").max().alias("INSTRUMENT_SUBTYPE"),
            ]
        )
    )

    df_grouped = (
        df_union.join(mf_attributes, on="ISIN", how="left")
        .with_columns([pl.lit("Mutual Funds").alias("INSTRUMENT_CLASS")])
        .join(mf_category_lazy, how="cross")
    )
    return df_grouped
