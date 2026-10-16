"""Foreign exchange (FX) observation, rate provider, and transformation domain models.

Owns
----
- FXObservation record for point-in-time exchange rates.
- FXRateProvider fast O(1) point-in-time rate lookup with 30-day bounded fallback.
- Transformation of Bronze FX observations into a continuous daily Silver series.
- Staleness policy enforcement (maximum 7 calendar days forward carry).
- Distinction between valid observed rates and missing rates.

Does not own
-------------
- External API calls to Yahoo Finance (owned by infrastructure.providers.market.currency).
- Multi-currency portfolio accounting (owned by domain.investments).
- Physical table persistence in DuckDB (owned by infrastructure.warehouse).
"""

from dataclasses import dataclass
from datetime import date, timedelta

import polars as pl


@dataclass(frozen=True)
class FXObservation:
    """A single foreign-exchange rate observation."""

    rate: float | None
    currency: str
    observation_date: date
    is_interpolated: bool = False

    @property
    def is_missing(self) -> bool:
        """Return True when no rate is available for this date × currency pair."""
        return self.rate is None

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the rate, or *fallback* (default NaN) when missing.

        Using NaN as the default makes missing rates visible in aggregations
        (NaN propagates) rather than silently using 1.0 or 0.0.
        """
        return self.rate if self.rate is not None else fallback


class FXRateProvider:
    """Point-in-time foreign exchange rate provider backed by an in-memory map.

    Provides fast O(1) rate lookups for (date, currency_id) tuples with a
    bounded 30-day backward fallback for weekends/holidays.
    """

    def __init__(self, df_fx: pl.DataFrame | None, default_currency_id: str) -> None:
        self.default_currency_id = default_currency_id
        self.fx_map: dict[tuple[date, str], float] = {}
        if df_fx is not None and not df_fx.is_empty():
            # Fast O(1) dictionary
            df_sorted = df_fx.sort(["Date"])
            for row in df_sorted.to_dicts():
                d = row["Date"]
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                self.fx_map[(d, str(row["Currency_ID"]))] = float(row["FX_Rate"])

    def get_rate(self, d: date, currency_id: str) -> float | None:
        """Get the exchange rate to default currency on date `d`."""
        if currency_id == self.default_currency_id or not currency_id:
            return 1.0

        rate = self.fx_map.get((d, currency_id))
        if rate is not None:
            return rate

        # Fallback to latest available rate: search backwards up to 30 days
        for i in range(1, 31):
            fallback_date = d - timedelta(days=i)
            rate = self.fx_map.get((fallback_date, currency_id))
            if rate is not None:
                return rate

        return None


def transform_currency_fx_rates(
    df_bronze_lazy: pl.LazyFrame,
    df_currency_master_lazy: pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.LazyFrame:
    """Transforms Bronze FX observations into a daily Silver series.

    Missing dates may use the latest prior observation for up to seven calendar
    days (weekends and short market holidays). Rates before the first observation,
    rates older than the staleness limit, and invalid rates fail closed.

    Parameters
    ----------
    df_bronze_lazy : pl.LazyFrame
        Bronze raw FX observations LazyFrame.
    df_currency_master_lazy : pl.LazyFrame
        Currency master dimension LazyFrame.
    global_start_date : date
        Global start date of daily series.
    global_end_date : date
        Global end date of daily series.

    Returns
    -------
    pl.LazyFrame
        Continuous daily FX Silver LazyFrame.
    """
    # 1. Create a continuous date spine
    df_spine = pl.DataFrame(
        {
            "Date": pl.date_range(
                start=global_start_date, end=global_end_date, interval="1d", eager=True
            )
        }
    ).lazy()

    # 2. Get active tickers
    df_active_tickers = (
        df_currency_master_lazy.filter(pl.col("Is_Active"))
        .select(["UID", "ISO", "Target_Currency_Code", "yF_Ticker"])
        .rename({"UID": "Currency_ID", "ISO": "Currency_Code"})
    )

    # 3. Join Spine with Tickers (Cross Join to get all combinations)
    df_spine_full = df_spine.join(df_active_tickers, how="cross")

    # 4. Validate malformed observed rates, then aggregate valid observations to daily level.
    invalid_source_fx = (
        df_bronze_lazy.filter(
            pl.col("FX_Rate").is_not_null()
            & (~pl.col("FX_Rate").is_finite() | (pl.col("FX_Rate") <= 0))
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        )
        .select(["Date", "Currency_ID", "FX_Rate"])
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 10) of invalid source FX rates for error diagnostics
        .limit(10)
        .collect()
    )
    if not invalid_source_fx.is_empty():
        raise ValueError(
            "Bronze contains non-positive or non-finite FX rates not marked as closure gaps: "
            f"{invalid_source_fx.to_dicts()}"
        )

    df_bronze_agg = df_bronze_lazy.group_by(["Date", "Currency_ID"]).agg(
        [
            pl.when(
                pl.col("FX_Rate").is_not_null()
                & pl.col("FX_Rate").is_finite()
                & (pl.col("FX_Rate") > 0)
                & ~pl.col("Is_Closure_Gap").fill_null(False)
            )
            .then(pl.col("FX_Rate"))
            .otherwise(None)
            .last()
            .alias("FX_Rate"),
            pl.col("Data_Provider").last(),
            pl.col("Extraction_Time").last(),
            pl.col("Is_Closure_Gap").last(),
        ]
    )

    # 5. Left join continuous spine with actual rates
    df_continuous = df_spine_full.join(df_bronze_agg, on=["Date", "Currency_ID"], how="left")

    # 6. Forward-fill only from prior observations. Retain the observation date
    # internally so a long gap cannot be mistaken for a current FX rate.
    max_fx_staleness_days = 7
    df_sorted = df_continuous.sort(["Currency_ID", "Date"]).with_columns(
        (pl.col("Is_Closure_Gap").fill_null(True) | pl.col("FX_Rate").is_null()).alias("Is_Imputed")
    )
    df_sorted = df_sorted.with_columns(
        pl.when(~pl.col("Is_Imputed"))
        .then(pl.col("Date"))
        .otherwise(None)
        .alias("FX_Observation_Date")
    )

    df_filled = (
        df_sorted.with_columns(
            pl.col("FX_Rate").forward_fill().over("Currency_ID"),
            pl.col("Data_Provider").forward_fill().over("Currency_ID"),
            pl.col("Extraction_Time").forward_fill().over("Currency_ID"),
            pl.col("FX_Observation_Date").forward_fill().over("Currency_ID"),
        )
        .with_columns(
            (pl.col("Date") - pl.col("FX_Observation_Date")).dt.total_days().alias("FX_Age_Days"),
            pl.col("Date")
            .filter(~pl.col("Is_Imputed"))
            .min()
            .over("Currency_ID")
            .alias("First_Observation_Date"),
        )
        .with_columns(
            (pl.col("Is_Imputed") | (pl.col("FX_Observation_Date") != pl.col("Date"))).alias(
                "Is_Imputed"
            )
        )
    )

    invalid_fx = (
        df_filled.filter(
            pl.col("FX_Rate").is_null()
            | ~pl.col("FX_Rate").is_finite()
            | (pl.col("FX_Rate") <= 0)
            | pl.col("FX_Age_Days").is_null()
            | (pl.col("FX_Age_Days") > max_fx_staleness_days)
        )
        .select(
            [
                "Date",
                "Currency_ID",
                "Currency_Code",
                "FX_Rate",
                "FX_Observation_Date",
                "FX_Age_Days",
            ]
        )
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 20) of missing or stale FX observations for error diagnostics
        .limit(20)
        .collect()
    )
    if not invalid_fx.is_empty():
        raise ValueError(
            "Missing, invalid, or stale FX history. FX observations may be carried forward "
            f"for at most {max_fx_staleness_days} calendar days. "
            f"Examples: {invalid_fx.to_dicts()}. Add earlier FX data or restrict the "
            "pipeline start date."
        )

    # 7. Final Projection
    df_final = df_filled.select(
        [
            "Date",
            "Currency_ID",
            "Currency_Code",
            "Target_Currency_Code",
            "FX_Rate",
            "yF_Ticker",
            "Data_Provider",
            "Extraction_Time",
            "Is_Imputed",
            "First_Observation_Date",
        ]
    )

    return df_final
