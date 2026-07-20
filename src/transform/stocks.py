import polars as pl
import os
from datetime import datetime
import fastexcel


def process_stock_closing_statement(file_path: str) -> pl.DataFrame:
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
    seen: dict[str, int] = {}

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


def get_stg_stock_market_data(valid_files: list[str]) -> pl.LazyFrame:
    """
    Extracts dates from filenames, processes the binaries, 
    and applies the final PQ & DAX transformations.
    Returns a LazyFrame.
    """
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
            "No valid Stock PL statements found in Folder")

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


def get_stg_stock_market_data_ref(stg_stock_market_data_lazy: pl.LazyFrame) -> pl.LazyFrame:
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


def process_stock_transactions(file_path: str) -> pl.DataFrame:
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


def get_base_stock_transactions(valid_files: list[str]) -> pl.LazyFrame:
    """
    Acts as the STOCK_TRANSACTIONS helper query.
    Processes files and sets data types.
    Returns a single LazyFrame containing both Buys and Sells.
    """
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
        raise ValueError("No valid Stock Orders found in Folder")

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


def transform_stg_stock_trades(base_stock_orders_lazy: pl.LazyFrame, trade_type: str) -> pl.LazyFrame:
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


def get_stg_stock_master_ref(stg_stock_market_data_lazy: pl.LazyFrame, d_asset_subcategory_lazy: pl.LazyFrame) -> pl.LazyFrame:
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
