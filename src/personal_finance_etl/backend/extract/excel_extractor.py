"""Legacy Excel extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.files.excel.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.files.excel import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
    extract_us_stock_transactions_raw,
)

__all__ = [
    "extract_mf_market_data_raw",
    "extract_mf_transactions_raw",
    "extract_stock_market_data_raw",
    "extract_stock_transactions_raw",
    "extract_us_stock_transactions_raw",
]
