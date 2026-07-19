import numpy as np
from datetime import date
from pyxirr import xirr


def calculate_cagr(start_value: float, end_value: float, days: int) -> float:
    """Calculate annualized CAGR. Returns 0.0 if inputs are invalid."""
    if start_value <= 0 or end_value <= 0 or days <= 0:
        return 0.0
    try:
        return float(((end_value / start_value) ** (365.0 / days)) - 1)
    except OverflowError:
        return 9999.0  # Cap astronomical annualized returns


def calculate_xirr(dates: list[date], amounts: list[float]) -> float:
    """Calculate XIRR strictly from a list of dates and cashflows."""
    try:
        return xirr(dates, amounts) or 0.0
    except Exception:
        return 0.0


def calculate_risk_metrics(
    inst_returns: dict[date, float],
    bm_returns: dict[date, float],
    past_dates: list[date],
    periods_per_year: float
) -> tuple[float, float, float, float]:
    """
    Calculate Beta, Tracking Error (Ann), Upside Capture, and Downside Capture.
    Returns: (beta, t_err_ann, up_capture, down_capture)
    """
    if len(past_dates) <= 2:
        return 0.0, 0.0, 0.0, 0.0

    ira_list = [inst_returns[d] for d in past_dates if d in inst_returns]
    bra_list = [bm_returns[d] for d in past_dates if d in bm_returns]

    if len(ira_list) <= 1 or len(ira_list) != len(bra_list):
        return 0.0, 0.0, 0.0, 0.0

    ira = np.array(ira_list)
    bra = np.array(bra_list)

    beta = up_c = down_c = 0.0

    # Beta
    cmat = np.cov(ira, bra)
    if cmat[1, 1] != 0:
        beta = cmat[0, 1] / cmat[1, 1]

    # Tracking Error
    t_err_raw = float(np.std(ira - bra, ddof=1))
    t_err_ann = t_err_raw * (periods_per_year ** 0.5)

    # Upside Capture
    up_idx = bra > 0
    if np.any(up_idx):
        bru = float(np.prod(1 + bra[up_idx])) - 1
        if bru != 0:
            up_c = (float(np.prod(1 + ira[up_idx])) - 1) / bru

    # Downside Capture
    dn_idx = bra < 0
    if np.any(dn_idx):
        brd = float(np.prod(1 + bra[dn_idx])) - 1
        if brd != 0:
            down_c = (float(np.prod(1 + ira[dn_idx])) - 1) / brd

    return beta, t_err_ann, up_c, down_c
