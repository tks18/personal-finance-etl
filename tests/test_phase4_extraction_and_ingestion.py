# pyright: reportPrivateUsage=false
"""Unit and integration tests for Phase 4: Extraction and Ingestion.

Owns
----
- Verification of 100% object identity equivalence ('is') between legacy extract/pipeline modules and canonical targets.
- Verification of statement locator file discovery and categorization heuristics.
- Verification of in-memory CSV extraction adapters and schema tagging.
- Verification of external SQLite household database base table extraction.
- Verification of market data provider delta caching logic.
- Verification of asset ingestion strategy protocol compliance.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any
from unittest.mock import MagicMock

# Canonical imports
from personal_finance_etl.application.ingestion.asset_strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)
from personal_finance_etl.application.ingestion.coordinator import (
    DataExtractor,
)
from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
    CurrencyPipeline,
    USMarketPipeline,
)

# Legacy imports
from personal_finance_etl.backend.extract import (
    benchmark_extractor as legacy_benchmark_ext,
)
from personal_finance_etl.backend.extract import (
    csv_extractor as legacy_csv,
)
from personal_finance_etl.backend.extract import (
    currency_extractor as legacy_currency_ext,
)
from personal_finance_etl.backend.extract import (
    excel_extractor as legacy_excel,
)
from personal_finance_etl.backend.extract import (
    sqlite_extractor as legacy_sqlite,
)
from personal_finance_etl.backend.extract import (
    statement_locator as legacy_locator,
)
from personal_finance_etl.backend.extract import (
    us_market_extractor as legacy_us_market_ext,
)
from personal_finance_etl.backend.pipeline import (
    benchmark_pipeline as legacy_benchmark_pipe,
)
from personal_finance_etl.backend.pipeline import (
    currency_pipeline as legacy_currency_pipe,
)
from personal_finance_etl.backend.pipeline import (
    strategies as legacy_strategies,
)
from personal_finance_etl.backend.pipeline import (
    us_market_pipeline as legacy_us_market_pipe,
)
from personal_finance_etl.backend.pipeline.core import extractor as legacy_core_ext
from personal_finance_etl.contracts.extraction import ExtractorEntityStatus
from personal_finance_etl.infrastructure.providers.files.csv import (
    extract_benchmark_master_raw,
    extract_currency_mapping_raw,
    extract_macro_parameters_raw,
    extract_opening_balances_raw,
    extract_stg_benchmark_mapping,
    extract_stg_mf_isin_mapping,
)
from personal_finance_etl.infrastructure.providers.files.excel import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
    extract_us_stock_transactions_raw,
)
from personal_finance_etl.infrastructure.providers.files.locator import (
    categorize_statement_files,
)
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


def test_phase4_legacy_identity_equivalence() -> None:
    """Verify that every deactivated legacy module delegates to canonical targets with identity 'is'."""
    # File Providers
    assert legacy_locator.categorize_statement_files is categorize_statement_files
    assert legacy_csv.extract_stg_mf_isin_mapping is extract_stg_mf_isin_mapping
    assert legacy_csv.extract_currency_mapping_raw is extract_currency_mapping_raw
    assert legacy_csv.extract_stg_benchmark_mapping is extract_stg_benchmark_mapping
    assert legacy_csv.extract_benchmark_master_raw is extract_benchmark_master_raw
    assert legacy_csv.extract_macro_parameters_raw is extract_macro_parameters_raw
    assert legacy_csv.extract_opening_balances_raw is extract_opening_balances_raw
    assert legacy_excel.extract_mf_market_data_raw is extract_mf_market_data_raw
    assert legacy_excel.extract_mf_transactions_raw is extract_mf_transactions_raw
    assert legacy_excel.extract_stock_market_data_raw is extract_stock_market_data_raw
    assert legacy_excel.extract_stock_transactions_raw is extract_stock_transactions_raw
    assert legacy_excel.extract_us_stock_transactions_raw is extract_us_stock_transactions_raw
    assert legacy_sqlite.SQLiteExtractor is SQLiteExtractor

    # Market Providers
    assert legacy_currency_ext.CurrencyExtractor is CurrencyExtractor
    assert legacy_benchmark_ext.BenchmarkExtractor is BenchmarkExtractor
    assert legacy_us_market_ext.USMarketExtractor is USMarketExtractor

    # Ingestion Coordinators & Strategies
    assert legacy_core_ext.DataExtractor is DataExtractor
    assert legacy_strategies.AssetPipeline is AssetPipeline
    assert legacy_strategies.StockPipeline is StockPipeline
    assert legacy_strategies.USStockPipeline is USStockPipeline
    assert legacy_strategies.MutualFundPipeline is MutualFundPipeline
    assert legacy_currency_pipe.CurrencyPipeline is CurrencyPipeline
    assert legacy_benchmark_pipe.BenchmarkPipeline is BenchmarkPipeline
    assert legacy_us_market_pipe.USMarketPipeline is USMarketPipeline


def test_statement_locator_categorization(tmp_path: Any) -> None:
    """Verify recursive scanning and categorization of statement files."""
    # Create directory structure with mock files
    (tmp_path / "Stock PL Statements").mkdir(parents=True)
    (tmp_path / "Stock PL Statements" / "pl_2026.xlsx").write_text("dummy")

    (tmp_path / "Mutual Funds - Holdings").mkdir(parents=True)
    (tmp_path / "Mutual Funds - Holdings" / "mf_holdings.xlsx").write_text("dummy")

    (tmp_path / "Stock - Orders").mkdir(parents=True)
    (tmp_path / "Stock - Orders" / "orders.xlsx").write_text("dummy")

    (tmp_path / "Mutual Funds - Orders").mkdir(parents=True)
    (tmp_path / "Mutual Funds - Orders" / "mf_orders.xlsx").write_text("dummy")

    (tmp_path / "IND Money (US Stocks)" / "Transaction Reports").mkdir(parents=True)
    (tmp_path / "IND Money (US Stocks)" / "Transaction Reports" / "us_tx.xlsx").write_text("dummy")

    # Temporary lock file that should be ignored
    (tmp_path / "Stock - Orders" / "~$lock.xlsx").write_text("temp")

    cats = categorize_statement_files(str(tmp_path), strict=True)
    assert len(cats["stock_pl"]) == 1
    assert len(cats["mf_holdings"]) == 1
    assert len(cats["stock_orders"]) == 1
    assert len(cats["mf_orders"]) == 1
    assert len(cats["us_stock_transactions"]) == 1


def test_csv_extraction_adapters() -> None:
    """Verify parsing and schema assignment for CSV evidence assets."""
    # MF ISIN Mapping
    raw_isin = b"INSTRUMENT_NAME,ISIN\nTest Growth Fund,INF123456789\n"
    lf_isin = extract_stg_mf_isin_mapping("isin.csv", "/data", raw_isin)
    df_isin = lf_isin.collect()
    assert df_isin.height == 1
    assert df_isin["ISIN"][0] == "INF123456789"
    assert df_isin["__file_name__"][0] == "isin.csv"

    # Currency Mapping
    raw_curr = b"UID,Currency_Code,Target_Currency_Code,yF_Ticker,Currency_Name,Is_Active\nUSD,USD,INR,USDINR=X,US Dollar,true\n"
    lf_curr = extract_currency_mapping_raw("curr.csv", "/data", raw_curr)
    df_curr = lf_curr.collect()
    assert df_curr.height == 1
    assert df_curr["Currency_Code"][0] == "USD"
    assert df_curr["Is_Active"][0] is True

    # Benchmark Master
    raw_bench = b"ID,Benchmark_Name,yF_Ticker,Currency\nNIFTY50,Nifty 50,^NSEI,INR\n"
    lf_bench = extract_benchmark_master_raw("bench.csv", "/data", raw_bench)
    df_bench = lf_bench.collect()
    assert df_bench.height == 1
    assert df_bench["yF_Ticker"][0] == "^NSEI"


def test_sqlite_extractor_base_tables(tmp_path: Any) -> None:
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
    zcat, agroup, assets, curr, inout = extractor.extract_base_tables(
        "test_household.sqlite", str(tmp_path), raw_bytes
    )

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
