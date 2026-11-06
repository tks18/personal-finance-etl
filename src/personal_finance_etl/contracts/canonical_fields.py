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
            "UID",
            "CATEGORY_NAME",
            "TYPE",
            "CATEGORY_ID",
            "IS_DEL",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_ASSET_GROUP: frozenset(
        {
            "UID",
            "ASSET_GROUP",
            "ORDER_NUM",
            "IS_DEL",
        }
    ),
    DatasetId.HOUSEHOLD_ASSETS: frozenset(
        {
            "UID",
            "ASSET_NAME",
            "GROUP_ID",
            "CURRENCY_ID",
            "IS_DEL",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_CURRENCY: frozenset(
        {
            "UID",
            "CURRENCY_NAME",
            "CURRENCY_CODE",
            "CURRENCY_SYMBOL",
            "IS_DEL",
            "ORDER_NUM",
        }
    ),
    DatasetId.HOUSEHOLD_INOUTCOME: frozenset(
        {
            "UID",
            "TRANSACTION_DATE",
            "ASSET_ID",
            "CATEGORY_ID",
            "AMOUNT",
            "TRANSACTION_TYPE",
            "SUB_CATEGORY_ID",
            "TO_ASSET_ID",
            "CONTENT",
            "MEMO",
            "IS_DEL",
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
            "Scheme Name",
            "Benchmark Index",
        }
    ),
    DatasetId.INVESTMENT_BENCHMARK_MASTER: frozenset(
        {
            "Index Name",
            "Ticker",
            "Currency",
            "Description",
        }
    ),
    DatasetId.INVESTMENT_MACRO_PARAMETERS: frozenset(
        {
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
