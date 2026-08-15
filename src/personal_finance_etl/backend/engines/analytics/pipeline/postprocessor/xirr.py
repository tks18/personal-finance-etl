from datetime import date
from typing import Any

import polars as pl
from pyxirr import xirr

from personal_finance_etl.backend.utils.helpers import to_date_obj


class PortfolioXIRRCalculator:
    """Calculates portfolio XIRR per closing date."""

    @staticmethod
    def calculate(
        unique_dates: list[date],
        global_cashflows: list[dict[str, Any]],
        portfolio_terminals: dict[date, dict[str, float]],
    ) -> pl.DataFrame:
        for cf in global_cashflows:
            cf["date_obj"] = to_date_obj(cf["date"])

        global_cashflows.sort(key=lambda x: x["date_obj"] or date.min)
        cf_ptr = 0
        port_rows: list[dict[str, Any]] = []
        port_dl: list[date] = []
        port_al: list[float] = []

        for d in unique_dates:
            d_obj = to_date_obj(d)
            if not d_obj:
                continue

            while cf_ptr < len(global_cashflows):
                cf = global_cashflows[cf_ptr]
                cf_d = cf["date_obj"]
                if cf_d and cf_d <= d_obj:
                    port_dl.append(cf_d)
                    port_al.append(cf["amount"])
                    cf_ptr += 1
                else:
                    break

            pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
            t_val = pt_entry.get("val", 0.0)
            t_shadow = pt_entry.get("shadow_val", 0.0)
            t_after_tax = pt_entry.get("after_tax_val", 0.0)

            if port_dl:
                port_dl.append(d_obj)
                port_al.append(t_val)
                try:
                    pxirr = xirr(port_dl, port_al) or 0.0
                except Exception:
                    pxirr = 0.0

                bm_port_al = port_al[:-1] + [t_shadow]
                try:
                    bm_pxirr = xirr(port_dl, bm_port_al) or 0.0
                except Exception:
                    bm_pxirr = 0.0

                at_port_al = port_al[:-1] + [t_after_tax]
                try:
                    at_pxirr = xirr(port_dl, at_port_al) or 0.0
                except Exception:
                    at_pxirr = 0.0

                port_dl.pop()
                port_al.pop()
            else:
                pxirr = bm_pxirr = at_pxirr = 0.0

            port_rows.append(
                {
                    "Closing_Date": d,
                    "Portfolio_XIRR": pxirr,
                    "Portfolio_After_Tax_XIRR": at_pxirr,
                    "Portfolio_BM_XIRR": bm_pxirr,
                    "Portfolio_Active_Return": pxirr - bm_pxirr,
                }
            )

        return pl.DataFrame(port_rows)
