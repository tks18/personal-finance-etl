from datetime import date, datetime
from decimal import Decimal
from numbers import Real
from typing import Any

import polars as pl

from personal_finance_etl.backend.engines.analytics.core.math import calculate_xirr
from personal_finance_etl.backend.utils.helpers import to_date_obj


def _numeric_value(value: object) -> float | None:
    """Return a numeric value as float; reject dates, booleans, and other objects."""
    if value is None or isinstance(value, (bool, date, datetime)):
        return None
    if not isinstance(value, (Real, Decimal)):
        return None
    return float(value)


class PortfolioXIRRCalculator:
    """Calculate portfolio and benchmark XIRR without inventing zero returns."""

    @staticmethod
    def calculate(
        unique_dates: list[date],
        global_cashflows: list[dict[str, Any]],
        portfolio_terminals: dict[date, dict[str, float]],
    ) -> pl.DataFrame:
        # Normalize once so every stored cashflow date is known to be a real date.
        cashflows: list[dict[str, Any]] = []
        for cf in global_cashflows:
            parsed_cf_date = to_date_obj(cf.get("date"))
            if parsed_cf_date is None:
                raise ValueError(
                    f"Portfolio cashflow has an invalid or missing date: {cf.get('date')!r}"
                )
            cashflows.append({**cf, "date_obj": parsed_cf_date})
        cashflows.sort(key=lambda item: item["date_obj"])

        cf_ptr = 0
        port_rows: list[dict[str, Any]] = []
        port_dates: list[date] = []
        port_amounts: list[float] = []
        local_amounts: list[float] = []
        benchmark_amounts: list[float] = []
        benchmark_local_amounts: list[float] = []

        def optional_difference(left: float | None, right: float | None) -> float | None:
            return left - right if left is not None and right is not None else None

        def terminal_result(
            dates: list[date], amounts: list[float], terminal: float | None, as_of: date
        ) -> float | None:
            if terminal is None:
                return None
            result = calculate_xirr(dates + [as_of], amounts + [terminal])
            return result.value

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
                    # Preserve invalid/missing evidence as NaN so XIRR returns a diagnostic null.
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

            pt_entry = portfolio_terminals.get(d_obj, {})
            t_val = _numeric_value(pt_entry.get("val"))
            t_shadow = _numeric_value(pt_entry.get("shadow_val"))
            t_after_tax = _numeric_value(pt_entry.get("after_tax_val", t_val))
            t_val_local = _numeric_value(pt_entry.get("val_local", t_val))
            t_shadow_local = _numeric_value(pt_entry.get("shadow_val_local"))

            pxirr = terminal_result(port_dates, port_amounts, t_val, d_obj)
            at_pxirr = terminal_result(port_dates, port_amounts, t_after_tax, d_obj)
            pxirr_local = terminal_result(port_dates, local_amounts, t_val_local, d_obj)
            bm_pxirr = terminal_result(port_dates, benchmark_amounts, t_shadow, d_obj)
            bm_pxirr_local = terminal_result(
                port_dates, benchmark_local_amounts, t_shadow_local, d_obj
            )

            port_rows.append(
                {
                    "Closing_Date": d_obj,
                    "Portfolio_XIRR": pxirr,
                    "Portfolio_After_Tax_XIRR": at_pxirr,
                    "Portfolio_BM_XIRR": bm_pxirr,
                    "Portfolio_Active_Return": optional_difference(pxirr, bm_pxirr),
                    "XIRR_Local": pxirr_local,
                    "FX_XIRR_Impact": optional_difference(pxirr, pxirr_local),
                    "BM_XIRR_Local": bm_pxirr_local,
                    "Active_Return_Local": optional_difference(pxirr_local, bm_pxirr_local),
                }
            )

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
