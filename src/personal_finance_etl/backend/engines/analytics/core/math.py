import math
from datetime import date

from pyxirr import xirr

from personal_finance_etl.backend.types.calculation import CagrResult, CalculationStatus, XirrResult


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


def calculate_xirr(dates: list[date], amounts: list[float]) -> XirrResult:
    """Calculate XIRR from a list of dates and cashflows.

    Returns an XirrResult with explicit status instead of bare float | NaN so that
    downstream aggregations can distinguish a failed computation from a genuine 0% return.

    Statuses:
        VALID           — solver converged, value is reliable.
        INVALID_INPUT   — degenerate cashflows (all same sign, empty, < 2 entries).
        UNDEFINED       — solver returned None (e.g. zero-length holding).
        NON_CONVERGENT  — Newton's method did not converge within tolerance.
    """
    if len(dates) != len(amounts):
        return XirrResult(None, "INVALID_INPUT", "Date and amount counts do not match")
    if len(dates) < 2:
        return XirrResult(None, "INVALID_INPUT", "Fewer than 2 cashflow dates")

    try:
        if any(not math.isfinite(float(a)) for a in amounts):
            return XirrResult(
                None, "INVALID_INPUT", "Cashflows contain null, NaN, or infinite amounts"
            )
    except (TypeError, ValueError):
        return XirrResult(None, "INVALID_INPUT", "Cashflows contain non-numeric amounts")

    if any(not d for d in dates):
        return XirrResult(None, "INVALID_INPUT", "Cashflow dates must be date values")

    has_negative = any(a < 0 for a in amounts)
    has_positive = any(a > 0 for a in amounts)
    if not has_negative or not has_positive:
        return XirrResult(None, "INVALID_INPUT", "Cashflows must have both outflows and inflows")

    try:
        result = xirr(dates, amounts)
        if result is None:
            return XirrResult(None, "UNDEFINED", "Solver returned None")
        value = float(result)
        if not math.isfinite(value):
            return XirrResult(None, "UNDEFINED", "Solver returned a non-finite result")
        return XirrResult(value, "VALID")
    except Exception as exc:
        msg = str(exc).lower()
        if "converge" in msg or "iteration" in msg or "newton" in msg:
            return XirrResult(None, "NON_CONVERGENT", str(exc))
        return XirrResult(None, "INVALID_INPUT", str(exc))
