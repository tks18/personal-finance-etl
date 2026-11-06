"""Authoritative catalog of canonical Bronze field vocabularies and validation.

Owns
----
- CANONICAL_PROVENANCE_FIELDS: Authoritative set of immutable pipeline provenance fields.
- CANONICAL_BRONZE_FIELDS: Catalog mapping canonical Bronze DatasetIds to permitted field names.
- is_valid_canonical_field: Predicate verifying if a field is permitted for a target Bronze dataset.
- get_canonical_fields: Lookup returning the complete permitted field set for a Bronze dataset.

Does not own
-------------
- Column mapping configuration models (owned by config.sources.mapping).
- Mapping compilation or execution (owned by application.normalization).
- Physical DuckDB Bronze DDL generation (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "CANONICAL_BRONZE_FIELDS",
    "CANONICAL_PROVENANCE_FIELDS",
    "get_canonical_fields",
    "is_valid_canonical_field",
]

CANONICAL_PROVENANCE_FIELDS: frozenset[str] = frozenset(
    {
        "artifact_id",
        "__file_name__",
        "__folder_path__",
    }
)

CANONICAL_BRONZE_FIELDS: dict[DatasetId, frozenset[str]] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: frozenset(
        {
            "S_NO",
            "IS_DEL",
            "MODIFY_DATE",
            "UID",
            "CATEGORY_NAME",
            "ORDER_SEQUENCE",
            "TYPE",
            "STATUS",
            "CATEGORY_ID",
            "IS_SYNCED",
            "SYNC_TIME",
            "SYNC_VERSION",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_ASSET_GROUP: frozenset(
        {
            "DEVICE_ID",
            "UID",
            "IS_DEL",
            "USE_TIME",
            "ASSET_GROUP",
            "TYPE",
            "ORDER_SEQUENCE",
            "IS_SYNCED",
            "SYNC_TIME",
            "SYNC_VERSION",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_ASSETS: frozenset(
        {
            "S_NO",
            "CARD_STATEMENT_DATE",
            "CARD_PAYMENT_DATE",
            "ASSET_NAME",
            "ORDER_SEQUENCE",
            "IS_DEL",
            "ASSET_DESCRIPTION",
            "NOTES",
            "TRANSFER_EXPENSE",
            "CARD_AUTOPAY",
            "APP_PACKAGE",
            "APP_NAME",
            "SMS_TEL",
            "SMS_STRING",
            "ADDED_TIME",
            "CARD_USAGE_HURDLE_TYPE",
            "CARD_USAGE_HURDLE_START_DATE",
            "CARD_USAGE_HURDLE_AMOUNT",
            "UID",
            "CURRENCY_ID",
            "AUTOPAY_ASSET_ID",
            "ASSET_GROUP_ID",
            "GROUP_ID",
            "IS_SYNCED",
            "SYNC_TIME",
            "SYNC_VERSION",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_CURRENCY: frozenset(
        {
            "S_NO",
            "UID",
            "CURRENCY_NAME",
            "ISO",
            "MAIN_ISO",
            "IS_DEL",
            "ORDER_SEQUENCE",
            "RATE",
            "SYMBOL",
            "INSERT_TYPE",
            "SYMBOL_POSITION",
            "IS_MAIN_CURRENCY",
            "IS_SHOW",
            "MODIFY_DATE",
            "DECIMAL_POINT",
            "IS_SYNCED",
            "SYNC_TIME",
            "SYNC_VERSION",
            "CURRENCY_CODE",
            "CURRENCY_SYMBOL",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_INOUTCOME: frozenset(
        {
            "S_NO",
            "UID",
            "ASSET_ID",
            "CARDDIVIDMONTH",
            "CATEGORY_ID",
            "TO_ASSET_ID",
            "DESCRIPTION",
            "TIMESTAMP",
            "DATE",
            "TIME",
            "PAID",
            "TRANSACTION_TYPE",
            "BASE_AMOUNT",
            "TRANSFER_UID",
            "FEES_NOTES",
            "SMS_RDATE",
            "LOCAL_AMOUNT",
            "ASSET_NAME",
            "CATEGORY_NAME",
            "CARD_DIVIDE_ID",
            "CARD_DIVIDE_MONTH_STR",
            "MARK",
            "TRANSFER_FEES",
            "SMS_ORIGIN",
            "SMS_PARSE_CONTENT",
            "IS_DEL",
            "UPDATED_TIME",
            "CURRENCY_ID",
            "AMOUNT_ACCOUNT",
            "LAT",
            "LONG",
            "GSTD",
            "IS_SYNCED",
            "SYNC_TIME",
            "SYNC_VERSION",
            "TRANSACTION_DATE",
            "AMOUNT",
            "SUB_CATEGORY_ID",
            "CONTENT",
            "MEMO",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_OPENING_BALANCES: frozenset(
        {
            "UID",
            "Account_Name",
            "Balance",
            "Balance_Date",
            "Currency",
            "Z_PK",
            "Z_ENT",
            "Z_OPT",
            "ZASSET_GROUP",
            "ZASSET_ID",
            "ZCATEGORY_ID",
            "ZOPPOSITEAID",
            "ZAID",
            "ZCATEGORYID",
            "ZCURRENCYID",
            "ZFEE_ID",
            "ZISDEL",
            "ZISSYNCED",
            "ZMARK",
            "ZSYNCCHECK",
            "ZSYNCVERSION",
            "ZUTIME",
            "ZDATE",
            "ZAMOUNT",
            "ZAMOUNTACCOUNT",
            "ZAMOUNTSUB",
            "ZSYNCTIME",
            "ZASSET_NAME",
            "ZASSET_NIC",
            "ZCARDDIVIDID",
            "ZCATEGORY_NAME",
            "ZCONTENT",
            "ZDO_TYPE",
            "ZMONEY",
            "ZASSETUID",
            "ZCARDDIVIDEMONTH",
            "ZCARDDIVIDEMONTHSTR",
            "ZCARDDIVIDEUID",
            "ZCARDTIMESTAMPSTR",
            "ZCATEGORYUID",
            "ZCURRENCY",
            "ZCURRENCYUID",
            "ZGSTD",
            "ZLAT",
            "ZLNG",
            "ZMEMO",
            "ZPAID",
            "ZSMSORIGINE",
            "ZSMSPARSECONTENTS",
            "ZSMSRDATE",
            "ZTOASSETUID",
            "ZTXDATESTR",
            "ZTXUIDFEE",
            "ZTXUIDTRANS",
            "ZUID",
            "ZWTIME",
            "ZZDATA1",
            "ZZDATA2",
        }
    ),
    DatasetId.INVESTMENT_MF_ISIN_MAPPING: frozenset(
        {
            "INSTRUMENT_NAME",
            "ISIN",
        }
    ),
    DatasetId.INVESTMENT_BENCHMARK_MAPPING: frozenset(
        {
            "ISIN",
            "Sector",
            "Industry",
            "Benchmark_ID",
            "Yahoo_Ticker",
            "Tax_Instrument_Type",
            "Tax_Instrument_Subtype",
            "Country",
            "Geo",
            "Geo_Subtype",
            "Ticker",
            "Scheme Name",
            "Benchmark Index",
        }
    ),
    DatasetId.INVESTMENT_BENCHMARK_MASTER: frozenset(
        {
            "ID",
            "Benchmark_Name",
            "yF_Ticker",
            "Currency",
            "Index Name",
            "Ticker",
            "Description",
        }
    ),
    DatasetId.INVESTMENT_MACRO_PARAMETERS: frozenset(
        {
            "FY",
            "FY_Start_Date",
            "FY_End_Date",
            "Debt_MF_Cutoff_Date",
            "Inflation_Rate",
            "Risk_Free_Rate",
            "Estimated_Ordinary_Income_Tax_Rate",
            "Equity_LTCG_Exemption",
            "Equity_Listed_LTCG",
            "Equity_Listed_STCG",
            "Equity_Unlisted_LTCG",
            "Equity_Unlisted_STCG",
            "Gold_LTCG",
            "Gold_STCG",
            "Debt_MF_Pre_Cutoff_LTCG",
            "Debt_MF_Pre_Cutoff_STCG",
            "Debt_MF_Post_Cutoff_LTCG",
            "Debt_MF_Post_Cutoff_STCG",
            "Other_Debt_LTCG",
            "Other_Debt_STCG",
            "Default_LTCG",
            "Default_STCG",
            "Remarks",
            "Parameter",
            "Value",
            "Effective_Date",
        }
    ),
    DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS: frozenset(
        {
            "Trade Date",
            "Settlement Date",
            "Symbol",
            "Security Name",
            "Transaction Type",
            "Quantity",
            "Price",
            "Gross Amount",
            "Commission",
            "Net Amount",
            "Currency",
        }
    ),
    DatasetId.INVESTMENT_MF_ORDERS: frozenset(
        {
            "Order Date",
            "Order No",
            "Scheme Name",
            "Transaction Type",
            "Units",
            "NAV",
            "Amount",
            "STT",
            "Stamp Duty",
            "Total Amount",
        }
    ),
    DatasetId.INVESTMENT_STOCK_ORDERS: frozenset(
        {
            "Order Date",
            "Order No",
            "Symbol",
            "Exchange",
            "Order Type",
            "Quantity",
            "Price",
            "Trade Value",
            "Brokerage",
            "STT",
            "Stamp Duty",
            "GST",
            "Total Charges",
            "Net Amount",
        }
    ),
    DatasetId.MARKET_MF_HOLDINGS: frozenset(
        {
            "Scheme Name",
            "Folio No",
            "Units",
            "Nav",
            "Current Value",
            "Invested Value",
            "Gain/Loss",
            "Gain/Loss %",
            "Month Date",
            "__file_category__",
        }
    ),
    DatasetId.MARKET_CURRENCY_MAPPING: frozenset(
        {
            "UID",
            "Currency_Code",
            "Target_Currency_Code",
            "Ticker",
            "yF_Ticker",
            "Currency_Name",
            "Is_Active",
        }
    ),
    DatasetId.MARKET_CURRENCY_FX_RATES: frozenset(
        {
            "Ticker",
            "Date",
            "Close",
            "Open",
            "High",
            "Low",
            "Volume",
        }
    ),
    DatasetId.MARKET_STOCK_HOLDINGS: frozenset(
        {
            "Symbol",
            "ISIN",
            "Quantity",
            "Average Price",
            "Close Price",
            "Current Value",
            "Investment Value",
            "P&L",
            "P&L %",
            "Month Date",
            "__file_category__",
        }
    ),
    DatasetId.MARKET_BENCHMARK_HISTORY: frozenset(
        {
            "Ticker",
            "Date",
            "Close",
            "Open",
            "High",
            "Low",
            "Volume",
        }
    ),
    DatasetId.MARKET_US_STOCK_PRICES: frozenset(
        {
            "Ticker",
            "Date",
            "Close",
            "Open",
            "High",
            "Low",
            "Volume",
        }
    ),
    DatasetId.COMMON_COLUMN_MASTER: frozenset(
        {
            "TABLE_NAME",
            "OLD_COLUMN",
            "NEW_COLUMN",
        }
    ),
}


def is_valid_canonical_field(dataset_id: DatasetId, field: str) -> bool:
    """Verify whether a candidate field name is valid for a canonical Bronze dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier to evaluate.
    field : str
        Candidate column name to check.

    Returns
    -------
    bool
        True if the field is an accepted domain column or pipeline provenance column.
    """
    if field in CANONICAL_PROVENANCE_FIELDS:
        return True
    permitted = CANONICAL_BRONZE_FIELDS.get(dataset_id)
    if permitted is None:
        return False
    return field in permitted


def get_canonical_fields(dataset_id: DatasetId) -> frozenset[str] | None:
    """Retrieve the full set of permitted fields (domain + provenance) for a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.

    Returns
    -------
    frozenset[str] | None
        Frozenset of valid field names, or None if the dataset is not in the Bronze registry.
    """
    domain_fields = CANONICAL_BRONZE_FIELDS.get(dataset_id)
    if domain_fields is None:
        return None
    return domain_fields | CANONICAL_PROVENANCE_FIELDS
