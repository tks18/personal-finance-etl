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


def calculate_modified_dietz(
    start_value: float,
    end_value: float,
    cashflows: list[float],
    cashflow_days_remaining: list[float],
    total_days: float,
) -> float:
    """Calculate Modified Dietz absolute return.

    Useful for short time horizons (< 12M) where XIRR converges poorly.
    """
    if total_days <= 0:
        return 0.0

    net_cf = sum(cashflows)
    weighted_cf = sum(
        cf * (days / total_days)
        for cf, days in zip(cashflows, cashflow_days_remaining, strict=False)
    )

    denominator = start_value + weighted_cf
    if denominator == 0:
        return 0.0

    return float((end_value - start_value - net_cf) / denominator)
