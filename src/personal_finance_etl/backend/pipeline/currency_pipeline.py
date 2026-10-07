import os
from datetime import date

import polars as pl

from personal_finance_etl.backend.extract.currency_extractor import CurrencyExtractor
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.transform.currency_transformer import transform_currency_fx_rates
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class CurrencyPipeline:
    def __init__(
        self, cp: ControlPlane, bronze: BronzeLayer, status_queue: ILogger, max_workers: int = 8
    ):
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
        """Runs the Currency FX pipeline."""

        logger.info("Phase 3.6: Dynamic Currency FX Extraction & Transformation...")
        logger.info(f"  -> Target Global Range: {global_start_date} to {global_end_date}")

        self.status_queue.put(
            EngineStatus(
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
        df_delta, new_files = extractor.extract_currency_delta(
            df_currency, global_start_date, global_end_date, df_bronze_cached
        )

        self.status_queue.put(
            EngineStatus(
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
                }
            )
        else:
            df_bronze_full_lazy = df_bronze_full.lazy()

        # 4. Transform to Silver (Continuous Series)
        self.status_queue.put(
            EngineStatus(
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
            EngineStatus(
                msg="Currency FX Pipeline Completed.",
                data=None,
                progress=1.0,
                level=LogLevel.SUCCESS,
            )
        )

        return df_silver
