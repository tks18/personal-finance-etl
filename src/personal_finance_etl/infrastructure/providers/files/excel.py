# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Excel parsing and evidence extraction adapter.

Owns
----
- In-memory parsing of Excel binary statements using fastexcel.
- Header detection and normalization across financial statement structures.
- Date extraction heuristics from file basenames.
- Ingestion metadata tagging (Month Date, __file_category__, artifact_id).

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

from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = [
    "ExcelExtractor",
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

        if header_anchor is None and header_row is not None:
            df_data = excel_reader.load_sheet(target_sheet, header_row=header_row).to_polars()
            if df_data.is_empty():
                return pl.LazyFrame()
            clean_headers: list[str] = []
            seen: dict[str, int] = {}
            for i, h in enumerate(df_data.columns):
                header_str = h.strip()
                if header_str in ("", "None", "null"):
                    header_str = f"Unnamed_{i}"
                if header_str in seen:
                    seen[header_str] += 1
                    header_str = f"{header_str}_{seen[header_str]}"
                else:
                    seen[header_str] = 0
                clean_headers.append(header_str)
            df_data = df_data.rename(dict(zip(df_data.columns, clean_headers, strict=False)))
            first_col = clean_headers[0]
        else:
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

        meta_exprs: list[pl.Expr] = []

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

        final_df = df_data.with_columns(meta_exprs) if meta_exprs else df_data

        diagnostics.debug(
            "Parsed %s in %.2fs - %d rows extracted",
            filename,
            time.perf_counter() - t0,
            final_df.height,
        )
        return final_df.lazy()
