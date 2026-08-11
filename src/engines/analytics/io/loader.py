"""
Loader Module.
Handles loading and strict-typing of DataFrames.
"""

import os
from typing import Any

import polars as pl


def parse_date_col(df: pl.DataFrame) -> pl.DataFrame:
    """Force parse the 'Date' column natively into pl.Date."""
    if "Date" in df.columns and getattr(df.schema["Date"], "base_type", df.schema["Date"]) in [
        pl.Utf8,
        pl.String,
    ]:
        try:
            return df.with_columns(
                pl.col("Date").str.strptime(pl.Date, format="%Y-%m-%d", strict=False)
            )
        except Exception:
            return df.with_columns(pl.col("Date").cast(pl.Date, strict=False))
    return df


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


class TaxDataLoader:
    """Pre-processes all dataframes required for tax evaluation."""

    @classmethod
    def _normalize(
        cls,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame | None,
        df_b: pl.DataFrame | None,
    ) -> tuple[
        pl.DataFrame, pl.DataFrame, pl.DataFrame, dict[str, dict[str, Any]], pl.DataFrame | None
    ]:
        df_p = parse_date_col(df_p)
        df_s = parse_date_col(df_s)
        df_m = parse_date_col(df_m)

        isin_master: dict[str, dict[str, Any]] = (
            {str(row["ISIN"]): row for row in df_i.to_dicts()} if df_i is not None else {}
        )

        if df_b is not None:
            df_b = parse_date_col(df_b)

        for c in ["Quantity", "Price", "Value"]:
            df_p = clean_numeric_col(df_p, c)
        for c in ["Quantity", "Price", "Sell Value"]:
            df_s = clean_numeric_col(df_s, c)
        for c in ["Quantity", "Closing Price", "Buy Value"]:
            df_m = clean_numeric_col(df_m, c)

        return df_p, df_s, df_m, isin_master, df_b

    @classmethod
    def load_all(
        cls, p_path: str, s_path: str, m_path: str, i_path: str | None, b_path: str | None
    ) -> tuple[
        pl.DataFrame, pl.DataFrame, pl.DataFrame, dict[str, dict[str, Any]], pl.DataFrame | None
    ]:

        df_p = pl.read_csv(p_path, infer_schema_length=500_000)
        df_s = pl.read_csv(s_path, infer_schema_length=500_000)
        df_m = pl.read_csv(m_path, infer_schema_length=500_000)

        df_i = pl.read_csv(i_path, infer_schema_length=500_000) if i_path else None

        df_b = None
        if b_path and os.path.exists(b_path):
            df_b = pl.read_csv(b_path, infer_schema_length=500_000)

        return cls._normalize(df_p, df_s, df_m, df_i, df_b)

    @classmethod
    def load_from_dataframes(
        cls,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame | None,
        df_b: pl.DataFrame | None,
    ) -> tuple[
        pl.DataFrame, pl.DataFrame, pl.DataFrame, dict[str, dict[str, Any]], pl.DataFrame | None
    ]:

        return cls._normalize(df_p, df_s, df_m, df_i, df_b)
