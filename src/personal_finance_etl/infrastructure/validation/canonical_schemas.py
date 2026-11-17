"""Canonical Bronze tabular validation schemas.

Owns
----
- CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ZCATEGORY.
- CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ASSET_GROUP.
- CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ASSETS.
- CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_CURRENCY.
- CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_INOUTCOME.
- CANONICAL_BRONZE_HOUSEHOLD_OPENING_BALANCES_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_OPENING_BALANCES.
- CANONICAL_BRONZE_INVESTMENT_MF_ISIN_MAPPING_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.INVESTMENT_MF_ISIN_MAPPING.
- CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MAPPING_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.INVESTMENT_BENCHMARK_MAPPING.
- CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MASTER_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.INVESTMENT_BENCHMARK_MASTER.
- CANONICAL_BRONZE_INVESTMENT_MACRO_PARAMETERS_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.INVESTMENT_MACRO_PARAMETERS.
- CANONICAL_BRONZE_MARKET_CURRENCY_MAPPING_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.MARKET_CURRENCY_MAPPING.
- CANONICAL_BRONZE_SCHEMAS: Registry mapping DatasetIds to authoritative canonical Bronze schemas.
- get_canonical_bronze_schema: Safe accessor for retrieving the canonical Bronze schema for a given DatasetId.
- has_canonical_bronze_schema: Inspection predicate determining whether a DatasetId has a registered canonical schema.

Does not own
-------------
- Source schema compilation (owned by infrastructure.validation.compiler).
- Validation execution or telemetry emission (owned by PanderaDataFrameValidator).
- Downstream Medallion persistence or schema management (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_OPENING_BALANCES_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA",
    "CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MAPPING_SCHEMA",
    "CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MASTER_SCHEMA",
    "CANONICAL_BRONZE_INVESTMENT_MACRO_PARAMETERS_SCHEMA",
    "CANONICAL_BRONZE_INVESTMENT_MF_ISIN_MAPPING_SCHEMA",
    "CANONICAL_BRONZE_INVESTMENT_MF_ORDERS_SCHEMA",
    "CANONICAL_BRONZE_MARKET_CURRENCY_MAPPING_SCHEMA",
    "CANONICAL_BRONZE_MARKET_MF_HOLDINGS_SCHEMA",
    "CANONICAL_BRONZE_SCHEMAS",
    "get_canonical_bronze_schema",
    "has_canonical_bronze_schema",
]

CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "CATEGORY_NAME": pa.Column(pl.String, nullable=False, name="CATEGORY_NAME"),
        "TYPE": pa.Column(pl.Int64, nullable=False, name="TYPE"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "MODIFY_DATE": pa.Column(pl.Int64, nullable=True, name="MODIFY_DATE"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "STATUS": pa.Column(pl.Int64, nullable=True, name="STATUS"),
        "CATEGORY_ID": pa.Column(pl.String, nullable=True, name="CATEGORY_ID"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_zcategory",
)

CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "ASSET_GROUP": pa.Column(pl.String, nullable=False, name="ASSET_GROUP"),
        "TYPE": pa.Column(pl.Int64, nullable=False, name="TYPE"),
        "DEVICE_ID": pa.Column(pl.Int64, nullable=True, name="DEVICE_ID"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "USE_TIME": pa.Column(pl.Int64, nullable=True, name="USE_TIME"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_asset_group",
)

CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "ASSET_NAME": pa.Column(pl.String, nullable=False, name="ASSET_NAME"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "CARD_STATEMENT_DATE": pa.Column(pl.String, nullable=True, name="CARD_STATEMENT_DATE"),
        "CARD_PAYMENT_DATE": pa.Column(pl.String, nullable=True, name="CARD_PAYMENT_DATE"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "IS_DEL": pa.Column(pl.String, nullable=True, name="IS_DEL"),
        "ASSET_DESCRIPTION": pa.Column(pl.String, nullable=True, name="ASSET_DESCRIPTION"),
        "NOTES": pa.Column(pl.String, nullable=True, name="NOTES"),
        "TRANSFER_EXPENSE": pa.Column(pl.Int64, nullable=True, name="TRANSFER_EXPENSE"),
        "CARD_AUTOPAY": pa.Column(pl.Int64, nullable=True, name="CARD_AUTOPAY"),
        "APP_PACKAGE": pa.Column(pl.String, nullable=True, name="APP_PACKAGE"),
        "APP_NAME": pa.Column(pl.String, nullable=True, name="APP_NAME"),
        "SMS_TEL": pa.Column(pl.String, nullable=True, name="SMS_TEL"),
        "SMS_STRING": pa.Column(pl.String, nullable=True, name="SMS_STRING"),
        "ADDED_TIME": pa.Column(pl.Int64, nullable=True, name="ADDED_TIME"),
        "CARD_USAGE_HURDLE_TYPE": pa.Column(pl.Int64, nullable=True, name="CARD_USAGE_HURDLE_TYPE"),
        "CARD_USAGE_HURDLE_START_DATE": pa.Column(
            pl.Float64, nullable=True, name="CARD_USAGE_HURDLE_START_DATE"
        ),
        "CARD_USAGE_HURDLE_AMOUNT": pa.Column(
            pl.Float64, nullable=True, name="CARD_USAGE_HURDLE_AMOUNT"
        ),
        "CURRENCY_ID": pa.Column(pl.String, nullable=True, name="CURRENCY_ID"),
        "AUTOPAY_ASSET_ID": pa.Column(pl.String, nullable=True, name="AUTOPAY_ASSET_ID"),
        "ASSET_GROUP_ID": pa.Column(pl.String, nullable=True, name="ASSET_GROUP_ID"),
        "GROUP_ID": pa.Column(pl.String, nullable=True, required=False, name="GROUP_ID"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_assets",
)

CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "CURRENCY_NAME": pa.Column(pl.String, nullable=False, name="CURRENCY_NAME"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "ISO": pa.Column(pl.String, nullable=True, name="ISO"),
        "MAIN_ISO": pa.Column(pl.String, nullable=True, name="MAIN_ISO"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "RATE": pa.Column(pl.Float64, nullable=True, name="RATE"),
        "SYMBOL": pa.Column(pl.String, nullable=True, name="SYMBOL"),
        "INSERT_TYPE": pa.Column(pl.String, nullable=True, name="INSERT_TYPE"),
        "SYMBOL_POSITION": pa.Column(pl.String, nullable=True, name="SYMBOL_POSITION"),
        "IS_MAIN_CURRENCY": pa.Column(pl.Int64, nullable=True, name="IS_MAIN_CURRENCY"),
        "IS_SHOW": pa.Column(pl.Int64, nullable=True, name="IS_SHOW"),
        "MODIFY_DATE": pa.Column(pl.Int64, nullable=True, name="MODIFY_DATE"),
        "DECIMAL_POINT": pa.Column(pl.Int64, nullable=True, name="DECIMAL_POINT"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "CURRENCY_CODE": pa.Column(pl.String, nullable=True, required=False, name="CURRENCY_CODE"),
        "CURRENCY_SYMBOL": pa.Column(
            pl.String, nullable=True, required=False, name="CURRENCY_SYMBOL"
        ),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_currency",
)

CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "TRANSACTION_TYPE": pa.Column(pl.String, nullable=False, name="TRANSACTION_TYPE"),
        "BASE_AMOUNT": pa.Column(pl.String, nullable=False, name="BASE_AMOUNT"),
        "ASSET_ID": pa.Column(pl.String, nullable=True, required=False, name="ASSET_ID"),
        "TIMESTAMP": pa.Column(pl.String, nullable=True, required=False, name="TIMESTAMP"),
        "S_NO": pa.Column(pl.Int64, nullable=True, required=False, name="S_NO"),
        "CARDDIVIDMONTH": pa.Column(
            pl.String, nullable=True, required=False, name="CARDDIVIDMONTH"
        ),
        "CATEGORY_ID": pa.Column(pl.String, nullable=True, required=False, name="CATEGORY_ID"),
        "TO_ASSET_ID": pa.Column(pl.String, nullable=True, required=False, name="TO_ASSET_ID"),
        "DESCRIPTION": pa.Column(pl.String, nullable=True, required=False, name="DESCRIPTION"),
        "DATE": pa.Column(pl.String, nullable=True, required=False, name="DATE"),
        "TIME": pa.Column(pl.String, nullable=True, required=False, name="TIME"),
        "PAID": pa.Column(pl.String, nullable=True, required=False, name="PAID"),
        "TRANSFER_UID": pa.Column(pl.String, nullable=True, required=False, name="TRANSFER_UID"),
        "FEES_NOTES": pa.Column(pl.String, nullable=True, required=False, name="FEES_NOTES"),
        "SMS_RDATE": pa.Column(pl.String, nullable=True, required=False, name="SMS_RDATE"),
        "LOCAL_AMOUNT": pa.Column(pl.String, nullable=True, required=False, name="LOCAL_AMOUNT"),
        "ASSET_NAME": pa.Column(pl.String, nullable=True, required=False, name="ASSET_NAME"),
        "CATEGORY_NAME": pa.Column(pl.String, nullable=True, required=False, name="CATEGORY_NAME"),
        "CARD_DIVIDE_ID": pa.Column(
            pl.String, nullable=True, required=False, name="CARD_DIVIDE_ID"
        ),
        "CARD_DIVIDE_MONTH_STR": pa.Column(
            pl.String, nullable=True, required=False, name="CARD_DIVIDE_MONTH_STR"
        ),
        "MARK": pa.Column(pl.Int64, nullable=True, required=False, name="MARK"),
        "TRANSFER_FEES": pa.Column(pl.String, nullable=True, required=False, name="TRANSFER_FEES"),
        "SMS_ORIGIN": pa.Column(pl.String, nullable=True, required=False, name="SMS_ORIGIN"),
        "SMS_PARSE_CONTENT": pa.Column(
            pl.String, nullable=True, required=False, name="SMS_PARSE_CONTENT"
        ),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, required=False, name="IS_DEL"),
        "UPDATED_TIME": pa.Column(pl.Int64, nullable=True, required=False, name="UPDATED_TIME"),
        "CURRENCY_ID": pa.Column(pl.String, nullable=True, required=False, name="CURRENCY_ID"),
        "AMOUNT_ACCOUNT": pa.Column(
            pl.Float64, nullable=True, required=False, name="AMOUNT_ACCOUNT"
        ),
        "LAT": pa.Column(pl.Float64, nullable=True, required=False, name="LAT"),
        "LONG": pa.Column(pl.Float64, nullable=True, required=False, name="LONG"),
        "GSTD": pa.Column(pl.String, nullable=True, required=False, name="GSTD"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, required=False, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, required=False, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, required=False, name="SYNC_VERSION"),
        "TRANSACTION_DATE": pa.Column(
            pl.String, nullable=True, required=False, name="TRANSACTION_DATE"
        ),
        "AMOUNT": pa.Column(pl.Float64, nullable=True, required=False, name="AMOUNT"),
        "SUB_CATEGORY_ID": pa.Column(
            pl.String, nullable=True, required=False, name="SUB_CATEGORY_ID"
        ),
        "CONTENT": pa.Column(pl.String, nullable=True, required=False, name="CONTENT"),
        "MEMO": pa.Column(pl.String, nullable=True, required=False, name="MEMO"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_inoutcome",
)

CANONICAL_BRONZE_HOUSEHOLD_OPENING_BALANCES_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "Z_PK": pa.Column(pl.Int64, nullable=False, unique=True, name="Z_PK"),
        "Z_ENT": pa.Column(pl.Int64, nullable=True, required=False, name="Z_ENT"),
        "Z_OPT": pa.Column(pl.Int64, nullable=True, required=False, name="Z_OPT"),
        "ZASSET_GROUP": pa.Column(pl.Int64, nullable=True, required=False, name="ZASSET_GROUP"),
        "ZASSET_ID": pa.Column(pl.Int64, nullable=True, required=False, name="ZASSET_ID"),
        "ZCATEGORY_ID": pa.Column(pl.Int64, nullable=True, required=False, name="ZCATEGORY_ID"),
        "ZOPPOSITEAID": pa.Column(pl.Int64, nullable=True, required=False, name="ZOPPOSITEAID"),
        "ZAID": pa.Column(pl.Int64, nullable=True, required=False, name="ZAID"),
        "ZCATEGORYID": pa.Column(pl.Int64, nullable=True, required=False, name="ZCATEGORYID"),
        "ZCURRENCYID": pa.Column(pl.Int64, nullable=True, required=False, name="ZCURRENCYID"),
        "ZFEE_ID": pa.Column(pl.Int64, nullable=True, required=False, name="ZFEE_ID"),
        "ZISDEL": pa.Column(pl.Int64, nullable=True, required=False, name="ZISDEL"),
        "ZISSYNCED": pa.Column(pl.Int64, nullable=True, required=False, name="ZISSYNCED"),
        "ZMARK": pa.Column(pl.Int64, nullable=True, required=False, name="ZMARK"),
        "ZSYNCCHECK": pa.Column(pl.Int64, nullable=True, required=False, name="ZSYNCCHECK"),
        "ZSYNCVERSION": pa.Column(pl.Int64, nullable=True, required=False, name="ZSYNCVERSION"),
        "ZUTIME": pa.Column(pl.Float64, nullable=True, required=False, name="ZUTIME"),
        "ZDATE": pa.Column(pl.Float64, nullable=True, required=False, name="ZDATE"),
        "ZAMOUNT": pa.Column(pl.Float64, nullable=True, required=False, name="ZAMOUNT"),
        "ZAMOUNTACCOUNT": pa.Column(
            pl.Float64, nullable=True, required=False, name="ZAMOUNTACCOUNT"
        ),
        "ZAMOUNTSUB": pa.Column(pl.Float64, nullable=True, required=False, name="ZAMOUNTSUB"),
        "ZSYNCTIME": pa.Column(pl.Float64, nullable=True, required=False, name="ZSYNCTIME"),
        "ZASSET_NAME": pa.Column(pl.String, nullable=True, required=False, name="ZASSET_NAME"),
        "ZASSET_NIC": pa.Column(pl.String, nullable=True, required=False, name="ZASSET_NIC"),
        "ZCARDDIVIDID": pa.Column(pl.String, nullable=True, required=False, name="ZCARDDIVIDID"),
        "ZCATEGORY_NAME": pa.Column(
            pl.String, nullable=True, required=False, name="ZCATEGORY_NAME"
        ),
        "ZCONTENT": pa.Column(pl.String, nullable=True, required=False, name="ZCONTENT"),
        "ZDO_TYPE": pa.Column(pl.String, nullable=True, required=False, name="ZDO_TYPE"),
        "ZMONEY": pa.Column(pl.String, nullable=True, required=False, name="ZMONEY"),
        "ZASSETUID": pa.Column(pl.String, nullable=True, required=False, name="ZASSETUID"),
        "ZCARDDIVIDEMONTH": pa.Column(
            pl.String, nullable=True, required=False, name="ZCARDDIVIDEMONTH"
        ),
        "ZCARDDIVIDEMONTHSTR": pa.Column(
            pl.String, nullable=True, required=False, name="ZCARDDIVIDEMONTHSTR"
        ),
        "ZCARDDIVIDEUID": pa.Column(
            pl.String, nullable=True, required=False, name="ZCARDDIVIDEUID"
        ),
        "ZCARDTIMESTAMPSTR": pa.Column(
            pl.String, nullable=True, required=False, name="ZCARDTIMESTAMPSTR"
        ),
        "ZCATEGORYUID": pa.Column(pl.String, nullable=True, required=False, name="ZCATEGORYUID"),
        "ZCURRENCY": pa.Column(pl.String, nullable=True, required=False, name="ZCURRENCY"),
        "ZCURRENCYUID": pa.Column(pl.String, nullable=True, required=False, name="ZCURRENCYUID"),
        "ZGSTD": pa.Column(pl.String, nullable=True, required=False, name="ZGSTD"),
        "ZLAT": pa.Column(pl.Float64, nullable=True, required=False, name="ZLAT"),
        "ZLNG": pa.Column(pl.Float64, nullable=True, required=False, name="ZLNG"),
        "ZMEMO": pa.Column(pl.String, nullable=True, required=False, name="ZMEMO"),
        "ZPAID": pa.Column(pl.String, nullable=True, required=False, name="ZPAID"),
        "ZSMSORIGINE": pa.Column(pl.String, nullable=True, required=False, name="ZSMSORIGINE"),
        "ZSMSPARSECONTENTS": pa.Column(
            pl.String, nullable=True, required=False, name="ZSMSPARSECONTENTS"
        ),
        "ZSMSRDATE": pa.Column(pl.String, nullable=True, required=False, name="ZSMSRDATE"),
        "ZTOASSETUID": pa.Column(pl.String, nullable=True, required=False, name="ZTOASSETUID"),
        "ZTXDATESTR": pa.Column(pl.String, nullable=True, required=False, name="ZTXDATESTR"),
        "ZTXUIDFEE": pa.Column(pl.String, nullable=True, required=False, name="ZTXUIDFEE"),
        "ZTXUIDTRANS": pa.Column(pl.String, nullable=True, required=False, name="ZTXUIDTRANS"),
        "ZUID": pa.Column(pl.String, nullable=True, required=False, name="ZUID"),
        "ZWTIME": pa.Column(pl.String, nullable=True, required=False, name="ZWTIME"),
        "ZZDATA1": pa.Column(pl.String, nullable=True, required=False, name="ZZDATA1"),
        "ZZDATA2": pa.Column(pl.String, nullable=True, required=False, name="ZZDATA2"),
        "Account_Name": pa.Column(pl.String, nullable=True, required=False, name="Account_Name"),
        "Balance": pa.Column(pl.Float64, nullable=True, required=False, name="Balance"),
        "Balance_Date": pa.Column(pl.String, nullable=True, required=False, name="Balance_Date"),
        "Currency": pa.Column(pl.String, nullable=True, required=False, name="Currency"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_opening_balances",
)

CANONICAL_BRONZE_INVESTMENT_MF_ISIN_MAPPING_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "INSTRUMENT_NAME": pa.Column(
            pl.String, nullable=False, unique=True, name="INSTRUMENT_NAME"
        ),
        "ISIN": pa.Column(pl.String, nullable=False, name="ISIN"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_investment_mf_isin_mapping",
)

CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MAPPING_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "ISIN": pa.Column(pl.String, nullable=False, unique=True, name="ISIN"),
        "Sector": pa.Column(pl.String, nullable=True, required=False, name="Sector"),
        "Industry": pa.Column(pl.String, nullable=True, required=False, name="Industry"),
        "Benchmark_ID": pa.Column(pl.String, nullable=True, required=False, name="Benchmark_ID"),
        "Yahoo_Ticker": pa.Column(pl.String, nullable=True, required=False, name="Yahoo_Ticker"),
        "Tax_Instrument_Type": pa.Column(
            pl.String, nullable=True, required=False, name="Tax_Instrument_Type"
        ),
        "Tax_Instrument_Subtype": pa.Column(
            pl.String, nullable=True, required=False, name="Tax_Instrument_Subtype"
        ),
        "Country": pa.Column(pl.String, nullable=True, required=False, name="Country"),
        "Geo": pa.Column(pl.String, nullable=True, required=False, name="Geo"),
        "Geo_Subtype": pa.Column(pl.String, nullable=True, required=False, name="Geo_Subtype"),
        "Ticker": pa.Column(pl.String, nullable=True, required=False, name="Ticker"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_investment_benchmark_mapping",
)

CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MASTER_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "ID": pa.Column(pl.String, nullable=False, unique=True, name="ID"),
        "Benchmark_Name": pa.Column(pl.String, nullable=False, name="Benchmark_Name"),
        "yF_Ticker": pa.Column(pl.String, nullable=True, required=False, name="yF_Ticker"),
        "Currency": pa.Column(pl.String, nullable=True, required=False, name="Currency"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_investment_benchmark_master",
)

CANONICAL_BRONZE_INVESTMENT_MACRO_PARAMETERS_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "FY": pa.Column(pl.String, nullable=False, unique=True, name="FY"),
        "FY_Start_Date": pa.Column(pl.Date, nullable=False, name="FY_Start_Date"),
        "FY_End_Date": pa.Column(pl.Date, nullable=False, name="FY_End_Date"),
        "Debt_MF_Cutoff_Date": pa.Column(
            pl.Date, nullable=True, required=False, name="Debt_MF_Cutoff_Date"
        ),
        "Inflation_Rate": pa.Column(
            pl.Float64, nullable=True, required=False, name="Inflation_Rate"
        ),
        "Risk_Free_Rate": pa.Column(
            pl.Float64, nullable=True, required=False, name="Risk_Free_Rate"
        ),
        "Estimated_Ordinary_Income_Tax_Rate": pa.Column(
            pl.Float64, nullable=True, required=False, name="Estimated_Ordinary_Income_Tax_Rate"
        ),
        "Equity_LTCG_Exemption": pa.Column(
            pl.Int64, nullable=True, required=False, name="Equity_LTCG_Exemption"
        ),
        "Equity_Listed_LTCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Equity_Listed_LTCG"
        ),
        "Equity_Listed_STCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Equity_Listed_STCG"
        ),
        "Equity_Unlisted_LTCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Equity_Unlisted_LTCG"
        ),
        "Equity_Unlisted_STCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Equity_Unlisted_STCG"
        ),
        "Gold_LTCG": pa.Column(pl.Float64, nullable=True, required=False, name="Gold_LTCG"),
        "Gold_STCG": pa.Column(pl.Float64, nullable=True, required=False, name="Gold_STCG"),
        "Debt_MF_Pre_Cutoff_LTCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Debt_MF_Pre_Cutoff_LTCG"
        ),
        "Debt_MF_Pre_Cutoff_STCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Debt_MF_Pre_Cutoff_STCG"
        ),
        "Debt_MF_Post_Cutoff_LTCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Debt_MF_Post_Cutoff_LTCG"
        ),
        "Debt_MF_Post_Cutoff_STCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Debt_MF_Post_Cutoff_STCG"
        ),
        "Other_Debt_LTCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Other_Debt_LTCG"
        ),
        "Other_Debt_STCG": pa.Column(
            pl.Float64, nullable=True, required=False, name="Other_Debt_STCG"
        ),
        "Default_LTCG": pa.Column(pl.Float64, nullable=True, required=False, name="Default_LTCG"),
        "Default_STCG": pa.Column(pl.Float64, nullable=True, required=False, name="Default_STCG"),
        "Remarks": pa.Column(pl.String, nullable=True, required=False, name="Remarks"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_investment_macro_parameters",
)

CANONICAL_BRONZE_MARKET_CURRENCY_MAPPING_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "Currency_Code": pa.Column(pl.String, nullable=False, name="Currency_Code"),
        "Target_Currency_Code": pa.Column(pl.String, nullable=False, name="Target_Currency_Code"),
        "yF_Ticker": pa.Column(pl.String, nullable=True, required=False, name="yF_Ticker"),
        "Currency_Name": pa.Column(pl.String, nullable=True, required=False, name="Currency_Name"),
        "Is_Active": pa.Column(pl.Boolean, nullable=True, required=False, name="Is_Active"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_market_currency_mapping",
)

CANONICAL_BRONZE_MARKET_MF_HOLDINGS_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "Scheme Name": pa.Column(pl.String, nullable=False, name="Scheme Name"),
        "AMC": pa.Column(pl.String, nullable=True, required=False, name="AMC"),
        "Category": pa.Column(pl.String, nullable=True, required=False, name="Category"),
        "Sub-category": pa.Column(pl.String, nullable=True, required=False, name="Sub-category"),
        "Folio No.": pa.Column(pl.String, nullable=True, required=False, name="Folio No."),
        "Source": pa.Column(pl.String, nullable=True, required=False, name="Source"),
        "Units": pa.Column(pl.String, nullable=True, required=False, name="Units"),
        "Invested Value": pa.Column(
            pl.String, nullable=True, required=False, name="Invested Value"
        ),
        "Current Value": pa.Column(pl.String, nullable=True, required=False, name="Current Value"),
        "Returns": pa.Column(pl.String, nullable=True, required=False, name="Returns"),
        "XIRR": pa.Column(pl.String, nullable=True, required=False, name="XIRR"),
        "Month Date": pa.Column(pl.Date, nullable=False, name="Month Date"),
        "__file_category__": pa.Column(
            pl.String, nullable=True, required=False, name="__file_category__"
        ),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_market_mf_holdings",
)

CANONICAL_BRONZE_INVESTMENT_MF_ORDERS_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "Scheme Name": pa.Column(pl.String, nullable=False, name="Scheme Name"),
        "Transaction Type": pa.Column(pl.String, nullable=False, name="Transaction Type"),
        "Units": pa.Column(pl.String, nullable=True, required=False, name="Units"),
        "NAV": pa.Column(pl.String, nullable=True, required=False, name="NAV"),
        "Amount": pa.Column(pl.String, nullable=True, required=False, name="Amount"),
        "Date": pa.Column(pl.String, nullable=True, required=False, name="Date"),
        "Month Date": pa.Column(pl.Date, nullable=True, required=False, name="Month Date"),
        "__file_category__": pa.Column(
            pl.String, nullable=True, required=False, name="__file_category__"
        ),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_investment_mf_orders",
)

CANONICAL_BRONZE_SCHEMAS: dict[DatasetId, pa.DataFrameSchema] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA,
    DatasetId.HOUSEHOLD_ASSET_GROUP: CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA,
    DatasetId.HOUSEHOLD_ASSETS: CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA,
    DatasetId.HOUSEHOLD_CURRENCY: CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA,
    DatasetId.HOUSEHOLD_INOUTCOME: CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA,
    DatasetId.HOUSEHOLD_OPENING_BALANCES: CANONICAL_BRONZE_HOUSEHOLD_OPENING_BALANCES_SCHEMA,
    DatasetId.INVESTMENT_MF_ISIN_MAPPING: CANONICAL_BRONZE_INVESTMENT_MF_ISIN_MAPPING_SCHEMA,
    DatasetId.INVESTMENT_BENCHMARK_MAPPING: CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MAPPING_SCHEMA,
    DatasetId.INVESTMENT_BENCHMARK_MASTER: CANONICAL_BRONZE_INVESTMENT_BENCHMARK_MASTER_SCHEMA,
    DatasetId.INVESTMENT_MACRO_PARAMETERS: CANONICAL_BRONZE_INVESTMENT_MACRO_PARAMETERS_SCHEMA,
    DatasetId.MARKET_CURRENCY_MAPPING: CANONICAL_BRONZE_MARKET_CURRENCY_MAPPING_SCHEMA,
    DatasetId.MARKET_MF_HOLDINGS: CANONICAL_BRONZE_MARKET_MF_HOLDINGS_SCHEMA,
    DatasetId.INVESTMENT_MF_ORDERS: CANONICAL_BRONZE_INVESTMENT_MF_ORDERS_SCHEMA,
}


def get_canonical_bronze_schema(dataset_id: DatasetId) -> pa.DataFrameSchema:
    """Retrieve the authoritative canonical Bronze Pandera schema for a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Target canonical dataset identifier.

    Returns
    -------
    pa.DataFrameSchema
        Authoritative Pandera DataFrameSchema for the dataset.

    Raises
    ------
    KeyError
        If no canonical Bronze schema is registered for the specified DatasetId.
    """
    if dataset_id not in CANONICAL_BRONZE_SCHEMAS:
        registered = sorted(d.value for d in CANONICAL_BRONZE_SCHEMAS)
        raise KeyError(
            f"No canonical Bronze validation schema registered for dataset '{dataset_id}'. "
            f"Registered datasets: {registered}."
        )
    return CANONICAL_BRONZE_SCHEMAS[dataset_id]


def has_canonical_bronze_schema(dataset_id: DatasetId) -> bool:
    """Check whether an authoritative canonical Bronze Pandera schema exists for a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Target canonical dataset identifier.

    Returns
    -------
    bool
        True if a canonical Bronze schema is registered, False otherwise.
    """
    return dataset_id in CANONICAL_BRONZE_SCHEMAS
