"""DEPRECATED - Legacy utility helpers shim module.

This module has been deactivated as part of Phase 2 of the Grand Refactor.
Canonical implementations now reside in:
- `personal_finance_etl.domain.common.dates` (calendar, FY, strict date parsing)
- `personal_finance_etl.domain.common.validation` (numeric parsing, frame validation)
- `personal_finance_etl.infrastructure.filesystem.paths` (resource, temp, cache paths)

This file is maintained strictly as a backwards-compatible pass-through delegation shim.
Do not edit or add logic here.
"""

from personal_finance_etl.domain.common.dates import (
    ensure_date_col,
    get_file_name,
    get_fy_folder_name,
    get_fy_start_year,
    get_month_folder_name,
    parse_strict_date,
    to_date_obj,
    validate_and_parse_dates,
)
from personal_finance_etl.domain.common.validation import (
    FinancialSourceValidationError,
    clean_numeric_col,
    parse_strict_numeric,
    validate_and_parse_numerics,
)
from personal_finance_etl.infrastructure.filesystem.paths import (
    get_cache_dir,
    get_temp_dir,
    resource_path,
)

__all__ = [
    "FinancialSourceValidationError",
    "clean_numeric_col",
    "ensure_date_col",
    "get_cache_dir",
    "get_file_name",
    "get_fy_folder_name",
    "get_fy_start_year",
    "get_month_folder_name",
    "get_temp_dir",
    "parse_strict_date",
    "parse_strict_numeric",
    "resource_path",
    "to_date_obj",
    "validate_and_parse_dates",
    "validate_and_parse_numerics",
]
