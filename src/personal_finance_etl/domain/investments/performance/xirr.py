"""Internal Rate of Return (XIRR) solver and portfolio XIRR series calculator.

Owns
----
- calculate_xirr: Pure mathematical XIRR solver returning a typed XirrResult.
- PortfolioXIRRCalculator: Calculates running portfolio, benchmark, and currency XIRR time-series.
- Re-exports of XirrResult and CalculationStatus.

Does not own
-------------
- Terminal valuation logic (owned by domain.investments.lots).
- Presentation rendering (owned by presentation).
"""

import math
from datetime import date, datetime
from decimal import Decimal
from numbers import Real
from typing import Required, cast

import polars as pl
from pyxirr import xirr

from personal_finance_etl.domain.common.calculation import (
    CalculationStatus as CalculationStatus,
)
from personal_finance_etl.domain.common.calculation import (
    XirrResult as XirrResult,
)
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import CashflowDict, TerminalValueDict


def _validate_xirr_inputs(dates: list[date], amounts: list[float]) -> XirrResult | None:
    """Validate input cashflows and dates for mathematical XIRR solvability.

    Parameters
    ----------
    dates : list[date]
        Cashflow observation dates.
    amounts : list[float]
        Signed cashflow amounts.

    Returns
    -------
    XirrResult | None
        Error result if input is invalid; None if inputs are valid for the solver.
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

    return None


def _execute_xirr_solver(dates: list[date], amounts: list[float]) -> XirrResult:
    """Execute pyxirr solver and map results or exceptions to typed XirrResult.

    Parameters
    ----------
    dates : list[date]
        Observation dates.
    amounts : list[float]
        Signed cashflow amounts.

    Returns
    -------
    XirrResult
        Typed outcome with convergence or error metadata.
    """
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


def calculate_xirr(dates: list[date], amounts: list[float]) -> XirrResult:
    """Calculate XIRR from a list of dates and cashflows.

    Returns an XirrResult with explicit status instead of bare float | NaN so that
    downstream aggregations can distinguish a failed computation from a genuine 0% return.

    Parameters
    ----------
    dates : list[date]
        Chronological cashflow dates.
    amounts : list[float]
        Signed cashflow values.

    Returns
    -------
    XirrResult
        Calculation status and resolved rate of return.
    """
    validation_err = _validate_xirr_inputs(dates, amounts)
    if validation_err is not None:
        return validation_err

    return _execute_xirr_solver(dates, amounts)


def numeric_value(value: object) -> float | None:
    """Return a numeric value as float; reject dates, booleans, and other objects."""
    if value is None or isinstance(value, (bool, date, datetime)):
        return None
    if not isinstance(value, (Real, Decimal)):
        return None
    return float(value)


_numeric_value = numeric_value


class _StoredCashflow(CashflowDict):
    """Internal cashflow record with normalized native date representation."""

    date_obj: Required[date]


def _normalize_and_sort_cashflows(global_cashflows: list[CashflowDict]) -> list[_StoredCashflow]:
    """Parse and sort global cashflows by native date object.

    Parameters
    ----------
    global_cashflows : list[CashflowDict]
        Raw input cashflow dictionaries.

    Returns
    -------
    list[_StoredCashflow]
        Chronologically sorted cashflow records.
    """
    cashflows: list[_StoredCashflow] = []
    for cf in global_cashflows:
        parsed_cf_date = to_date_obj(cf.get("date"))
        if parsed_cf_date is None:
            raise ValueError(
                f"Portfolio cashflow has an invalid or missing date: {cf.get('date')!r}"
            )
        cashflows.append(_StoredCashflow(**cf, date_obj=parsed_cf_date))
    cashflows.sort(key=lambda item: item["date_obj"])
    return cashflows


def _terminal_result(
    dates: list[date], amounts: list[float], terminal: float | None, as_of: date
) -> float | None:
    """Calculate portfolio XIRR including terminal valuation cashflow on closing date."""
    if terminal is None:
        return None
    result = calculate_xirr(dates + [as_of], amounts + [terminal])
    return result.value


def _build_evaluation_row(
    d_obj: date,
    port_dates: list[date],
    port_amounts: list[float],
    local_amounts: list[float],
    benchmark_amounts: list[float],
    benchmark_local_amounts: list[float],
    pt_entry: dict[str, object],
) -> dict[str, object]:
    """Derive Mark-to-Market XIRR metrics and attribution differentials for a single date.

    Parameters
    ----------
    d_obj : date
        Evaluation date.
    port_dates : list[date]
        Accumulated cashflow dates.
    port_amounts : list[float]
        Accumulated INR cashflow amounts.
    local_amounts : list[float]
        Accumulated local currency cashflow amounts.
    benchmark_amounts : list[float]
        Accumulated benchmark shadow cashflow amounts.
    benchmark_local_amounts : list[float]
        Accumulated benchmark shadow local cashflow amounts.
    pt_entry : dict[str, object]
        Terminal valuation snapshot for the date.

    Returns
    -------
    dict[str, object]
        Calculated portfolio XIRR series row.
    """
    t_val = _numeric_value(pt_entry.get("val"))
    t_shadow = _numeric_value(pt_entry.get("shadow_val"))
    t_after_tax = _numeric_value(pt_entry.get("after_tax_val", t_val))
    t_val_local = _numeric_value(pt_entry.get("val_local", t_val))
    t_shadow_local = _numeric_value(pt_entry.get("shadow_val_local"))

    pxirr = _terminal_result(port_dates, port_amounts, t_val, d_obj)
    at_pxirr = _terminal_result(port_dates, port_amounts, t_after_tax, d_obj)
    pxirr_local = _terminal_result(port_dates, local_amounts, t_val_local, d_obj)
    bm_pxirr = _terminal_result(port_dates, benchmark_amounts, t_shadow, d_obj)
    bm_pxirr_local = _terminal_result(port_dates, benchmark_local_amounts, t_shadow_local, d_obj)

    def opt_diff(left: float | None, right: float | None) -> float | None:
        return left - right if left is not None and right is not None else None

    return {
        "Closing_Date": d_obj,
        "Portfolio_XIRR": pxirr,
        "Portfolio_After_Tax_XIRR": at_pxirr,
        "Portfolio_BM_XIRR": bm_pxirr,
        "Portfolio_Active_Return": opt_diff(pxirr, bm_pxirr),
        "XIRR_Local": pxirr_local,
        "FX_XIRR_Impact": opt_diff(pxirr, pxirr_local),
        "BM_XIRR_Local": bm_pxirr_local,
        "Active_Return_Local": opt_diff(pxirr_local, bm_pxirr_local),
    }


class PortfolioXIRRCalculator:
    """Calculate portfolio and benchmark XIRR without inventing zero returns."""

    @staticmethod
    def calculate(
        unique_dates: list[date],
        global_cashflows: list[CashflowDict],
        portfolio_terminals: dict[date, TerminalValueDict] | dict[date, dict[str, float]],
    ) -> pl.DataFrame:
        """Calculate running portfolio, benchmark, after-tax, and local currency XIRR time-series.

        Parameters
        ----------
        unique_dates : list[date]
            Chronological evaluation dates.
        global_cashflows : list[CashflowDict]
            Chronological portfolio cashflows including purchase, sale, and distribution flows.
        portfolio_terminals : dict[date, TerminalValueDict] | dict[date, dict[str, float]]
            Mapping of closing date to mark-to-market terminal valuations.

        Returns
        -------
        pl.DataFrame
            DataFrame keyed by Closing_Date with Port_XIRR, BM_XIRR, Local_XIRR,
            Local_BM_XIRR, After_Tax_XIRR, Active_Return, and FX_Impact metrics.
        """
        cashflows = _normalize_and_sort_cashflows(global_cashflows)

        cf_ptr = 0
        port_rows: list[dict[str, object]] = []
        port_dates: list[date] = []
        port_amounts: list[float] = []
        local_amounts: list[float] = []
        benchmark_amounts: list[float] = []
        benchmark_local_amounts: list[float] = []

        for d in unique_dates:
            d_obj = to_date_obj(d)
            if d_obj is None:
                continue

            while cf_ptr < len(cashflows):
                cf = cashflows[cf_ptr]
                cf_date: date = cf["date_obj"]
                if cf_date <= d_obj:
                    amount = _numeric_value(cf.get("amount"))
                    local_amount = _numeric_value(cf.get("amount_local", cf.get("amount")))
                    benchmark_amount = _numeric_value(cf.get("benchmark_amount"))
                    benchmark_local_amount = _numeric_value(cf.get("benchmark_amount_local"))

                    port_amounts.append(amount if amount is not None else float("nan"))
                    local_amounts.append(local_amount if local_amount is not None else float("nan"))
                    benchmark_amounts.append(
                        benchmark_amount if benchmark_amount is not None else float("nan")
                    )
                    benchmark_local_amounts.append(
                        benchmark_local_amount
                        if benchmark_local_amount is not None
                        else float("nan")
                    )
                    port_dates.append(cf_date)
                    cf_ptr += 1
                else:
                    break

            pt_entry = portfolio_terminals.get(d_obj) or {}
            row = _build_evaluation_row(
                d_obj=d_obj,
                port_dates=port_dates,
                port_amounts=port_amounts,
                local_amounts=local_amounts,
                benchmark_amounts=benchmark_amounts,
                benchmark_local_amounts=benchmark_local_amounts,
                pt_entry=cast(dict[str, object], pt_entry),
            )
            port_rows.append(row)

        return pl.DataFrame(
            port_rows,
            schema={
                "Closing_Date": pl.Date,
                "Portfolio_XIRR": pl.Float64,
                "Portfolio_After_Tax_XIRR": pl.Float64,
                "Portfolio_BM_XIRR": pl.Float64,
                "Portfolio_Active_Return": pl.Float64,
                "XIRR_Local": pl.Float64,
                "FX_XIRR_Impact": pl.Float64,
                "BM_XIRR_Local": pl.Float64,
                "Active_Return_Local": pl.Float64,
            },
        )


__all__ = [
    "CalculationStatus",
    "PortfolioXIRRCalculator",
    "XirrResult",
    "calculate_xirr",
    "numeric_value",
]
