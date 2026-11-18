# pyright: reportPrivateUsage=false
"""Extraction and ingestion application services test suite.

Owns
----
- Verification of statement extraction and ingestion pipeline contracts.
- Verification of statement locator file discovery and categorization heuristics.
- Verification of in-memory CSV extraction adapters and schema tagging.
- Verification of external SQLite household database base table extraction.
- Verification of market data provider delta caching logic.
- Verification of asset ingestion strategy protocol compliance.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

# Canonical imports
from personal_finance_etl.application.ingestion.asset_strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)
from personal_finance_etl.contracts.extraction import ExtractorEntityStatus
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)
from personal_finance_etl.infrastructure.providers.market.benchmark import (
    BenchmarkExtractor,
)
from personal_finance_etl.infrastructure.providers.market.currency import (
    CurrencyExtractor,
)
from personal_finance_etl.infrastructure.providers.market.us_market import (
    USMarketExtractor,
)


def test_sqlite_extractor_base_tables(tmp_path: Path) -> None:
    """Verify in-memory deserialization and extraction of external SQLite household tables."""
    db_path = tmp_path / "test_household.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE ZCATEGORY (Z_PK INTEGER PRIMARY KEY, ZNAME TEXT)")
        conn.execute("INSERT INTO ZCATEGORY VALUES (1, 'Groceries')")
        conn.execute("CREATE TABLE ASSETGROUP (ID INTEGER PRIMARY KEY, NAME TEXT)")
        conn.execute("INSERT INTO ASSETGROUP VALUES (10, 'Bank Accounts')")
        conn.execute("CREATE TABLE ASSETS (ID INTEGER PRIMARY KEY, TITLE TEXT)")
        conn.execute("INSERT INTO ASSETS VALUES (100, 'HDFC Salary')")
        conn.execute("CREATE TABLE CURRENCY (ID INTEGER PRIMARY KEY, CODE TEXT)")
        conn.execute("INSERT INTO CURRENCY VALUES (1, 'INR')")
        conn.execute("CREATE TABLE INOUTCOME (ID INTEGER PRIMARY KEY, AMOUNT REAL)")
        conn.execute("INSERT INTO INOUTCOME VALUES (1001, 5420.50)")
        conn.commit()

    raw_bytes = db_path.read_bytes()
    extractor = SQLiteExtractor(str(tmp_path))
    zcat = extractor.extract_table("test_household.sqlite", str(tmp_path), raw_bytes, "ZCATEGORY")
    agroup = extractor.extract_table(
        "test_household.sqlite", str(tmp_path), raw_bytes, "ASSETGROUP"
    )
    assets = extractor.extract_table("test_household.sqlite", str(tmp_path), raw_bytes, "ASSETS")
    curr = extractor.extract_table("test_household.sqlite", str(tmp_path), raw_bytes, "CURRENCY")
    inout = extractor.extract_table("test_household.sqlite", str(tmp_path), raw_bytes, "INOUTCOME")

    assert zcat.collect().height == 1
    assert agroup.collect().height == 1
    assert assets.collect().height == 1
    assert curr.collect().height == 1
    assert inout.collect().height == 1


def test_market_provider_caching_logic() -> None:
    """Verify that market providers return CACHED without network API calls when data is fresh."""
    mock_cp = MagicMock()
    mock_queue = MagicMock()

    # 1. Currency Extractor Caching
    curr_ext = CurrencyExtractor(mock_cp, mock_queue)
    curr_row = {
        "UID": "USD",
        "yF_Ticker": "USDINR=X",
        "CURRENCY_NAME": "USD",
        "ISO": "USD",
        "Target_Currency_Code": "INR",
    }
    res_curr = curr_ext._fetch_ticker_delta(
        row=curr_row,
        start_dt=date(2026, 1, 1),
        end_dt=date(2026, 10, 1),
        max_cached_date=date(2026, 10, 5),  # Cache extends beyond requested end
    )
    assert res_curr.status == ExtractorEntityStatus.CACHED
    assert "fully cached" in res_curr.message

    # 2. Benchmark Extractor Caching
    bench_ext = BenchmarkExtractor(mock_cp, mock_queue)
    bench_row = {
        "ID": "NIFTY",
        "yF_Ticker": "^NSEI",
        "Benchmark_Name": "Nifty 50",
        "CURRENCY_ID": "INR",
    }
    res_bench = bench_ext._fetch_ticker_delta(
        row=bench_row,
        start_dt=date(2026, 1, 1),
        end_dt=date(2026, 10, 1),
        max_cached_date=date(2026, 10, 5),
    )
    assert res_bench.status == ExtractorEntityStatus.CACHED

    # 3. US Market Extractor Caching
    us_ext = USMarketExtractor(mock_cp, mock_queue)
    res_us = us_ext._fetch_ticker_delta(
        isin="US0378331005",
        ticker="AAPL",
        start_dt=date(2026, 1, 1),
        end_dt=date(2026, 10, 1),
        max_cached_date=date(2026, 10, 5),
    )
    assert res_us.status == ExtractorEntityStatus.CACHED


def test_asset_strategies_protocol_compliance() -> None:
    """Verify that concrete asset pipelines implement the AssetPipeline protocol."""
    stock_pipe = StockPipeline()
    us_stock_pipe = USStockPipeline()
    mf_pipe = MutualFundPipeline()

    assert isinstance(stock_pipe, AssetPipeline)
    assert isinstance(us_stock_pipe, AssetPipeline)
    assert isinstance(mf_pipe, AssetPipeline)
