"""File format and discovery evidence adapters.

Owns
----
- CSV and Excel statement parsing adapters.
- External household SQLite source extraction adapter.
- Local filesystem statement discovery and locator adapter.

Does not own
-------------
- Validation of business contents (owned by domain.common.validation).
- Bronze database storage (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.files.csv import (
    extract_benchmark_master_raw,
    extract_currency_mapping_raw,
    extract_macro_parameters_raw,
    extract_opening_balances_raw,
    extract_stg_benchmark_mapping,
    extract_stg_mf_isin_mapping,
)
from personal_finance_etl.infrastructure.providers.files.excel import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
    extract_us_stock_transactions_raw,
)
from personal_finance_etl.infrastructure.providers.files.locator import (
    categorize_statement_files,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)

__all__ = [
    "SQLiteExtractor",
    "categorize_statement_files",
    "extract_benchmark_master_raw",
    "extract_currency_mapping_raw",
    "extract_macro_parameters_raw",
    "extract_mf_market_data_raw",
    "extract_mf_transactions_raw",
    "extract_opening_balances_raw",
    "extract_stg_benchmark_mapping",
    "extract_stg_mf_isin_mapping",
    "extract_stock_market_data_raw",
    "extract_stock_transactions_raw",
    "extract_us_stock_transactions_raw",
]
