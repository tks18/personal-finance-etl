from datetime import date

import polars as pl

from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class BenchmarkTransformer:
    """
    Reads the raw benchmark dataset from Bronze and creates a daily Silver
    series using only prior observations. A benchmark observation may be carried
    forward for at most seven calendar days. Missing initial history, stale data,
    and invalid prices fail closed instead of being fabricated by backward fill.
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

        # Reject invalid published prices; explicit closure-gap/null rows are treated as
        # missing observations and may inherit a prior valid close within the staleness limit.
        invalid_source_prices = df_bronze_benchmark.filter(
            pl.col("Close").is_not_null()
            & (~pl.col("Close").is_finite() | (pl.col("Close") <= 0))
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        ).select(["Date", "yF_Ticker", "Close"]).head(10)
        if not invalid_source_prices.is_empty():
            raise ValueError(
                "Bronze contains non-positive or non-finite benchmark closes not marked as "
                f"closure gaps: {invalid_source_prices.to_dicts()}"
            )

        # Only valid, non-gap closes can reset the observation date.
        df_clean = (
            df_bronze_benchmark.filter(
                pl.col("Close").is_not_null()
                & pl.col("Close").is_finite()
                & (pl.col("Close") > 0)
                & ~pl.col("Is_Closure_Gap").fill_null(False)
            )
            .sort(["Date", "yF_Ticker"])
            .unique(subset=["Date", "yF_Ticker"], keep="last")
        )

        if df_clean.is_empty():
            raise ValueError(
                "Benchmark Bronze data contains no valid, non-gap close observations "
                "for the requested range."
            )

        # Create a full date index across the required range. Benchmark values may
        # only flow forward from an observation on or before the valuation date.
        # Never backward-fill: dates before the first observation must stay unknown.
        max_benchmark_staleness_days = 7
        df_full_idx = pl.DataFrame(
            {
                "Date": pl.date_range(
                    start=global_start_date,
                    end=global_end_date,
                    interval="1d",
                    eager=True,
                ).cast(pl.Date)
            }
        )

        tickers = sorted(df_clean["yF_Ticker"].unique().to_list())
        if not tickers:
            raise ValueError("Benchmark Bronze data has no tickers with valid observations.")

        # Keep the observation date distinct from the daily spine date. A backward
        # as-of join selects only the latest valid observation at or before each day.
        df_observations = df_clean.with_columns(
            pl.col("Date").alias("Benchmark_Observation_Date")
        ).sort(["Date", "yF_Ticker"])
        df_spine = (
            df_full_idx.join(
                pl.DataFrame({"yF_Ticker": tickers}),
                how="cross",
            )
            .sort(["Date", "yF_Ticker"])
        )

        df_filled = df_spine.join_asof(
            df_observations,
            on="Date",
            by="yF_Ticker",
            strategy="backward",
        ).sort(["Date", "yF_Ticker"])

        df_filled = df_filled.with_columns(
            (pl.col("Date") - pl.col("Benchmark_Observation_Date"))
            .dt.total_days()
            .alias("Benchmark_Age_Days")
        ).with_columns(
            pl.when(
                pl.col("Benchmark_Age_Days").is_not_null()
                & (pl.col("Benchmark_Age_Days") <= max_benchmark_staleness_days)
            )
            .then(pl.col("Close"))
            .otherwise(None)
            .cast(pl.Float64)
            .alias("Close"),
            (
                pl.col("Benchmark_Observation_Date").is_null()
                | (pl.col("Benchmark_Observation_Date") != pl.col("Date"))
            ).alias("Is_Closure_Gap"),
            (
                pl.col("Benchmark_Observation_Date").is_null()
                | (pl.col("Benchmark_Observation_Date") != pl.col("Date"))
            ).alias("Is_Imputed"),
        )

        # Do not fail just because a requested date predates the first observation
        # or falls in a gap longer than the staleness limit. Those values are
        # intentionally null so downstream return calculations can remain undefined
        # instead of consuming a fabricated price. Warn with a small diagnostic sample.
        unavailable = df_filled.filter(pl.col("Close").is_null()).select(
            ["Date", "yF_Ticker", "Benchmark_Observation_Date", "Benchmark_Age_Days"]
        )
        if not unavailable.is_empty():
            logger.warning(
                "Benchmark prices are unavailable before the first observation or beyond "
                f"the {max_benchmark_staleness_days}-day staleness limit. "
                f"Examples: {unavailable.head(10).to_dicts()}"
            )

        transformed_dfs = [df_filled]

        df_silver = (
            pl.concat(transformed_dfs, how="diagonal") if transformed_dfs else pl.DataFrame()
        )

        # Drop internal raw tracking columns before writing to Silver
        cols_to_drop = [
            c
            for c in [
                "__file_name__",
                "__folder_path__",
                "__ingested_at__",
                "Benchmark_Observation_Date",
                "Benchmark_Age_Days",
            ]
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
