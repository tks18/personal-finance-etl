from datetime import date

import numpy as np
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


def _compute_risk_adjusted(
    r: np.ndarray,
    periods_per_year: float,
    risk_free_rate: float,
) -> tuple[float, float, float, float]:
    """
    Compute Sharpe, Sortino, Calmar, Max Drawdown for a periodic return series.
    Returns: (sharpe, sortino, calmar, max_drawdown)
    """
    ZERO = 0.0
    n = len(r)
    if n < 2:
        return ZERO, ZERO, ZERO, ZERO

    sqrt_p = periods_per_year**0.5

    ann_mean = float(np.mean(r)) * periods_per_year
    ann_std = float(np.std(r, ddof=1)) * sqrt_p

    # Sortino: semi-deviation — std computed only over negative return observations.
    # Using np.where(..., 0.0) would include the zeroed positive returns in the
    # sample-size denominator, inflating n and deflating std, which overstates
    # the Sortino ratio. Filtering to negatives-only is the correct definition.
    down_r = r[r < 0]
    ann_down_std = (float(np.std(down_r, ddof=1)) * sqrt_p) if len(down_r) > 1 else ZERO

    # Max Drawdown via cumulative product peak-to-trough
    cum = np.cumprod(1.0 + r)
    roll_max = np.maximum.accumulate(cum)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = np.where(roll_max > 0, (cum - roll_max) / roll_max, 0.0)
    max_dd = float(np.min(dd))

    # Annualized geometric return for Calmar
    try:
        ann_geom = float(np.prod(1.0 + r) ** (periods_per_year / n)) - 1.0
    except (OverflowError, ZeroDivisionError):
        ann_geom = ann_mean

    sharpe = (ann_mean - risk_free_rate) / ann_std if ann_std > 0 else ZERO
    sortino = (ann_mean - risk_free_rate) / ann_down_std if ann_down_std > 0 else ZERO
    calmar = ann_geom / abs(max_dd) if max_dd < -1e-4 else ZERO

    return sharpe, sortino, calmar, max_dd


def calculate_risk_metrics(
    inst_returns: dict[date, float],
    bm_returns: dict[date, float],
    past_dates: list[date],
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float, float]:
    """
    Calculate risk metrics for instrument and benchmark return series.

    Returns:
        (beta, t_err_ann, up_capture, down_capture,
         inst_sharpe, inst_sortino, inst_calmar, inst_max_dd,
         bm_sharpe,   bm_sortino,   bm_calmar,   bm_max_dd)
    """
    ZERO = 0.0
    ZEROS_12: tuple[float, ...] = (ZERO,) * 12
    if len(past_dates) <= 2:
        return ZEROS_12  # type: ignore[return-value]

    ira_list = [inst_returns[d] for d in past_dates if d in inst_returns]
    bra_list = [bm_returns[d] for d in past_dates if d in bm_returns]

    if len(ira_list) <= 1 or len(ira_list) != len(bra_list):
        return ZEROS_12  # type: ignore[return-value]

    ira = np.array(ira_list)
    bra = np.array(bra_list)

    # --- Beta ---
    beta = ZERO
    cmat = np.cov(ira, bra)
    if cmat[1, 1] != 0:
        beta = float(cmat[0, 1] / cmat[1, 1])

    # --- Tracking Error (annualised) ---
    t_err_raw = float(np.std(ira - bra, ddof=1))
    t_err_ann = t_err_raw * (periods_per_year**0.5)

    # --- Upside / Downside Capture ---
    up_c = dn_c = ZERO
    up_idx = bra > 0
    if np.any(up_idx):
        bru = float(np.prod(1 + bra[up_idx])) - 1
        if bru != 0:
            up_c = (float(np.prod(1 + ira[up_idx])) - 1) / bru
    dn_idx = bra < 0
    if np.any(dn_idx):
        brd = float(np.prod(1 + bra[dn_idx])) - 1
        if brd != 0:
            dn_c = (float(np.prod(1 + ira[dn_idx])) - 1) / brd

    # --- Risk-Adjusted Ratios (instrument & benchmark) ---
    inst_sharpe, inst_sortino, inst_calmar, inst_max_dd = _compute_risk_adjusted(
        ira, periods_per_year, risk_free_rate
    )
    bm_sharpe, bm_sortino, bm_calmar, bm_max_dd = _compute_risk_adjusted(
        bra, periods_per_year, risk_free_rate
    )

    return (
        beta,
        t_err_ann,
        up_c,
        dn_c,
        inst_sharpe,
        inst_sortino,
        inst_calmar,
        inst_max_dd,
        bm_sharpe,
        bm_sortino,
        bm_calmar,
        bm_max_dd,
    )
