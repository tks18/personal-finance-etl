import math
from datetime import date

from pyxirr import xirr

from personal_finance_etl.backend.types.calculation import XirrResult


def calculate_cagr(start_value: float, end_value: float, days: int) -> float:
    """Calculate annualised Compound Annual Growth Rate (CAGR).

    CAGR = (end_value / start_value) ^ (365 / days) − 1

    Returns 0.0 for degenerate inputs (non-positive values or zero duration).
    Returns NaN on arithmetic overflow (e.g. astronomical synthetic returns)
    so that the bad value propagates visibly through aggregations rather than
    being silently clamped.

    Parameters
    ----------
    start_value:
        Cost basis or opening value. Must be > 0.
    end_value:
        Current market value. Must be > 0.
    days:
        Holding duration in calendar days. Must be > 0.
    """
    if start_value <= 0 or end_value <= 0 or days <= 0:
        return 0.0
    try:
        return float(((end_value / start_value) ** (365.0 / days)) - 1)
    except OverflowError:
        return float(
            "nan"
        )  # Astronomical return — NaN is safer than a sentinel to avoid polluting aggregations


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
