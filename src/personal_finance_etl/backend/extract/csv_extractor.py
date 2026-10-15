"""Legacy CSV extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.files.csv.
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

__all__ = [
    "extract_benchmark_master_raw",
    "extract_currency_mapping_raw",
    "extract_macro_parameters_raw",
    "extract_opening_balances_raw",
    "extract_stg_benchmark_mapping",
    "extract_stg_mf_isin_mapping",
]
