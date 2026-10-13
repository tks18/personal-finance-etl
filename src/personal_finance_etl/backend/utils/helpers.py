"""
Shared utility helpers for the Investment Manager application.
"""

import importlib.resources
import math
import os
import sys
import tempfile
from datetime import date, datetime
from typing import Any

import polars as pl

from personal_finance_etl.backend.types.validation import FinancialSourceValidationError


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for PyInstaller, PyPI, and local dev."""
    # 1. PyInstaller (EXE)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return os.path.join(str(meipass), relative_path)

    # 2. Local Dev (Root Directory)
    local_path = os.path.join(os.path.abspath("."), relative_path)
    if os.path.exists(local_path):
        return local_path

    # 3. PyPI (pip install via hatchling)
    try:
        parts = relative_path.replace("\\", "/").split("/")
        pkg_path = importlib.resources.files("personal_finance_etl").joinpath(*parts)
        if pkg_path.is_file() or pkg_path.is_dir():
            return str(pkg_path)
    except (TypeError, ModuleNotFoundError, FileNotFoundError):
        # EXPECTED_FALLBACK: Package resource lookup not available in this installation layout
        pass

    return local_path


def get_temp_dir() -> str:
    """Return a consistent temporary directory for the application."""
    path = os.path.join(tempfile.gettempdir(), "PersonalFinanceETL")
    os.makedirs(path, exist_ok=True)
    return path


def get_cache_dir(base_path: str, subfolder: str = "") -> str:
    """Return an absolute path to a cache directory inside the given base path."""
    path = os.path.join(base_path, "cache")
    if subfolder:
        path = os.path.join(path, subfolder)
    os.makedirs(path, exist_ok=True)
    return path


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


def to_date_obj(val: str | date | datetime | None, *, strict: bool = False) -> date | None:
    """Flexibly coerce a value to a Python date object.

    If strict is True, populated values that cannot be parsed raise ValueError
    instead of silently returning None.
    """
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    else:
        val_clean = str(val).strip()
        if not val_clean or val_clean.lower() in ("null", "none"):
            return None
        val_date_part = val_clean.split(" ")[0]
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%y"):
            try:
                return datetime.strptime(val_date_part, fmt).date()
            except ValueError:
                pass
            if val_date_part != val_clean:
                try:
                    return datetime.strptime(val_clean, fmt).date()
                except ValueError:
                    pass
        if strict:
            raise ValueError(f"Cannot parse date from populated value: {val!r}")
        return None


def get_fy_start_year(dt: date) -> int:
    """Return the starting year of the Indian financial year for a given date."""
    return dt.year if dt.month >= 4 else dt.year - 1


def get_fy_folder_name(dt: date) -> str:
    """Return the Indian financial year folder name for a given date (e.g. '2024-25')."""
    year = get_fy_start_year(dt)
    return f"{year}-{str(year + 1)[-2:]}"


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


def parse_strict_numeric(
    value: Any,
    *,
    field_name: str = "numeric_field",
    source: str | None = None,
    sheet: str | None = None,
    row_identifier: Any = None,
    optional: bool = False,
) -> float | None:
    """Strictly parse a scalar financial numeric value.

    A blank/None value in an optional field returns None.
    A malformed or non-finite populated value raises FinancialSourceValidationError.
    """
    if value is None:
        if optional:
            return None
        raise FinancialSourceValidationError(
            f"Required financial numeric field {field_name!r} is missing/null",
            source=source,
            sheet=sheet,
            field_name=field_name,
            raw_value=value,
            row_identifier=row_identifier,
        )

    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            if optional:
                return None
            raise FinancialSourceValidationError(
                f"Financial numeric in {field_name!r} cannot be NaN or infinite: {value!r}",
                source=source,
                sheet=sheet,
                field_name=field_name,
                raw_value=value,
                row_identifier=row_identifier,
            )
        return float(value)

    val_str = str(value).strip().replace(",", "").rstrip("%").strip()
    if val_str == "" or val_str.lower() in ("null", "none", "nan", "-", "--", "n/a", "na"):
        if optional:
            return None
        raise FinancialSourceValidationError(
            f"Required financial numeric field {field_name!r} is empty",
            source=source,
            sheet=sheet,
            field_name=field_name,
            raw_value=value,
            row_identifier=row_identifier,
        )

    try:
        parsed = float(val_str)
        if not math.isfinite(parsed):
            raise ValueError("Non-finite numeric")
        return parsed
    except ValueError as err:
        raise FinancialSourceValidationError(
            f"Malformed financial numeric in field {field_name!r}: {value!r}",
            source=source,
            sheet=sheet,
            field_name=field_name,
            raw_value=value,
            row_identifier=row_identifier,
        ) from err


def parse_strict_date(
    value: Any,
    formats: tuple[str, ...] = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d-%b-%y",
        "%d-%m-%Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
    ),
    *,
    field_name: str = "date_field",
    source: str | None = None,
    sheet: str | None = None,
    row_identifier: Any = None,
    optional: bool = False,
) -> date | None:
    """Strictly parse a scalar financial date value.

    A blank/None value in an optional field returns None.
    A populated value that cannot be parsed under any format raises FinancialSourceValidationError.
    """
    if value is None:
        if optional:
            return None
        raise FinancialSourceValidationError(
            f"Required date field {field_name!r} is missing/null",
            source=source,
            sheet=sheet,
            field_name=field_name,
            raw_value=value,
            row_identifier=row_identifier,
        )

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    val_str = str(value).strip()
    if val_str == "" or val_str.lower() in ("null", "none"):
        if optional:
            return None
        raise FinancialSourceValidationError(
            f"Required date field {field_name!r} is empty",
            source=source,
            sheet=sheet,
            field_name=field_name,
            raw_value=value,
            row_identifier=row_identifier,
        )

    clean_val = val_str.split("T")[0]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
        if clean_val != val_str:
            try:
                return datetime.strptime(clean_val, fmt).date()
            except ValueError:
                pass

    raise FinancialSourceValidationError(
        f"Malformed financial date in field {field_name!r}: {value!r}",
        source=source,
        sheet=sheet,
        field_name=field_name,
        raw_value=value,
        row_identifier=row_identifier,
    )


def validate_and_parse_numerics(
    lf: pl.LazyFrame,
    numeric_cols: list[str],
    *,
    optional_cols: set[str] | None = None,
    source_col: str = "__file_name__",
    sheet: str | None = None,
    row_id_col: str | None = None,
) -> pl.LazyFrame:
    """Validates numeric columns across a LazyFrame.

    If any populated numeric is malformed (e.g. '1O0', non-numeric strings),
    raises FinancialSourceValidationError with source context rather than
    silently collapsing it to 0.0 or null.
    """
    schema = lf.collect_schema()
    available_cols = [c for c in numeric_cols if c in schema.names()]
    if not available_cols:
        return lf

    opt_set = optional_cols or set()
    has_source = source_col in schema.names()
    has_row_id = row_id_col is not None and row_id_col in schema.names()

    NULL_SENTINELS = ["null", "none", "nan", "-", "--", "n/a", "na"]

    invalid_checks: list[pl.Expr] = []
    for c in available_cols:
        raw_text = (
            pl.col(c)
            .cast(pl.String)
            .str.replace_all(",", "")
            .str.strip_chars("% \t\r\n")
        )
        is_populated = (
            pl.col(c).is_not_null()
            & (raw_text != "")
            & (~raw_text.str.to_lowercase().is_in(NULL_SENTINELS))
        )
        parsed = raw_text.cast(pl.Float64, strict=False)
        if c in opt_set:
            invalid_checks.append(is_populated & (parsed.is_null() | ~parsed.is_finite()))
        else:
            invalid_checks.append((~is_populated) | (parsed.is_null() | ~parsed.is_finite()))

    if invalid_checks:
        select_cols = available_cols.copy()
        if has_source:
            select_cols.append(source_col)
        if has_row_id and row_id_col is not None:
            select_cols.append(row_id_col)

        bad_rows = lf.filter(pl.any_horizontal(invalid_checks)).select(select_cols).limit(10).collect()
        if bad_rows.height > 0:
            row_dict = bad_rows.row(0, named=True)
            faulty_col = available_cols[0]
            faulty_val = row_dict.get(faulty_col)
            for c in available_cols:
                raw_v = row_dict.get(c)
                if raw_v is not None:
                    raw_s = str(raw_v).replace(",", "").strip().rstrip("%").strip()
                    if c in opt_set and (raw_s == "" or raw_s.lower() in NULL_SENTINELS):
                        continue
                    if c not in opt_set and (raw_s == "" or raw_s.lower() in NULL_SENTINELS):
                        faulty_col = c
                        faulty_val = raw_v
                        break
                    try:
                        p = float(raw_s)
                        if not math.isfinite(p):
                            faulty_col = c
                            faulty_val = raw_v
                            break
                    except ValueError:
                        faulty_col = c
                        faulty_val = raw_v
                        break
                elif c not in opt_set:
                    faulty_col = c
                    faulty_val = None
                    break

            source_val = str(row_dict.get(source_col)) if has_source else None
            row_id_val = str(row_dict.get(row_id_col)) if has_row_id and row_id_col else None
            raise FinancialSourceValidationError(
                f"Malformed or missing financial numeric in field {faulty_col!r}: {faulty_val!r}",
                source=source_val,
                sheet=sheet,
                field_name=faulty_col,
                raw_value=faulty_val,
                row_identifier=row_id_val,
            )

    cast_exprs = [
        pl.when(
            pl.col(c)
            .cast(pl.String)
            .str.replace_all(",", "")
            .str.strip_chars("% \t\r\n")
            .str.to_lowercase()
            .is_in(NULL_SENTINELS)
            | (pl.col(c).cast(pl.String).str.strip_chars("% \t\r\n") == "")
        )
        .then(None)
        .otherwise(
            pl.col(c)
            .cast(pl.String)
            .str.replace_all(",", "")
            .str.strip_chars("% \t\r\n")
            .cast(pl.Float64, strict=False)
        )
        .alias(c)
        for c in available_cols
    ]
    return lf.with_columns(cast_exprs)


def validate_and_parse_dates(
    lf: pl.LazyFrame,
    date_cols_formats: dict[str, list[str]],
    *,
    optional_cols: set[str] | None = None,
    source_col: str = "__file_name__",
    sheet: str | None = None,
    row_id_col: str | None = None,
) -> pl.LazyFrame:
    """Validates date columns across a LazyFrame.

    If any populated date cannot be parsed under the specified formats,
    raises FinancialSourceValidationError rather than silently turning it into null.
    """
    schema = lf.collect_schema()
    available_cols = [c for c in date_cols_formats if c in schema.names()]
    if not available_cols:
        return lf

    opt_set = optional_cols or set()
    has_source = source_col in schema.names()
    has_row_id = row_id_col is not None and row_id_col in schema.names()

    invalid_checks: list[pl.Expr] = []
    cast_exprs: list[pl.Expr] = []

    for c in available_cols:
        formats = date_cols_formats[c]
        raw_text = pl.col(c).cast(pl.String).str.strip_chars()
        is_populated = (
            pl.col(c).is_not_null()
            & (raw_text != "")
            & (~raw_text.str.to_lowercase().is_in(["null", "none", "nan"]))
        )
        parse_attempts = [
            pl.col(c).cast(pl.Date, strict=False)
        ] + [
            raw_text.str.to_date(fmt, strict=False)
            for fmt in formats
        ] + [
            raw_text.str.to_datetime(fmt, strict=False).dt.date()
            for fmt in formats
            if "%H" in fmt or "%I" in fmt
        ]
        parsed = pl.coalesce(parse_attempts)
        if c in opt_set:
            invalid_checks.append(is_populated & parsed.is_null())
        else:
            invalid_checks.append((~is_populated) | parsed.is_null())
        cast_exprs.append(parsed.alias(c))

    if invalid_checks:
        select_cols = available_cols.copy()
        if has_source:
            select_cols.append(source_col)
        if has_row_id and row_id_col is not None:
            select_cols.append(row_id_col)

        bad_rows = lf.filter(pl.any_horizontal(invalid_checks)).select(select_cols).limit(10).collect()
        if bad_rows.height > 0:
            row_dict = bad_rows.row(0, named=True)
            faulty_col = available_cols[0]
            faulty_val = row_dict.get(faulty_col)
            for c in available_cols:
                raw_v = row_dict.get(c)
                if raw_v is not None:
                    raw_s = str(raw_v).strip()
                    if c not in opt_set and (raw_s == "" or raw_s.lower() in ("null", "none")):
                        faulty_col = c
                        faulty_val = raw_v
                        break
                    try:
                        parse_strict_date(raw_s, tuple(date_cols_formats[c]), optional=c in opt_set)
                    except FinancialSourceValidationError:
                        faulty_col = c
                        faulty_val = raw_v
                        break
                elif c not in opt_set:
                    faulty_col = c
                    faulty_val = None
                    break

            source_val = str(row_dict.get(source_col)) if has_source else None
            row_id_val = str(row_dict.get(row_id_col)) if has_row_id and row_id_col else None
            raise FinancialSourceValidationError(
                f"Malformed or missing financial date in field {faulty_col!r}: {faulty_val!r}",
                source=source_val,
                sheet=sheet,
                field_name=faulty_col,
                raw_value=faulty_val,
                row_identifier=row_id_val,
            )

    return lf.with_columns(cast_exprs)
