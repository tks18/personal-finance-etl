"""Financial source validation exceptions, numeric parsing, and frame validation.

Owns
----
- FinancialSourceValidationError distinguishing invalid populated data from valid nulls.
- Strict scalar numeric parsing (parse_strict_numeric) with contextual error metadata.
- Polars numeric column cleaning and frame validation (validate_and_parse_numerics).

Does not own
-------------
- Date parsing and calendar financial year semantics (owned by domain.common.dates).
- Filesystem resource resolution (owned by infrastructure.filesystem.paths).
- Domain entity constraints (owned by domain.*).
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl


class FinancialSourceValidationError(ValueError):
    """Raised when a populated source value fails strict financial parsing.

    Distinguishes malformed inputs (which must fail loudly to avoid silent data
    corruption) from absent optional fields (which resolve to valid nulls).
    """

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        sheet: str | None = None,
        field_name: str | None = None,
        raw_value: Any = None,
        row_identifier: Any = None,
    ) -> None:
        context_parts: list[str] = []
        if source:
            context_parts.append(f"source={source}")
        if sheet:
            context_parts.append(f"sheet={sheet}")
        if field_name:
            context_parts.append(f"field={field_name}")
        if raw_value is not None:
            context_parts.append(f"raw_value={raw_value!r}")
        if row_identifier is not None:
            context_parts.append(f"row={row_identifier}")
        ctx_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        super().__init__(f"{message}{ctx_str}")
        self.source = source
        self.sheet = sheet
        self.field_name = field_name
        self.raw_value = raw_value
        self.row_identifier = row_identifier


NULL_SENTINELS = ["null", "none", "nan", "-", "--", "n/a", "na"]


def clean_numeric_col(df: pl.DataFrame, col: str) -> pl.DataFrame:
    """Strip currency formatting from a string column and cast to Float64.

    Parameters
    ----------
    df : pl.DataFrame
        Input DataFrame.
    col : str
        Target column name.

    Returns
    -------
    pl.DataFrame
        DataFrame with the cleaned numeric column.
    """
    schema = df.schema
    if col in df.columns:
        dtype = schema[col]
        base = dtype.base_type() if callable(getattr(dtype, "base_type", None)) else dtype
        if base in (pl.Utf8, pl.String):
            return df.with_columns(
                pl.col(col).str.replace_all(r"[\\',]", "").str.strip_chars().cast(pl.Float64)
            )
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
    if val_str == "" or val_str.lower() in NULL_SENTINELS:
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


def _diagnose_numeric_failure(
    row_dict: dict[str, Any],
    available_cols: list[str],
    opt_set: set[str],
    source_val: str | None,
    sheet: str | None,
    row_id_val: str | None,
) -> None:
    """Diagnose the specific column and value that caused a numeric validation failure."""
    faulty_col = available_cols[0]
    faulty_val = row_dict.get(faulty_col)

    for c in available_cols:
        raw_v = row_dict.get(c)
        if raw_v is not None:
            raw_s = str(raw_v).replace(",", "").strip().rstrip("%").strip()
            if c in opt_set and (raw_s == "" or raw_s.lower() in NULL_SENTINELS):
                continue
            if c not in opt_set and (raw_s == "" or raw_s.lower() in NULL_SENTINELS):
                faulty_col, faulty_val = c, raw_v
                break
            try:
                p = float(raw_s)
                if not math.isfinite(p):
                    faulty_col, faulty_val = c, raw_v
                    break
            except ValueError:
                faulty_col, faulty_val = c, raw_v
                break
        elif c not in opt_set:
            faulty_col, faulty_val = c, None
            break

    raise FinancialSourceValidationError(
        f"Malformed or missing financial numeric in field {faulty_col!r}: {faulty_val!r}",
        source=source_val,
        sheet=sheet,
        field_name=faulty_col,
        raw_value=faulty_val,
        row_identifier=row_id_val,
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
    """Validate and parse numeric columns across a LazyFrame.

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

        bad_rows = (
            lf.filter(pl.any_horizontal(invalid_checks))
            .select(select_cols)
            .limit(10)
            .collect()
        )
        if bad_rows.height > 0:
            row_dict = bad_rows.row(0, named=True)
            source_val = str(row_dict.get(source_col)) if has_source else None
            row_id_val = str(row_dict.get(row_id_col)) if has_row_id and row_id_col else None
            _diagnose_numeric_failure(
                row_dict, available_cols, opt_set, source_val, sheet, row_id_val
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
