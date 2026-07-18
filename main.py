import polars as pl
import sqlite3
import os
import glob
from datetime import datetime
import fastexcel
from dateutil.relativedelta import relativedelta
import calendar

# Ensure this matches your actual DB paths
SOURCE_DB_FOLDER = r"G:\My Drive\MoneyManager"
TARGET_DB_BASE_PATH = r"D:\Python Projects\personal-finance-etl\outputs"
COLUMN_MASTER_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\COLUMN_MASTER.csv"
MF_ISIN_CSV_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\MF_ISIN_MAPPING.csv"
BENCHMARK_MAPPING_CSV_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\BENCHMARK_MAPPING.csv"
BENCHMARK_MASTER_CSV_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\BENCHMARK_MASTER.csv"
TAX_RATES_CSV_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\TAX_RATES.csv"
OPENING_BALANCE_CSV_PATH = r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__\OPENING_BALANCE.csv"
STATEMENTS_FOLDER = r"G:\My Drive\Docs\Financial Docs\Statements"

# ==========================================
# 1. EXTRACTION LAYER
# ==========================================


def get_latest_sqlite_backup(folder_path):
    """Finds the most recently modified SQLite file in the MoneyManager folder."""
    files = glob.glob(os.path.join(folder_path, "*.*")
                      )  # Adjust extension if needed (e.g. *.db, *.sqlite)
    if not files:
        raise FileNotFoundError(f"No database backup found in {folder_path}")
    return max(files, key=os.path.getmtime)


def get_column_mapping(table_name="CATEGORY"):
    """Reads COLUMN_MASTER.csv and returns a dictionary of {OLD_COLUMN: NEW_COLUMN}"""
    df_map = pl.read_csv(COLUMN_MASTER_PATH)

    # Filter for the specific table and create a dict
    mapping = (
        df_map.filter(pl.col("TABLE_NAME") == table_name)
        .select(["OLD_COLUMN", "NEW_COLUMN"])
        .rows()
    )
    return {old: new for old, new in mapping}

# ==========================================
# STAGING TABLES (In-Memory Only)
# ==========================================


def get_stg_mf_isin_mapping(csv_path):
    """
    Loads the ISIN mapping as a LazyFrame.
    This will NOT be written to SQLite. It will be passed to the 
    Investment Master transformation to replicate the DAX calculated column.
    """
    schema_overrides = {
        "INSTRUMENT_NAME": pl.String,
        "ISIN": pl.String
    }

    # Return the LazyFrame directly
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)


def get_stg_benchmark_mapping(csv_path):
    """
    Loads the Benchmark mapping as a LazyFrame.
    Will be passed to the Investment Master transformation to replicate 
    DAX calculated columns via joins.
    """
    schema_overrides = {
        "ISIN": pl.String,
        "Sector": pl.String,
        "Industry": pl.String,
        "Benchmark_ID": pl.String
    }

    # Return the LazyFrame directly
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)

# ==========================================
# STAGING: STOCK MARKET DATA
# ==========================================


def process_stock_closing_statement(file_path):
    """
    Acts as the ProcessStockClosingStatements helper query.
    Reads an unstructured Excel file, finds the 'Unrealised trades' block, 
    and returns a clean Polars DataFrame.
    """
    # Use fastexcel to load the workbook
    excel_reader = fastexcel.read_excel(file_path)

    # Power Query logic: Look for "Trade Level", then "Sheet", then "Sheet1"
    sheet_names = excel_reader.sheet_names
    target_sheet = None
    for name in ["Trade Level", "Sheet", "Sheet1"]:
        if name in sheet_names:
            target_sheet = name
            break

    if not target_sheet:
        return pl.DataFrame()  # Return empty if no valid sheet found

    # Read the sheet entirely without assuming headers (read as raw matrix)
    df_raw = excel_reader.load_sheet(target_sheet, header_row=None).to_polars()

    # We must dynamically find where "Unrealised trades" is located in Column 1 (index 0)
    col_1 = df_raw.columns[0]

    # Find the row index of "Unrealised trades"
    start_search = df_raw.with_row_index().filter(
        pl.col(col_1) == "Unrealised trades")

    if start_search.is_empty():
        return pl.DataFrame()  # Pattern not found

    # The actual headers are usually 1 row below the title.
    # Power Query: Table.PositionOf + 2 (because PQ skips the title and the blank row)
    header_idx = start_search["index"][0] + 2

    # Slice the dataframe starting from the header row
    df_sliced = df_raw.slice(header_idx)

    # Deduplicate and clean headers before renaming
    raw_headers = df_sliced.row(0)
    clean_headers = []
    seen = {}

    for i, h in enumerate(raw_headers):
        # Convert nulls or purely whitespace headers to a default string
        header_str = str(h).strip() if h is not None else ""
        if header_str in ("", "None", "null"):
            header_str = f"Unnamed_{i}"

        # Ensure it is unique
        if header_str in seen:
            seen[header_str] += 1
            header_str = f"{header_str}_{seen[header_str]}"
        else:
            seen[header_str] = 0

        clean_headers.append(header_str)

    # Now rename safely with unique headers
    df_data = df_sliced.slice(1).rename(
        {old: new for old, new in zip(df_sliced.columns, clean_headers)}
    )

    # Filter out rows where the primary column is null
    first_col = clean_headers[0]
    null_search = df_data.with_row_index().filter(pl.col(first_col).is_null())

    if not null_search.is_empty():
        end_idx = null_search["index"][0]
        df_data = df_data.slice(0, end_idx)

    return df_data


def get_stg_stock_market_data(folder_path):
    """
    Iterates the folder, extracts dates from filenames, processes the binaries, 
    and applies the final PQ & DAX transformations.
    Returns a LazyFrame.
    """

    # 1. Power Query: Filtered Rows (Folder iteration & extension check)
    search_pattern = os.path.join(folder_path, "**", "*.xlsx")
    excel_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    # Filter for "Stock PL Statements" in path
    valid_files = [f for f in excel_files if "Stock PL Statements" in f]

    all_dfs = []

    for file_path in valid_files:
        filename = os.path.basename(file_path)

        # Power Query: Extract Text Between Delimiters ("- " and ".")
        try:
            date_str = filename.split("- ")[1].split(".")[0].strip()
            # Adjust format if needed (e.g., %b %Y)
            month_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except (IndexError, ValueError):
            continue  # Skip files that don't match the naming convention

        # Process the binary
        df_processed = process_stock_closing_statement(file_path)

        if df_processed.is_empty():
            continue

        # Add metadata columns
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("Name"),
            pl.lit(month_date).alias("Month Date")
        )

        all_dfs.append(df_processed)

    if not all_dfs:
        raise ValueError(
            f"No valid Stock PL statements found in {folder_path}")

    # 2. Combine all processed files into a single LazyFrame
    # We use pl.concat with how="diagonal" because some sheets might have 'Unealised P&L'
    # while others have 'Unrealised P&L' (handling typo variations).
    df_combined = pl.concat(all_dfs, how="diagonal").lazy()
    available_cols = df_combined.collect_schema().names()

    # 3. Apply Final PQ & DAX Transformations
    df_transformed = df_combined.filter(pl.col("Stock name").is_not_null())

    # Power Query: Handle the typo in "Unrealised P&L" vs "Unealised P&L" dynamically
    if "Unealised P&L" in available_cols and "Unrealised P&L" in available_cols:
        df_transformed = (
            df_transformed
            .with_columns([
                pl.col("Unealised P&L").cast(pl.Float64).fill_null(0.0),
                pl.col("Unrealised P&L").cast(pl.Float64).fill_null(0.0)
            ])
            .with_columns(
                (pl.col("Unealised P&L") + pl.col("Unrealised P&L")
                 ).alias("Unrealised P&L_Final")
            )
            .drop(["Unealised P&L", "Unrealised P&L"])
            .rename({"Unrealised P&L_Final": "Unrealised P&L"})
        )
    elif "Unealised P&L" in available_cols and "Unrealised P&L" not in available_cols:
        df_transformed = df_transformed.rename(
            {"Unealised P&L": "Unrealised P&L"})

    current_cols = df_transformed.collect_schema().names()
    num_cols = ["Quantity", "Buy price", "Buy value",
                "Closing price", "Closing value", "Unrealised P&L"]

    df_transformed = (df_transformed  # Power Query: Change Types
                      .with_columns([
                          pl.col(c).cast(pl.String).str.replace_all(",", "").cast(
                              pl.Float64, strict=False).fill_null(0.0)
                          for c in num_cols if c in current_cols
                      ])
                      .with_columns([
                          # Using try_parse_dates on the string dates from Excel
                          pl.col("Buy date").str.to_date(
                              "%d-%m-%Y", strict=False),
                          pl.col("Closing date").str.to_date(
                              "%d-%m-%Y", strict=False)
                      ])

                      # DAX: Calculated Columns
                      .with_columns(
                          pl.when(pl.col("ISIN").str.contains("INF"))
                          .then(pl.lit("ETFs"))
                            .otherwise(pl.lit("Direct Stocks"))
                            .alias("STOCKS_CLASS"),

                          pl.lit("INR_INR").alias("CURRENCY_ID")
                      )

                      # Power Query: Reordered Columns (Select)
                      .select([
                          "Name", "Month Date", "Stock name", "ISIN", "Quantity",
                          "Buy date", "Buy price", "Buy value", "Closing date",
                          "Closing price", "Closing value", "Unrealised P&L",
                          "Remark", "STOCKS_CLASS", "CURRENCY_ID"
                      ])
                      )

    return df_transformed

# ==========================================
# STAGING: MUTUAL FUND MARKET DATA
# ==========================================


def process_mf_statement(file_path):
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
    seen = {}

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


def get_stg_mf_market_data(folder_path, stg_mf_isin_mapping_lazy):
    """
    Iterates folder, extracts dates, processes binaries, 
    and applies final PQ & DAX transformations (including LOOKUPVALUE).
    Returns a LazyFrame.
    """
    search_pattern = os.path.join(folder_path, "**", "*.xlsx")
    excel_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    # Filter for "Mutual Funds - Holdings"
    valid_files = [f for f in excel_files if "Mutual Funds - Holdings" in f]

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
        raise ValueError(f"No valid MF statements found in {folder_path}")

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

# ==========================================
# CONSOLIDATED INVESTMENT MARKET DATA
# ==========================================


def get_stg_stock_market_data_ref(stg_stock_market_data_lazy):
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Stocks.
    Groups by Date, ISIN, Instrument Name, Closing Price, and Buy Price,
    then sums the Quantity and calculates the values.
    """
    df_grouped = (
        stg_stock_market_data_lazy
        # SUMMARIZE (Group By)
        .group_by([
            pl.col("Month Date").alias("Date"),
            "ISIN",
            pl.col("Stock name").alias("Instrument Name"),
            pl.col("Closing price").alias("Closing Price"),
            pl.col("Buy price").alias("Buy Price")
        ])
        # CALCULATE(SUM(Quantity))
        .agg(
            pl.col("Quantity").sum().alias("Quantity")
        )
        # Add DAX Calculated Columns
        .with_columns([
            (pl.col("Quantity") * pl.col("Closing Price")).alias("Closing Value"),
            (pl.col("Quantity") * pl.col("Buy Price")).alias("Buy Value"),
            (pl.col("Closing Price") - pl.col("Buy Price")).alias("Unit P/L")
        ])
        .with_columns(
            (pl.col("Quantity") * pl.col("Unit P/L")).alias("Total P/L")
        )
    )
    return df_grouped


def get_stg_mf_market_data_ref(stg_mf_market_data_lazy):
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

# ==========================================
# STAGING: STOCK TRANSACTIONS (BUY/SELL)
# ==========================================


def process_stock_transactions(file_path):
    """
    Acts as the ProcessStockTransactions helper query.
    Reads 'Sheet1', skips 5 rows of broker headers, and promotes the 6th row.
    """
    excel_reader = fastexcel.read_excel(file_path)

    if "Sheet1" not in excel_reader.sheet_names:
        return pl.DataFrame()

    # Read the sheet natively, skipping the first 5 rows
    df_raw = excel_reader.load_sheet("Sheet1", header_row=5).to_polars()

    # Filter where Stock name is not null
    if "Stock name" in df_raw.columns:
        df_clean = df_raw.filter(pl.col("Stock name").is_not_null())
    else:
        df_clean = pl.DataFrame()

    return df_clean


def get_base_stock_transactions(folder_path):
    """
    Acts as the STOCK_TRANSACTIONS helper query.
    Iterates the 'Stock - Orders' folder, processes files, and sets data types.
    Returns a single LazyFrame containing both Buys and Sells.
    """
    search_pattern = os.path.join(folder_path, "**", "*.xlsx")
    excel_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    # Filter for "Stock - Orders"
    valid_files = [f for f in excel_files if "Stock - Orders" in f]

    all_dfs = []

    for file_path in valid_files:
        df_processed = process_stock_transactions(file_path)

        if df_processed.is_empty():
            continue

        filename = os.path.basename(file_path)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("Name"))

        all_dfs.append(df_processed)

    if not all_dfs:
        raise ValueError(f"No valid Stock Orders found in {folder_path}")

    df_combined = pl.concat(all_dfs, how="diagonal").lazy()

    df_transformed = (
        df_combined
        # Power Query: Filter out empty strings in Stock Name
        .filter(pl.col("Stock name") != "")

        # Select required columns
        .select([
            "Name", "Stock name", "Symbol", "ISIN", "Type",
            "Quantity", "Value", "Exchange", "Exchange Order Id",
            "Execution date and time", "Order status"
        ])

        # Power Query: Type Casting & Date Conversion
        .with_columns([
            pl.col("Quantity").cast(pl.Float64),
            pl.col("Value").cast(pl.Float64),
            # PQ extracts just the Date from the DateTime string
            pl.col("Execution date and time")
              .str.to_datetime(format="%d-%m-%Y %I:%M %p", strict=False)
              .dt.date()
              .alias("Execution date and time")
        ])
    )

    return df_transformed


def transform_stg_stock_trades(base_stock_orders_lazy, trade_type):
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
            pl.when(pl.col("Quantity") == 0).then(0.0)
              .otherwise(pl.col("Value") / pl.col("Quantity"))
              .alias("Price")
        )
    )

    return df_transformed

# ==========================================
# STAGING: MUTUAL FUND TRANSACTIONS (BUY/SELL)
# ==========================================


def process_mf_transaction_statements(file_path):
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
    seen = {}

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


def get_base_mf_transactions(folder_path):
    """
    Acts as the MF_TRANSACTIONS helper query.
    Iterates folder, extracts complex dates, and parses binaries.
    """
    search_pattern = os.path.join(folder_path, "**", "*.xlsx")
    excel_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    valid_files = [f for f in excel_files if "Mutual Funds - Orders" in f]

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
        raise ValueError(f"No valid MF Orders found in {folder_path}")

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


def transform_stg_mf_trades(base_mf_orders_lazy, stg_mf_isin_mapping_lazy, trade_type):
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

# ==========================================
# Staging: PURCHASE REFERENCES & AGGREGATIONS
# ==========================================


def get_purchase_reference(df_lazy, instrument_col, date_col, price_col, qty_col):
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Purchases.
    Groups by Instrument, ISIN, Date, and Price, then sums the Quantity.
    Returns: ISIN, Date, Price, Quantity, Value
    """
    df_grouped = (
        df_lazy
        # SUMMARIZE equivalent
        .group_by([
            "ISIN",
            pl.col(instrument_col).alias("Instrument name"),
            pl.col(date_col).alias("Date"),
            pl.col(price_col).alias("Price")
        ])
        # CALCULATE(SUM(Quantity)) equivalent
        .agg(
            pl.col(qty_col).sum().alias("Quantity")
        )
        # DAX: Value = Quantity * Price
        .with_columns(
            (pl.col("Quantity") * pl.col("Price")).alias("Value")
        )
    )
    return df_grouped

# ==========================================
# Staging: SALE REFERENCES & TIME-DEPENDENT JOIN
# ==========================================


def get_sale_reference(df_sale_lazy, df_purchase_ref_lazy, instrument_col, date_col, price_col, qty_col):
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Sales.
    Also calculates the Rolling Average Buy Price based on historical purchases.
    """

    # Step 1: Base Sale Aggregation (SUMMARIZE + SUM(Quantity))
    df_sale_grouped = (
        df_sale_lazy
        .group_by([
            "ISIN",
            pl.col(instrument_col).alias("Instrument name"),
            pl.col(date_col).alias("Date"),
            pl.col(price_col).alias("Sell Price")
        ])
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        .with_columns((pl.col("Quantity") * pl.col("Sell Price")).alias("Sell Value"))
    )

    # Step 2: Cumulative Sum of Purchases (Rolling calculation for DAX VAR Qty & VAR Val)
    # We sort by ISIN and Date, then calculate rolling sums to get total historical buys up to each date
    df_purchase_rolling = (
        df_purchase_ref_lazy
        .select(["ISIN", "Date", "Quantity", "Value"])
        .sort(["ISIN", "Date"])
        .with_columns([
            pl.col("Quantity").cum_sum().over("ISIN").alias("Cum_Buy_Qty"),
            pl.col("Value").cum_sum().over("ISIN").alias("Cum_Buy_Val")
        ])
    )

    # Step 3: ASOF Join (Replicating FILTER(Date <= Sale Date))
    # join_asof perfectly matches each sale to the most recent historical purchase state
    df_final = (
        df_sale_grouped
        .sort(["ISIN", "Date"])  # Both frames must be sorted by the join keys
        .with_columns(pl.col("Date"))
        .join_asof(
            df_purchase_rolling.sort(["ISIN", "Date"]),
            on="Date",
            by="ISIN",
            strategy="backward"  # Matches the closest date <= Sale Date
        )
        # Calculate final DAX columns
        .with_columns(
            # Buy Price = DIVIDE(Cum_Buy_Val, Cum_Buy_Qty, 0)
            pl.when(pl.col("Cum_Buy_Qty").is_null()
                    | (pl.col("Cum_Buy_Qty") == 0))
              .then(0.0)
              .otherwise(pl.col("Cum_Buy_Val") / pl.col("Cum_Buy_Qty"))
              .alias("Buy Price")
        )
        .with_columns([
            (pl.col("Quantity") * pl.col("Buy Price")).alias("Buy Value"),
            (pl.col("Sell Price") - pl.col("Buy Price")).alias("Unit P/L")
        ])
        .with_columns(
            (pl.col("Unit P/L") * pl.col("Quantity")).alias("Total P/L")
        )
        # Keep only required columns
        .select([
            "ISIN", "Instrument name", "Date", "Quantity", "Sell Price",
            "Sell Value", "Buy Price", "Buy Value", "Unit P/L", "Total P/L"
        ])
    )

    return df_final

# ==========================================
# INVESTMENT MASTER (REFERENCES)
# ==========================================


def get_stg_stock_master_ref(stg_stock_market_data_lazy, d_asset_subcategory_lazy):
    """
    Translates stg_StockMasterRef.
    Groups by ISIN, Name, and Class, and adds static Stock attributes.
    """

    # DAX LOOKUPVALUE equivalent for CATEGORY_ID
    # We find the UID where ASSET_NAME == "Stocks & ETFs"
    category_id_df = d_asset_subcategory_lazy.filter(
        pl.col("ASSET_NAME") == "Stocks & ETFs").select("UID").collect()
    stock_category_id = category_id_df[0,
                                       0] if not category_id_df.is_empty() else None

    df_grouped = (
        stg_stock_market_data_lazy
        # SUMMARIZE equivalent (distinct)
        .select(["ISIN", pl.col("Stock name").alias("INSTRUMENT_NAME"), pl.col("STOCKS_CLASS").alias("INSTRUMENT_CLASS")])
        .unique()
        # Add DAX Calculated Columns
        .with_columns([
            pl.col("INSTRUMENT_NAME").alias("INSTRUMENT_HOUSE"),
            pl.lit("Equity").alias("INSTRUMENT_TYPE"),
            pl.col("INSTRUMENT_CLASS").alias("INSTRUMENT_SUBTYPE"),
            pl.lit(stock_category_id).alias("CATEGORY_ID")
        ])
    )
    return df_grouped


def get_stg_mf_master_ref(stg_mf_market_data_lazy, stg_mf_purchase_transactions_lazy, stg_mf_sale_transactions_lazy, d_asset_subcategory_lazy):
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

# ==========================================
# MASTER CALENDAR TABLE
# ==========================================


def get_stg_calendar_ref(
    f_inc_lazy, f_exp_lazy, f_trans_lazy, f_opbal_lazy,
    stg_mkt_lazy, f_pur_lazy, f_sale_lazy
):
    """
    Translates stg_CalendarRef.
    Unions the DATE columns from all 7 fact tables to find the min and max dates.
    """
    def safe_date_cast(col_name):
        return pl.coalesce([
            # 1. If it's already a Date or Datetime, this cast succeeds
            pl.col(col_name).cast(pl.Date, strict=False),

            # 2. If it's a standard string Date ("YYYY-MM-DD")
            pl.col(col_name).cast(pl.String).str.to_date(
                "%Y-%m-%d", strict=False),

            # 3. If it's a standard string Date ("DD-MM-YYYY")
            pl.col(col_name).cast(pl.String).str.to_date(
                "%d-%m-%Y", strict=False),

            # 4. If it's a string Datetime ("YYYY-MM-DD HH:MM:SS")
            pl.col(col_name).cast(pl.String).str.to_datetime(
                "%Y-%m-%d %H:%M:%S", strict=False).dt.date()
        ]).alias("DATE")

    df_union = pl.concat([
        f_inc_lazy.select(safe_date_cast("DATE")),
        f_exp_lazy.select(safe_date_cast("DATE")),
        f_trans_lazy.select(safe_date_cast("DATE")),
        f_opbal_lazy.select(safe_date_cast("ZTXDATESTR")),
        stg_mkt_lazy.select(safe_date_cast("Date")),
        f_pur_lazy.select(safe_date_cast("Date")),
        f_sale_lazy.select(safe_date_cast("Date"))
    ]).unique()

    # We collect this immediately because we need the scalar min/max values to generate the calendar range
    df_collected = df_union.drop_nulls().collect()

    min_date = df_collected["DATE"].min()
    max_date = df_collected["DATE"].max()

    return min_date, max_date

# ==========================================
# 2. TRANSFORMATION LAYER
# ==========================================


def transform_d_income_category(source_db_path, column_mapping):
    """Executes the PQ and DAX logic using Polars LazyFrames."""

    # Connect and read the ZCATEGORY table directly into Polars
    # We use read_database to pull the data, then immediately convert to lazy() for optimization
    query = "SELECT * FROM ZCATEGORY"
    uri = f"sqlite:///{source_db_path}"

    # Note: If adbc fails on the source read, you can fallback to standard sqlite3 fetchall
    # and pl.DataFrame(), but read_database with adbc/sqlalchemy is best.
    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        # PQ: #"Renamed Columns"
        .rename(column_mapping)

        # PQ: CATEGORY_MASTER -> #"Filtered Rows" (IS_DEL <> 1)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")

        # PQ: d_Income_Category -> #"Filtered Rows"
        # (TYPE = 0) and ((Length(CATEGORY_ID) < 1) or CATEGORY_ID is null)
        .filter(
            (pl.col("TYPE") == 0) &
            (pl.col("CATEGORY_ID").is_null() |
             (pl.col("CATEGORY_ID").str.len_chars() < 1))
        )

        # PQ: #"Removed Other Columns"
        .select([
            "S_NO",
            "MODIFY_DATE",
            "UID",
            "CATEGORY_NAME",
            "ORDER_SEQUENCE"
        ])

        # DAX: CATEGORY_NAME_SHORT
        # Using string replacement to remove "Income from " if it exists
        .with_columns(
            pl.col("CATEGORY_NAME")
            .str.replace("Income from ", "", literal=True)
            .alias("CATEGORY_NAME_SHORT")
        )
    )

    return df_transformed


def transform_d_income_subcategory(source_db_path, column_mapping, df_d_income_category_lazy):
    """
    Executes the PQ and DAX logic for Income Subcategories.
    Requires the lazy frame of d_Income_Category to replicate DAX's RELATED().
    """
    query = "SELECT * FROM ZCATEGORY"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    # 1. Power Query Steps
    df_pq = (
        df_lazy
        .rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 0 AND CATEGORY_ID length > 0
        .filter(
            (pl.col("TYPE") == 0) &
            pl.col("CATEGORY_ID").is_not_null() &
            (pl.col("CATEGORY_ID").str.len_chars() > 0)
        )
        .select([
            "S_NO",
            "MODIFY_DATE",
            "UID",
            "CATEGORY_NAME",
            "ORDER_SEQUENCE",
            "CATEGORY_ID"
        ])
    )

    # 2. DAX Steps (RELATED and IF/SEARCH)
    # Replicate RELATED(d_IncomeCategory[CATEGORY_NAME_SHORT])
    df_joined = df_pq.join(
        df_d_income_category_lazy.select(["UID", "CATEGORY_NAME_SHORT"]),
        left_on="CATEGORY_ID",
        right_on="UID",
        how="left"
    )

    df_transformed = (
        df_joined
        .with_columns(
            # DAX: SEARCH is case-insensitive. We use "(?i)" in Polars regex to mimic this.
            # ISERROR(SEARCH) means "If it does NOT contain 'Allowance', then [CATEGORY_NAME], else 'Allowances'"
            pl.when(
                (pl.col("CATEGORY_NAME_SHORT") == "Salary") &
                pl.col("CATEGORY_NAME").str.contains("(?i)allowance")
            )
            .then(pl.lit("Allowances"))
            .otherwise(pl.col("CATEGORY_NAME"))
            .alias("CATEGORY_GROUPS")
        )
        # Drop the joined column to keep the table matching the exact output needed
        .drop("CATEGORY_NAME_SHORT")
    )

    return df_transformed

# ==========================================
# EXPENSE CATEGORY TRANSFORMATION
# ==========================================


def transform_d_expense_category(source_db_path, column_mapping):
    """Executes the PQ logic for Expense Categories (TYPE = 1)."""

    query = "SELECT * FROM ZCATEGORY"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        .rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 1 (Expense) and parent category check (null or empty)
        .filter(
            (pl.col("TYPE") == 1) &
            (pl.col("CATEGORY_ID").is_null() |
             (pl.col("CATEGORY_ID").str.len_chars() < 1))
        )
        .select([
            "S_NO",
            "MODIFY_DATE",
            "UID",
            "CATEGORY_NAME",
            "ORDER_SEQUENCE"
        ])
    )

    return df_transformed


def transform_d_expense_subcategory(source_db_path, column_mapping):
    """Executes the PQ logic for Expense Subcategories."""

    # Notice we don't need to pass the parent lazy frame here because
    # there is no DAX RELATED() logic needed for this table.
    query = "SELECT * FROM ZCATEGORY"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        .rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 1 (Expense) and child category check (has parent ID)
        .filter(
            (pl.col("TYPE") == 1) &
            pl.col("CATEGORY_ID").is_not_null() &
            (pl.col("CATEGORY_ID").str.len_chars() > 0)
        )
        .select([
            "S_NO",
            "MODIFY_DATE",
            "UID",
            "CATEGORY_NAME",
            "ORDER_SEQUENCE",
            "CATEGORY_ID"
        ])
    )

    return df_transformed

# ==========================================
# ASSET CATEGORY & SUBCATEGORY
# ==========================================


def transform_d_asset_category(source_db_path, column_mapping):
    """Executes the PQ logic for Asset Categories (ASSETGROUP)."""

    query = "SELECT * FROM ASSETGROUP"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        .rename(column_mapping)
        # IS_DEL <> 1
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select([
            "DEVICE_ID",
            "UID",
            "USE_TIME",
            "ASSET_GROUP",
            "TYPE",
            "ORDER_SEQUENCE"
        ])
    )

    return df_transformed


def transform_d_asset_subcategory(source_db_path, column_mapping):
    """Executes the PQ logic for Asset Subcategories (ASSETS)."""

    query = "SELECT * FROM ASSETS"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        .rename(column_mapping)
        # IS_DEL = 0
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select([
            "S_NO",
            "CARD_STATEMENT_DATE",
            "CARD_PAYMENT_DATE",
            "ASSET_NAME",
            "ORDER_SEQUENCE",
            "ASSET_DESCRIPTION",
            "NOTES",
            "TRANSFER_EXPENSE",
            "CARD_AUTOPAY",
            "ADDED_TIME",
            "UID",
            "CURRENCY_ID",
            "AUTOPAY_ASSET_ID",
            "ASSET_GROUP_ID"
        ])
    )

    return df_transformed

# ==========================================
# CURRENCY MASTER
# ==========================================


def transform_d_currency(source_db_path, column_mapping):
    """Executes the PQ logic for the Currency Master table."""

    query = "SELECT * FROM CURRENCY"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_transformed = (
        df_lazy
        .rename(column_mapping)
        # IS_DEL <> 1
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select([
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
            "DECIMAL_POINT"
        ])
    )

    return df_transformed

# ==========================================
# BENCHMARK MASTER
# ==========================================


def transform_d_investment_benchmark_master(csv_path):
    """Executes the PQ logic for the Benchmark Master table."""

    # Enforce strict string types as defined in your Power Query
    schema_overrides = {
        "ID": pl.String,
        "Benchmark_Name": pl.String,
        "yF_Ticker": pl.String,
        "Currency": pl.String
    }

    df_lazy = pl.scan_csv(csv_path, schema_overrides=schema_overrides)

    return df_lazy

# ==========================================
# TAX RATES MASTER
# ==========================================


def transform_d_tax_rates(csv_path):
    """Executes the PQ logic for the Tax Rates table."""

    # We use schema overrides to strictly enforce the types from your PQ logic.
    # We map PQ Percentage.Type -> pl.Float64, and PQ type date -> pl.Date.
    schema_overrides = {
        "FY": pl.String,
        "FY_Start_Date": pl.Date,
        "FY_End_Date": pl.Date,
        "Debt_MF_Cutoff_Date": pl.Date,
        "Equity_Listed_LTCG": pl.Float64,
        "Equity_Listed_STCG": pl.Float64,
        "Equity_Unlisted_LTCG": pl.Float64,
        "Equity_Unlisted_STCG": pl.Float64,
        "Gold_LTCG": pl.Float64,
        "Gold_STCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_STCG": pl.Float64,
        "Debt_MF_Post_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Post_Cutoff_STCG": pl.Float64,
        "Other_Debt_LTCG": pl.Float64,
        "Other_Debt_STCG": pl.Float64,
        "Default_LTCG": pl.Float64,
        "Default_STCG": pl.Float64,
        "Equity_LTCG_Exemption": pl.Int64,
        "Remarks": pl.String
    }

    # try_parse_dates=True tells Polars to automatically parse 'YYYY-MM-DD' strings
    # into native Date objects based on the schema overrides.
    df_lazy = pl.scan_csv(
        csv_path,
        schema_overrides=schema_overrides,
        try_parse_dates=True
    )

    return df_lazy

# ==========================================
# TRANSACTIONS (FACT TABLES)
# ==========================================


def get_base_transactions(source_db_path, column_mapping):
    """
    Acts as the TRANSACTIONS helper query. 
    Reads INOUTCOME once, renames columns, and filters deleted rows.
    """
    query = "SELECT * FROM INOUTCOME"
    uri = f"sqlite:///{source_db_path}"

    df_lazy = pl.read_database_uri(query, uri, engine="adbc").lazy()

    df_base = (
        df_lazy
        .rename(column_mapping)
        # Power Query used IS_DEL <> "1" (String comparison).
        # We cast to string first to be safe, then filter.
        .with_columns([
            pl.col("IS_DEL").cast(pl.String),
            pl.col("LOCAL_AMOUNT").cast(
                pl.Float64, strict=False).fill_null(0.0),
            pl.col("AMOUNT_ACCOUNT").cast(
                pl.Float64, strict=False).fill_null(0.0),
            pl.col("TRANSACTION_TYPE").cast(pl.Int64, strict=False)
        ])
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
    )

    return df_base


def transform_f_income_transactions(base_transactions_lazy):
    """
    Branches off the base transactions for Income (TYPE = 0) 
    and applies the DAX calculation.
    """
    df_transformed = (
        base_transactions_lazy
        .filter(pl.col("TRANSACTION_TYPE") == 0)
        .select([
            "S_NO", "UID", "ASSET_ID", "CARDDIVIDMONTH", "CATEGORY_ID",
            "TO_ASSET_ID", "DESCRIPTION", "TIMESTAMP", "DATE", "TIME",
            "PAID", "TRANSACTION_TYPE", "BASE_AMOUNT", "TRANSFER_UID",
            "FEES_NOTES", "LOCAL_AMOUNT", "MARK", "TRANSFER_FEES",
            "UPDATED_TIME", "CURRENCY_ID", "AMOUNT_ACCOUNT"
        ])
        # DAX: EXCH_RATE = DIVIDE(AMOUNT_ACCOUNT, LOCAL_AMOUNT, 0)
        .with_columns(
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )
    )

    return df_transformed


def transform_f_expense_transactions(base_transactions_lazy):
    """
    Branches off the base transactions for Expenses (TYPE = 1) 
    and applies the EXCH_RATE calculation.
    """
    df_transformed = (
        base_transactions_lazy
        .filter(pl.col("TRANSACTION_TYPE") == 1)
        .select([
            "S_NO", "UID", "ASSET_ID", "CARDDIVIDMONTH", "CATEGORY_ID",
            "TO_ASSET_ID", "DESCRIPTION", "TIMESTAMP", "DATE", "TIME",
            "PAID", "TRANSACTION_TYPE", "BASE_AMOUNT", "TRANSFER_UID",
            "FEES_NOTES", "LOCAL_AMOUNT", "MARK", "TRANSFER_FEES",
            "UPDATED_TIME", "CURRENCY_ID", "AMOUNT_ACCOUNT"
        ])
        # DAX: EXCH_RATE = DIVIDE(AMOUNT_ACCOUNT, LOCAL_AMOUNT, 0)
        .with_columns(
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )
    )

    return df_transformed


def transform_f_transfer_transactions(
    base_transactions_lazy,
    d_asset_subcategory_lazy,
    d_asset_category_lazy
):
    """
    Branches off base transactions for Transfers (TYPE = 3 or 4) 
    and applies RELATED() logic via joins, plus temporal shifts for EDATE().
    """

    # 1. Replicate DAX RELATED() by joining up the Asset hierarchy
    # Join Transactions (ASSET_ID) -> SubCategory (UID)
    df_joined_sub = base_transactions_lazy.join(
        d_asset_subcategory_lazy.select([
            pl.col("UID").alias("SUB_UID"),
            "ASSET_GROUP_ID"
        ]),
        left_on="ASSET_ID",
        right_on="SUB_UID",
        how="left"
    )

    # Join SubCategory (ASSET_GROUP_ID) -> Category (UID) to get ASSET_GROUP
    df_joined_cat = df_joined_sub.join(
        d_asset_category_lazy.select([
            pl.col("UID").alias("CAT_UID"),
            "ASSET_GROUP"
        ]),
        left_on="ASSET_GROUP_ID",
        right_on="CAT_UID",
        how="left"
    )

    df_transformed = (
        df_joined_cat
        # Filter for Types 3 or 4
        .filter((pl.col("TRANSACTION_TYPE") == 3) | (pl.col("TRANSACTION_TYPE") == 4))

        # Select base columns
        .select([
            "S_NO", "UID", "ASSET_ID", "CARDDIVIDMONTH", "CATEGORY_ID",
            "TO_ASSET_ID", "DESCRIPTION", "TIMESTAMP", "DATE", "TIME",
            "PAID", "TRANSACTION_TYPE", "BASE_AMOUNT", "TRANSFER_UID",
            "FEES_NOTES", "LOCAL_AMOUNT", "MARK", "TRANSFER_FEES",
            "UPDATED_TIME", "CURRENCY_ID", "AMOUNT_ACCOUNT",
            "ASSET_GROUP"  # Kept temporarily for the calculation
        ])

        # Add Independent Calculated Columns
        .with_columns(
            # TRANSFER_TYPE
            pl.when(pl.col("TRANSACTION_TYPE") == 3)
            .then(pl.lit("Out"))
            .otherwise(pl.lit("In"))
            .alias("TRANSFER_TYPE"),

            # EXCH_RATE
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )

        # Add Dependent Calculated Columns (These rely on the previous step's outputs)
        .with_columns(
            # AMOUNT_PROPER
            pl.when(pl.col("TRANSFER_TYPE") == "Out")
            .then(pl.col("LOCAL_AMOUNT") * -1)
            .otherwise(pl.col("LOCAL_AMOUNT"))
            .alias("AMOUNT_PROPER"),

            # ADJUSTED_DATE_FOR_ANALYSIS (EDATE equivalent)
            pl.when(pl.col("ASSET_GROUP") == "Investments")
            .then(pl.col("DATE").cast(pl.String).str.to_date("%Y-%m-%d", strict=False).dt.offset_by("-1mo"))
            .otherwise(pl.col("DATE").cast(pl.String).str.to_date("%Y-%m-%d", strict=False))
            .alias("ADJUSTED_DATE_FOR_ANALYSIS")
        )

        # Clean up: Drop the temporary ASSET_GROUP column so it matches the exact schema
        .drop("ASSET_GROUP")
    )

    return df_transformed

# ==========================================
# OPENING BALANCES (FACT TABLE)
# ==========================================


def transform_f_opening_balances(csv_path, column_mapping):
    """Executes the PQ logic for Opening Balances."""

    # We use try_parse_dates so Polars automatically attempts to parse ZTXDATESTR
    df_lazy = pl.scan_csv(csv_path, try_parse_dates=True)

    df_transformed = (
        df_lazy
        # Apply the dynamic column mapping first
        .rename(column_mapping)

        # Select the columns immediately to minimize memory footprint
        .select([
            "Z_PK", "ZUTIME", "ZDATE", "ZAMOUNT", "ZAMOUNTACCOUNT",
            "ZAMOUNTSUB", "ZCONTENT", "ZDO_TYPE", "ZASSETUID",
            "ZCATEGORYUID", "ZCURRENCYUID", "ZTOASSETUID", "ZTXDATESTR",
            "ZTXUIDFEE", "ZTXUIDTRANS", "ZUID"
        ])

        # Enforce the strict types defined in your Power Query step.
        # Note: If ZTXDATESTR is a non-standard datetime string, replace .cast(pl.Datetime)
        # with .str.to_datetime(format="%Y-%m-%d %H:%M:%S") matching your CSV's exact format.
        .with_columns(
            pl.col("Z_PK").cast(pl.Int64),
            pl.col("ZUTIME").cast(pl.Int64),
            # PQ 'type number' handles decimals
            pl.col("ZDATE").cast(pl.Float64),
            pl.col("ZAMOUNT").cast(pl.Float64),
            pl.col("ZAMOUNTACCOUNT").cast(pl.Float64),
            pl.col("ZAMOUNTSUB").cast(pl.Float64),
            pl.col("ZDO_TYPE").cast(pl.Int64),
            pl.col("ZTXDATESTR").cast(pl.Datetime,
                                      strict=False).cast(pl.Date, strict=False)
        )
    )

    return df_transformed


def transform_stg_investment_market_data(stock_ref_lazy, mf_ref_lazy):
    """
    Translates DAX UNION + SUMMARIZE.
    Concatenates the Stock and MF aggregated tables and selects the final columns.
    """

    # Ensure both frames have the exact same columns in the exact same order for UNION
    select_cols = [
        "Date", "ISIN", "Quantity", "Closing Price", "Buy Price",
        "Closing Value", "Buy Value", "Unit P/L", "Total P/L"
    ]

    df_union = pl.concat([
        mf_ref_lazy.select(select_cols),
        stock_ref_lazy.select(select_cols)
    ], how="vertical")

    # The outer SUMMARIZE in DAX acts as a distinct/group by on the unioned result.
    # We group by all columns to remove any exact duplicates, mirroring the DAX behavior.
    df_final = df_union.group_by(select_cols).agg([])

    return df_final

# ==========================================
# Investment Purchases and Sale data
# ==========================================


def get_f_tf_investment_purchase_data(stock_ref, mf_ref):
    """Translates DAX UNION + SUMMARIZE for Purchases."""
    select_cols = ["ISIN", "Date", "Price", "Quantity", "Value"]

    df_union = pl.concat([
        stock_ref.select(select_cols),
        mf_ref.select(select_cols)
    ], how="vertical")

    df_final = (
        df_union
        .group_by(select_cols).agg([])  # SUMMARIZE (distinct)
        # DAX calculated col
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final


def get_f_tf_investment_sale_data(stock_ref, mf_ref):
    """Translates DAX UNION + SUMMARIZE for Sales."""
    select_cols = [
        "ISIN", "Date", "Quantity", "Sell Price", "Sell Value",
        "Buy Price", "Buy Value", "Unit P/L", "Total P/L"
    ]

    df_union = pl.concat([
        stock_ref.select(select_cols),
        mf_ref.select(select_cols)
    ], how="vertical")

    df_final = (
        df_union
        .group_by(select_cols).agg([])  # SUMMARIZE (distinct)
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final

# ==========================================
# BENCHMARK & MARKET DATA
# ==========================================


def get_f_investment_benchmark_data(folder_path):
    """
    Acts as the f_Investment_Benchmark_Data query.
    Iterates the 'Market - Benchmark Files' folder and reads the CSVs.
    """
    search_pattern = os.path.join(folder_path, "**", "*.csv")
    csv_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    valid_files = [f for f in csv_files if "Market - Benchmark Files" in f]

    all_dfs = []

    for file_path in valid_files:
        filename = os.path.basename(file_path)

        # Read the CSV. Polars handles promotion of headers automatically.
        # Enforce the date format based on your data if necessary, or use try_parse_dates
        df_csv = pl.read_csv(file_path, try_parse_dates=True)

        df_csv = df_csv.with_columns(pl.lit(filename).alias("Name"))
        all_dfs.append(df_csv)

    if not all_dfs:
        print("No Benchmark data found, skipping.")
        return pl.DataFrame().lazy()

    df_combined = pl.concat(all_dfs, how="diagonal").lazy()

    df_transformed = (
        df_combined
        .select([
            "Name", "Date", "ID", "Benchmark_Name", "yF_Ticker",
            "Currency", "Close"
        ])
        .with_columns([
            pl.col("Date").cast(pl.Date, strict=False),
            pl.col("ID").cast(pl.String),
            pl.col("Benchmark_Name").cast(pl.String),
            pl.col("yF_Ticker").cast(pl.String),
            pl.col("Currency").cast(pl.String),
            pl.col("Close").cast(pl.Float64, strict=False)
        ])
    )

    return df_transformed


def get_f_investment_market_data(folder_path):
    """
    Acts as the f_Investment_Market_Data query.
    Reads the heavily processed 55-column market data CSVs.
    Handles the 'Replaced Errors' step by casting with strict=False (which converts errors to Nulls).
    """
    search_pattern = os.path.join(folder_path, "**", "*.csv")
    csv_files = [f for f in glob.glob(
        search_pattern, recursive=True) if not os.path.basename(f).startswith("~")]

    valid_files = [f for f in csv_files if "Market - Processed Files" in f]

    all_dfs = []

    for file_path in valid_files:
        filename = os.path.basename(file_path)

        # We read all columns as strings initially to gracefully handle the
        # "Replaced Errors" step from Power Query later during the cast.
        df_csv = pl.read_csv(file_path, infer_schema_length=0)
        df_csv = df_csv.with_columns(pl.lit(filename).alias("Name"))
        all_dfs.append(df_csv)

    if not all_dfs:
        print("No Processed Market data found, skipping.")
        return pl.DataFrame().lazy()

    df_combined = pl.concat(all_dfs, how="diagonal").lazy()

    # Define columns that should be Float64 (including all Percentage types)
    float_cols = [
        "Quantity", "Buy_Price", "Market_Price", "Buy_Value", "Close_Value", "P/L",
        "Returns_%", "Lot_CAGR", "CAGR", "XIRR", "BM_Buy_Price", "BM_Market_Price",
        "Lot_BM_Returns_%", "Lot_BM_CAGR", "BM_CAGR", "BM_XIRR", "Active_Return",
        "Lot_Alpha", "Beta", "Tracking_Error", "Information_Ratio", "Upside_Capture",
        "Downside_Capture", "Tax_Rate", "Unrealized_LTCG", "Unrealized_STCG",
        "Unrealized_Loss", "LTCG_Tax_If_Sold", "STCG_Tax_If_Sold", "After_Tax_PL",
        "After_Tax_Close_Value", "Outperformance_Probability", "Portfolio_XIRR",
        "Portfolio_BM_XIRR", "Portfolio_Active_Return", "Portfolio_Weight_%",
        "Lot_Weight_%", "FY_Realized_LTCG", "FY_Realized_STCG", "FY_Realized_Loss", "FY_LTCG_Remaining_Exemption"
    ]

    int_cols = [
        "Age_Days", "LTCG_Threshold_Days", "Days_To_LTCG"
    ]

    bool_cols = ["Is_Lagging_Benchmark", "Stepup_Eligible"]
    date_cols = ["Closing_Date", "Buy_Date"]

    df_transformed = (
        df_combined
        # Power Query: Changed Type + Changed Type 1 + Replaced Errors.
        # By using strict=False, Polars automatically converts any parsing errors (like text in a float column) to Nulls,
        # perfectly mirroring your Table.ReplaceErrorValues(..., null) step.
        .with_columns([
            pl.col(c).cast(pl.Float64, strict=False) for c in float_cols if c in df_combined.collect_schema().names()
        ])
        .with_columns([
            pl.col(c).cast(pl.Int64, strict=False) for c in int_cols if c in df_combined.collect_schema().names()
        ])
        .with_columns([
            (pl.col(c).cast(pl.String).str.to_uppercase() == "TRUE").alias(c)
            for c in bool_cols if c in df_combined.collect_schema().names()
        ])
        .with_columns([
            pl.col(c).str.to_date("%Y-%m-%d", strict=False) for c in date_cols if c in df_combined.collect_schema().names()
        ])
    )

    return df_transformed

# ==========================================
# FINAL INVESTMENT MASTER
# ==========================================


def get_d_tf_investment_master(stock_master_ref, mf_master_ref, stg_benchmark_mapping_lazy):
    """
    Translates d_tf_InvestmentMaster.
    Unions the Stock and MF references into a single distinct dimension table,
    then joins the Benchmark Mapping to pull in Sector, Industry, Tax flags, etc.
    """

    # Define common schema to ensure clean union
    select_cols = [
        "ISIN", "INSTRUMENT_NAME", "INSTRUMENT_HOUSE", "INSTRUMENT_CLASS",
        "INSTRUMENT_TYPE", "INSTRUMENT_SUBTYPE", "CATEGORY_ID"
    ]

    # Union the Stock and MF References
    df_master_union = pl.concat([
        stock_master_ref.select(select_cols),
        mf_master_ref.select(select_cols)
    ]).unique(subset=["ISIN"])  # Ensure one row per ISIN

    # Replicate DAX LOOKUPVALUE by joining the Benchmark Mapping
    df_final = (
        df_master_union
        .join(stg_benchmark_mapping_lazy, on="ISIN", how="left")
        .select([
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
            pl.col("Tax_Instrument_Subtype").alias("TAX_SUBTYPE")
        ])
    )

    return df_final


def transform_d_calendar(min_date, max_date):
    """
    Generates all 40 requested time-intelligence columns for the Calendar Master.
    Assumes an April 1st - March 31st Financial Year.
    """
    import datetime
    from dateutil.relativedelta import relativedelta
    import calendar
    import polars as pl

    start_date = (min_date.replace(day=1) - relativedelta(months=1))
    last_day_of_max_month = calendar.monthrange(
        max_date.year, max_date.month)[1]
    end_date = max_date.replace(day=last_day_of_max_month)

    df_cal = pl.DataFrame({
        "Date": pl.date_range(start_date, end_date, "1d", eager=True)
    }).lazy()

    df_transformed = (
        df_cal
        # Block 1: Base Numeric and String Extractions
        .with_columns([
            pl.col("Date").dt.day().alias("Day"),
            pl.col("Date").dt.strftime("%A").alias("Day Name"),
            pl.col("Date").dt.strftime("%a").alias("Day Name Short"),
            pl.col("Date").dt.ordinal_day().alias("Day Ordinal"),
            pl.col("Date").dt.weekday().alias("Weekday"),
            pl.col("Date").dt.week().alias("Week"),
            pl.col("Date").dt.month().alias("Month"),
            pl.col("Date").dt.strftime("%B").alias("Month Name"),
            pl.col("Date").dt.strftime("%b").alias("Month Name Short"),
            pl.col("Date").dt.quarter().alias("Quarter"),
            pl.col("Date").dt.year().alias("Year"),
            pl.col("Date").dt.offset_by("-3mo").alias("FY_Shift"),

            pl.col("Date").dt.truncate("1mo").alias("Start of Month"),
            pl.col("Date").dt.month_end().alias("End of Month"),
            pl.col("Date").dt.truncate("1w").alias("Start of Week"),
        ])

        # Block 2: Dependent Dates (Quarters and Weeks)
        .with_columns([
            pl.col("Start of Week").dt.offset_by("6d").alias("End of Week"),

            (pl.col("Year").cast(pl.String) + "-" +
             ((pl.col("Quarter") - 1) * 3 +
              1).cast(pl.String).str.pad_start(2, '0') + "-01"
             ).str.to_date("%Y-%m-%d", strict=False).alias("Start of Quarter")
        ])

        # Block 3a: Dependent End of Quarter and FY Extracts
        .with_columns([
            pl.col("Start of Quarter").dt.offset_by(
                "3mo").dt.offset_by("-1d").alias("End of Quarter"),

            pl.col("FY_Shift").dt.year().alias("FY Year"),
            pl.col("FY_Shift").dt.month().alias("FY Month"),
            pl.col("FY_Shift").dt.quarter().alias("FY Quarter"),
            pl.col("Week").alias("Week Ordinal")
        ])

        # Block 3b: SPLIT HERE - Safe to reference End of Quarter now
        .with_columns([
            pl.col("Start of Month").alias("FY Start of Month"),
            pl.col("End of Month").alias("FY End of Month"),
            pl.col("Start of Quarter").alias("FY Start of Quarter"),
            pl.col("End of Quarter").alias("FY End of Quarter")
        ])

        # Block 4: String Concat and Labels
        .with_columns([
            (pl.lit("Day ") + pl.col("Day Ordinal").cast(pl.String)
             ).alias("Day Ordinal Name"),
            (pl.lit("Wk ") + pl.col("Week Ordinal").cast(pl.String)
             ).alias("Week Ordinal Name"),
            (pl.lit("Q") + pl.col("Quarter").cast(pl.String)).alias("Quarter Name"),
            (pl.lit("Q") + pl.col("FY Quarter").cast(pl.String)
             ).alias("FY Quarter Name"),

            (pl.lit("FY") + pl.col("FY Year").cast(pl.String).str.slice(2, 2) + "-" +
             (pl.col("FY Year") + 1).cast(pl.String).str.slice(2, 2)).alias("Financial Year"),

            pl.col("Date").dt.strftime("%B %Y").alias("Month - Year"),
            pl.col("Date").dt.strftime("%b-%y").alias("Short Month - Year"),
            pl.col("Date").dt.strftime("%b '%y").alias("V Short Month - Year"),

            (pl.lit("Week ") + pl.col("Week").cast(pl.String)).alias("Week Name"),
            pl.when(pl.col("Weekday").is_in([6, 7])).then(
                1).otherwise(0).alias("IS_WEEKEND")
        ])

        # Block 5: Final Cross-Concatenations
        .with_columns([
            (pl.col("Quarter Name") + "-" +
             pl.col("Year").cast(pl.String)).alias("Quarter - Year"),
            (pl.col("FY Quarter Name") + "-" +
             pl.col("Financial Year")).alias("FY Quarter - Year"),
            (pl.lit("W") + pl.col("Week").cast(pl.String) + "-" +
             pl.col("Year").cast(pl.String)).alias("Week - Year"),
            (pl.col("Week Name") + " - " +
             pl.col("Year").cast(pl.String)).alias("Week Name - Year")
        ])

        # Clean up
        .drop("FY_Shift")
        .select([
            "Date", "Day", "Day Name", "Day Name Short", "Day Ordinal", "Day Ordinal Name",
            "Weekday", "Week", "Week Ordinal", "Week Ordinal Name", "Month", "Month Name",
            "Month Name Short", "Quarter", "Quarter Name", "Year", "FY Month", "FY Year",
            "Start of Month", "FY Start of Month", "FY Quarter", "FY Quarter Name",
            "Month - Year", "Short Month - Year", "Quarter - Year", "FY Quarter - Year",
            "Financial Year", "Start of Quarter", "FY Start of Quarter", "End of Month",
            "FY End of Month", "End of Quarter", "FY End of Quarter", "V Short Month - Year",
            "Week - Year", "Week Name", "Start of Week", "End of Week", "Week Name - Year",
            "IS_WEEKEND"
        ])
    )

    return df_transformed

# ==========================================
# 3. SQLITE DDL & PRAGMA OPTIMIZATION
# ==========================================


def setup_sqlite_schema(db_path):
    """Deletes old DB, applies production PRAGMAs, and creates strict schemas."""
    if os.path.exists(db_path):
        os.remove(db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # --- Production PRAGMAs ---
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.execute("PRAGMA cache_size = -20000;")
        cursor.execute("PRAGMA mmap_size = 2147483648;")

        # --- DDL: d_Income_Category ---
        # Assuming UID is the primary key based on the naming convention
        cursor.executescript("""
            -- DDL: d_Calendar
            CREATE TABLE d_Calendar (
                Date DATE PRIMARY KEY,
                Day INTEGER,
                "Day Name" TEXT,
                "Day Name Short" TEXT,
                "Day Ordinal" INTEGER,
                "Day Ordinal Name" TEXT,
                Weekday INTEGER,
                Week INTEGER,
                "Week Ordinal" INTEGER,
                "Week Ordinal Name" TEXT,
                Month INTEGER,
                "Month Name" TEXT,
                "Month Name Short" TEXT,
                Quarter INTEGER,
                "Quarter Name" TEXT,
                Year INTEGER,
                "FY Month" INTEGER,
                "FY Year" INTEGER,
                "Start of Month" DATE,
                "FY Start of Month" DATE,
                "FY Quarter" INTEGER,
                "FY Quarter Name" TEXT,
                "Month - Year" TEXT,
                "Short Month - Year" TEXT,
                "Quarter - Year" TEXT,
                "FY Quarter - Year" TEXT,
                "Financial Year" TEXT,
                "Start of Quarter" DATE,
                "FY Start of Quarter" DATE,
                "End of Month" DATE,
                "FY End of Month" DATE,
                "End of Quarter" DATE,
                "FY End of Quarter" DATE,
                "V Short Month - Year" TEXT,
                "Week - Year" TEXT,
                "Week Name" TEXT,
                "Start of Week" DATE,
                "End of Week" DATE,
                "Week Name - Year" TEXT,
                IS_WEEKEND INTEGER
            );
            
            -- DDL: d_Income_Category
            CREATE TABLE d_Income_Category (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_NAME_SHORT TEXT
            );

            -- DDL: d_Income_Subcategory
            CREATE TABLE d_Income_Subcategory (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_ID TEXT,
                CATEGORY_GROUPS TEXT,
                FOREIGN KEY (CATEGORY_ID) REFERENCES d_Income_Category(UID)
            );

            -- DDL: d_Expense_Category
            CREATE TABLE d_Expense_Category (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER
            );

            -- DDL: d_Expense_Subcategory
            CREATE TABLE d_Expense_Subcategory (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_ID TEXT,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Category(UID)
            );

            -- DDL: d_Asset_Category
            CREATE TABLE d_Asset_Category (
                DEVICE_ID INTEGER,
                UID TEXT PRIMARY KEY,
                USE_TIME INTEGER,
                ASSET_GROUP TEXT,
                TYPE INTEGER,
                ORDER_SEQUENCE INTEGER
            );

            -- DDL: d_AssetSubCategory
            CREATE TABLE d_Asset_SubCategory (
                S_NO INTEGER,
                CARD_STATEMENT_DATE INTEGER,
                CARD_PAYMENT_DATE INTEGER,
                ASSET_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                ASSET_DESCRIPTION TEXT,
                NOTES INTEGER,
                TRANSFER_EXPENSE INTEGER,
                CARD_AUTOPAY INTEGER,
                ADDED_TIME INTEGER,
                UID TEXT PRIMARY KEY,
                CURRENCY_ID TEXT,
                AUTOPAY_ASSET_ID INTEGER,
                ASSET_GROUP_ID TEXT,
                FOREIGN KEY(ASSET_GROUP_ID) REFERENCES d_Asset_Category(UID)
            );

            -- DDL: d_Currency
            CREATE TABLE d_Currency (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                CURRENCY_NAME TEXT,
                ISO TEXT,
                MAIN_ISO TEXT,
                ORDER_SEQUENCE INTEGER,
                RATE REAL,
                SYMBOL TEXT,
                INSERT_TYPE TEXT,
                SYMBOL_POSITION TEXT,
                IS_MAIN_CURRENCY INTEGER,
                IS_SHOW INTEGER,
                MODIFY_DATE INTEGER,
                DECIMAL_POINT INTEGER
            );

            -- DDL: d_Investment_Benchmark_Master
            CREATE TABLE d_Investment_Benchmark_Master (
                ID TEXT PRIMARY KEY,
                Benchmark_Name TEXT,
                yF_Ticker TEXT,
                Currency TEXT
            );
            
            -- DDL: d_tf_InvestmentMaster
            CREATE TABLE d_tf_Investment_Master (
                ISIN TEXT PRIMARY KEY,
                INSTRUMENT_NAME TEXT,
                INSTRUMENT_HOUSE TEXT,
                INSTRUMENT_CLASS TEXT,
                INSTRUMENT_TYPE TEXT,
                INSTRUMENT_SUBTYPE TEXT,
                CATEGORY_ID TEXT,
                SECTOR TEXT,
                INDUSTRY TEXT,
                BENCHMARK_ID TEXT,
                TAX_TYPE TEXT,
                TAX_SUBTYPE TEXT,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID)
            );

            -- DDL: d_Tax_Rates
            CREATE TABLE d_Tax_Rates (
                FY TEXT PRIMARY KEY,
                FY_Start_Date DATE,
                FY_End_Date DATE,
                Debt_MF_Cutoff_Date DATE,
                Equity_Listed_LTCG REAL,
                Equity_Listed_STCG REAL,
                Equity_Unlisted_LTCG REAL,
                Equity_Unlisted_STCG REAL,
                Gold_LTCG REAL,
                Gold_STCG REAL,
                Debt_MF_Pre_Cutoff_LTCG REAL,
                Debt_MF_Pre_Cutoff_STCG REAL,
                Debt_MF_Post_Cutoff_LTCG REAL,
                Debt_MF_Post_Cutoff_STCG REAL,
                Other_Debt_LTCG REAL,
                Other_Debt_STCG REAL,
                Default_LTCG REAL,
                Default_STCG REAL,
                Equity_LTCG_Exemption INTEGER,
                Remarks TEXT,
                FOREIGN KEY(FY_Start_Date) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Income_Transactions
            CREATE TABLE f_Income_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                EXCH_RATE REAL,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date)
            );

            CREATE TABLE f_Expense_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                EXCH_RATE REAL,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Transfer_Transactions
            CREATE TABLE f_Transfer_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                TRANSFER_TYPE TEXT,
                EXCH_RATE REAL,
                AMOUNT_PROPER REAL,
                ADJUSTED_DATE_FOR_ANALYSIS DATE,
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(TO_ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Opening_Balances
            CREATE TABLE f_Opening_Balances (
                Z_PK INTEGER PRIMARY KEY,
                ZUTIME INTEGER,
                ZDATE REAL,
                ZAMOUNT REAL,
                ZAMOUNTACCOUNT REAL,
                ZAMOUNTSUB REAL,
                ZCONTENT TEXT,
                ZDO_TYPE INTEGER,
                ZASSETUID TEXT,
                ZCATEGORYUID TEXT,
                ZCURRENCYUID TEXT,
                ZTOASSETUID TEXT,
                ZTXDATESTR DATE,
                ZTXUIDFEE TEXT,
                ZTXUIDTRANS TEXT,
                ZUID TEXT,
                FOREIGN KEY(ZCURRENCYUID) REFERENCES d_Currency(UID),
                FOREIGN KEY(ZASSETUID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(ZTXDATESTR) REFERENCES d_Calendar(Date)
            );

            -- DDL: stg_InvestmentMarketData
            CREATE TABLE stg_Investment_Market_Data (
                Date DATE,
                ISIN TEXT,
                Quantity REAL,
                "Closing Price" REAL,
                "Buy Price" REAL,
                "Closing Value" REAL,
                "Buy Value" REAL,
                "Unit P/L" REAL,
                "Total P/L" REAL,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN)
            );

            -- DDL: f_tf_InvestmentPurchaseData
            CREATE TABLE f_tf_Investment_Purchase_Data (
                ISIN TEXT,
                Date DATE,
                Price REAL,
                Quantity REAL,
                Value REAL,
                CURRENCY_ID TEXT,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
            );

            -- DDL: f_tf_InvestmentSaleData
            CREATE TABLE f_tf_Investment_Sale_Data (
                ISIN TEXT,
                Date DATE,
                Quantity REAL,
                "Sell Price" REAL,
                "Sell Value" REAL,
                "Buy Price" REAL,
                "Buy Value" REAL,
                "Unit P/L" REAL,
                "Total P/L" REAL,
                CURRENCY_ID TEXT,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
            );

            -- DDL: f_Investment_Benchmark_Data
            CREATE TABLE f_Investment_Benchmark_Data (
                Name TEXT,
                Date DATE,
                ID TEXT,
                Benchmark_Name TEXT,
                yF_Ticker TEXT,
                Currency TEXT,
                Close REAL,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ID) REFERENCES d_Investment_Benchmark_Master(ID)
            );

            -- DDL: f_Investment_Market_Data
            -- (Simplified schema definition for brevity, SQLite's loose typing will handle the rest)
            CREATE TABLE f_Investment_Market_Data (
                Name TEXT, Closing_Date DATE, ISIN TEXT, BENCHMARK_ID TEXT, TAX_TYPE TEXT, 
                TAX_SUBTYPE TEXT, Buy_Date DATE, Age_Days INTEGER, LTCG_Threshold_Days INTEGER, 
                Days_To_LTCG INTEGER, Holding_Type TEXT, Quantity REAL, Buy_Price REAL, 
                Market_Price REAL, Buy_Value REAL, Close_Value REAL, "P/L" REAL, 
                "Returns_%" REAL, Lot_CAGR REAL, CAGR REAL, XIRR REAL, BM_Buy_Price REAL, 
                BM_Market_Price REAL, "Lot_BM_Returns_%" REAL, Lot_BM_CAGR REAL, BM_CAGR REAL, 
                BM_XIRR REAL, Active_Return REAL, Lot_Alpha REAL, Is_Lagging_Benchmark INTEGER, 
                Beta REAL, Tracking_Error REAL, Information_Ratio REAL, Upside_Capture REAL, 
                Downside_Capture REAL, Tax_Rate REAL, Unrealized_LTCG REAL, Unrealized_STCG REAL, 
                Unrealized_Loss REAL, LTCG_Tax_If_Sold REAL, STCG_Tax_If_Sold REAL, After_Tax_PL REAL, 
                After_Tax_Close_Value REAL, Outperformance_Probability REAL, Portfolio_XIRR REAL, 
                Portfolio_BM_XIRR REAL, Portfolio_Active_Return REAL, "Portfolio_Weight_%" REAL, 
                "Lot_Weight_%" REAL, FY TEXT, FY_Realized_LTCG REAL, FY_Realized_STCG REAL, 
                FY_Realized_Loss REAL, FY_LTCG_Remaining_Exemption INTEGER, Stepup_Eligible INTEGER, 
                Harvest_Recommendation TEXT,
                FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(Buy_Date) REFERENCES d_Calendar(Date)
            );
        """)


def apply_indexes_and_optimize(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Asset Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_category ON d_Asset_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_subcategory ON d_Asset_Subcategory(UID);")

        # Expense Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_category ON d_Expense_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_subcategory ON d_Expense_Subcategory(UID);")

        # Income Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_income_category ON d_Income_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_income_subcategory ON d_Income_Subcategory(UID);")

        # Fact Table Indexes: Incomes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_date ON f_Income_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_category ON f_Income_Transactions(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_currency ON f_Income_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_asset ON f_Income_Transactions(ASSET_ID);")

        # Fact Table Indexes: Expenses
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_date ON f_Expense_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_category ON f_Expense_Transactions(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_currency ON f_Expense_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_asset ON f_Expense_Transactions(ASSET_ID);")

        # Fact Table Indexes: Transfers
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_date ON f_Transfer_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_adj_date ON f_Transfer_Transactions(ADJUSTED_DATE_FOR_ANALYSIS);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_currency ON f_Transfer_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_asset ON f_Transfer_Transactions(ASSET_ID);")

        # Fact Table Indexes: Opening Balances
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_uid ON f_Opening_Balances(ZUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_asset ON f_Opening_Balances(ZASSETUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_currency ON f_Opening_Balances(ZCURRENCYUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_category ON f_Opening_Balances(ZCATEGORYUID);")

        # Final Investment Benchmark & Market Data Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_bm_id ON f_Investment_Benchmark_Data(ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_bm_date ON f_Investment_Benchmark_Data(Date);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_mkt_isin ON f_Investment_Market_Data(ISIN);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_mkt_date ON f_Investment_Market_Data(Closing_Date);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_buy_date ON f_Investment_Market_Data(Buy_Date);")

        # Investment Master Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_invmst_cat ON d_tf_Investment_Master(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_invmst_class ON d_tf_Investment_Master(INSTRUMENT_CLASS);")

        cursor.execute("PRAGMA optimize;")

# ==========================================
# 4. ORCHESTRATION & EXECUTION
# ==========================================


def generate_target_db_path(base_path):
    now = datetime.now()
    if now.month >= 4:
        fy_str = f"{now.year}-{str(now.year + 1)[-2:]}"
    else:
        fy_str = f"{now.year - 1}-{str(now.year)[-2:]}"
        
    month_year_str = now.strftime("%m-%Y")
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    file_name = f"Personal_Finance_DB_{timestamp_str}.db"
    
    full_dir_path = os.path.join(base_path, fy_str, month_year_str)
    os.makedirs(full_dir_path, exist_ok=True)
    
    return os.path.join(full_dir_path, file_name)


def main():
    target_db_path = generate_target_db_path(TARGET_DB_BASE_PATH)

    # 1. Setup Target DB
    setup_sqlite_schema(target_db_path)

    # 2. Extract Data
    latest_backup = get_latest_sqlite_backup(SOURCE_DB_FOLDER)
    category_mapping = get_column_mapping("CATEGORY")
    asset_group_mapping = get_column_mapping("ASSETGROUP")
    assets_mapping = get_column_mapping("ASSETS")
    currency_mapping = get_column_mapping("CURRENCY")
    inoutcome_mapping = get_column_mapping("INOUTCOME")
    opbal_mapping = get_column_mapping("ZOPBAL")

    # Staging Tables for Downstream Processing
    stg_mf_isin_mapping_lazy = get_stg_mf_isin_mapping(MF_ISIN_CSV_PATH)
    stg_benchmark_mapping_lazy = get_stg_benchmark_mapping(
        BENCHMARK_MAPPING_CSV_PATH)

    print("Parsing unstructured Stock Excel files...")
    stg_stock_market_data_lazy = get_stg_stock_market_data(STATEMENTS_FOLDER)

    print("Parsing unstructured Mutual Fund Excel files...")
    stg_mf_market_data_lazy = get_stg_mf_market_data(
        STATEMENTS_FOLDER,
        stg_mf_isin_mapping_lazy  # Passed in to replicate LOOKUPVALUE
    )

    stg_stock_market_data_ref_lazy = get_stg_stock_market_data_ref(
        stg_stock_market_data_lazy)
    stg_mf_market_data_ref_lazy = get_stg_mf_market_data_ref(
        stg_mf_market_data_lazy)

    print("Parsing Stock Trade Orders...")
    base_stock_orders_lazy = get_base_stock_transactions(STATEMENTS_FOLDER)

    stg_stock_purchase_transactions_lazy = transform_stg_stock_trades(
        base_stock_orders_lazy,
        trade_type="BUY"
    )

    stg_stock_sale_transactions_lazy = transform_stg_stock_trades(
        base_stock_orders_lazy,
        trade_type="SELL"
    )

    print("Parsing Mutual Fund Trade Orders...")
    base_mf_orders_lazy = get_base_mf_transactions(STATEMENTS_FOLDER)

    stg_mf_purchase_transactions_lazy = transform_stg_mf_trades(
        base_mf_orders_lazy,
        stg_mf_isin_mapping_lazy,
        trade_type="PURCHASE"
    )

    stg_mf_sale_transactions_lazy = transform_stg_mf_trades(
        base_mf_orders_lazy,
        stg_mf_isin_mapping_lazy,
        trade_type="REDEEM"
    )

    print("Aggregating Investment Purchases...")
    # Investment Purchase Aggregations
    mf_purchase_ref_lazy = get_purchase_reference(
        stg_mf_purchase_transactions_lazy, "Final Scheme Name", "Date", "NAV", "Units"
    )
    stock_purchase_ref_lazy = get_purchase_reference(
        stg_stock_purchase_transactions_lazy, "Stock name", "Execution date and time", "Price", "Quantity"
    )

    print("Processing Investment Sales and Rolling Buy-Price Aggregations...")
    # Investment Sale Aggregations (with Time-Series Rolling Buy Price)
    mf_sale_ref_lazy = get_sale_reference(
        stg_mf_sale_transactions_lazy, mf_purchase_ref_lazy,
        "Final Scheme Name", "Date", "NAV", "Units"
    )
    stock_sale_ref_lazy = get_sale_reference(
        stg_stock_sale_transactions_lazy, stock_purchase_ref_lazy,
        "Stock name", "Execution date and time", "Price", "Quantity"
    )

    # 3. Transform Data
    # Incomes
    d_income_category_lazy = transform_d_income_category(
        latest_backup, category_mapping)
    d_income_subcategory_lazy = transform_d_income_subcategory(
        latest_backup,
        category_mapping,
        d_income_category_lazy
    )

    # Expenses
    d_expense_category_lazy = transform_d_expense_category(
        latest_backup, category_mapping)
    d_expense_subcategory_lazy = transform_d_expense_subcategory(
        latest_backup, category_mapping)

    # Assets
    d_asset_category_lazy = transform_d_asset_category(
        latest_backup, asset_group_mapping)
    d_asset_subcategory_lazy = transform_d_asset_subcategory(
        latest_backup, assets_mapping)

    # Currency
    d_currency_lazy = transform_d_currency(latest_backup, currency_mapping)

    # Benchmark Master
    d_benchmark_master_lazy = transform_d_investment_benchmark_master(
        BENCHMARK_MASTER_CSV_PATH)

    # Tax Rates
    d_tax_rates_lazy = transform_d_tax_rates(TAX_RATES_CSV_PATH)

    # Fact tables
    # Base Transactions
    base_transactions_lazy = get_base_transactions(
        latest_backup, inoutcome_mapping)

    # Incomes
    f_income_transactions_lazy = transform_f_income_transactions(
        base_transactions_lazy)

    # Expenses
    f_expense_transactions_lazy = transform_f_expense_transactions(
        base_transactions_lazy)

    # Transfers
    f_transfer_transactions_lazy = transform_f_transfer_transactions(
        base_transactions_lazy,
        d_asset_subcategory_lazy,
        d_asset_category_lazy
    )

    # Opening Balances
    f_opening_balances_lazy = transform_f_opening_balances(
        OPENING_BALANCE_CSV_PATH,
        opbal_mapping
    )

    # Investment Market Data - Staging
    stg_investment_market_data_lazy = transform_stg_investment_market_data(
        stg_stock_market_data_ref_lazy,
        stg_mf_market_data_ref_lazy
    )

    # Investment Purchase & Sale Tables
    f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(
        stock_purchase_ref_lazy, mf_purchase_ref_lazy
    )
    f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(
        stock_sale_ref_lazy, mf_sale_ref_lazy
    )

    # Investment Benchmark & Market Data
    f_investment_benchmark_data_lazy = get_f_investment_benchmark_data(
        STATEMENTS_FOLDER)
    f_investment_market_data_lazy = get_f_investment_market_data(
        STATEMENTS_FOLDER)

    print("Building Investment Master...")
    stg_stock_master_ref_lazy = get_stg_stock_master_ref(
        stg_stock_market_data_lazy,
        d_asset_subcategory_lazy
    )

    stg_mf_master_ref_lazy = get_stg_mf_master_ref(
        stg_mf_market_data_lazy,
        stg_mf_purchase_transactions_lazy,
        stg_mf_sale_transactions_lazy,
        d_asset_subcategory_lazy
    )

    # Investment Master
    d_tf_investment_master_lazy = get_d_tf_investment_master(
        stg_stock_master_ref_lazy,
        stg_mf_master_ref_lazy,
        stg_benchmark_mapping_lazy
    )

    print("Generating Master Calendar...")
    min_date, max_date = get_stg_calendar_ref(
        f_income_transactions_lazy,
        f_expense_transactions_lazy,
        f_transfer_transactions_lazy,
        f_opening_balances_lazy,  # Make sure this matches your variable name
        stg_investment_market_data_lazy,
        f_tf_inv_purchase_data_lazy,
        f_tf_inv_sale_data_lazy
    )

    # Calendar Master
    d_calendar_lazy = transform_d_calendar(min_date, max_date)

    # Execute Lazy DataFrame
    df_d_income_category = d_income_category_lazy.collect()
    df_d_income_subcategory = d_income_subcategory_lazy.collect()
    df_d_expense_category = d_expense_category_lazy.collect()
    df_d_expense_subcategory = d_expense_subcategory_lazy.collect()
    df_d_asset_category = d_asset_category_lazy.collect()
    df_d_asset_subcategory = d_asset_subcategory_lazy.collect()
    df_d_currency = d_currency_lazy.collect()
    df_d_benchmark_master = d_benchmark_master_lazy.collect()
    df_d_tax_rates = d_tax_rates_lazy.collect()
    df_f_income_transactions = f_income_transactions_lazy.collect()
    df_f_expense_transactions = f_expense_transactions_lazy.collect()
    df_f_transfer_transactions = f_transfer_transactions_lazy.collect()
    df_f_opening_balances = f_opening_balances_lazy.collect()
    df_stg_investment_market_data = stg_investment_market_data_lazy.collect()
    df_f_tf_inv_purchase = f_tf_inv_purchase_data_lazy.collect()
    df_f_tf_inv_sale = f_tf_inv_sale_data_lazy.collect()
    df_f_investment_benchmark_data = f_investment_benchmark_data_lazy.collect()
    df_f_investment_market_data = f_investment_market_data_lazy.collect()
    df_d_tf_investment_master = d_tf_investment_master_lazy.collect()
    df_d_calendar = d_calendar_lazy.collect()

    # 4. Load Data into Target SQLite
    connection_uri = f"sqlite:///{target_db_path}"

    df_d_calendar.write_database(
        table_name="d_Calendar", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    df_d_income_category.write_database(
        table_name="d_Income_Category",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_income_subcategory.write_database(
        table_name="d_Income_Subcategory",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_expense_category.write_database(
        table_name="d_Expense_Category",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_expense_subcategory.write_database(
        table_name="d_Expense_Subcategory",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_asset_category.write_database(
        table_name="d_Asset_Category",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_asset_subcategory.write_database(
        table_name="d_Asset_Subcategory",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_currency.write_database(
        table_name="d_Currency",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_benchmark_master.write_database(
        table_name="d_Investment_Benchmark_Master",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_d_tf_investment_master.write_database(
        table_name="d_tf_Investment_Master", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    df_d_tax_rates.write_database(
        table_name="d_Tax_Rates",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_f_income_transactions.write_database(
        table_name="f_Income_Transactions",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_f_expense_transactions.write_database(
        table_name="f_Expense_Transactions",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_f_transfer_transactions.write_database(
        table_name="f_Transfer_Transactions",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_f_opening_balances.write_database(
        table_name="f_Opening_Balances",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_stg_investment_market_data.write_database(
        table_name="stg_Investment_Market_Data",
        connection=connection_uri,
        if_table_exists="append",
        engine="adbc"
    )

    df_f_tf_inv_purchase.write_database(
        table_name="f_tf_Investment_Purchase_Data", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    df_f_tf_inv_sale.write_database(
        table_name="f_tf_Investment_Sale_Data", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    df_f_investment_benchmark_data.write_database(
        table_name="f_Investment_Benchmark_Data", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    df_f_investment_market_data.write_database(
        table_name="f_Investment_Market_Data", connection=connection_uri,
        if_table_exists="append", engine="adbc"
    )

    apply_indexes_and_optimize(target_db_path)

    # 5. Optimize
    with sqlite3.connect(target_db_path) as conn:
        conn.cursor().execute("PRAGMA optimize;")

    print("ETL complete. All tables generated successfully.")


if __name__ == "__main__":
    main()
