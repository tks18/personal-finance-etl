"""Deterministic fingerprinting and serialization for Monte Carlo simulation provenance.

Owns
----
- Serializing heterogeneous simulation assumption models into deterministic JSON representations.
- Computing SHA-256 digests over Polars DataFrame/LazyFrame tabular simulation inputs and outputs.
- Deriving model fingerprints from capital market assumptions and FIRE rules.
- Resolving effective simulation as-of evaluation dates from tabular data columns.

Does not own
-------------
- Database persistence or run status tracking (owned by run_repository.py).
- Numerical Monte Carlo simulation kernel execution (owned by domain.fire.simulation).
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import cast

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules

__all__ = [
    "compute_model_fingerprint",
    "fingerprint_dataframe",
    "json_safe",
    "resolve_input_as_of_date",
]


def json_safe(value: object) -> object:
    """Recursively serialize objects to JSON-compatible data structures.

    Parameters
    ----------
    value : object
        Arbitrary Python object to convert.

    Returns
    -------
    object
        JSON-serializable representation with standardized stringification.
    """
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {str(key): json_safe(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        items = cast(list[object] | tuple[object, ...], value)
        return [json_safe(item) for item in items]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def fingerprint_dataframe(input_df: pl.DataFrame | pl.LazyFrame | None) -> str:
    """Compute deterministic SHA-256 fingerprint of a tabular DataFrame.

    Parameters
    ----------
    input_df : pl.DataFrame | pl.LazyFrame | None
        Input DataFrame or LazyFrame to evaluate.

    Returns
    -------
    str
        Hexadecimal SHA-256 digest of column headers and sorted row data.

    Raises
    ------
    TypeError
        If input does not expose Polars-compatible columns and to_dicts().
    """
    if input_df is None:
        return "no-input"
    # Materialization Boundary: FORENSIC_SERIALIZATION
    # Materialize lazyframe input if necessary to compute canonical row-level SHA-256 digest
    df = input_df.collect() if isinstance(input_df, pl.LazyFrame) else input_df
    if not hasattr(df, "to_dicts") or not hasattr(df, "columns"):
        raise TypeError("Simulation input must expose Polars-compatible columns and to_dicts().")
    columns: list[str] = [str(column) for column in df.columns]
    rows = cast(list[dict[str, object]], df.to_dicts())
    digest = hashlib.sha256()
    header = json.dumps(columns, ensure_ascii=False, separators=(",", ":"))
    digest.update(header.encode("utf-8"))
    digest.update(b"\n")
    for row in rows:
        safe_row = json_safe(row)
        encoded = json.dumps(
            safe_row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        digest.update(encoded.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def compute_model_fingerprint(rules: FinancialRules) -> str:
    """Derive deterministic SHA-256 digest of simulation assumption models.

    Parameters
    ----------
    rules : FinancialRules
        Financial configuration rules containing simulation assumptions.

    Returns
    -------
    str
        Hex digest representing model fingerprint.
    """
    combined_rules = {
        "monte_carlo": rules.assumptions.monte_carlo.model_dump(),
        "fire": rules.assumptions.fire.model_dump(),
        "cma": rules.assumptions.cma.model_dump(),
    }
    return hashlib.sha256(
        json.dumps(
            json_safe(combined_rules),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def resolve_input_as_of_date(
    input_df: pl.DataFrame | pl.LazyFrame | None,
    input_as_of_date: date | str | None,
) -> str | None:
    """Infer or format as-of date string from input DataFrame columns.

    Parameters
    ----------
    input_df : pl.DataFrame | pl.LazyFrame | None
        Input dataframe evaluated for date timestamps.
    input_as_of_date : date | str | None
        Explicit date override, if available.

    Returns
    -------
    str | None
        Resolved ISO date string or None.
    """
    if input_as_of_date is not None:
        if isinstance(input_as_of_date, datetime):
            return input_as_of_date.date().isoformat()
        if isinstance(input_as_of_date, date):
            return input_as_of_date.isoformat()
        return str(input_as_of_date)

    if not isinstance(input_df, pl.DataFrame) or input_df.height == 0:
        return None

    candidate_cols = [
        "MONTH_START_DATE",
        "MONTH_END_DATE",
        "Date",
        "DATE",
        "as_of_date",
        "Closing_Date",
    ]
    for col in candidate_cols:
        if col in input_df.columns:
            try:
                max_val = input_df[col].max()
                if max_val is not None:
                    if isinstance(max_val, datetime):
                        return max_val.date().isoformat()
                    if isinstance(max_val, date):
                        return max_val.isoformat()
                    return str(max_val).split("T", maxsplit=1)[0].split(" ", maxsplit=1)[0]
            except (KeyError, TypeError, ValueError, AttributeError):
                pass
    return None
