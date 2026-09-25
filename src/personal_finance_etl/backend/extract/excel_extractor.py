# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import re
import time
from datetime import datetime

import fastexcel
import polars as pl

from personal_finance_etl.backend.utils.logger import logger


def _clean_excel_headers(df_sliced: pl.DataFrame) -> tuple[pl.DataFrame, str]:
    """Reusable header detection + cleaning for all Excel parsers."""
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

    df_data = df_sliced.slice(1).rename(
        {old: new for old, new in zip(df_sliced.columns, clean_headers, strict=False)}
    )
    first_col = clean_headers[0]
    return df_data, first_col


def _process_mf_statement(filename: str, raw_bytes: bytes) -> pl.DataFrame:

    t0 = time.perf_counter()
    logger.debug(f"[EXTRACT:EXCEL] Starting parse for MF Holding Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Holdings" not in excel_reader.sheet_names:
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Missing 'Holdings' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()

    df_raw = excel_reader.load_sheet("Holdings", header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Could not find 'Scheme Name' anchor (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()

    header_idx = start_search["index"][0]
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    final_df = df_data.filter(pl.col(first_col).is_not_null())
    logger.debug(
        f"[EXTRACT:EXCEL] Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
    )
    return final_df


def extract_mf_market_data_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Expects list of (filename, folder_path, raw_bytes)"""
    all_dfs = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                logger.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            logger.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_mf_statement(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_mf_transaction_statements(filename: str, raw_bytes: bytes) -> pl.DataFrame:

    t0 = time.perf_counter()
    logger.debug(f"[EXTRACT:EXCEL] Starting parse for MF Transaction Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Transactions" not in excel_reader.sheet_names:
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Missing 'Transactions' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Transactions", header_row=None).to_polars()
    if df_raw.is_empty():
        return pl.DataFrame()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        logger.debug(f"[EXTRACT:EXCEL] Skipped {filename}: Could not find 'Scheme Name' anchor")
        return pl.DataFrame()
    header_idx = start_search["index"][0]
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    final_df = df_data.filter(pl.col(first_col).is_not_null())
    logger.debug(
        f"[EXTRACT:EXCEL] Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
    )
    return final_df


def extract_mf_transactions_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    all_dfs = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4}|\d{2}-\d{4})", filename)
            if not match:
                logger.warning(f"File skipped (regex miss): {filename}")
                continue
            date_str = match.group(1)
            if len(date_str.split("-")) == 2:
                month_date = datetime.strptime(f"01-{date_str}", "%d-%m-%Y").date()
            else:
                month_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            logger.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_mf_transaction_statements(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_closing_statement(filename: str, raw_bytes: bytes) -> pl.DataFrame:

    t0 = time.perf_counter()
    logger.debug(f"[EXTRACT:EXCEL] Starting parse for Stock Closing Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    sheet_names = excel_reader.sheet_names
    target_sheet = next(
        (name for name in ["Trade Level", "Sheet", "Sheet1"] if name in sheet_names), None
    )
    if not target_sheet:
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Missing target sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet(target_sheet, header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Unrealised trades")
    if start_search.is_empty():
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Could not find 'Unrealised trades' anchor"
        )
        return pl.DataFrame()

    header_idx = start_search["index"][0] + 2
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    null_search = df_data.with_row_index().filter(pl.col(first_col).is_null())
    if not null_search.is_empty():
        end_idx = null_search["index"][0]
        df_data = df_data.slice(0, end_idx)

    logger.debug(
        f"[EXTRACT:EXCEL] Parsed {filename} in {time.perf_counter() - t0:.2f}s - {df_data.height} rows extracted"
    )
    return df_data


def extract_stock_market_data_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    all_dfs = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                logger.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            logger.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_stock_closing_statement(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_transactions(filename: str, raw_bytes: bytes) -> pl.DataFrame:

    t0 = time.perf_counter()
    logger.debug(f"[EXTRACT:EXCEL] Starting parse for Stock Transaction Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Sheet1" not in excel_reader.sheet_names:
        logger.debug(
            f"[EXTRACT:EXCEL] Skipped {filename}: Missing 'Sheet1' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Sheet1", header_row=5).to_polars()
    if "Stock name" in df_raw.columns:
        final_df = df_raw.filter(pl.col("Stock name").is_not_null())
        logger.debug(
            f"[EXTRACT:EXCEL] Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
        )
        return final_df
    logger.debug(f"[EXTRACT:EXCEL] Skipped {filename}: Could not find 'Stock name' column")
    return pl.DataFrame()


def extract_stock_transactions_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    all_dfs = []
    for filename, folder_path, raw_bytes in valid_files:
        df_processed = _process_stock_transactions(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()
