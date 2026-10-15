"""Common financial domain primitives.

Owns
----
- Deterministic canonical identity generation.
- Financial source validation exceptions and semantics.
- General financial calculation result containers and statuses.
- Shared pure Polars analytical expressions.
- Financial date and fiscal year helpers.

Does not own
-------------
- Arbitrary utilities or dump-ground code.
- Filesystem path handling or caching (owned by infrastructure.filesystem).
- Domain-specific accounting rules (owned by domain.household, domain.investments, etc.).
"""

from personal_finance_etl.domain.common.calculation import (
    CagrResult,
    CalculationStatus,
    CpiResult,
    XirrResult,
)
from personal_finance_etl.domain.common.dates import (
    DEFAULT_DATE_FORMATS,
    add_fy_if_missing,
    ensure_date_col,
    get_file_name,
    get_fy_folder_name,
    get_fy_start_year,
    get_fy_string,
    get_month_folder_name,
    parse_strict_date,
    to_date_obj,
    validate_and_parse_dates,
)
from personal_finance_etl.domain.common.identity import (
    canonicalize_value,
    generate_deterministic_id,
)
from personal_finance_etl.domain.common.polars import (
    pct_growth,
    rolling_avg,
    rolling_std,
    rolling_sum,
    safe_divide,
)
from personal_finance_etl.domain.common.validation import (
    FinancialSourceValidationError,
    clean_numeric_col,
    parse_strict_numeric,
    validate_and_parse_numerics,
)

__all__ = [
    "DEFAULT_DATE_FORMATS",
    "CagrResult",
    "CalculationStatus",
    "CpiResult",
    "FinancialSourceValidationError",
    "XirrResult",
    "add_fy_if_missing",
    "canonicalize_value",
    "clean_numeric_col",
    "ensure_date_col",
    "generate_deterministic_id",
    "get_file_name",
    "get_fy_folder_name",
    "get_fy_start_year",
    "get_fy_string",
    "get_month_folder_name",
    "parse_strict_date",
    "parse_strict_numeric",
    "pct_growth",
    "rolling_avg",
    "rolling_std",
    "rolling_sum",
    "safe_divide",
    "to_date_obj",
    "validate_and_parse_dates",
    "validate_and_parse_numerics",
]
