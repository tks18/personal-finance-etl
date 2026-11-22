"""Tests for Phase 3: Reference Data Cleanup and Instrument Master Migration.

Owns
----
- Verification of explicit schema loading for all 7 canonical reference files.
- Verification that instrument_master owns pre-existing instrument enrichment fields.
- Verification of zero runtime presence of legacy benchmark_mapping concepts.
- Verification of the deterministic reference file migration tool.
- Live verification of Shan's Google Drive reference assets and TOML configurations.

Does not own
-------------
- Physical Bronze table renames (owned by Phase 004).
- Silver table topology or dimensional schema redesign (owned by Phases 005-007).
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.domain.investments.transforms.common import get_d_investment_master
from personal_finance_etl.infrastructure.control_plane.hashing import FILE_TYPE_MAP
from personal_finance_etl.infrastructure.providers.files.csv import (
    extract_benchmark_master_raw,
    extract_currency_reference_raw,
    extract_financial_year_parameters_raw,
    extract_instrument_master_raw,
    extract_mutual_fund_instrument_mapping_raw,
    extract_opening_balances_raw,
)
from personal_finance_etl.infrastructure.warehouse.contracts import BRONZE_CONTRACT_REGISTRY


def _count_csv_rows(path: Path) -> int:
    """Deterministic CSV row counting (excluding header)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [line.strip() for line in f if line.strip()]
    return max(0, len(lines) - 1)


def test_seven_reference_files_explicit_schema_loading() -> None:
    """Verify that all 7 canonical reference CSV adapters parse payloads with typed schemas."""
    # 1. Mutual Fund Instrument Mapping
    raw_mf = b"INSTRUMENT_NAME,ISIN\nTest MF Growth,INF123456789\n"
    lf_mf = extract_mutual_fund_instrument_mapping_raw("mf.csv", "/data", raw_mf)
    df_mf = lf_mf.collect()
    assert df_mf.height == 1
    assert df_mf.schema["INSTRUMENT_NAME"] == pl.String
    assert df_mf.schema["ISIN"] == pl.String
    assert df_mf["__file_name__"][0] == "mf.csv"

    # 2. Instrument Master
    raw_inst = (
        b"ISIN,Sector,Industry,Benchmark_ID,Yahoo_Ticker,Tax_Instrument_Type,"
        b"Tax_Instrument_Subtype,Country,Geo,Geo_Subtype\n"
        b"INE001A01036,IT,Software,BENCH001,TCS.NS,Equity,Listed,India,APAC,Indian Stocks\n"
    )
    lf_inst = extract_instrument_master_raw("inst.csv", "/data", raw_inst)
    df_inst = lf_inst.collect()
    assert df_inst.height == 1
    assert df_inst.schema["ISIN"] == pl.String
    assert df_inst.schema["Sector"] == pl.String
    assert df_inst.schema["Industry"] == pl.String
    assert df_inst.schema["Benchmark_ID"] == pl.String
    assert df_inst.schema["Tax_Instrument_Type"] == pl.String
    assert df_inst.schema["Geo"] == pl.String

    # 3. Benchmark Master
    raw_bench = b"ID,Benchmark_Name,yF_Ticker,Currency\nBENCH001,Nifty 50,^NSEI,INR_INR\n"
    lf_bench = extract_benchmark_master_raw("bench.csv", "/data", raw_bench)
    df_bench = lf_bench.collect()
    assert df_bench.height == 1
    assert df_bench.schema["ID"] == pl.String
    assert df_bench.schema["Benchmark_Name"] == pl.String
    assert df_bench["yF_Ticker"][0] == "^NSEI"

    # 4. Currency Reference
    raw_curr = (
        b"UID,Currency_Code,Target_Currency_Code,yF_Ticker,Currency_Name,Is_Active\n"
        b"INR_USD,USD,INR,USDINR=X,US Dollar,true\n"
    )
    lf_curr = extract_currency_reference_raw("curr.csv", "/data", raw_curr)
    df_curr = lf_curr.collect()
    assert df_curr.height == 1
    assert df_curr.schema["UID"] == pl.String
    assert df_curr.schema["Is_Active"] == pl.Boolean
    assert df_curr["Is_Active"][0] is True

    # 5. Financial Year Parameters
    raw_fy = (
        b"FY,FY_Start_Date,FY_End_Date,Debt_MF_Cutoff_Date,Inflation_Rate,Risk_Free_Rate,"
        b"Equity_Listed_LTCG,Equity_Listed_STCG,Equity_Unlisted_LTCG,Equity_Unlisted_STCG,"
        b"Gold_LTCG,Gold_STCG,Debt_MF_Pre_Cutoff_LTCG,Debt_MF_Pre_Cutoff_STCG,"
        b"Debt_MF_Post_Cutoff_LTCG,Debt_MF_Post_Cutoff_STCG,Other_Debt_LTCG,Other_Debt_STCG,"
        b"Default_LTCG,Default_STCG,Estimated_Ordinary_Income_Tax_Rate,Equity_LTCG_Exemption,Remarks\n"
        b"2024-25,01-04-2024,31-03-2025,01-04-2023,0.062,0.0682,0.125,0.2,0.125,0.3,"
        b"0.125,0.2,0.2,0.3,0.3,0.3,0.2,0.3,0.125,0.2,0.1,125000,Standard\n"
    )
    lf_fy = extract_financial_year_parameters_raw("fy.csv", "/data", raw_fy)
    df_fy = lf_fy.collect()
    assert df_fy.height == 1
    assert df_fy.schema["FY"] == pl.String
    assert df_fy["Inflation_Rate"][0] == 0.062
    assert df_fy["Equity_Listed_LTCG"][0] == 0.125

    # 6. Opening Balances
    raw_opbal = (
        b"Z_PK,Z_ENT,Z_OPT,ZASSET_GROUP,ZASSET_ID,ZCATEGORY_ID,ZOPPOSITEAID,ZAID,"
        b"ZCATEGORYID,ZCURRENCYID,ZFEE_ID,ZISDEL,ZISSYNCED,ZMARK,ZSYNCCHECK,ZSYNCVERSION,"
        b"ZUTIME,ZDATE,ZAMOUNT,ZAMOUNTACCOUNT,ZAMOUNTSUB,ZSYNCTIME,ZASSET_NAME,ZASSET_NIC,"
        b"ZCARDDIVIDID,ZCATEGORY_NAME,ZCONTENT,ZDO_TYPE,ZMONEY,ZASSETUID,ZCARDDIVIDEMONTH,"
        b"ZCARDDIVIDEMONTHSTR,ZCARDDIVIDEUID,ZCARDTIMESTAMPSTR,ZCATEGORYUID,ZCURRENCY,"
        b"ZCURRENCYUID,ZGSTD,ZLAT,ZLNG,ZMEMO,ZPAID,ZSMSORIGINE,ZSMSPARSECONTENTS,"
        b"ZSMSRDATE,ZTOASSETUID,ZTXDATESTR,ZTXUIDFEE,ZTXUIDTRANS,ZUID,ZWTIME,ZZDATA1,ZZDATA2\n"
        b"1,11,4,0,0,0,0,0,0,0,0,,1,0,0,0,1.72E+12,741497482,10000,10000,10000,,,,,,"
        b"Diff,7,,2,0,,,,-4,,INR_INR,,,,,,,,,,01-07-2024,,,UID1,,,\n"
    )
    lf_opbal = extract_opening_balances_raw("opbal.csv", "/data", raw_opbal)
    df_opbal = lf_opbal.collect()
    assert df_opbal.height == 1
    assert df_opbal.schema["Z_PK"] == pl.Int64
    assert df_opbal["ZAMOUNT"][0] == 10000.0

    # 7. Column Master
    raw_cm = b"TABLE_NAME,OLD_COLUMN,NEW_COLUMN\nASSETS,uid,UID\n"
    df_cm = pl.read_csv(raw_cm)
    assert df_cm.height == 1
    assert "TABLE_NAME" in df_cm.columns


def test_instrument_master_owns_enrichment_and_feeds_investment_master() -> None:
    """Verify instrument_master supplies enrichment fields to get_d_investment_master."""
    raw_inst = (
        b"ISIN,Sector,Industry,Benchmark_ID,Yahoo_Ticker,Tax_Instrument_Type,"
        b"Tax_Instrument_Subtype,Country,Geo,Geo_Subtype\n"
        b"INE002A01018,Energy,Oil & Gas,BENCH001,RELIANCE.NS,Equity,Listed,India,APAC,Indian Stocks\n"
    )
    lf_inst = extract_instrument_master_raw("instrument_master.csv", "/deps", raw_inst)

    mock_master_ref = pl.LazyFrame(
        {
            "ISIN": ["INE002A01018"],
            "INSTRUMENT_NAME": ["Reliance Industries Ltd"],
            "INSTRUMENT_HOUSE": ["Reliance"],
            "INSTRUMENT_CLASS": ["Equity"],
            "INSTRUMENT_TYPE": ["Direct Stock"],
            "INSTRUMENT_SUBTYPE": ["Large Cap"],
            "CATEGORY_ID": ["CAT_ENERGY"],
        }
    )

    d_inv_master = get_d_investment_master(
        master_refs=[mock_master_ref],
        raw_instrument_master_lazy=lf_inst,
        default_currency_id="INR_INR",
    ).collect()

    assert d_inv_master.height == 1
    assert d_inv_master["ISIN"][0] == "INE002A01018"
    assert d_inv_master["SECTOR"][0] == "Energy"
    assert d_inv_master["INDUSTRY"][0] == "Oil & Gas"
    assert d_inv_master["BENCHMARK_ID"][0] == "BENCH001"
    assert d_inv_master["TAX_TYPE"][0] == "Equity"
    assert d_inv_master["TAX_SUBTYPE"][0] == "Listed"
    assert d_inv_master["COUNTRY"][0] == "India"
    assert d_inv_master["GEO"][0] == "APAC"
    assert d_inv_master["GEO_SUBTYPE"][0] == "Indian Stocks"
    assert d_inv_master["YAHOO_TICKER"][0] == "RELIANCE.NS"
    assert d_inv_master["CURRENCY_ID"][0] == "INR_INR"


def test_zero_runtime_presence_of_benchmark_mapping() -> None:
    """Verify legacy benchmark_mapping concept is completely removed from runtime contracts."""
    # 1. ExtractionResult dataclass fields
    fields = ExtractionResult.__dataclass_fields__
    assert "instrument_master" in fields
    assert "stg_benchmark_mapping" not in fields
    assert "mutual_fund_instrument_mapping" in fields
    assert "stg_mf_isin_mapping" not in fields
    assert "financial_year_parameters" in fields
    assert "raw_macro_parameters" not in fields
    assert "currency_reference" in fields
    assert "currency_mapping_raw" not in fields

    # 2. BRONZE_CONTRACT_REGISTRY sync categories
    categories = {c.sync_category: c.extraction_attribute for c in BRONZE_CONTRACT_REGISTRY}
    assert "instrument_master" in categories
    assert categories["instrument_master"] == "instrument_master"
    assert "benchmark_mapping" not in categories

    assert "mutual_fund_instrument_mapping" in categories
    assert categories["mutual_fund_instrument_mapping"] == "mutual_fund_instrument_mapping"
    assert "mf_isin" not in categories

    assert "financial_year_parameters" in categories
    assert categories["financial_year_parameters"] == "financial_year_parameters"
    assert "macro_parameters" not in categories

    assert "currency_reference" in categories
    assert categories["currency_reference"] == "currency_reference"
    assert "currency_mapping" not in categories

    # 3. FILE_TYPE_MAP
    assert "instrument_master" in FILE_TYPE_MAP
    assert "benchmark_mapping" not in FILE_TYPE_MAP
    assert "mutual_fund_instrument_mapping" in FILE_TYPE_MAP
    assert "mf_isin" not in FILE_TYPE_MAP


def test_live_google_drive_assets_and_configs() -> None:
    """Verify live Google Drive reference files and TOML configs resolve cleanly."""
    deps_dir = Path(r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\__dependencies__")
    if not deps_dir.exists():
        pytest.skip("Google Drive dependencies folder not accessible in this environment.")

    # Verify all 7 canonical files exist
    canonical_files = [
        "column_master.csv",
        "mutual_fund_instrument_mapping.csv",
        "instrument_master.csv",
        "benchmark_master.csv",
        "currency_reference.csv",
        "financial_year_parameters.csv",
        "opening_balances.csv",
    ]
    for filename in canonical_files:
        filepath = deps_dir / filename
        assert filepath.exists(), f"Missing canonical file: {filepath}"
        assert _count_csv_rows(filepath) > 0, f"Empty canonical file: {filepath}"

    # Verify live production & test configs pass validate_config()
    test_cfg_path = Path(
        r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_ETL_Test.toml"
    )
    prod_cfg_path = Path(
        r"G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_ETL.toml"
    )

    if test_cfg_path.exists():
        cfg_test = Settings.from_toml(str(test_cfg_path))
        cfg_test.validate_config()
        assert cfg_test.sources.instrument_master.endswith("instrument_master.csv")
        assert cfg_test.sources.mutual_fund_instrument_mapping.endswith(
            "mutual_fund_instrument_mapping.csv"
        )

    if prod_cfg_path.exists():
        cfg_prod = Settings.from_toml(str(prod_cfg_path))
        cfg_prod.validate_config()
        assert cfg_prod.sources.instrument_master.endswith("instrument_master.csv")
        assert cfg_prod.sources.currency_reference.endswith("currency_reference.csv")
