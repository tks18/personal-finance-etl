"""Mutual fund dimension, trade, and market data transformations.

Owns
----
- Transformation and strict validation of monthly mutual fund holdings.
- Aggregation of mutual fund market data reference (implied prices and unit PnL).
- Ingestion and date/numeric parsing of raw CAS trade orders.
- Filtering and scheme-name mapping of mutual fund purchases and redemptions.
- Mutual fund instrument master reference extraction (stg_MFMasterRef).

Does not own
-------------
- Excel statement parsing (owned by infrastructure.providers.files.excel).
- FIFO queue allocation (owned by domain.investments.lots.fifo).
"""

import polars as pl

from personal_finance_etl.domain.common.dates import validate_and_parse_dates
from personal_finance_etl.domain.common.validation import validate_and_parse_numerics


def _filter_active_mf_holdings(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter out empty placeholder rows before running strict numeric validation."""
    scheme_clean = pl.col("Scheme Name").cast(pl.String).str.strip_chars()
    return df.filter(
        scheme_clean.is_not_null()
        & (scheme_clean != "")
        & (
            ~scheme_clean.str.to_uppercase().is_in(
                ["NO HOLDINGS FOUND", "NO DATA FOUND", "NO HOLDING FOUND"]
            )
        )
    ).with_columns(
        pl.col("Folio No.").cast(pl.String),
    )


def get_stg_mf_market_data(
    raw_data: pl.LazyFrame, stg_mf_isin_mapping_lazy: pl.LazyFrame, default_currency_id: str
) -> pl.LazyFrame:
    """Apply final PQ & DAX transformations (including LOOKUPVALUE).

    Returns a LazyFrame.
    """
    df_transformed = _filter_active_mf_holdings(raw_data)

    num_cols = ["Units", "Invested Value", "Current Value", "Returns", "XIRR"]
    df_transformed = validate_and_parse_numerics(
        df_transformed,
        num_cols,
        optional_cols={"XIRR", "Returns"},
        source_col="__file_name__",
    )

    df_transformed = (
        df_transformed
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
                "__file_category__",
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
    """Translate DAX SUMMARIZE + CALCULATE(SUM) for Mutual Funds.

    Groups by Date, ISIN, and Instrument Name, sums the Units and Values,
    and back-calculates the implied prices.
    """
    df_grouped = (
        stg_mf_market_data_lazy
        # SUMMARIZE (Group By)
        .group_by(
            [
                "__file_category__",
                pl.col("Month Date").alias("Date"),
                "ISIN",
                pl.col("Scheme Name").alias("Instrument Name"),
                "CURRENCY_ID",
            ]
        )
        # CALCULATE(SUM(Units)), SUM(Current Value), SUM(Invested Value)
        .agg(
            [
                pl.col("Units").sum().alias("Quantity"),
                pl.col("Current Value").sum().alias("Closing_Value"),
                pl.col("Invested Value").sum().alias("Buy_Value"),
            ]
        )
        # Add DAX Calculated Columns (with division by zero protection)
        .with_columns(
            [
                pl.when(pl.col("Quantity") == 0)
                .then(0.0)
                .otherwise(pl.col("Closing_Value") / pl.col("Quantity"))
                .alias("Closing_Price"),
                pl.when(pl.col("Quantity") == 0)
                .then(0.0)
                .otherwise(pl.col("Buy_Value") / pl.col("Quantity"))
                .alias("Buy_Price"),
            ]
        )
        .with_columns((pl.col("Closing_Price") - pl.col("Buy_Price")).alias("Unit_PnL"))
        .with_columns((pl.col("Unit_PnL") * pl.col("Quantity")).alias("Total_PnL"))
    )
    return df_grouped


def get_base_mf_transactions(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Acts as the MF_TRANSACTIONS helper query.

    Extracts complex dates, and parses binaries.
    """
    df_combined = raw_data

    scheme_clean = pl.col("Scheme Name").cast(pl.String).str.strip_chars()
    df_transformed = df_combined.filter(
        scheme_clean.is_not_null()
        & (scheme_clean != "")
        & (
            ~scheme_clean.str.to_uppercase().is_in(
                ["NO TRANSACTIONS FOUND", "NO DATA FOUND", "NO TRANSACTION FOUND"]
            )
        )
    ).select(
        [
            "__file_name__",
            "__folder_path__",
            "__file_category__",
            "Month Date",
            "Scheme Name",
            "Transaction Type",
            "Units",
            "NAV",
            "Amount",
            "Date",
        ]
    )

    df_transformed = validate_and_parse_numerics(
        df_transformed,
        ["Units", "NAV", "Amount"],
        source_col="__file_name__",
    )
    df_transformed = validate_and_parse_dates(
        df_transformed,
        {"Date": ["%d %b %Y", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"]},
        source_col="__file_name__",
    )

    return df_transformed


def transform_stg_mf_trades(
    base_mf_orders_lazy: pl.LazyFrame,
    stg_mf_isin_mapping_lazy: pl.LazyFrame,
    scheme_mapping: dict[str, str],
    trade_type: str,
) -> pl.LazyFrame:
    """Branch into Purchase or Sale tables.

    Apply DAX SWITCH logic for old names and run the ISIN LOOKUPVALUE join.
    trade_type must be "PURCHASE" or "REDEEM".
    """
    # 1. Filter for the specific transaction type
    df_filtered = base_mf_orders_lazy.filter(
        pl.col("Transaction Type").str.contains(f"(?i){trade_type}")
    )

    # 2. DAX SWITCH Logic (Fixing old Scheme Names via configuration)
    if not scheme_mapping:
        scheme_mapping = {}

    # Replace strings natively if they exist in the dictionary, otherwise keep original
    df_mapped = df_filtered.with_columns(
        pl.col("Scheme Name")
        .replace_strict(scheme_mapping, default=pl.col("Scheme Name"))
        .alias("Final Scheme Name")
    )

    # 3. DAX LOOKUPVALUE logic for ISIN
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
    """Translate stg_MFMasterRef.

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

    # Step 2: Extract distinct attributes from Market Data and join back
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
