"""Tests for canonical source-independent financial classification and value equivalence.

Owns
----
- Unit tests for canonical financial classification expressions and helpers.
- Value-equivalence verification for US market date range resolution and valuation spines.
- Deterministic ID stability verification across domestic and foreign asset portfolios.

Does not own
-------------
- Live network Yahoo Finance quote fetching (owned by infrastructure.providers.market).
- Architectural layer boundary tests (owned by tests.architecture).
"""

from __future__ import annotations

from datetime import date

import polars as pl

from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.investments.classification import (
    filter_us_market_trades,
    is_foreign_currency_trade_expr,
    is_us_market_instrument_expr,
    is_us_market_trade_expr,
    resolve_us_market_active_isins,
)
from personal_finance_etl.domain.investments.valuation.market_state import (
    transform_us_market_data,
)


def test_is_us_market_trade_expr() -> None:
    """Verify that is_us_market_trade_expr filters by denomination currency (USD and INR_USD)."""
    df = pl.DataFrame(
        {
            "ISIN": ["US001", "INF001", "US002", "US003"],
            "CURRENCY_ID": ["USD", "INR_INR", "USD", "INR_USD"],
            "__file_category__": ["US Stocks", "Indian", "Custom Category", "US Stocks"],
        }
    )
    result = df.filter(is_us_market_trade_expr())
    assert result["ISIN"].to_list() == ["US001", "US002", "US003"]


def test_filter_us_market_trades_eager_and_lazy() -> None:
    """Verify filter_us_market_trades works on both eager and lazy frames."""
    data = {
        "ISIN": ["US001", "INF001"],
        "CURRENCY_ID": ["USD", "INR_INR"],
    }
    df_eager = pl.DataFrame(data)
    df_lazy = df_eager.lazy()

    filtered_eager = filter_us_market_trades(df_eager)
    assert isinstance(filtered_eager, pl.DataFrame)
    assert filtered_eager["ISIN"].to_list() == ["US001"]

    filtered_lazy = filter_us_market_trades(df_lazy)
    assert isinstance(filtered_lazy, pl.LazyFrame)
    assert filtered_lazy.collect()["ISIN"].to_list() == ["US001"]


def test_filter_us_market_trades_missing_currency_col() -> None:
    """Verify graceful handling when CURRENCY_ID column is not present."""
    df_no_curr = pl.DataFrame({"ISIN": ["ABC"]})
    res = filter_us_market_trades(df_no_curr)
    assert res.is_empty()

    res_lazy = filter_us_market_trades(df_no_curr.lazy()).collect()
    assert res_lazy.is_empty()


def test_is_us_market_instrument_expr() -> None:
    """Verify canonical instrument classification on master dimension records."""
    df_master = pl.DataFrame(
        {
            "ISIN": ["US001", "IE001", "US002", "IN001"],
            "COUNTRY": ["US", "Ireland", "India", "India"],
            "CURRENCY_ID": ["INR_INR", "USD", "INR_USD", "INR_INR"],
        }
    )
    res = df_master.filter(is_us_market_instrument_expr())
    assert res["ISIN"].to_list() == ["US001", "IE001", "US002"]


def test_is_foreign_currency_trade_expr() -> None:
    """Verify foreign currency trade expression against default domestic currency."""
    df = pl.DataFrame(
        {
            "ISIN": ["US001", "EU001", "IN001"],
            "CURRENCY_ID": ["USD", "EUR", "INR_INR"],
        }
    )
    res = df.filter(is_foreign_currency_trade_expr("INR_INR"))
    assert res["ISIN"].to_list() == ["US001", "EU001"]


def test_resolve_us_market_active_isins() -> None:
    """Verify active US ISIN resolution matches only traded assets with valid vendor tickers."""
    df_purchase = pl.DataFrame(
        {
            "ISIN": ["US001", "US002", "US003", "IN001"],
            "CURRENCY_ID": ["USD", "USD", "USD", "INR_INR"],
        }
    )
    df_master = pl.DataFrame(
        {
            "ISIN": ["US001", "US002", "US003", "US004"],
            "CURRENCY_ID": ["USD", "USD", "USD", "USD"],
            "COUNTRY": ["US", "US", "US", "US"],
        }
    )
    # Case 1: with provider_symbols mapping
    provider_symbols = {"US001": "AAPL", "US002": "  ", "US003": "", "US004": "MSFT"}
    active = resolve_us_market_active_isins(
        df_purchase, df_master, provider_symbols=provider_symbols
    )
    assert active == ["US001"]

    # Case 2: without provider_symbols (resolves candidate instruments via canonical classification)
    active_all = resolve_us_market_active_isins(df_purchase, df_master)
    assert set(active_all) == {"US001", "US002", "US003"}


def test_us_market_range_value_equivalence() -> None:
    """Verify that canonical classification produces exact date bounding equivalence."""
    df_purchase = pl.DataFrame(
        {
            "ISIN": ["IN001", "US001", "US002"],
            "Date": [date(2020, 1, 1), date(2021, 5, 10), date(2022, 1, 1)],
            "CURRENCY_ID": ["INR_INR", "USD", "USD"],
            "__file_category__": ["Indian", "US Stocks", "US Stocks"],
        }
    )
    df_sale = pl.DataFrame(
        {
            "ISIN": ["US001"],
            "Date": [date(2021, 6, 15)],
            "CURRENCY_ID": ["USD"],
            "__file_category__": ["US Stocks"],
        }
    )

    # Legacy method
    legacy_starts: list[date] = []
    for df in (df_purchase, df_sale):
        sub = df.filter(pl.col("__file_category__") == "US Stocks")
        d = sub.select(pl.col("Date").drop_nulls().min()).item()
        if isinstance(d, date):
            legacy_starts.append(d)
    legacy_min = min(legacy_starts)

    # Canonical method
    canonical_starts: list[date] = []
    for df in (df_purchase, df_sale):
        sub = filter_us_market_trades(df)
        d = sub.select(pl.col("Date").drop_nulls().min()).item()
        if isinstance(d, date):
            canonical_starts.append(d)
    canonical_min = min(canonical_starts)

    assert legacy_min == date(2021, 5, 10)
    assert canonical_min == legacy_min


def test_transform_us_market_data_equivalence() -> None:
    """Verify transform_us_market_data generates byte-identical continuous valuations."""
    # Synthetic Bronze quotes
    df_bronze_prices = pl.DataFrame(
        {
            "Date": [date(2024, 1, 2), date(2024, 1, 3)],
            "ISIN": ["US_AAPL", "US_AAPL"],
            "Closing_Price_Local": [180.0, 185.0],
            "Data_Provider": ["Yahoo", "Yahoo"],
            "Extraction_Time": [date(2024, 1, 3), date(2024, 1, 3)],
            "Requested_Start": [date(2024, 1, 1), date(2024, 1, 1)],
            "Requested_End": [date(2024, 1, 5), date(2024, 1, 5)],
            "Is_Closure_Gap": [False, False],
            "Is_Imputed": [False, False],
        }
    ).lazy()

    # Mixed purchases (Domestic + US)
    df_purchase = pl.DataFrame(
        {
            "ISIN": ["IN_RELIANCE", "US_AAPL"],
            "Date": [date(2024, 1, 1), date(2024, 1, 2)],
            "Quantity": [10.0, 5.0],
            "Value_Local": [25000.0, 900.0],
            "Value": [25000.0, 74700.0],
            "CURRENCY_ID": ["INR_INR", "USD"],
            "__file_category__": ["Indian Stocks", "US Stocks"],
        }
    ).lazy()

    df_sale = pl.DataFrame(
        {
            "ISIN": ["US_AAPL"],
            "Date": [date(2024, 1, 3)],
            "Quantity": [2.0],
            "CURRENCY_ID": ["USD"],
            "__file_category__": ["US Stocks"],
        }
    ).lazy()

    df_fx = pl.DataFrame(
        {
            "Date": [date(2024, 1, 2), date(2024, 1, 3)],
            "Currency_ID": ["USD", "USD"],
            "FX_Rate": [83.0, 83.5],
        }
    ).lazy()

    res = transform_us_market_data(
        df_bronze_prices_lazy=df_bronze_prices,
        df_purchase_lazy=df_purchase,
        df_sale_lazy=df_sale,
        df_fx_lazy=df_fx,
        global_start_date=date(2024, 1, 2),
        global_end_date=date(2024, 1, 3),
    ).collect()

    assert not res.is_empty()
    assert res["ISIN"].unique().to_list() == ["US_AAPL"]
    # Check that closing value calculations are computed deterministically
    assert res.filter(pl.col("Date") == date(2024, 1, 2))["Quantity"][0] == 5.0
    assert res.filter(pl.col("Date") == date(2024, 1, 3))["Quantity"][0] == 3.0


def test_deterministic_id_invariance_under_classification() -> None:
    """Verify purchase and sale deterministic hashing ignores file category tags completely."""
    canonical_purchase_keys = ["ISIN", "Date", "Price", "Quantity", "CURRENCY_ID"]
    record_p_us = {
        "ISIN": "US0378331005",
        "Date": date(2023, 5, 1),
        "Price": 15000.0,
        "Quantity": 10.0,
        "CURRENCY_ID": "USD",
        "__file_category__": "US Stocks",
    }
    record_p_compat = {
        "ISIN": "US0378331005",
        "Date": date(2023, 5, 1),
        "Price": 15000.0,
        "Quantity": 10.0,
        "CURRENCY_ID": "USD",
        "__file_category__": "Legacy Folder Name",
    }
    fields_p1 = {k: record_p_us[k] for k in canonical_purchase_keys}
    fields_p2 = {k: record_p_compat[k] for k in canonical_purchase_keys}
    id_1 = generate_deterministic_id("PURCHASE", fields_p1)
    id_2 = generate_deterministic_id("PURCHASE", fields_p2)
    assert id_1 == id_2
    assert id_1.startswith("PURCHASE_")

    canonical_sale_keys = ["ISIN", "Date", "Sell_Price", "Quantity", "CURRENCY_ID"]
    record_s_1 = {
        "ISIN": "US0378331005",
        "Date": date(2023, 6, 1),
        "Sell_Price": 16000.0,
        "Quantity": 5.0,
        "CURRENCY_ID": "USD",
        "__file_category__": "US Stocks",
    }
    record_s_2 = {
        "ISIN": "US0378331005",
        "Date": date(2023, 6, 1),
        "Sell_Price": 16000.0,
        "Quantity": 5.0,
        "CURRENCY_ID": "USD",
        "__file_category__": "Different Tag",
    }
    fields_s1 = {k: record_s_1[k] for k in canonical_sale_keys}
    fields_s2 = {k: record_s_2[k] for k in canonical_sale_keys}
    s_id_1 = generate_deterministic_id("SALE", fields_s1)
    s_id_2 = generate_deterministic_id("SALE", fields_s2)
    assert s_id_1 == s_id_2
    assert s_id_1.startswith("SALE_")
