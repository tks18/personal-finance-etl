"""Declarative DuckDB Bronze layer schema definitions.

Owns
----
- Deterministic, explicit DDL for all 20 canonical Bronze lakehouse tables.
- Fixed physical table columns, types, nullability, and operational provenance fields.

Does not own
-------------
- Physical bronze table synchronization or row insertion (owned by infrastructure.warehouse.bronze).
- Pre-Bronze raw staging tables (owned by pre_bronze.py).
- Higher warehouse analytical layers (owned by silver.py, gold.py, meta.py).
"""

from __future__ import annotations

BRONZE_DDL = """
CREATE TABLE IF NOT EXISTS bronze.r_SQLite_ZCategory (
    S_NO BIGINT,
    IS_DEL BIGINT,
    MODIFY_DATE BIGINT,
    UID VARCHAR,
    CATEGORY_NAME VARCHAR,
    ORDER_SEQUENCE BIGINT,
    TYPE BIGINT,
    STATUS BIGINT,
    CATEGORY_ID VARCHAR,
    IS_SYNCED BIGINT,
    SYNC_TIME DOUBLE,
    SYNC_VERSION BIGINT,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_SQLite_AssetGroup (
    DEVICE_ID BIGINT,
    UID VARCHAR,
    IS_DEL BIGINT,
    USE_TIME BIGINT,
    ASSET_GROUP VARCHAR,
    TYPE BIGINT,
    ORDER_SEQUENCE BIGINT,
    IS_SYNCED BIGINT,
    SYNC_TIME DOUBLE,
    SYNC_VERSION BIGINT,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_SQLite_Assets (
    S_NO BIGINT,
    CARD_STATEMENT_DATE VARCHAR,
    CARD_PAYMENT_DATE VARCHAR,
    ASSET_NAME VARCHAR,
    ORDER_SEQUENCE BIGINT,
    IS_DEL VARCHAR,
    ASSET_DESCRIPTION VARCHAR,
    NOTES VARCHAR,
    TRANSFER_EXPENSE BIGINT,
    CARD_AUTOPAY BIGINT,
    APP_PACKAGE VARCHAR,
    APP_NAME VARCHAR,
    SMS_TEL VARCHAR,
    SMS_STRING VARCHAR,
    ADDED_TIME BIGINT,
    CARD_USAGE_HURDLE_TYPE BIGINT,
    CARD_USAGE_HURDLE_START_DATE DOUBLE,
    CARD_USAGE_HURDLE_AMOUNT DOUBLE,
    UID VARCHAR,
    CURRENCY_ID VARCHAR,
    AUTOPAY_ASSET_ID VARCHAR,
    ASSET_GROUP_ID VARCHAR,
    GROUP_ID VARCHAR,
    IS_SYNCED BIGINT,
    SYNC_TIME DOUBLE,
    SYNC_VERSION BIGINT,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_SQLite_Currency (
    S_NO BIGINT,
    UID VARCHAR,
    CURRENCY_NAME VARCHAR,
    ISO VARCHAR,
    MAIN_ISO VARCHAR,
    IS_DEL BIGINT,
    ORDER_SEQUENCE BIGINT,
    RATE DOUBLE,
    SYMBOL VARCHAR,
    INSERT_TYPE VARCHAR,
    SYMBOL_POSITION VARCHAR,
    IS_MAIN_CURRENCY BIGINT,
    IS_SHOW BIGINT,
    MODIFY_DATE BIGINT,
    DECIMAL_POINT BIGINT,
    IS_SYNCED BIGINT,
    SYNC_TIME DOUBLE,
    SYNC_VERSION BIGINT,
    CURRENCY_CODE VARCHAR,
    CURRENCY_SYMBOL VARCHAR,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_SQLite_InOutcome (
    S_NO BIGINT,
    UID VARCHAR,
    ASSET_ID VARCHAR,
    CARDDIVIDMONTH VARCHAR,
    CATEGORY_ID VARCHAR,
    TO_ASSET_ID VARCHAR,
    DESCRIPTION VARCHAR,
    TIMESTAMP VARCHAR,
    DATE VARCHAR,
    TIME VARCHAR,
    PAID VARCHAR,
    TRANSACTION_TYPE VARCHAR,
    BASE_AMOUNT VARCHAR,
    TRANSFER_UID VARCHAR,
    FEES_NOTES VARCHAR,
    SMS_RDATE VARCHAR,
    LOCAL_AMOUNT VARCHAR,
    ASSET_NAME VARCHAR,
    CATEGORY_NAME VARCHAR,
    CARD_DIVIDE_ID VARCHAR,
    CARD_DIVIDE_MONTH_STR VARCHAR,
    MARK BIGINT,
    TRANSFER_FEES VARCHAR,
    SMS_ORIGIN VARCHAR,
    SMS_PARSE_CONTENT VARCHAR,
    IS_DEL BIGINT,
    UPDATED_TIME BIGINT,
    CURRENCY_ID VARCHAR,
    AMOUNT_ACCOUNT DOUBLE,
    LAT DOUBLE,
    LONG DOUBLE,
    GSTD VARCHAR,
    IS_SYNCED BIGINT,
    SYNC_TIME DOUBLE,
    SYNC_VERSION BIGINT,
    TRANSACTION_DATE VARCHAR,
    AMOUNT DOUBLE,
    SUB_CATEGORY_ID VARCHAR,
    CONTENT VARCHAR,
    MEMO VARCHAR,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_MF_ISIN_Mapping (
    INSTRUMENT_NAME VARCHAR,
    ISIN VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Benchmark_Mapping (
    ISIN VARCHAR,
    Sector VARCHAR,
    Industry VARCHAR,
    Benchmark_ID VARCHAR,
    Yahoo_Ticker VARCHAR,
    Tax_Instrument_Type VARCHAR,
    Tax_Instrument_Subtype VARCHAR,
    Country VARCHAR,
    Geo VARCHAR,
    Geo_Subtype VARCHAR,
    Ticker VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Opening_Balances (
    Z_PK BIGINT,
    Z_ENT BIGINT,
    Z_OPT BIGINT,
    ZASSET_GROUP BIGINT,
    ZASSET_ID BIGINT,
    ZCATEGORY_ID BIGINT,
    ZOPPOSITEAID BIGINT,
    ZAID BIGINT,
    ZCATEGORYID BIGINT,
    ZCURRENCYID BIGINT,
    ZFEE_ID BIGINT,
    ZISDEL BIGINT,
    ZISSYNCED BIGINT,
    ZMARK BIGINT,
    ZSYNCCHECK BIGINT,
    ZSYNCVERSION BIGINT,
    ZUTIME DOUBLE,
    ZDATE DOUBLE,
    ZAMOUNT DOUBLE,
    ZAMOUNTACCOUNT DOUBLE,
    ZAMOUNTSUB DOUBLE,
    ZSYNCTIME DOUBLE,
    ZASSET_NAME VARCHAR,
    ZASSET_NIC VARCHAR,
    ZCARDDIVIDID VARCHAR,
    ZCATEGORY_NAME VARCHAR,
    ZCONTENT VARCHAR,
    ZDO_TYPE VARCHAR,
    ZMONEY VARCHAR,
    ZASSETUID VARCHAR,
    ZCARDDIVIDEMONTH VARCHAR,
    ZCARDDIVIDEMONTHSTR VARCHAR,
    ZCARDDIVIDEUID VARCHAR,
    ZCARDTIMESTAMPSTR VARCHAR,
    ZCATEGORYUID VARCHAR,
    ZCURRENCY VARCHAR,
    ZCURRENCYUID VARCHAR,
    ZGSTD VARCHAR,
    ZLAT DOUBLE,
    ZLNG DOUBLE,
    ZMEMO VARCHAR,
    ZPAID VARCHAR,
    ZSMSORIGINE VARCHAR,
    ZSMSPARSECONTENTS VARCHAR,
    ZSMSRDATE VARCHAR,
    ZTOASSETUID VARCHAR,
    ZTXDATESTR VARCHAR,
    ZTXUIDFEE VARCHAR,
    ZTXUIDTRANS VARCHAR,
    ZUID VARCHAR,
    ZWTIME VARCHAR,
    ZZDATA1 VARCHAR,
    ZZDATA2 VARCHAR,
    UID VARCHAR,
    Account_Name VARCHAR,
    Balance DOUBLE,
    Balance_Date VARCHAR,
    Currency VARCHAR,
    ORDER_NUM BIGINT,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Benchmark_Master (
    ID VARCHAR,
    Benchmark_Name VARCHAR,
    yF_Ticker VARCHAR,
    Currency VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Macro_Parameters (
    FY VARCHAR,
    FY_Start_Date DATE,
    FY_End_Date DATE,
    Debt_MF_Cutoff_Date DATE,
    Inflation_Rate DOUBLE,
    Risk_Free_Rate DOUBLE,
    Estimated_Ordinary_Income_Tax_Rate DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    Equity_Listed_LTCG DOUBLE,
    Equity_Listed_STCG DOUBLE,
    Equity_Unlisted_LTCG DOUBLE,
    Equity_Unlisted_STCG DOUBLE,
    Gold_LTCG DOUBLE,
    Gold_STCG DOUBLE,
    Debt_MF_Pre_Cutoff_LTCG DOUBLE,
    Debt_MF_Pre_Cutoff_STCG DOUBLE,
    Debt_MF_Post_Cutoff_LTCG DOUBLE,
    Debt_MF_Post_Cutoff_STCG DOUBLE,
    Other_Debt_LTCG DOUBLE,
    Other_Debt_STCG DOUBLE,
    Default_LTCG DOUBLE,
    Default_STCG DOUBLE,
    Remarks VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Column_Master (
    TABLE_NAME VARCHAR,
    OLD_COLUMN VARCHAR,
    NEW_COLUMN VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_MF_Market_Data (
    "Scheme Name" VARCHAR,
    AMC VARCHAR,
    Category VARCHAR,
    "Sub-category" VARCHAR,
    "Folio No." VARCHAR,
    Source VARCHAR,
    Units VARCHAR,
    "Invested Value" VARCHAR,
    "Current Value" VARCHAR,
    Returns VARCHAR,
    XIRR VARCHAR,
    "Month Date" DATE,
    __file_category__ VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_US_Stock_Transactions (
    "Stock Name" VARCHAR,
    ISIN VARCHAR,
    "Stock Symbol" VARCHAR,
    "Yahoo Ticker" VARCHAR,
    "Order Date" TIMESTAMP_MS,
    Currency VARCHAR,
    "Transaction Type" VARCHAR,
    "Order Type" VARCHAR,
    Quantity DOUBLE,
    "Price ($)" DOUBLE,
    "Order Amount ($)" DOUBLE,
    "Brokerage ($)" DOUBLE,
    "Exch Rate" DOUBLE,
    "Order Amount (INR)" DOUBLE,
    "Brokerage (INR)" DOUBLE,
    __file_category__ VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Currency_Mapping (
    UID VARCHAR,
    Currency_Code VARCHAR,
    Target_Currency_Code VARCHAR,
    yF_Ticker VARCHAR,
    Currency_Name VARCHAR,
    Is_Active BOOLEAN,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Currency_FX_Data (
    Date DATE,
    Currency_ID VARCHAR,
    Currency_Name VARCHAR,
    Currency_Code VARCHAR,
    Target_Currency_Code VARCHAR,
    yF_Ticker VARCHAR,
    FX_Rate DOUBLE,
    Data_Provider VARCHAR,
    Extraction_Time VARCHAR,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_MF_Transactions (
    "Scheme Name" VARCHAR,
    "Transaction Type" VARCHAR,
    Units VARCHAR,
    NAV VARCHAR,
    Amount VARCHAR,
    Date VARCHAR,
    "Month Date" DATE,
    __file_category__ VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Stock_Market_Data (
    "Stock name" VARCHAR,
    ISIN VARCHAR,
    Quantity VARCHAR,
    "Buy date" VARCHAR,
    "Buy price" VARCHAR,
    "Buy value" VARCHAR,
    "Closing date" VARCHAR,
    "Closing price" VARCHAR,
    "Closing value" VARCHAR,
    "Unrealised P&L" VARCHAR,
    Remark VARCHAR,
    "Month Date" DATE,
    __file_category__ VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Stock_Transactions (
    "Stock name" VARCHAR,
    Symbol VARCHAR,
    ISIN VARCHAR,
    Type VARCHAR,
    Quantity DOUBLE,
    Value DOUBLE,
    Exchange VARCHAR,
    "Exchange Order Id" VARCHAR,
    "Execution date and time" VARCHAR,
    "Order status" VARCHAR,
    __file_category__ VARCHAR,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_Benchmark_Data (
    Date DATE,
    Close DOUBLE,
    ID VARCHAR,
    Benchmark_Name VARCHAR,
    yF_Ticker VARCHAR,
    CURRENCY_ID VARCHAR,
    Data_Provider VARCHAR,
    Extraction_Time VARCHAR,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    artifact_id VARCHAR
);

CREATE TABLE IF NOT EXISTS bronze.r_US_Stock_Prices (
    Date DATE,
    ISIN VARCHAR,
    yF_Ticker VARCHAR,
    Closing_Price_Local DOUBLE,
    Data_Provider VARCHAR,
    Extraction_Time VARCHAR,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    artifact_id VARCHAR
);
"""
