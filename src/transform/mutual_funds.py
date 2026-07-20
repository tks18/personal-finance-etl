import polars as pl
import os
from datetime import datetime
import fastexcel


def process_mf_statement(file_path: str) -> pl.DataFrame:
    """
    Acts as the ProcessMFStatements helper query.
    Reads unstructured Excel file, finds 'Scheme Name', 
    and returns a clean DataFrame.
    """
    excel_reader = fastexcel.read_excel(file_path)

    # Power Query logic: Filter for "Holdings" sheet
    if "Holdings" not in excel_reader.sheet_names:
        return pl.DataFrame()

    df_raw = excel_reader.load_sheet("Holdings", header_row=None).to_polars()
    col_1 = df_raw.columns[0]

    # Dynamically find the row where "Scheme Name" appears
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")

    if start_search.is_empty():
        return pl.DataFrame()

    # Power Query: Table.PositionOf (unlike stocks, the header IS this row)
    header_idx = start_search["index"][0]

    # Slice the dataframe starting from the header row
    df_sliced = df_raw.slice(header_idx)

    # ---------------------------------------------------------
    # Deduplicate and clean headers before renaming
    # ---------------------------------------------------------
    raw_headers = df_sliced.row(0)
    clean_headers = []
    seen: dict[str, int] = {}

    for i, h in enumerate(raw_headers):
        header_str = str(h).strip() if h is not None else ""
        if header_str in ("", "None", "null"):
            header_str = f"Unnamed_{i}"

        if header_str in seen:
            seen[header_str] += 1
            header_str = f"{header_str}_{seen[header_str]}"
        else:
            seen[header_str] = 0

        clean_headers.append(header_str)

    # Rename columns using the cleaned header list
    df_data = df_sliced.slice(1).rename(
        {old: new for old, new in zip(df_sliced.columns, clean_headers)}
    )

    # Filter out rows where the primary column (Scheme Name) is null
    first_col = clean_headers[0]
    df_clean = df_data.filter(pl.col(first_col).is_not_null())

    return df_clean


def get_stg_mf_market_data(valid_files: list[str], stg_mf_isin_mapping_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Extracts dates, processes binaries, 
    and applies final PQ & DAX transformations (including LOOKUPVALUE).
    Returns a LazyFrame.
    """
    all_dfs = []

    for file_path in valid_files:
        filename = os.path.basename(file_path)

        # Extract Text Between Delimiters (" - " and ".")
        try:
            date_str = filename.split(" - ")[1].split(".")[0].strip()
            month_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except (IndexError, ValueError):
            continue

        df_processed = process_mf_statement(file_path)

        if df_processed.is_empty():
            continue

        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("Name"),
            pl.lit(month_date).alias("Month Date")
        )

        all_dfs.append(df_processed)

    if not all_dfs:
        raise ValueError("No valid MF statements found in Folder")

    df_combined = pl.concat(all_dfs, how="diagonal").lazy()

    # Apply PQ & DAX Transformations
    df_transformed = (
        df_combined
        # Replace "N/A" with "0" in XIRR before casting
        .with_columns(
            pl.col("XIRR").str.replace("N/A", "0").fill_null("0")
        )

        # Power Query: Change Types
        .with_columns([
            # Usually better as string if leading zeros matter, but cast to Int64 if preferred
            pl.col("Folio No.").cast(pl.String),
            pl.col("Units").cast(pl.Float64),
            pl.col("Invested Value").cast(pl.Float64),
            pl.col("Current Value").cast(pl.Float64),
            pl.col("Returns").cast(pl.Float64),
            pl.col("XIRR").cast(pl.Float64)
        ])

        # Filter: Scheme Name <> "NO HOLDINGS FOUND"
        .filter(pl.col("Scheme Name") != "NO HOLDINGS FOUND")

        # DAX: CURRENCY_ID
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))

        # DAX: LOOKUPVALUE for ISIN
        # This replicates DAX by joining the MF_ISIN_MAPPING table
        .join(
            stg_mf_isin_mapping_lazy,
            left_on="Scheme Name",
            right_on="INSTRUMENT_NAME",
            how="left"
        )

        # Final Select (Ensure output matches your expected schema)
        .select([
            "Name", "Month Date", "Scheme Name", "AMC", "Category",
            "Sub-category", "Folio No.", "Source", "Units",
            "Invested Value", "Current Value", "Returns", "XIRR",
            "CURRENCY_ID", "ISIN"
        ])
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
        .group_by([
            pl.col("Month Date").alias("Date"),
            "ISIN",
            pl.col("Scheme Name").alias("Instrument Name")
        ])
        # CALCULATE(SUM(Units)), SUM(Current Value), SUM(Invested Value)
        .agg([
            pl.col("Units").sum().alias("Quantity"),
            pl.col("Current Value").sum().alias("Closing Value"),
            pl.col("Invested Value").sum().alias("Buy Value")
        ])
        # Add DAX Calculated Columns (with division by zero protection)
        .with_columns([
            pl.when(pl.col("Quantity") == 0).then(0.0)
              .otherwise(pl.col("Closing Value") / pl.col("Quantity"))
              .alias("Closing Price"),

            pl.when(pl.col("Quantity") == 0).then(0.0)
              .otherwise(pl.col("Buy Value") / pl.col("Quantity"))
              .alias("Buy Price")
        ])
        .with_columns(
            (pl.col("Closing Price") - pl.col("Buy Price")).alias("Unit P/L")
        )
        .with_columns(
            (pl.col("Unit P/L") * pl.col("Quantity")).alias("Total P/L")
        )
    )
    return df_grouped


def process_mf_transaction_statements(file_path: str) -> pl.DataFrame:
    """
    Acts as the ProcessMFTransactionStatements helper query.
    Reads the 'Transactions' sheet and dynamically finds the header row.
    """
    excel_reader = fastexcel.read_excel(file_path)

    if "Transactions" not in excel_reader.sheet_names:
        return pl.DataFrame()

    df_raw = excel_reader.load_sheet(
        "Transactions", header_row=None).to_polars()

    if df_raw.is_empty():
        return pl.DataFrame()

    col_1 = df_raw.columns[0]

    # Find the row where "Scheme Name" appears
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")

    if start_search.is_empty():
        return pl.DataFrame()

    header_idx = start_search["index"][0]

    df_sliced = df_raw.slice(header_idx)

    # ---------------------------------------------------------
    # Deduplicate and clean headers before renaming
    # ---------------------------------------------------------
    raw_headers = df_sliced.row(0)
    clean_headers = []
    seen: dict[str, int] = {}

    for i, h in enumerate(raw_headers):
        header_str = str(h).strip() if h is not None else ""
        if header_str in ("", "None", "null"):
            header_str = f"Unnamed_{i}"

        if header_str in seen:
            seen[header_str] += 1
            header_str = f"{header_str}_{seen[header_str]}"
        else:
            seen[header_str] = 0

        clean_headers.append(header_str)

    # Rename columns and slice the data
    df_data = df_sliced.slice(1).rename(
        {old: new for old, new in zip(df_sliced.columns, clean_headers)}
    )

    # Filter out rows where the primary column is null
    first_col = clean_headers[0]
    df_clean = df_data.filter(pl.col(first_col).is_not_null())

    return df_clean


def get_base_mf_transactions(valid_files: list[str]) -> pl.LazyFrame:
    """
    Acts as the MF_TRANSACTIONS helper query.
    Extracts complex dates, and parses binaries.
    """
    all_dfs = []

    for file_path in valid_files:
        filename = os.path.basename(file_path)

        # Power Query logic for Date: Date.FromText("01-" & BeforeDelimiter & "-" & AfterDelimiter.1)
        # Assuming filename structure like: "Something - MM-YYYY.xlsx"
        try:
            date_str = filename.split(" - ")[1].split(".")[0].strip()
            parts = date_str.split("-")
            # If parts is [MM, YYYY], construct "01-MM-YYYY"
            if len(parts) == 2:
                month_date_str = f"01-{parts[0]}-{parts[1]}"
                month_date = datetime.strptime(
                    month_date_str, "%d-%m-%Y").date()
            else:
                # Fallback if standard format
                month_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except (IndexError, ValueError):
            continue

        df_processed = process_mf_transaction_statements(file_path)

        if df_processed.is_empty():
            continue

        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("Name"),
            pl.lit(month_date).alias("Month Date")
        )

        all_dfs.append(df_processed)

    if not all_dfs:
        raise ValueError("No valid MF Orders found in Folder")

    df_combined = pl.concat(all_dfs, how="diagonal").lazy()

    df_transformed = (
        df_combined
        .select([
            "Name", "Month Date", "Scheme Name", "Transaction Type",
            "Units", "NAV", "Amount", "Date"
        ])
        .with_columns([
            pl.col("Units").cast(pl.Float64),
            pl.col("NAV").cast(pl.Float64),
            pl.col("Amount").cast(pl.Float64),

            # Use strict=False as Excel dates might be dirty
            pl.col("Date").str.to_date("%d %b %Y", strict=False)
        ])
    )

    return df_transformed


def transform_stg_mf_trades(base_mf_orders_lazy: pl.LazyFrame, stg_mf_isin_mapping_lazy: pl.LazyFrame, trade_type: str) -> pl.LazyFrame:
    """
    Branches into Purchase or Sale tables, applies DAX SWITCH logic for old names,
    and runs the ISIN LOOKUPVALUE join.
    trade_type must be "PURCHASE" or "REDEEM".
    """
    # 1. Filter for the specific transaction type
    df_filtered = base_mf_orders_lazy.filter(
        pl.col("Transaction Type").str.contains(f"(?i){trade_type}")
    )

    # 2. DAX SWITCH Logic (Fixing old Scheme Names)
    # Using a dictionary mapping for cleaner execution
    scheme_mapping = {
        "Quant Tax Plan Direct Growth": "Quant ELSS Tax Saver Fund Direct Growth",
        "IDBI India Top 100 Equity Fund Direct Growth": "LIC MF Large Cap Fund Direct Growth",
        "TATA DIGITAL INDIA FUND DIRECT PLAN GROWTH": "Tata Digital India Fund Direct Growth",
        "ICICI PRUDENTIAL TECHNOLOGY FUND - DIRECT PLAN - GROWTH": "ICICI Prudential Technology Direct Plan Growth",
        "DSP BlackRock Small Cap Fund - Direct - Growth": "DSP Small Cap Direct Plan Growth"
    }

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
        how="left"
    )

    return df_transformed


def get_stg_mf_master_ref(stg_mf_market_data_lazy: pl.LazyFrame, stg_mf_purchase_transactions_lazy: pl.LazyFrame, stg_mf_sale_transactions_lazy: pl.LazyFrame, d_asset_subcategory_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Translates stg_MFMasterRef.
    Unions unique ISINs across MF tables, then looks up attributes from Market Data.
    """

    # Get Category ID for Mutual Funds
    category_id_df = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Mutual Funds").select("UID").collect()
    mf_category_id = category_id_df[0,
                                    0] if not category_id_df.is_empty() else None

    # Step 1: UNION of ISIN and Name across the 3 MF tables
    df_union = pl.concat([
        stg_mf_market_data_lazy.select(
            ["ISIN", pl.col("Scheme Name").alias("INSTRUMENT_NAME")]),
        stg_mf_purchase_transactions_lazy.select(
            ["ISIN", pl.col("Final Scheme Name").alias("INSTRUMENT_NAME")]),
        stg_mf_sale_transactions_lazy.select(
            ["ISIN", pl.col("Final Scheme Name").alias("INSTRUMENT_NAME")])
    ]).unique()

    # Step 2: To replicate the CALCULATE(MAX()) and LOOKUPVALUE from Market Data,
    # we get a distinct list of attributes from the Market Data table and join them back.
    mf_attributes = (
        stg_mf_market_data_lazy
        .select(["ISIN", "AMC", "Category", "Sub-category"])
        .group_by("ISIN")
        .agg([
            pl.col("AMC").first().alias("INSTRUMENT_HOUSE"),
            pl.col("Category").max().alias("INSTRUMENT_TYPE"),
            pl.col("Sub-category").max().alias("INSTRUMENT_SUBTYPE")
        ])
    )

    df_grouped = (
        df_union
        .join(mf_attributes, on="ISIN", how="left")
        .with_columns([
            pl.lit("Mutual Funds").alias("INSTRUMENT_CLASS"),
            pl.lit(mf_category_id).alias("CATEGORY_ID")
        ])
    )
    return df_grouped
