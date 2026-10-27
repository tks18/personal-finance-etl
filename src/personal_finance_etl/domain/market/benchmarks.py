"""Market benchmark transformations and continuous series construction.

Owns
----
- Transformation of Bronze benchmark close observations into a continuous daily Silver series.
- Staleness policy enforcement (maximum 7 calendar days forward carry).
- Fail-closed validation for non-positive or non-finite prices.
- Backward as-of joins preventing backward-fill of future observations.

Does not own
-------------
- Yahoo Finance data acquisition (owned by infrastructure.providers.market.benchmark).
- Storage or persistence in DuckDB (owned by infrastructure.warehouse).
"""

from datetime import date

import polars as pl


def transform_benchmark_data(
    df_bronze_benchmark: pl.DataFrame | pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.DataFrame:
    """Transform raw benchmark observations into a continuous daily Silver series.

    Missing dates may inherit the latest prior observation for up to seven calendar
    days. Missing initial history, observations older than the staleness limit,
    and invalid prices fail closed instead of being fabricated.

    Parameters
    ----------
    df_bronze_benchmark : pl.DataFrame | pl.LazyFrame
        Bronze benchmark observations.
    global_start_date : date
        Start date of the required continuous daily spine.
    global_end_date : date
        End date of the required continuous daily spine.

    Returns
    -------
    pl.DataFrame
        Daily continuous Silver benchmark series.
    """
    if isinstance(df_bronze_benchmark, pl.LazyFrame):
        # Materialization Boundary: STATEFUL_ALGORITHM_BOUNDARY
        # Materialize bronze benchmark frame for sequential price gap closure validation
        df_bronze_benchmark = df_bronze_benchmark.collect()

    if df_bronze_benchmark.is_empty():
        return pl.DataFrame()

    # Reject invalid published prices; explicit closure-gap/null rows are treated as
    # missing observations and may inherit a prior valid close within the staleness limit.
    invalid_source_prices = (
        df_bronze_benchmark.filter(
            pl.col("Close").is_not_null()
            & (~pl.col("Close").is_finite() | (pl.col("Close") <= 0))
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        )
        .select(["Date", "yF_Ticker", "Close"])
        .head(10)
    )
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
    df_spine = df_full_idx.join(
        pl.DataFrame({"yF_Ticker": tickers}),
        how="cross",
    ).sort(["Date", "yF_Ticker"])

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

    # Diagnostic warning on unavailable prices
    unavailable = df_filled.filter(pl.col("Close").is_null()).select(
        ["Date", "yF_Ticker", "Benchmark_Observation_Date", "Benchmark_Age_Days"]
    )
    if not unavailable.is_empty():
        # Unavailable rows intentionally remain null after the staleness policy is applied.
        pass

    df_silver = df_filled

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

    return df_silver


class BenchmarkTransformer:
    """Read Bronze benchmark data and build a continuous daily Silver series."""

    def transform(
        self,
        df_bronze_benchmark: pl.DataFrame | pl.LazyFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Transform Bronze benchmark observations into a continuous daily Silver series."""
        df_silver = transform_benchmark_data(
            df_bronze_benchmark,
            global_start_date,
            global_end_date,
        )

        return df_silver
