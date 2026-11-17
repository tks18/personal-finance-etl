# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Excel parsing and evidence extraction adapter.

Owns
----
- In-memory parsing of Excel binary statements using fastexcel.
- Header detection and normalization across financial statement structures.
- Date extraction heuristics from file basenames.
- Ingestion metadata tagging (__file_name__, __folder_path__, Month Date, __file_category__, artifact_id).

Does not own
-------------
- Validation of business logic (owned by domain.common.validation).
- File reading from disk (payloads provided via Control Plane Raw Store).
"""

from __future__ import annotations

import re
import time
from datetime import datetime

import fastexcel
import polars as pl

from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = [
    "ExcelExtractor",
    "extract_mf_market_data_raw",
    "extract_mf_transactions_raw",
    "extract_stock_market_data_raw",
    "extract_stock_transactions_raw",
    "extract_us_stock_transactions_raw",
]

diagnostics = get_observability_diagnostics(__name__)


def _clean_excel_headers(df_sliced: pl.DataFrame) -> tuple[pl.DataFrame, str]:
    """Reusable header detection + cleaning for all Excel parsers."""
    raw_headers = df_sliced.row(0)
    clean_headers: list[str] = []
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

    df_data = df_sliced.slice(1).rename(dict(zip(df_sliced.columns, clean_headers, strict=False)))
    first_col = clean_headers[0]
    return df_data, first_col


class ExcelExtractor:
    """Provider adapter for physical extraction of Excel workbook statements.

    Parameters
    ----------
    base_folder : str, default ""
        Base folder path for file resolution.
    """

    def __init__(self, base_folder: str = "") -> None:
        self.base_folder = base_folder

    def extract_sheet(
        self,
        filename: str,
        folder_path: str,
        raw_bytes: bytes,
        sheet_name: str | None = None,
        candidate_sheets: list[str] | None = None,
        header_row: int | None = None,
        header_anchor: str | None = None,
        anchor_offset: int = 0,
        stop_on_blank: bool = False,
        file_category: str | None = None,
    ) -> pl.LazyFrame:
        """Extract a single worksheet from Excel binary bytes.

        Parameters
        ----------
        filename : str
            Source filename for context and date extraction.
        folder_path : str
            Parent directory path.
        raw_bytes : bytes
            Binary payload of the Excel workbook.
        sheet_name : str | None, default None
            Target worksheet name. If None, candidate_sheets or first worksheet is used.
        candidate_sheets : list[str] | None, default None
            Ordered candidate worksheet names to inspect if sheet_name is None.
        header_row : int | None, default None
            Explicit zero-based row index for table headers.
        header_anchor : str | None, default None
            Anchor column header string to scan for across worksheet rows.
        anchor_offset : int, default 0
            Row offset relative to header_anchor where column headers begin.
        stop_on_blank : bool, default False
            Whether extraction stops when the first empty cell in the primary column is encountered.
        file_category : str | None, default None
            Optional domain category classification string (e.g. "Indian MF").

        Returns
        -------
        pl.LazyFrame
            Extracted source-shaped tabular data.
        """
        if not raw_bytes:
            return pl.LazyFrame()

        t0 = time.perf_counter()
        diagnostics.debug("Starting Excel extraction for: %s", filename)
        excel_reader = fastexcel.read_excel(raw_bytes)
        available_sheets = excel_reader.sheet_names

        target_sheet: str | None = None
        if sheet_name is not None:
            if sheet_name in available_sheets:
                target_sheet = sheet_name
        elif candidate_sheets:
            target_sheet = next((s for s in candidate_sheets if s in available_sheets), None)
        elif available_sheets:
            target_sheet = available_sheets[0]

        if target_sheet is None:
            diagnostics.debug(
                "Skipped %s: Could not resolve target sheet (requested: %s, candidates: %s, available: %s)",
                filename,
                sheet_name,
                candidate_sheets,
                available_sheets,
            )
            return pl.LazyFrame()

        df_raw = excel_reader.load_sheet(target_sheet, header_row=None).to_polars()
        if df_raw.is_empty():
            return pl.LazyFrame()

        header_idx: int = 0
        if header_anchor is not None:
            anchor_clean = header_anchor.strip()
            start_search = df_raw.with_row_index().filter(
                pl.any_horizontal(
                    pl.all().cast(pl.String, strict=False).str.strip_chars() == anchor_clean
                )
            )
            if start_search.is_empty():
                diagnostics.debug(
                    "Skipped %s: Could not find header anchor '%s' in sheet '%s'",
                    filename,
                    header_anchor,
                    target_sheet,
                )
                return pl.LazyFrame()
            header_idx = int(start_search["index"][0]) + anchor_offset
        elif header_row is not None:
            header_idx = header_row

        if header_idx >= df_raw.height:
            return pl.LazyFrame()

        df_sliced = df_raw.slice(header_idx)
        if df_sliced.is_empty():
            return pl.LazyFrame()

        df_data, first_col = _clean_excel_headers(df_sliced)

        if stop_on_blank:
            null_search = df_data.with_row_index().filter(pl.col(first_col).is_null())
            if not null_search.is_empty():
                end_idx = int(null_search["index"][0])
                df_data = df_data.slice(0, end_idx)
        else:
            df_data = df_data.filter(pl.col(first_col).is_not_null())

        meta_exprs: list[pl.Expr] = [
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
        ]

        if file_category is not None:
            meta_exprs.append(pl.lit(file_category).alias("__file_category__"))

        match = re.search(r"(\d{2}-\d{2}-\d{4}|\d{2}-\d{4})", filename)
        if match:
            date_str = match.group(1)
            try:
                if len(date_str.split("-")) == 2:
                    parsed_date = datetime.strptime(f"01-{date_str}", "%d-%m-%Y").date()
                else:
                    parsed_date = datetime.strptime(date_str, "%d-%m-%Y").date()
                meta_exprs.append(pl.lit(parsed_date).alias("Month Date"))
            except ValueError:
                pass

        final_df = df_data.with_columns(meta_exprs)

        diagnostics.debug(
            "Parsed %s in %.2fs - %d rows extracted",
            filename,
            time.perf_counter() - t0,
            final_df.height,
        )
        return final_df.lazy()


def _process_mf_statement(filename: str, raw_bytes: bytes) -> pl.DataFrame:
    """Parse a single mutual fund holdings Excel statement from raw binary bytes.

    Parameters
    ----------
    filename : str
        Source filename for logging context.
    raw_bytes : bytes
        Binary payload of the Excel workbook.

    Returns
    -------
    pl.DataFrame
        Extracted mutual fund holdings records.
    """
    t0 = time.perf_counter()
    diagnostics.debug(f"Starting parse for MF Holding Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Holdings" not in excel_reader.sheet_names:
        diagnostics.debug(
            f"Skipped {filename}: Missing 'Holdings' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()

    df_raw = excel_reader.load_sheet("Holdings", header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        diagnostics.debug(
            f"Skipped {filename}: Could not find 'Scheme Name' anchor (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()

    header_idx = int(start_search["index"][0])
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    final_df = df_data.filter(pl.col(first_col).is_not_null())
    diagnostics.debug(
        f"Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
    )
    return final_df


def extract_mf_market_data_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Extract mutual fund market data from a list of raw statement payloads."""
    all_dfs: list[pl.DataFrame] = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                diagnostics.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            diagnostics.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_mf_statement(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
            pl.lit("Indian MF").alias("__file_category__"),
            pl.lit(artifact_id).alias("artifact_id"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_mf_transaction_statements(filename: str, raw_bytes: bytes) -> pl.DataFrame:
    """Parse mutual fund transaction order statements from raw binary bytes.

    Parameters
    ----------
    filename : str
        Source filename for logging context.
    raw_bytes : bytes
        Binary payload of the Excel workbook.

    Returns
    -------
    pl.DataFrame
        Extracted mutual fund transaction records.
    """
    t0 = time.perf_counter()
    diagnostics.debug(f"Starting parse for MF Transaction Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Transactions" not in excel_reader.sheet_names:
        diagnostics.debug(
            f"Skipped {filename}: Missing 'Transactions' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Transactions", header_row=None).to_polars()
    if df_raw.is_empty():
        return pl.DataFrame()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Scheme Name")
    if start_search.is_empty():
        diagnostics.debug(f"Skipped {filename}: Could not find 'Scheme Name' anchor")
        return pl.DataFrame()
    header_idx = int(start_search["index"][0])
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    final_df = df_data.filter(pl.col(first_col).is_not_null())
    diagnostics.debug(
        f"Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
    )
    return final_df


def extract_mf_transactions_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Parse raw Excel mutual fund transaction statements into a combined LazyFrame.

    Parameters
    ----------
    valid_files : list[tuple[str, str, bytes]]
        List of (filename, folder_path, raw_bytes) tuples.

    Returns
    -------
    pl.LazyFrame
        Combined lazy frame with metadata and month-date columns.
    """
    all_dfs: list[pl.DataFrame] = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4}|\d{2}-\d{4})", filename)
            if not match:
                diagnostics.warning(f"File skipped (regex miss): {filename}")
                continue
            date_str = match.group(1)
            if len(date_str.split("-")) == 2:
                month_date = datetime.strptime(f"01-{date_str}", "%d-%m-%Y").date()
            else:
                month_date = datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            diagnostics.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_mf_transaction_statements(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
            pl.lit("Indian MF").alias("__file_category__"),
            pl.lit(artifact_id).alias("artifact_id"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_closing_statement(filename: str, raw_bytes: bytes) -> pl.DataFrame:
    """Parse domestic stock closing valuation Excel workbook from raw binary bytes.

    Parameters
    ----------
    filename : str
        Source filename for logging context.
    raw_bytes : bytes
        Binary payload of the Excel workbook.

    Returns
    -------
    pl.DataFrame
        Extracted stock closing positions DataFrame.
    """
    t0 = time.perf_counter()
    diagnostics.debug(f"Starting parse for Stock Closing Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    sheet_names = excel_reader.sheet_names
    target_sheet = next(
        (name for name in ["Trade Level", "Sheet", "Sheet1"] if name in sheet_names), None
    )
    if not target_sheet:
        diagnostics.debug(
            f"Skipped {filename}: Missing target sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet(target_sheet, header_row=None).to_polars()
    col_1 = df_raw.columns[0]
    start_search = df_raw.with_row_index().filter(pl.col(col_1) == "Unrealised trades")
    if start_search.is_empty():
        diagnostics.debug(f"Skipped {filename}: Could not find 'Unrealised trades' anchor")
        return pl.DataFrame()

    header_idx = int(start_search["index"][0]) + 2
    df_sliced = df_raw.slice(header_idx)

    df_data, first_col = _clean_excel_headers(df_sliced)
    null_search = df_data.with_row_index().filter(pl.col(first_col).is_null())
    if not null_search.is_empty():
        end_idx = int(null_search["index"][0])
        df_data = df_data.slice(0, end_idx)

    diagnostics.debug(
        f"Parsed {filename} in {time.perf_counter() - t0:.2f}s - {df_data.height} rows extracted"
    )
    return df_data


def extract_stock_market_data_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Parse raw Excel domestic stock closing valuation statements into a combined LazyFrame.

    Parameters
    ----------
    valid_files : list[tuple[str, str, bytes]]
        List of (filename, folder_path, raw_bytes) tuples.

    Returns
    -------
    pl.LazyFrame
        Combined lazy frame with market valuation data and metadata.
    """
    all_dfs: list[pl.DataFrame] = []
    for filename, folder_path, raw_bytes in valid_files:
        try:
            match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
            if not match:
                diagnostics.warning(f"File skipped (regex miss): {filename}")
                continue
            month_date = datetime.strptime(match.group(1), "%d-%m-%Y").date()
        except ValueError:
            diagnostics.warning(f"File skipped (parse error): {filename}")
            continue
        df_processed = _process_stock_closing_statement(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit(month_date).alias("Month Date"),
            pl.lit("Indian Stocks").alias("__file_category__"),
            pl.lit(artifact_id).alias("artifact_id"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_stock_transactions(filename: str, raw_bytes: bytes) -> pl.DataFrame:
    """Parse domestic stock trade orders Excel statement from raw binary bytes.

    Parameters
    ----------
    filename : str
        Source filename for logging context.
    raw_bytes : bytes
        Binary payload of the Excel workbook.

    Returns
    -------
    pl.DataFrame
        Extracted trade order records DataFrame.
    """
    t0 = time.perf_counter()
    diagnostics.debug(f"Starting parse for Stock Transaction Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    if "Sheet1" not in excel_reader.sheet_names:
        diagnostics.debug(
            f"Skipped {filename}: Missing 'Sheet1' sheet (took {time.perf_counter() - t0:.2f}s)"
        )
        return pl.DataFrame()
    df_raw = excel_reader.load_sheet("Sheet1", header_row=5).to_polars()
    if "Stock name" in df_raw.columns:
        final_df = df_raw.filter(pl.col("Stock name").is_not_null())
        diagnostics.debug(
            f"Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
        )
        return final_df
    diagnostics.debug(f"Skipped {filename}: Could not find 'Stock name' column")
    return pl.DataFrame()


def extract_stock_transactions_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Parse raw Excel domestic stock trade order statements into a combined LazyFrame.

    Parameters
    ----------
    valid_files : list[tuple[str, str, bytes]]
        List of (filename, folder_path, raw_bytes) tuples.

    Returns
    -------
    pl.LazyFrame
        Combined lazy frame of trade order transactions.
    """
    all_dfs: list[pl.DataFrame] = []
    for filename, folder_path, raw_bytes in valid_files:
        df_processed = _process_stock_transactions(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit("Indian Stocks").alias("__file_category__"),
            pl.lit(artifact_id).alias("artifact_id"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()


def _process_us_stock_transactions(filename: str, raw_bytes: bytes) -> pl.DataFrame:
    """Parse foreign US equity transactions Excel statement from raw binary bytes.

    Parameters
    ----------
    filename : str
        Source filename for logging context.
    raw_bytes : bytes
        Binary payload of the Excel workbook.

    Returns
    -------
    pl.DataFrame
        Extracted US stock trade records DataFrame.
    """
    t0 = time.perf_counter()
    diagnostics.debug(f"Starting parse for US Stock Transaction Statement: {filename}")
    excel_reader = fastexcel.read_excel(raw_bytes)
    sheet_name = excel_reader.sheet_names[0]
    df_raw = excel_reader.load_sheet(sheet_name, header_row=0).to_polars()
    if "Stock Name" in df_raw.columns:
        final_df = df_raw.filter(pl.col("Stock Name").is_not_null())
        diagnostics.debug(
            f"Parsed {filename} in {time.perf_counter() - t0:.2f}s - {final_df.height} rows extracted"
        )
        return final_df
    diagnostics.debug(f"Skipped {filename}: Could not find 'Stock Name' column")
    return pl.DataFrame()


def extract_us_stock_transactions_raw(valid_files: list[tuple[str, str, bytes]]) -> pl.LazyFrame:
    """Parse raw Excel foreign/US stock trade transaction statements into a combined LazyFrame.

    Parameters
    ----------
    valid_files : list[tuple[str, str, bytes]]
        List of (filename, folder_path, raw_bytes) tuples.

    Returns
    -------
    pl.LazyFrame
        Combined lazy frame of US stock transactions.
    """
    all_dfs: list[pl.DataFrame] = []
    for filename, folder_path, raw_bytes in valid_files:
        df_processed = _process_us_stock_transactions(filename, raw_bytes)
        if df_processed.is_empty():
            continue
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        df_processed = df_processed.with_columns(
            pl.lit(filename).alias("__file_name__"),
            pl.lit(folder_path).alias("__folder_path__"),
            pl.lit("US Stocks").alias("__file_category__"),
            pl.lit(artifact_id).alias("artifact_id"),
        )
        all_dfs.append(df_processed)
    if not all_dfs:
        return pl.LazyFrame()
    return pl.concat(all_dfs, how="diagonal").lazy()
