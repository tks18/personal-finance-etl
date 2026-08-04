import os
import re
from datetime import datetime

import fastexcel
import polars as pl

from src.utils.logger import logger


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


def _process_mf_statement(file_path: str) -> pl.DataFrame:
    logger.debug(f"[Extractor] Processing MF Holding Statement: {os.path.basename(file_path)}")
    excel_reader = fastexcel.read_excel(file_path)
    if "Holdings" not in excel_reader.sheet_names:
        logger.debug(f"[Extractor] Skipped {os.path.basename(file_path)}: Missing 'Holdings' sheet")
        return pl.DataFrame()

    df_raw = excel_reader.load_sheet("Holdings", header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        logger.debug(
            f"[Extractor] Skipped {os.path.basename(file_path)}: Could not find 'Scheme Name' anchor"
        )
        return pl.DataFrame()

    header_idx = start_search["index"][0]
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    return df_data.filter(pl.col(first_col).is_not_null())


def extract_mf_market_data_raw(valid_files: list[str]) -> pl.LazyFrame:
    all_dfs = []
    for file_path in valid_files:
        filename = os.path.basename(file_path)
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                logger.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            logger.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_mf_statement(file_path)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(os.path.dirname(file_path)).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        raise ValueError("No valid MF statements found in Folder")
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_mf_transaction_statements(file_path: str) -> pl.DataFrame:
    excel_reader = fastexcel.read_excel(file_path)
    if "Transactions" not in excel_reader.sheet_names:
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Transactions", header_row=None).to_polars()
    if df_raw.is_empty():
        return pl.DataFrame()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        return pl.DataFrame()
    header_idx = start_search["index"][0]
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    return df_data.filter(pl.col(first_col).is_not_null())


def extract_mf_transactions_raw(valid_files: list[str]) -> pl.LazyFrame:
    all_dfs = []
    for file_path in valid_files:
        filename = os.path.basename(file_path)
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
        df_processed = _process_mf_transaction_statements(file_path)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(os.path.dirname(file_path)).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        raise ValueError("No valid MF transaction statements found in Folder")
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_closing_statement(file_path: str) -> pl.DataFrame:
    excel_reader = fastexcel.read_excel(file_path)
    sheet_names = excel_reader.sheet_names
    target_sheet = next(
        (name for name in ["Trade Level", "Sheet", "Sheet1"] if name in sheet_names), None
    )
    if not target_sheet:
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet(target_sheet, header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Unrealised trades")
    if start_search.is_empty():
        return pl.DataFrame()

    header_idx = start_search["index"][0] + 2
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    null_search = df_data.with_row_index().filter(pl.col(first_col).is_null())
    if not null_search.is_empty():
        end_idx = null_search["index"][0]
        df_data = df_data.slice(0, end_idx)
    return df_data


def extract_stock_market_data_raw(valid_files: list[str]) -> pl.LazyFrame:
    all_dfs = []
    for file_path in valid_files:
        filename = os.path.basename(file_path)
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                logger.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            logger.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_stock_closing_statement(file_path)
        if df_processed.is_empty():
            continue
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(os.path.dirname(file_path)).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        raise ValueError("No valid Stock PL statements found in Folder")
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_transactions(file_path: str) -> pl.DataFrame:
    excel_reader = fastexcel.read_excel(file_path)
    if "Sheet1" not in excel_reader.sheet_names:
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Sheet1", header_row=5).to_polars()
    if "Stock name" in df_raw.columns:
        return df_raw.filter(pl.col("Stock name").is_not_null())
    return pl.DataFrame()


def extract_stock_transactions_raw(valid_files: list[str]) -> pl.LazyFrame:
    all_dfs = []
    for file_path in valid_files:
        df_processed = _process_stock_transactions(file_path)
        if df_processed.is_empty():
            continue
        filename = os.path.basename(file_path)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(os.path.dirname(file_path)).alias("__folder_path__"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        raise ValueError("No valid Stock Trade statements found in Folder")
    return pl.concat(all_dfs, how="diagonal").lazy()
