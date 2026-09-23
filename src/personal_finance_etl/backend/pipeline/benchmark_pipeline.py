import datetime
import os

import polars as pl

from personal_finance_etl.backend.extract.benchmark_extractor import BenchmarkExtractor
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.raw import RawDocumentStore
from personal_finance_etl.backend.transform.benchmark_transformer import BenchmarkTransformer
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger


class BenchmarkPipeline:
    def __init__(self, raw_store: RawDocumentStore, bronze: BronzeLayer, status_queue: ILogger):
        self.raw_store = raw_store
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
            logger.info("  -> Bronze Cache: EMPTY. A full historical extraction will be performed.")
        else:
            cached_min = df_bronze_cached.select(pl.min("Date")).item()
            cached_max = df_bronze_cached.select(pl.max("Date")).item()
            logger.info(
                f"  -> Bronze Cache: FOUND {df_bronze_cached.height} rows ({cached_min} to {cached_max})."
            )

        # 2. Extract Delta from external sources to Raw Store
        extractor = BenchmarkExtractor(self.raw_store, self.status_queue)
        df_new_raw, virtual_files = extractor.extract_benchmark_delta(
            df_m=df_master,
            global_start_date=start_date,
            global_end_date=end_date,
            df_bronze_cached=df_bronze_cached,
        )

        # 3. Load Delta directly into Bronze Layer
        if not df_new_raw.is_empty():
            logger.info("Upserting new Parquet chunks to Bronze...")
            row_counts = self.bronze.upsert_table(
                df=df_new_raw,
                table_name="bronze.r_Benchmark_Data",
                actionable_files=virtual_files,
                full_replace=False,
            )

            for filepath in virtual_files:
                filename = os.path.basename(filepath)
                count = row_counts.get(filename, 0)
                self.bronze.file_tracker.register_file(filepath, "benchmark_history", count)

            # Refetch the complete cache post-upsert
            df_bronze_cached = self.bronze.get_table("r_Benchmark_Data")

        # 4. Transform Bronze into final Silver representations
        transformer = BenchmarkTransformer(self.status_queue)
        df_silver = transformer.transform(df_bronze_cached, start_date, end_date)

        logger.info(
            f"  -> Transformation Complete: Silver Benchmark table has {df_silver.height} market periods."
        )

        return df_silver
