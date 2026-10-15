"""Investment returns and compound growth calculation algorithms.

Owns
----
- calculate_cagr: Annualized Compound Annual Growth Rate computation with explicit status.
- Re-exports of CagrResult and CalculationStatus.

Does not own
-------------
- Cashflow internal rate of return (owned by domain.investments.performance.xirr).
- Lot state traversal (owned by domain.investments.lots).
"""

import math

from personal_finance_etl.domain.common.calculation import (
    CagrResult as CagrResult,
)
from personal_finance_etl.domain.common.calculation import (
    CalculationStatus as CalculationStatus,
)


def calculate_cagr(start_value: float, end_value: float, days: int) -> CagrResult:
    """Calculate annualised Compound Annual Growth Rate (CAGR).

    CAGR = (end_value / start_value) ^ (365 / days) − 1

    Returns CagrResult with explicit status instead of bare float 0.0 so callers
    can distinguish genuine flat returns (0.0% with VALID) from invalid or undefined inputs.

    Parameters
    ----------
    start_value:
        Cost basis or opening value. Must be > 0.
    end_value:
        Current market value. Must be > 0.
    days:
        Holding duration in calendar days. Must be > 0.
    """
    if not math.isfinite(start_value) or not math.isfinite(end_value):
        return CagrResult(
            value=None,
            status=CalculationStatus.INVALID_INPUT,
            reason="Non-finite input values in CAGR calculation",
        )
    if start_value <= 0:
        return CagrResult(
            value=None,
            status=CalculationStatus.INVALID_INPUT,
            reason=f"Start value must be positive, got {start_value}",
        )
    if end_value <= 0:
        return CagrResult(
            value=None,
            status=CalculationStatus.INVALID_INPUT,
            reason=f"End value must be positive, got {end_value}",
        )
    if days <= 0:
        return CagrResult(
            value=None,
            status=CalculationStatus.UNDEFINED,
            reason=f"Holding duration must be positive days, got {days}",
        )
    try:
        val = float(((end_value / start_value) ** (365.0 / days)) - 1.0)
        if not math.isfinite(val):
            return CagrResult(
                value=None,
                status=CalculationStatus.COMPUTATION_ERROR,
                reason="Calculated CAGR is non-finite",
            )
        return CagrResult(value=val, status=CalculationStatus.VALID)
    except OverflowError:
        return CagrResult(
            value=None,
            status=CalculationStatus.COMPUTATION_ERROR,
            reason="Arithmetic overflow in CAGR calculation",
        )


__all__ = [
    "CagrResult",
    "CalculationStatus",
    "calculate_cagr",
]
