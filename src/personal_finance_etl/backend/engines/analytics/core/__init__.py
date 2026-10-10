"""Analytics engine core module.

Public API
----------
``calculate_cagr``   — annualised CAGR from start/end value and days.
``calculate_xirr``   — XIRR solver returning a typed ``XirrResult``.
``XirrResult``       — re-exported from ``types.calculation`` for convenience.
"""

from personal_finance_etl.backend.engines.analytics.core.math import (
    calculate_cagr,
    calculate_xirr,
)
from personal_finance_etl.backend.types.calculation import XirrResult

__all__ = [
    "calculate_cagr",
    "calculate_xirr",
    "XirrResult",
]

