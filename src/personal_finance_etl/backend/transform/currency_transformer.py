from datetime import date

import polars as pl


def transform_currency_fx_rates(
    df_bronze_lazy: pl.LazyFrame,
    df_currency_master_lazy: pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.LazyFrame:
    """
    Transforms Bronze FX observations into a daily Silver series.

    Missing dates may use the latest prior observation for up to seven calendar
    days (weekends and short market holidays). Rates before the first observation,
    rates older than the staleness limit, and invalid rates fail closed.
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
