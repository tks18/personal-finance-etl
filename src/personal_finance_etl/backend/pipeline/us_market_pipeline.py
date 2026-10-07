import os
from datetime import date

import polars as pl

from personal_finance_etl.backend.extract.us_market_extractor import USMarketExtractor
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.transform.us_stocks_transformer import transform_us_market_data
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class USMarketPipeline:
    def __init__(
        self, cp: ControlPlane, bronze: BronzeLayer, status_queue: ILogger, max_workers: int = 8
    ):
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
        """Runs the US Market Data pipeline."""

        if df_purchase.is_empty():
            return pl.DataFrame()

        us_purchases = df_purchase.filter(pl.col("FILE_CATEGORY") == "US Stocks")
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
            EngineStatus(
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
                }
            )

        # 2. Extract Delta
        extractor = USMarketExtractor(self.cp, self.status_queue, self.max_workers)
        df_delta, new_files = extractor.extract_us_market_delta(
            isin_ticker_map, global_start_date, global_end_date, df_bronze_cached
        )

        self.status_queue.put(
            EngineStatus(
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
                }
            )
        else:
            df_bronze_full_lazy = df_bronze_full.lazy()

        # 4. Transform to Silver (Continuous Series and Spine)
        self.status_queue.put(
            EngineStatus(
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

        # Re-attach file mapping if needed for downstream (though normally not strictly required for gold)
        if not df_silver.is_empty() and "__folder_path__" not in df_silver.columns:
            if not df_delta.is_empty() and "__folder_path__" in df_delta.columns:
                # Add a dummy folder path just in case the schema expects it
                df_silver = df_silver.with_columns(
                    pl.lit("virtual://us_stock_market/silver_transformed.parquet").alias("__folder_path__"),
                    pl.lit("silver_transformed.parquet").alias("__file_name__"),
                )

        self.status_queue.put(
            EngineStatus(
                msg="US Market Pipeline Completed.",
                data=None,
                progress=1.0,
                level=LogLevel.SUCCESS,
            )
        )

        return df_silver

