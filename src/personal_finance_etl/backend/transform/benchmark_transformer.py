from datetime import date

import polars as pl

from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class BenchmarkTransformer:
    """
    Reads the complete raw benchmark dataset from the Bronze layer, applies
    date-range joins, and forward/backward fills closing prices to create
    a continuous daily timeseries for the Silver layer.
    """

    def __init__(self, status_queue: ILogger) -> None:
        self.status_queue = status_queue

    def transform(
        self,
        df_bronze_benchmark: pl.DataFrame | pl.LazyFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:

        self.status_queue.put(
            EngineStatus(
                msg=f"Transforming Bronze Benchmark Data into Silver ({global_start_date} to {global_end_date})...",
                data=None,
                progress=0.1,
                level=LogLevel.STEP,
            )
        )

        if isinstance(df_bronze_benchmark, pl.LazyFrame):
            df_bronze_benchmark = df_bronze_benchmark.collect()

        if df_bronze_benchmark.is_empty():
            logger.warning(
                "BenchmarkTransformer received empty Bronze data. Returning empty frame."
            )
            return pl.DataFrame()

        # Deduplicate on Date and yF_Ticker just in case (taking the latest available)
        df_clean = df_bronze_benchmark.sort(["Date", "yF_Ticker"]).unique(
            subset=["Date", "yF_Ticker"], keep="last"
        )

        # Create a full date index across the required range
        df_full_idx = pl.DataFrame(
            {
                "Date": pl.date_range(global_start_date, global_end_date, "1d", eager=True).cast(
                    pl.Date
                )
            }
        )

        # Process each ticker to ensure continuous daily forward filling
        tickers = df_clean["yF_Ticker"].unique().to_list()
        transformed_dfs: list[pl.DataFrame] = []

        for ticker in tickers:
            df_ticker = df_clean.filter(pl.col("yF_Ticker") == ticker)

            # Left join on the full date index
            df_filled = df_full_idx.join(df_ticker, on="Date", how="left")

            # We must carry forward the static metadata columns, then fill the Close price
            df_filled = df_filled.with_columns(
                pl.col("Is_Closure_Gap").fill_null(True).alias("Is_Imputed"),
                pl.col("Close").forward_fill().backward_fill(),
                pl.col("Data_Provider").forward_fill().backward_fill(),
                pl.col("Extraction_Time").forward_fill().backward_fill(),
                pl.col("ID").forward_fill().backward_fill(),
                pl.col("Benchmark_Name").forward_fill().backward_fill(),
                pl.col("yF_Ticker").fill_null(pl.lit(ticker)),
                pl.col("CURRENCY_ID").forward_fill().backward_fill(),
            )
            
            missing_check = df_filled.filter(pl.col("Close").is_null())
            if not missing_check.is_empty():
                raise ValueError(f"FATAL: Missing Benchmark data for ticker: {ticker}. Halting pipeline.")

            transformed_dfs.append(df_filled)

        df_silver = (
            pl.concat(transformed_dfs, how="diagonal") if transformed_dfs else pl.DataFrame()
        )

        # Drop internal raw tracking columns before writing to Silver
        cols_to_drop = [
            c
            for c in ["__file_name__", "__folder_path__", "__ingested_at__"]
            if c in df_silver.columns
        ]
        if cols_to_drop:
            df_silver = df_silver.drop(cols_to_drop)

        logger.info(f"BenchmarkTransformer generated Silver table with {df_silver.height} rows.")
        self.status_queue.put(
            EngineStatus(
                msg=f"Successfully transformed benchmark data ({global_start_date} to {global_end_date}).",
                data=None,
                progress=1.0,
                level=LogLevel.SUCCESS,
            )
        )

        return df_silver
