"""
Shared utility helpers for the Investment Manager application.
"""

import os
import sys
from datetime import date, datetime

import polars as pl


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for both dev and PyInstaller onefile."""
    try:
        # PyInstaller extracts resources to a temp folder at runtime
        base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def clean_numeric_col(df: pl.DataFrame, col: str) -> pl.DataFrame:
    """Strip currency formatting from a string column and cast to Float64."""
    if col in df.columns and getattr(df.schema[col], "base_type", df.schema[col]) in [
        pl.Utf8,
        pl.String,
    ]:
        df = df.with_columns(
            pl.col(col).str.replace_all(r"[\\',]", "").str.strip_chars().cast(pl.Float64)
        )
    return df


def to_date_obj(val: str | date | datetime | None) -> date | None:
    """Flexibly coerce a value to a Python date object."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip().split(" ")[0]
        for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                pass
        return None
    return None


def get_fy_folder_name(dt: date) -> str:
    """Return the Indian financial year folder name for a given date (e.g. '2024-25')."""
    year, month = dt.year, dt.month
    if month >= 4:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


def get_month_folder_name(dt: date) -> str:
    """Return a zero-padded month-year folder name (e.g. '04-2024')."""
    return f"{dt.month:02d}-{dt.year}"


def get_file_name(dt: date) -> str:
    """Return a zero-padded day-month-year CSV filename (e.g. '01-04-2024.csv')."""
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year}.csv"


def ensure_date_col[T: (pl.DataFrame, pl.LazyFrame)](df: T, col_name: str = "DATE") -> T:
    """Safely cast a column to Date, handling String, Datetime, or Date types."""
    schema = df.collect_schema() if hasattr(df, "collect_schema") else df.schema
    if col_name not in schema:
        return df

    dtype = schema[col_name]
    base = getattr(dtype, "base_type", dtype)

    if base in (getattr(pl, "Utf8", pl.String), pl.String):
        try:
            return df.with_columns(pl.col(col_name).str.to_date("%Y-%m-%d", strict=False))
        except AttributeError:
            return df.with_columns(pl.col(col_name).str.strptime(pl.Date, "%Y-%m-%d", strict=False))
    elif base == pl.Datetime:
        return df.with_columns(pl.col(col_name).cast(pl.Date))
    elif base != pl.Date:
        return df.with_columns(pl.col(col_name).cast(pl.Date, strict=False))

    return df
