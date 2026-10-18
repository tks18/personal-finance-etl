"""Calendar, Indian Financial Year (FY), and strict date parsing utilities.

Owns
----
- Indian financial year computations (get_fy_start_year, get_fy_folder_name, get_fy_string).
- Date coercion and strict scalar date validation (to_date_obj, parse_strict_date).
- Polars date column normalization and LazyFrame validation (ensure_date_col, validate_and_parse_dates, add_fy_if_missing).

Does not own
-------------
- Numeric parsing or scalar validation (owned by domain.common.validation).
- Tax lot holding period computation (owned by domain.tax).
- File storage and path creation (owned by infrastructure.filesystem).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

import polars as pl

from personal_finance_etl.domain.common.validation import FinancialSourceValidationError

DEFAULT_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d-%b-%y",
    "%d-%m-%Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
)


def get_fy_start_year(dt: date) -> int:
    """Return the starting calendar year of the Indian financial year for a given date.

    In India, the financial year runs from April 1 to March 31.
    """
    return dt.year if dt.month >= 4 else dt.year - 1


def get_fy_folder_name(dt: date) -> str:
    """Return the Indian financial year folder name for a given date (e.g., '2024-25')."""
    year = get_fy_start_year(dt)
    return f"{year}-{str(year + 1)[-2:]}"


def get_fy_string(dt: date) -> str:
    """Return standard Indian financial year label for a given date (e.g., '2024-25')."""
    return get_fy_folder_name(dt)


def get_month_folder_name(dt: date) -> str:
    """Return a zero-padded month-year folder name (e.g., '04-2024')."""
    return f"{dt.month:02d}-{dt.year}"


def get_file_name(dt: date) -> str:
    """Return a zero-padded day-month-year CSV filename (e.g., '01-04-2024.csv')."""
    return f"{dt.day:02d}-{dt.month:02d}-{dt.year}.csv"


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

    val_clean = str(val).strip()
    if not val_clean or val_clean.lower() in ("null", "none"):
        return None

    val_date_part = val_clean.split(" ", maxsplit=1)[0]
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


def ensure_date_col[T: (pl.DataFrame, pl.LazyFrame)](df: T, col_name: str = "DATE") -> T:
    """Safely cast a column to pl.Date, handling String, Datetime, or Date types."""
    schema = df.collect_schema() if hasattr(df, "collect_schema") else df.schema
    if col_name not in schema:
        return df

    dtype = schema[col_name]
    base = dtype.base_type() if callable(getattr(dtype, "base_type", None)) else dtype

    if base in (pl.Utf8, pl.String):
        return df.with_columns(pl.col(col_name).str.to_date("%Y-%m-%d", strict=False))
    if base == pl.Datetime:
        return df.with_columns(pl.col(col_name).cast(pl.Date))
    if base != pl.Date:
        return df.with_columns(pl.col(col_name).cast(pl.Date, strict=False))

    return df


def parse_strict_date(
    value: object,
    formats: tuple[str, ...] = DEFAULT_DATE_FORMATS,
    *,
    field_name: str = "date_field",
    source: str | None = None,
    sheet: str | None = None,
    row_identifier: object = None,
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

    clean_val = val_str.split("T", maxsplit=1)[0]
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


def _diagnose_date_failure(
    row_dict: Mapping[str, object],
    available_cols: list[str],
    date_cols_formats: dict[str, list[str]],
    opt_set: set[str],
    source_val: str | None,
    sheet: str | None,
    row_id_val: str | None,
) -> None:
    """Diagnose the specific column and value that caused a date validation failure."""
    faulty_col = available_cols[0]
    faulty_val = row_dict.get(faulty_col)

    for c in available_cols:
        raw_v = row_dict.get(c)
        if raw_v is not None:
            if isinstance(raw_v, (datetime, date)):
                continue
            raw_s = str(raw_v).strip()
            if c not in opt_set and (raw_s == "" or raw_s.lower() in ("null", "none")):
                faulty_col, faulty_val = c, raw_v
                break
            try:
                parse_strict_date(raw_v, tuple(date_cols_formats[c]), optional=c in opt_set)
            except FinancialSourceValidationError:
                faulty_col, faulty_val = c, raw_v
                break
        elif c not in opt_set:
            faulty_col, faulty_val = c, None
            break

    raise FinancialSourceValidationError(
        f"Malformed or missing financial date in field {faulty_col!r}: {faulty_val!r}",
        source=source_val,
        sheet=sheet,
        field_name=faulty_col,
        raw_value=faulty_val,
        row_identifier=row_id_val,
    )


def validate_and_parse_dates(
    lf: pl.LazyFrame,
    date_cols_formats: dict[str, list[str]],
    *,
    optional_cols: set[str] | None = None,
    source_col: str = "__file_name__",
    sheet: str | None = None,
    row_id_col: str | None = None,
) -> pl.LazyFrame:
    """Validate date columns across a LazyFrame.

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
        c_dtype = schema.get(c)
        base = (
            c_dtype.base_type()
            if c_dtype is not None and callable(getattr(c_dtype, "base_type", None))
            else c_dtype
        )
        parse_attempts: list[pl.Expr] = []
        if base == pl.Date:
            parse_attempts.append(pl.col(c))
        elif base == pl.Datetime:
            parse_attempts.append(pl.col(c).dt.date())
        elif base not in (pl.String, pl.Utf8):
            parse_attempts.append(pl.col(c).cast(pl.Date, strict=False))

        parse_attempts.extend(raw_text.str.to_date(fmt, strict=False) for fmt in formats)
        parse_attempts.extend(
            raw_text.str.to_datetime(fmt, strict=False).dt.date()
            for fmt in formats
            if "%H" in fmt or "%I" in fmt
        )
        parse_attempts.append(raw_text.str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False))
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

        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 10) of invalid date rows for structured error diagnostics
        bad_rows = (
            lf.filter(pl.any_horizontal(invalid_checks)).select(select_cols).limit(10).collect()
        )
        if bad_rows.height > 0:
            row_dict = bad_rows.row(0, named=True)
            source_val = str(row_dict.get(source_col)) if has_source else None
            row_id_val = str(row_dict.get(row_id_col)) if has_row_id and row_id_col else None
            _diagnose_date_failure(
                row_dict, available_cols, date_cols_formats, opt_set, source_val, sheet, row_id_val
            )

    return lf.with_columns(cast_exprs)


def add_fy_if_missing(df: pl.LazyFrame, date_col: str) -> pl.LazyFrame:
    """Add Financial Year (FY) column to a LazyFrame if missing."""
    if "FY" not in df.collect_schema().names():
        df = (
            df.with_columns(
                pl.col(date_col)
                .cast(pl.Date, strict=False)
                .dt.offset_by("-3mo")
                .dt.year()
                .alias("FY_Year")
            )
            .with_columns(
                (
                    pl.col("FY_Year").cast(pl.String)
                    + "-"
                    + (pl.col("FY_Year") + 1).cast(pl.String).str.slice(2, 2)
                ).alias("FY")
            )
            .drop("FY_Year")
        )
    return df
