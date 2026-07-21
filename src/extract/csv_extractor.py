import os

import polars as pl


def extract_stg_mf_isin_mapping(csv_path: str) -> pl.LazyFrame:
    schema_overrides = {"INSTRUMENT_NAME": pl.String, "ISIN": pl.String}
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)


def extract_stg_benchmark_mapping(csv_path: str) -> pl.LazyFrame:
    schema_overrides = {
        "ISIN": pl.String,
        "Sector": pl.String,
        "Industry": pl.String,
        "Benchmark_ID": pl.String,
    }
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)


def extract_benchmark_master_raw(csv_path: str) -> pl.LazyFrame:
    filename = os.path.basename(csv_path)
    folder = os.path.dirname(csv_path)
    schema_overrides = {
        "ID": pl.String,
        "Benchmark_Name": pl.String,
        "yF_Ticker": pl.String,
        "Currency": pl.String,
    }
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides).with_columns(
        pl.lit(filename).alias("__file_name__"), pl.lit(folder).alias("__folder_path__")
    )


def extract_tax_rates_raw(csv_path: str) -> pl.LazyFrame:
    filename = os.path.basename(csv_path)
    folder = os.path.dirname(csv_path)
    schema_overrides = {
        "FY": pl.String,
        "FY_Start_Date": pl.Date,
        "FY_End_Date": pl.Date,
        "Debt_MF_Cutoff_Date": pl.Date,
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
    return pl.scan_csv(
        csv_path, schema_overrides=schema_overrides, try_parse_dates=True
    ).with_columns(pl.lit(filename).alias("__file_name__"), pl.lit(folder).alias("__folder_path__"))


def extract_opening_balances_raw(csv_path: str) -> pl.LazyFrame:
    filename = os.path.basename(csv_path)
    folder = os.path.dirname(csv_path)

    df_lazy = pl.scan_csv(csv_path, try_parse_dates=True)
    return df_lazy.with_columns(
        pl.lit(filename).alias("__file_name__"), pl.lit(folder).alias("__folder_path__")
    )
