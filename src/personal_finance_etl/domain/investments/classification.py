"""Canonical financial classification rules and predicates.

Owns
----
- Pure canonical classification predicates and Polars expressions for market jurisdictions,
  denomination currencies, and financial instrument classes.
- Unified resolution of US and foreign market securities and trade activity without coupling to
  source file or folder taxonomies.

Does not own
-------------
- Physical file ingestion or folder discovery (owned by application.ingestion).
- Source-to-silver tabular transformations (owned by domain.investments.transforms).
- Database DDL schemas or warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar, overload

import polars as pl

DEFAULT_DOMESTIC_CURRENCY: str = "INR_INR"
DEFAULT_DOMESTIC_COUNTRY: str = "India"

DataFrameT = TypeVar("DataFrameT", pl.DataFrame, pl.LazyFrame)


def is_us_market_trade_expr(default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY) -> pl.Expr:
    """Vectorized Polars expression identifying foreign / US market transactions on trade records.

    Evaluates canonical trade classification by matching transactions whose denomination currency
    is not the base domestic currency (e.g. INR_USD, USD, or any foreign currency).

    Parameters
    ----------
    default_currency_id : str, default "INR_INR"
        Base domestic reporting currency identifier.

    Returns
    -------
    pl.Expr
        Boolean Polars expression matching foreign / US market trade records.
    """
    return (
        pl.col("CURRENCY_ID").is_not_null()
        & (pl.col("CURRENCY_ID") != default_currency_id)
        & (pl.col("CURRENCY_ID") != "")
    )


def is_foreign_currency_trade_expr(default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY) -> pl.Expr:
    """Vectorized Polars expression identifying foreign currency trade records requiring FX valuation.

    Parameters
    ----------
    default_currency_id : str, default "INR_INR"
        Base domestic reporting currency identifier.

    Returns
    -------
    pl.Expr
        Boolean Polars expression matching foreign currency trades requiring FX valuation.
    """
    return is_us_market_trade_expr(default_currency_id=default_currency_id)


@overload
def filter_us_market_trades(
    df: pl.DataFrame, default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY
) -> pl.DataFrame: ...


@overload
def filter_us_market_trades(
    df: pl.LazyFrame, default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY
) -> pl.LazyFrame: ...


def filter_us_market_trades(
    df: pl.DataFrame | pl.LazyFrame,
    default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY,
) -> pl.DataFrame | pl.LazyFrame:
    """Filter trades to foreign / US market transactions using canonical classification.

    Parameters
    ----------
    df : pl.DataFrame | pl.LazyFrame
        Trade purchase or sale dataset.
    default_currency_id : str, default "INR_INR"
        Base domestic reporting currency identifier.

    Returns
    -------
    pl.DataFrame | pl.LazyFrame
        Filtered dataset containing only foreign / US market transactions.
    """
    cols = df.collect_schema().names() if isinstance(df, pl.LazyFrame) else df.columns
    if "CURRENCY_ID" not in cols:
        return df.clear()
    return df.filter(is_us_market_trade_expr(default_currency_id=default_currency_id))


def is_us_market_instrument_expr(
    default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY,
    domestic_country: str = DEFAULT_DOMESTIC_COUNTRY,
) -> pl.Expr:
    """Vectorized Polars expression identifying foreign / US market securities on instrument master records.

    Evaluates canonical instrument classification by matching instruments whose denomination currency
    is not domestic, or whose jurisdiction is not domestic (e.g., US, Ireland, etc.).

    Parameters
    ----------
    default_currency_id : str, default "INR_INR"
        Base domestic reporting currency identifier.
    domestic_country : str, default "India"
        Base domestic jurisdiction identifier.

    Returns
    -------
    pl.Expr
        Boolean Polars expression matching foreign / US market instrument master records.
    """
    return (
        pl.col("CURRENCY_ID").is_not_null() & (pl.col("CURRENCY_ID") != default_currency_id)
    ) | (pl.col("COUNTRY").is_not_null() & (pl.col("COUNTRY") != domestic_country))


def resolve_us_market_active_isins(
    df_purchase: pl.DataFrame | pl.LazyFrame,
    df_master: pl.DataFrame | pl.LazyFrame,
    default_currency_id: str = DEFAULT_DOMESTIC_CURRENCY,
    provider_symbols: Mapping[str, str] | None = None,
) -> list[str]:
    """Resolve active US / foreign market ISINs that possess valid trade activity.

    Parameters
    ----------
    df_purchase : pl.DataFrame | pl.LazyFrame
        Investment purchase transactions.
    df_master : pl.DataFrame | pl.LazyFrame
        Harmonized instrument reference master dimension.
    default_currency_id : str, default "INR_INR"
        Base domestic reporting currency identifier.
    provider_symbols : Mapping[str, str] | None, default None
        Optional provider symbol mapping (e.g. ISIN to market ticker). When supplied,
        only ISINs present with non-empty market symbols in the mapping are retained.
        When omitted, candidates are resolved against instrument master records using
        canonical US / foreign instrument classification.

    Returns
    -------
    list[str]
        Deduplicated list of active foreign / US market ISIN strings.
    """
    df_p = df_purchase.collect() if isinstance(df_purchase, pl.LazyFrame) else df_purchase
    df_m = df_master.collect() if isinstance(df_master, pl.LazyFrame) else df_master

    if df_p.is_empty():
        return []

    us_purchases = filter_us_market_trades(df_p, default_currency_id=default_currency_id)
    if us_purchases.is_empty():
        return []

    active_candidate_isins = set(us_purchases["ISIN"].unique().to_list())
    if not active_candidate_isins or df_m.is_empty():
        return []

    if provider_symbols is not None:
        valid_isins = [
            isin
            for isin in active_candidate_isins
            if isin in provider_symbols and str(provider_symbols[isin]).strip() != ""
        ]
        valid_master = df_m.filter(pl.col("ISIN").is_in(valid_isins))
    else:
        valid_master = df_m.filter(
            pl.col("ISIN").is_in(list(active_candidate_isins))
            & is_us_market_instrument_expr(default_currency_id=default_currency_id)
        )
    return valid_master["ISIN"].unique().to_list()
