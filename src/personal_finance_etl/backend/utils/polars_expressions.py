"""DEPRECATED - Legacy Polars expressions shim module.

This module has been deactivated as part of Phase 2 of the Grand Refactor.
Canonical pure analytical Polars expressions now reside in:
`personal_finance_etl.domain.common.polars`

This file is maintained strictly as a backwards-compatible pass-through delegation shim.
Do not edit or add logic here.
"""

from personal_finance_etl.domain.common.polars import (
    pct_growth,
    rolling_avg,
    rolling_std,
    rolling_sum,
    safe_divide,
)

__all__ = [
    "pct_growth",
    "rolling_avg",
    "rolling_std",
    "rolling_sum",
    "safe_divide",
]
