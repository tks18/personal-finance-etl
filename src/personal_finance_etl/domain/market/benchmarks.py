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


def _validate_and_filter_clean_benchmark_observations(
    df_bronze_benchmark: pl.DataFrame,
) -> pl.DataFrame:
    """Validate source prices and filter down to unique, valid, non-gap observations.

    Parameters
    ----------
    df_bronze_benchmark : pl.DataFrame
        Materialized raw Bronze benchmark observations.

    Returns
    -------
    pl.DataFrame
        Deduplicated and filtered valid benchmark observations.

    Raises
    ------
    ValueError
        If Bronze observations contain non-positive or non-finite prices, or no valid closes.
    """
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

    return df_clean


def _build_benchmark_continuous_spine(
    tickers: list[str],
    global_start_date: date,
    global_end_date: date,
) -> pl.DataFrame:
    """Build a continuous daily Cartesian date spine for all active benchmark tickers.

    Parameters
    ----------
    tickers : list[str]
        List of unique active benchmark ticker symbols.
    global_start_date : date
        Start date of the required continuous daily spine.
    global_end_date : date
        End date of the required continuous daily spine.

    Returns
    -------
    pl.DataFrame
        Cross-joined continuous date and ticker spine.
    """
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

    return df_full_idx.join(
        pl.DataFrame({"yF_Ticker": tickers}),
        how="cross",
    ).sort(["Date", "yF_Ticker"])


def _apply_benchmark_asof_and_staleness(
    df_spine: pl.DataFrame,
    df_clean: pl.DataFrame,
    max_benchmark_staleness_days: int = 7,
) -> pl.DataFrame:
    """Align observations to daily spine via backward as-of join and apply staleness policy.

    Parameters
    ----------
    df_spine : pl.DataFrame
        Continuous daily date and ticker spine.
    df_clean : pl.DataFrame
        Clean benchmark observations.
    max_benchmark_staleness_days : int, default=7
        Maximum allowed days to carry forward prior benchmark observations.

    Returns
    -------
    pl.DataFrame
        Continuous benchmark series with staleness-clipped prices and imputation flags.
    """
    df_observations = df_clean.with_columns(
        pl.col("Date").alias("Benchmark_Observation_Date")
    ).sort(["Date", "yF_Ticker"])

    df_filled = df_spine.join_asof(
        df_observations,
        on="Date",
        by="yF_Ticker",
        strategy="backward",
    ).sort(["Date", "yF_Ticker"])

    return df_filled.with_columns(
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


def _project_final_benchmark_schema(df_filled: pl.DataFrame) -> pl.DataFrame:
    """Drop temporary tracking and lineage columns to finalize Silver benchmark schema.

    Parameters
    ----------
    df_filled : pl.DataFrame
        Staleness-verified benchmark series.

    Returns
    -------
    pl.DataFrame
        Final cleaned Silver benchmark DataFrame.
    """
    cols_to_drop = [
        c
        for c in [
            "__file_name__",
            "__folder_path__",
            "__ingested_at__",
            "Benchmark_Observation_Date",
            "Benchmark_Age_Days",
        ]
        if c in df_filled.columns
    ]
    if cols_to_drop:
        return df_filled.drop(cols_to_drop)
    return df_filled


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

    df_clean = _validate_and_filter_clean_benchmark_observations(df_bronze_benchmark)
    tickers = sorted(df_clean["yF_Ticker"].unique().to_list())
    if not tickers:
        raise ValueError("Benchmark Bronze data has no tickers with valid observations.")

    df_spine = _build_benchmark_continuous_spine(tickers, global_start_date, global_end_date)
    df_filled = _apply_benchmark_asof_and_staleness(
        df_spine, df_clean, max_benchmark_staleness_days=7
    )
    return _project_final_benchmark_schema(df_filled)


class BenchmarkTransformer:
    """Read Bronze benchmark data and build a continuous daily Silver series."""

    def transform(
        self,
        df_bronze_benchmark: pl.DataFrame | pl.LazyFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Transform Bronze benchmark observations into a continuous daily Silver series.

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
        return transform_benchmark_data(
            df_bronze_benchmark,
            global_start_date,
            global_end_date,
        )
