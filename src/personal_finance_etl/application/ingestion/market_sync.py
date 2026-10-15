"""Market data synchronization and layer publication coordination.

Owns
----
- Coordinating historical currency FX delta ingestion and Bronze/Silver publication.
- Coordinating historical benchmark index delta ingestion and Bronze/Silver publication.
- Coordinating US stock market price delta ingestion and Bronze/Silver publication.
- Logging provider extraction provenance events into the Control Plane audit log.
- Enforcing completeness assertion gates across external market feeds.

Does not own
-------------
- Low-level Yahoo Finance HTTP/API communication (owned by infrastructure.providers.market).
- Currency normalization formulas or valuation logic (owned by domain.market and domain.investments).
- Parquet storage files or DuckDB transaction commit mechanics (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import datetime
import os
from datetime import date

import polars as pl

from personal_finance_etl.backend.transform.benchmark_transformer import (
    BenchmarkTransformer,
)
from personal_finance_etl.backend.transform.currency_transformer import (
    transform_currency_fx_rates,
)
from personal_finance_etl.backend.transform.us_stocks_transformer import (
    transform_us_market_data,
)
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.logging import logger
from personal_finance_etl.infrastructure.providers.market.benchmark import (
    BenchmarkExtractor,
)
from personal_finance_etl.infrastructure.providers.market.currency import (
    CurrencyExtractor,
)
from personal_finance_etl.infrastructure.providers.market.us_market import (
    USMarketExtractor,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer

__all__ = [
    "BenchmarkPipeline",
    "CurrencyPipeline",
    "USMarketPipeline",
]


class CurrencyPipeline:
    """Synchronizes external daily Currency FX rates into Bronze and Silver layers."""

    def __init__(
        self, cp: ControlPlane, bronze: BronzeLayer, status_queue: StatusQueue, max_workers: int = 8
    ) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.max_workers = max_workers

    def run(
        self,
        df_currency: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Run the Currency FX pipeline."""
        logger.info("Phase 3.6: Dynamic Currency FX Extraction & Transformation...")
        logger.info(f"  -> Target Global Range: {global_start_date} to {global_end_date}")

        self.status_queue.put(
            EngineStatusMessage(
                msg="Starting Currency FX Pipeline...",
                data=None,
                progress=0.05,
                level=LogLevel.STEP,
            )
        )

        # 1. Load Bronze Cache
        df_bronze_cached = self.bronze.get_table("r_Currency_FX_Data")
        if df_bronze_cached.is_empty():
            logger.debug(
                "[ENGINE:CURRENCY] Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
            df_bronze_cached = pl.DataFrame(
                schema={
                    "Date": pl.Date,
                    "Currency_ID": pl.String,
                    "Currency_Code": pl.String,
                    "Target_Currency_Code": pl.String,
                    "yF_Ticker": pl.String,
                    "FX_Rate": pl.Float64,
                    "Data_Provider": pl.String,
                    "Extraction_Time": pl.String,
                    "Requested_Start": pl.Date,
                    "Requested_End": pl.Date,
                    "Is_Closure_Gap": pl.Boolean,
                }
            )
        else:
            cached_min = df_bronze_cached.select(pl.min("Date")).item()
            cached_max = df_bronze_cached.select(pl.max("Date")).item()
            logger.debug(
                f"[ENGINE:CURRENCY] Bronze Cache: FOUND {df_bronze_cached.height} rows ({cached_min} to {cached_max})."
            )

        # 2. Extract Delta
        extractor = CurrencyExtractor(self.cp, self.status_queue, self.max_workers)
        batch_res = extractor.extract_currency_delta(
            df_currency, global_start_date, global_end_date, df_bronze_cached
        )
        if self.cp.active_run_id:
            self.cp.runs.log_provider_requests(
                self.cp.active_run_id, batch_res.to_provider_requests()
            )
        batch_res.assert_complete("Currency Extractor")
        df_delta, new_files = batch_res.combined_frame, batch_res.injected_files

        self.status_queue.put(
            EngineStatusMessage(
                msg="Upserting Delta into Bronze Currency Lake...",
                data=None,
                progress=0.6,
                level=LogLevel.INFO,
            )
        )

        # 3. Upsert to Bronze
        if not df_delta.is_empty():
            logger.debug("[ENGINE:CURRENCY] Upserting new Parquet chunks to Bronze...")
            row_counts = self.bronze.upsert_table(
                df=df_delta,
                table_name="bronze.r_Currency_FX_Data",
                actionable_files=new_files,
                full_replace=False,
            )
            for filepath in new_files:
                filename = os.path.basename(filepath)
                count = row_counts.get(filename, 0)
                self.bronze.cp.artifacts.mark_synced([filepath])
                self.bronze.meta_layer.register_file(
                    filepath, "currency_history", count, self.bronze.cp
                )

        df_bronze_full = self.bronze.get_table("r_Currency_FX_Data")
        if df_bronze_full.is_empty():
            df_bronze_full_lazy = pl.LazyFrame(
                schema={
                    "Date": pl.Date,
                    "Currency_ID": pl.String,
                    "Currency_Code": pl.String,
                    "Target_Currency_Code": pl.String,
                    "yF_Ticker": pl.String,
                    "FX_Rate": pl.Float64,
                    "Data_Provider": pl.String,
                    "Extraction_Time": pl.String,
                    "Requested_Start": pl.Date,
                    "Requested_End": pl.Date,
                    "Is_Closure_Gap": pl.Boolean,
                }
            )
        else:
            df_bronze_full_lazy = df_bronze_full.lazy()

        # 4. Transform to Silver (Continuous Series)
        self.status_queue.put(
            EngineStatusMessage(
                msg="Transforming continuous Currency FX series...",
                data=None,
                progress=0.8,
                level=LogLevel.INFO,
            )
        )

        df_silver_lazy = transform_currency_fx_rates(
            df_bronze_full_lazy, df_currency.lazy(), global_start_date, global_end_date
        )

        df_silver = df_silver_lazy.collect(engine="streaming")

        self.status_queue.put(
            EngineStatusMessage(
                msg="Currency FX Pipeline Completed.",
                data=None,
                progress=1.0,
                level=LogLevel.SUCCESS,
            )
        )

        return df_silver


class BenchmarkPipeline:
    """Synchronizes external daily Benchmark index series into Bronze and Silver layers."""

    def __init__(self, cp: ControlPlane, bronze: BronzeLayer, status_queue: StatusQueue) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue

    def process(
        self,
        df_market: pl.DataFrame | None,
        df_purchase: pl.DataFrame | None,
        df_master: pl.DataFrame,
    ) -> pl.DataFrame:
        logger.info("Phase 3.5: Dynamic Benchmark Extraction & Transformation...")

        min_market, max_market, min_purch = None, None, None
        if df_market is not None and not df_market.is_empty():
            market_dates = df_market.select(pl.col("Date").drop_nulls())
            if not market_dates.is_empty():
                min_market = market_dates.select(pl.min("Date")).item()
                max_market = market_dates.select(pl.max("Date")).item()

        if df_purchase is not None and not df_purchase.is_empty():
            purch_dates = df_purchase.select(pl.col("Date").drop_nulls())
            if not purch_dates.is_empty():
                min_purch = purch_dates.select(pl.min("Date")).item()

        valid_starts = [d for d in [min_market, min_purch] if d is not None]
        start_date = min(valid_starts) if valid_starts else datetime.date(2000, 1, 1)
        end_date = max_market if max_market else datetime.date.today()

        if isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.date.fromisoformat(end_date)

        logger.info(f"  -> Target Global Range: {start_date} to {end_date}")

        # 1. Fetch cached bounds from Bronze Layer (Encapsulated)
        df_bronze_cached = self.bronze.get_table("r_Benchmark_Data")
        if df_bronze_cached.is_empty():
            logger.debug(
                "[ENGINE:BENCHMARK] Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
        else:
            cached_min = df_bronze_cached.select(pl.min("Date")).item()
            cached_max = df_bronze_cached.select(pl.max("Date")).item()
            logger.debug(
                f"[ENGINE:BENCHMARK] Bronze Cache: FOUND {df_bronze_cached.height} rows ({cached_min} to {cached_max})."
            )

        # 2. Extract Delta from external sources to Raw Store
        extractor = BenchmarkExtractor(self.cp, self.status_queue)
        batch_res = extractor.extract_benchmark_delta(
            df_m=df_master,
            global_start_date=start_date,
            global_end_date=end_date,
            df_bronze_cached=df_bronze_cached,
        )
        if self.cp.active_run_id:
            self.cp.runs.log_provider_requests(
                self.cp.active_run_id, batch_res.to_provider_requests()
            )
        batch_res.assert_complete("Benchmark Extractor")
        df_new_raw, virtual_files = batch_res.combined_frame, batch_res.injected_files

        # 3. Load Delta directly into Bronze Layer
        if not df_new_raw.is_empty():
            logger.debug("[ENGINE:BENCHMARK] Upserting new Parquet chunks to Bronze...")
            row_counts = self.bronze.upsert_table(
                df=df_new_raw,
                table_name="bronze.r_Benchmark_Data",
                actionable_files=virtual_files,
                full_replace=False,
            )

            for filepath in virtual_files:
                filename = os.path.basename(filepath)
                count = row_counts.get(filename, 0)
                self.bronze.cp.artifacts.mark_synced([filepath])
                self.bronze.meta_layer.register_file(
                    filepath, "benchmark_history", count, self.bronze.cp
                )

            # Refetch the complete cache post-upsert
            df_bronze_cached = self.bronze.get_table("r_Benchmark_Data")

        # 4. Transform Bronze into final Silver representations
        transformer = BenchmarkTransformer(self.status_queue)
        df_silver = transformer.transform(df_bronze_cached, start_date, end_date)

        logger.debug(
            f"[ENGINE:BENCHMARK] Transformation Complete: Silver Benchmark table has {df_silver.height} market periods."
        )

        return df_silver


class USMarketPipeline:
    """Synchronizes external daily US stock market prices into Bronze and Silver layers."""

    def __init__(
        self, cp: ControlPlane, bronze: BronzeLayer, status_queue: StatusQueue, max_workers: int = 8
    ) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.max_workers = max_workers

    def run(
        self,
        df_purchase: pl.DataFrame,
        df_sale: pl.DataFrame,
        df_master: pl.DataFrame,
        df_fx: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Run the US Market Data pipeline."""
        if df_purchase.is_empty():
            return pl.DataFrame()

        us_purchases = df_purchase.filter(pl.col("__file_category__") == "US Stocks")
        if us_purchases.is_empty():
            return pl.DataFrame()

        active_isins = us_purchases["ISIN"].unique().to_list()
        master_dict = dict(zip(df_master["ISIN"], df_master["YAHOO_TICKER"], strict=False))

        isin_ticker_map: dict[str, str] = {}
        for isin in active_isins:
            name = str(master_dict.get(isin, ""))
            if name:
                isin_ticker_map[str(isin)] = name

        logger.info("Phase 3.7: Dynamic US Market Data Extraction & Transformation...")
        logger.info(f"  -> Target Global Range: {global_start_date} to {global_end_date}")

        self.status_queue.put(
            EngineStatusMessage(
                msg="Starting US Market Data Pipeline...",
                data=None,
                progress=0.05,
                level=LogLevel.STEP,
            )
        )

        # 1. Load Bronze Cache
        df_bronze_cached = self.bronze.get_table("r_US_Stock_Prices")
        if df_bronze_cached.is_empty():
            logger.debug(
                "[ENGINE:US_MARKET] Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
            df_bronze_cached = pl.DataFrame(
                schema={
                    "Date": pl.Date,
                    "ISIN": pl.String,
                    "yF_Ticker": pl.String,
                    "Closing_Price_Local": pl.Float64,
                    "Data_Provider": pl.String,
                    "Extraction_Time": pl.String,
                    "Requested_Start": pl.Date,
                    "Requested_End": pl.Date,
                    "Is_Closure_Gap": pl.Boolean,
                }
            )

        # 2. Extract Delta
        extractor = USMarketExtractor(self.cp, self.status_queue, self.max_workers)
        batch_res = extractor.extract_us_market_delta(
            isin_ticker_map, global_start_date, global_end_date, df_bronze_cached
        )
        if self.cp.active_run_id:
            self.cp.runs.log_provider_requests(
                self.cp.active_run_id, batch_res.to_provider_requests()
            )
        batch_res.assert_complete("US Market Extractor")
        df_delta, new_files = batch_res.combined_frame, batch_res.injected_files

        self.status_queue.put(
            EngineStatusMessage(
                msg="Upserting Delta into Bronze US Market Lake...",
                data=None,
                progress=0.6,
                level=LogLevel.INFO,
            )
        )

        # 3. Upsert to Bronze
        if not df_delta.is_empty():
            logger.debug("[ENGINE:US_MARKET] Upserting new Parquet chunks to Bronze...")
            row_counts = self.bronze.upsert_table(
                df=df_delta,
                table_name="bronze.r_US_Stock_Prices",
                actionable_files=new_files,
                full_replace=False,
            )
            for filepath in new_files:
                filename = os.path.basename(filepath)
                count = row_counts.get(filename, 0)
                self.bronze.cp.artifacts.mark_synced([filepath])
                self.bronze.meta_layer.register_file(
                    filepath, "us_stock_market", count, self.bronze.cp
                )

        df_bronze_full = self.bronze.get_table("r_US_Stock_Prices")
        if df_bronze_full.is_empty():
            df_bronze_full_lazy = pl.LazyFrame(
                schema={
                    "Date": pl.Date,
                    "ISIN": pl.String,
                    "yF_Ticker": pl.String,
                    "Closing_Price_Local": pl.Float64,
                    "Data_Provider": pl.String,
                    "Extraction_Time": pl.String,
                    "Requested_Start": pl.Date,
                    "Requested_End": pl.Date,
                    "Is_Closure_Gap": pl.Boolean,
                }
            )
        else:
            df_bronze_full_lazy = df_bronze_full.lazy()

        # 4. Transform to Silver (Continuous Series and Spine)
        self.status_queue.put(
            EngineStatusMessage(
                msg="Transforming continuous US Market series...",
                data=None,
                progress=0.8,
                level=LogLevel.INFO,
            )
        )

        df_silver_lazy = transform_us_market_data(
            df_bronze_prices_lazy=df_bronze_full_lazy,
            df_purchase_lazy=df_purchase.lazy(),
            df_sale_lazy=df_sale.lazy(),
            df_fx_lazy=df_fx.lazy(),
            global_start_date=global_start_date,
            global_end_date=global_end_date,
        )

        df_silver = df_silver_lazy.collect(engine="streaming")

        self.status_queue.put(
            EngineStatusMessage(
                msg="US Market Pipeline Completed.",
                data=None,
                progress=1.0,
                level=LogLevel.SUCCESS,
            )
        )

        return df_silver
