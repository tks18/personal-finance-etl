from datetime import date

from pyxirr import xirr


def calculate_cagr(start_value: float, end_value: float, days: int) -> float:
    """Calculate annualized CAGR. Returns 0.0 if inputs are invalid."""
    if start_value <= 0 or end_value <= 0 or days <= 0:
        return 0.0
    try:
        return float(((end_value / start_value) ** (365.0 / days)) - 1)
    except OverflowError:
        return float(
            "nan"
        )  # Astronomical return — NaN is safer than a sentinel to avoid polluting aggregations


def calculate_xirr(dates: list[date], amounts: list[float]) -> float:
    """Calculate XIRR strictly from a list of dates and cashflows.

    Returns NaN on convergence failure or degenerate cashflows so that downstream
    aggregations (averages, ratios) can distinguish a failed computation from a
    genuine 0% return.
    """
    try:
        result = xirr(dates, amounts)
        return float(result) if result is not None else float("nan")
    except Exception:
        return float("nan")
