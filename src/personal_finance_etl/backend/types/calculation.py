"""Typed result containers for financial calculations (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All calculation result types have migrated to `personal_finance_etl.domain.common.calculation`.
"""

from personal_finance_etl.domain.common.calculation import (
    CagrResult,
    CalculationStatus,
    CpiResult,
    XirrResult,
)

__all__ = [
    "CagrResult",
    "CalculationStatus",
    "CpiResult",
    "XirrResult",
]
