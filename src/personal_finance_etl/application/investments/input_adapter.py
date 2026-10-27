"""Investment input adapters and per-ISIN payload extraction.

Owns
----
- TaxDataLoader: Pre-processes and normalizes raw tables for the quant run context.
- IsinDataExtractor: Extracts and chronologically sorts purchases, sales, and market observations
  for a single ISIN.
- parse_date_col, clean_numeric_col DataFrame cleaning utilities.

Does not own
-------------
- FIFO lot tracking (owned by domain.investments.lots.fifo).
- Physical warehouse persistence (owned by infrastructure.warehouse).
"""

import os
from typing import Protocol, cast

import polars as pl

from personal_finance_etl.domain.investments.contracts import (
    IsinMasterRecord,
    TradeRecord,
)
from personal_finance_etl.domain.investments.lots.ordering import (
    sort_purchases,
    sort_sales,
)


class IsinContextProtocol(Protocol):
    """Protocol for execution context supplying per-ISIN DataFrames and master metadata."""

    df_p: pl.DataFrame
    df_s: pl.DataFrame
    df_m: pl.DataFrame
    isin_master: dict[str, IsinMasterRecord]


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
        df_fx: pl.DataFrame | None = None,
    ) -> tuple[
        pl.DataFrame,
        pl.DataFrame,
        pl.DataFrame,
        dict[str, IsinMasterRecord],
        pl.DataFrame | None,
        pl.DataFrame | None,
    ]:
        """Normalize and type-align input DataFrames for investment tax evaluation.

        Parameters
        ----------
        df_p : pl.DataFrame
            Purchases DataFrame.
        df_s : pl.DataFrame
            Sales DataFrame.
        df_m : pl.DataFrame
            ISIN master metadata DataFrame.
        df_i : pl.DataFrame | None
            Historical inflation rates DataFrame.
        df_b : pl.DataFrame | None
            Benchmark indices closing prices DataFrame.
        df_fx : pl.DataFrame | None, default None
            Foreign exchange conversion rates DataFrame.

        Returns
        -------
        tuple
            Normalized DataFrames and ISIN master mapping dictionary.
        """
        df_p = parse_date_col(df_p)
        df_s = parse_date_col(df_s)
        df_m = parse_date_col(df_m)

        isin_master: dict[str, IsinMasterRecord] = (
            {str(row["ISIN"]): cast(IsinMasterRecord, row) for row in df_i.to_dicts()}
            if df_i is not None
            else {}
        )

        if df_b is not None:
            df_b = parse_date_col(df_b)

        if df_fx is not None:
            df_fx = parse_date_col(df_fx)

        for c in ["Quantity", "Price", "Value"]:
            df_p = clean_numeric_col(df_p, c)
        for c in ["Quantity", "Sell_Price", "Sell_Value"]:
            df_s = clean_numeric_col(df_s, c)
        for c in ["Quantity", "Closing_Price", "Buy_Value"]:
            df_m = clean_numeric_col(df_m, c)

        return df_p, df_s, df_m, isin_master, df_b, df_fx

    @classmethod
    def load_all(
        cls,
        p_path: str,
        s_path: str,
        m_path: str,
        i_path: str | None,
        b_path: str | None,
        fx_path: str | None = None,
    ) -> tuple[
        pl.DataFrame,
        pl.DataFrame,
        pl.DataFrame,
        dict[str, IsinMasterRecord],
        pl.DataFrame | None,
        pl.DataFrame | None,
    ]:
        """Read CSV files from disk, normalize date and numeric schemas, and return tuple.

        Parameters
        ----------
        p_path : str
            Filepath to purchases CSV.
        s_path : str
            Filepath to sales CSV.
        m_path : str
            Filepath to market data CSV.
        i_path : str | None
            Filepath to ISIN master CSV.
        b_path : str | None
            Filepath to benchmark index CSV.
        fx_path : str | None, optional
            Filepath to currency FX CSV, by default None.

        Returns
        -------
        tuple
            (df_p, df_s, df_m, isin_master_dict, df_b, df_fx) normalized structures.
        """
        df_p = pl.read_csv(p_path, infer_schema_length=500_000)
        df_s = pl.read_csv(s_path, infer_schema_length=500_000)
        df_m = pl.read_csv(m_path, infer_schema_length=500_000)

        df_i = pl.read_csv(i_path, infer_schema_length=500_000) if i_path else None

        df_b = None
        if b_path and os.path.exists(b_path):
            df_b = pl.read_csv(b_path, infer_schema_length=500_000)

        df_fx = None
        if fx_path and os.path.exists(fx_path):
            df_fx = pl.read_csv(fx_path, infer_schema_length=500_000)

        return cls._normalize(df_p, df_s, df_m, df_i, df_b, df_fx)

    @classmethod
    def load_from_dataframes(
        cls,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame | None,
        df_b: pl.DataFrame | None,
        df_fx: pl.DataFrame | None = None,
    ) -> tuple[
        pl.DataFrame,
        pl.DataFrame,
        pl.DataFrame,
        dict[str, IsinMasterRecord],
        pl.DataFrame | None,
        pl.DataFrame | None,
    ]:
        """Normalize in-memory DataFrames, parse date/numeric columns, and build master mapping.

        Parameters
        ----------
        df_p : pl.DataFrame
            Purchases DataFrame.
        df_s : pl.DataFrame
            Sales DataFrame.
        df_m : pl.DataFrame
            Market data DataFrame.
        df_i : pl.DataFrame | None
            ISIN master DataFrame.
        df_b : pl.DataFrame | None
            Benchmark index DataFrame.
        df_fx : pl.DataFrame | None, optional
            Currency FX DataFrame, by default None.

        Returns
        -------
        tuple
            (df_p, df_s, df_m, isin_master_dict, df_b, df_fx) normalized structures.
        """
        return cls._normalize(df_p, df_s, df_m, df_i, df_b, df_fx)


class IsinDataExtractor:
    """Adapts context tables into ordered, filtered per-ISIN input lists."""

    @staticmethod
    def extract(
        ctx: IsinContextProtocol, isin: str
    ) -> tuple[
        list[TradeRecord],
        list[TradeRecord],
        list[TradeRecord],
        IsinMasterRecord,
    ]:
        """Extract chronologically sorted purchases, sales, and market records for one ISIN.

        Parameters
        ----------
        ctx : IsinContextProtocol
            Context supplying raw purchases, sales, market, and master tables.
        isin : str
            Target instrument identifier.

        Returns
        -------
        tuple
            (sorted_purchases, sorted_sales, aggregated_market_records, master_metadata_record).
        """
        p_inst_raw = cast("list[TradeRecord]", ctx.df_p.filter(pl.col("ISIN") == isin).to_dicts())
        p_inst = sort_purchases(p_inst_raw)

        s_inst_raw = cast("list[TradeRecord]", ctx.df_s.filter(pl.col("ISIN") == isin).to_dicts())
        s_inst = sort_sales(s_inst_raw)

        m_inst = cast(
            "list[TradeRecord]",
            ctx.df_m.filter(pl.col("ISIN") == isin)
            .sort("Date")
            .group_by("Date", maintain_order=True)
            .agg(
                [
                    pl.col("Quantity").sum().alias("Quantity"),
                    pl.col("Closing_Price").last().alias("Closing_Price"),
                    pl.col("Buy_Value").sum().alias("Buy_Value"),
                ]
            )
            .to_dicts(),
        )
        master_row: IsinMasterRecord = ctx.isin_master.get(isin, {})
        return p_inst, s_inst, m_inst, master_row


__all__ = [
    "IsinContextProtocol",
    "IsinDataExtractor",
    "TaxDataLoader",
    "clean_numeric_col",
    "parse_date_col",
]
