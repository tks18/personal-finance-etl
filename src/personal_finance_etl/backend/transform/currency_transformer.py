from datetime import date

import polars as pl


def transform_currency_fx_rates(
    df_bronze_lazy: pl.LazyFrame,
    df_currency_master_lazy: pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.LazyFrame:
    """
    Transforms bronze raw currency data into a continuous silver daily series
    using forward fill and backward fill.
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

    # 4. Aggregate bronze data to daily level (in case of duplicates)
    df_bronze_agg = df_bronze_lazy.group_by(["Date", "Currency_ID"]).agg([
        pl.col("FX_Rate").last(),
        pl.col("Data_Provider").last(),
        pl.col("Extraction_Time").last(),
        pl.col("Is_Closure_Gap").last(),
    ])

    # 5. Left join continuous spine with actual rates
    df_continuous = df_spine_full.join(df_bronze_agg, on=["Date", "Currency_ID"], how="left")

    # 6. Forward-fill only over each Currency_ID window; track imputed vs actual
    df_sorted = df_continuous.sort(["Currency_ID", "Date"])

    df_filled = df_sorted.with_columns(
        pl.col("Is_Closure_Gap").fill_null(True).alias("Is_Imputed"),
        # Forward-fill only: use last known rate for weekends/holidays.
        # No backward-fill: dates before the first observation stay null.
        # A future observation must never be used to value a past date.
        pl.col("FX_Rate").forward_fill().over("Currency_ID"),
        pl.col("Data_Provider").forward_fill().over("Currency_ID"),
        pl.col("Extraction_Time").forward_fill().over("Currency_ID"),
    ).with_columns(
        # First_Observation_Date: earliest date with a real (non-imputed) rate per currency.
        pl.col("Date")
        .filter(~pl.col("Is_Imputed"))
        .min()
        .over("Currency_ID")
        .alias("First_Observation_Date"),
    )

    # Null FX rates after forward-fill mean no observation exists on or before that date.
    # The FX validation gate (FXValidationGate.validate) will raise at the ISIN level.
    missing_fx = df_filled.filter(pl.col("FX_Rate").is_null()).collect()
    if not missing_fx.is_empty():
        bad_currencies = missing_fx["Currency_Code"].unique().to_list()
        min_dates = (
            missing_fx.group_by("Currency_Code")
            .agg(pl.col("Date").min().alias("Earliest_Missing"))
            .to_dicts()
        )
        raise ValueError(
            f"Missing FX history before first observation for currencies: {bad_currencies}. "
            f"Earliest missing dates: {min_dates}. "
            "Add earlier FX data or restrict the pipeline start date."
        )

    # 7. Final Projection
    df_final = df_filled.select(
        [
            "Date", "Currency_ID", "Currency_Code", "Target_Currency_Code",
            "FX_Rate", "yF_Ticker", "Data_Provider", "Extraction_Time",
            "Is_Imputed", "First_Observation_Date",
        ]
    )

    return df_final
