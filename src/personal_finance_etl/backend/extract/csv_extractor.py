import io

import polars as pl


def extract_stg_mf_isin_mapping(filename: str, folder_path: str, raw_bytes: bytes) -> pl.LazyFrame:
    schema_overrides = {"INSTRUMENT_NAME": pl.String, "ISIN": pl.String}
    return (
        pl.read_csv(io.BytesIO(raw_bytes), schema_overrides=schema_overrides)
        .lazy()
        .with_columns(
            pl.lit(filename).alias("__file_name__"), pl.lit(folder_path).alias("__folder_path__")
        )
    )


def extract_stg_benchmark_mapping(
    filename: str, folder_path: str, raw_bytes: bytes
) -> pl.LazyFrame:
    schema_overrides = {
        "ISIN": pl.String,
        "Sector": pl.String,
        "Industry": pl.String,
        "Benchmark_ID": pl.String,
    }
    return (
        pl.read_csv(io.BytesIO(raw_bytes), schema_overrides=schema_overrides)
        .lazy()
        .with_columns(
            pl.lit(filename).alias("__file_name__"), pl.lit(folder_path).alias("__folder_path__")
        )
    )


def extract_benchmark_master_raw(filename: str, folder_path: str, raw_bytes: bytes) -> pl.LazyFrame:
    schema_overrides = {
        "ID": pl.String,
        "Benchmark_Name": pl.String,
        "yF_Ticker": pl.String,
        "Currency": pl.String,
    }
    return (
        pl.read_csv(io.BytesIO(raw_bytes), schema_overrides=schema_overrides)
        .lazy()
        .with_columns(
            pl.lit(filename).alias("__file_name__"), pl.lit(folder_path).alias("__folder_path__")
        )
    )


def extract_macro_parameters_raw(filename: str, folder_path: str, raw_bytes: bytes) -> pl.LazyFrame:
    schema_overrides = {
        "FY": pl.String,
        "FY_Start_Date": pl.Date,
        "FY_End_Date": pl.Date,
        "Debt_MF_Cutoff_Date": pl.Date,
        "Inflation_Rate": pl.Float64,
        "Risk_Free_Rate": pl.Float64,
        "Equity_Listed_LTCG": pl.Float64,
        "Equity_Listed_STCG": pl.Float64,
        "Equity_Unlisted_LTCG": pl.Float64,
        "Equity_Unlisted_STCG": pl.Float64,
        "Gold_LTCG": pl.Float64,
        "Gold_STCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_STCG": pl.Float64,
        "Debt_MF_Post_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Post_Cutoff_STCG": pl.Float64,
        "Other_Debt_LTCG": pl.Float64,
        "Other_Debt_STCG": pl.Float64,
        "Default_LTCG": pl.Float64,
        "Default_STCG": pl.Float64,
        "Equity_LTCG_Exemption": pl.Int64,
        "Remarks": pl.String,
    }
    return (
        pl.read_csv(io.BytesIO(raw_bytes), schema_overrides=schema_overrides, try_parse_dates=True)
        .lazy()
        .with_columns(
            pl.lit(filename).alias("__file_name__"), pl.lit(folder_path).alias("__folder_path__")
        )
    )


def extract_opening_balances_raw(filename: str, folder_path: str, raw_bytes: bytes) -> pl.LazyFrame:
    df = pl.read_csv(io.BytesIO(raw_bytes), try_parse_dates=True)
    return df.lazy().with_columns(
        pl.lit(filename).alias("__file_name__"), pl.lit(folder_path).alias("__folder_path__")
    )
