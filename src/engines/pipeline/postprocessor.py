"""
Pipeline PostProcessor.
Handles Portfolio-level calculations and lazy Polars joins.
"""

import bisect
from datetime import date
import polars as pl
from pyxirr import xirr

from src.engines.pipeline.context import RunContext
from src.utils.helpers import to_date_obj


class PostProcessor:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def run(self, lazy_df: pl.LazyFrame, unique_dates: list[date],
            global_cashflows: list[dict], portfolio_terminals: dict[date, dict],
            realized_events: list[dict]) -> pl.LazyFrame:
        """
        Calculates portfolio metrics and lazily attaches them to the lot-level DataFrame.
        """

        # 1. Portfolio XIRR per closing date
        global_cashflows.sort(key=lambda x: x["date"])
        cf_ptr = 0
        port_rows = []
        port_dl: list[date] = []
        port_al: list[float] = []

        for d in unique_dates:
            d_obj = to_date_obj(d)
            if not d_obj:
                continue

            while cf_ptr < len(global_cashflows):
                cf_d = to_date_obj(global_cashflows[cf_ptr]["date"])
                if cf_d and cf_d <= d_obj:
                    port_dl.append(cf_d)
                    port_al.append(global_cashflows[cf_ptr]["amount"])
                    cf_ptr += 1
                else:
                    break

            pt_entry = portfolio_terminals.get(
                d_obj, portfolio_terminals.get(d, {}))
            t_val = pt_entry.get("val", 0.0)
            t_shadow = pt_entry.get("shadow_val", 0.0)

            if port_dl:
                port_dl.append(d_obj)
                port_al.append(t_val)
                try:
                    pxirr = xirr(port_dl, port_al) or 0.0
                except Exception:
                    pxirr = 0.0

                port_al[-1] = t_shadow
                try:
                    bm_pxirr = xirr(port_dl, port_al) or 0.0
                except Exception:
                    bm_pxirr = 0.0

                port_dl.pop()
                port_al.pop()
            else:
                pxirr = bm_pxirr = 0.0

            port_rows.append({
                "Closing_Date": d,
                "Portfolio_XIRR": pxirr,
                "Portfolio_BM_XIRR": bm_pxirr,
                "Portfolio_Active_Return": pxirr - bm_pxirr,
            })

        lazy_df = lazy_df.join(pl.DataFrame(
            port_rows).lazy(), on="Closing_Date", how="left")

        # 2. Portfolio weights
        instr_val = (
            lazy_df
            .group_by(["Closing_Date", "ISIN"])
            .agg(pl.col("Close_Value").sum().alias("Instrument_Close_Value"))
        )
        port_tot = (
            instr_val
            .group_by("Closing_Date")
            .agg(pl.col("Instrument_Close_Value").sum().alias("Total_Portfolio_Value"))
        )
        instr_val = (
            instr_val
            .join(port_tot, on="Closing_Date", how="left")
            .with_columns(
                (pl.col("Instrument_Close_Value") / pl.col("Total_Portfolio_Value"))
                .round(8)
                .alias("Portfolio_Weight_%")
            )
        )
        lazy_df = lazy_df.join(
            instr_val.select(
                ["Closing_Date", "ISIN", "Instrument_Close_Value", "Portfolio_Weight_%"]),
            on=["Closing_Date", "ISIN"],
            how="left",
        )
        lazy_df = lazy_df.join(
            port_tot,
            on="Closing_Date",
            how="left",
        ).with_columns(
            (pl.col("Close_Value") / pl.col("Total_Portfolio_Value"))
            .round(8)
            .alias("Lot_Weight_%")
        ).drop("Total_Portfolio_Value", "Instrument_Close_Value")

        # 3. FY realized gains (bisect)
        realized_events.sort(key=lambda x: x["date"])
        re_dates = [e["date"] for e in realized_events]

        fy_rows = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if not d_obj:
                continue
            fy_sy = d_obj.year if d_obj.month >= 4 else d_obj.year - 1
            fy_start = date(fy_sy, 4, 1)

            right = bisect.bisect_right(re_dates, d_obj)
            left = bisect.bisect_left(re_dates,  fy_start, 0, right)

            ltcg_sum = stcg_sum = loss_sum = 0.0
            equity_ltcg_sum = 0.0
            for ev in realized_events[left:right]:
                g, gt = ev["gain"], ev["gain_type"]
                tt = ev.get("tax_type", "equity").lower()
                if gt == "LTCG" and g > 0:
                    ltcg_sum += g
                    if tt == "equity":
                        equity_ltcg_sum += g
                elif gt == "STCG" and g > 0:
                    stcg_sum += g
                elif g < 0:
                    loss_sum += g

            exemption_limit = self.ctx.fy_table.get_equity_ltcg_exemption(
                fy_start)

            fy_rows.append({
                "Closing_Date": d,
                "FY": f"{fy_sy}-{str(fy_sy + 1)[-2:]}",
                "FY_Realized_LTCG": round(ltcg_sum, 4),
                "FY_Realized_STCG": round(stcg_sum, 4),
                "FY_Realized_Loss": round(loss_sum, 4),
                "FY_LTCG_Remaining_Exemption": round(max(0.0, exemption_limit - equity_ltcg_sum), 4),
            })

        lazy_df = lazy_df.join(pl.DataFrame(
            fy_rows).lazy(), on="Closing_Date", how="left")

        # 4. Stepup eligible flag
        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("FY_LTCG_Remaining_Exemption"))
            ).alias("Stepup_Eligible")
        )

        # 5. Harvest recommendation
        lazy_df = lazy_df.with_columns(
            pl.when(pl.col("Unrealized_Loss") < 0)
              .then(pl.lit("HARVEST_LOSS"))
            .when(pl.col("Holding_Type") == "LTCG", pl.col("Stepup_Eligible"))
              .then(pl.lit("HARVEST_LTCG_EXEMPT"))
            .when(
                (pl.col("Holding_Type") == "STCG")
                & (pl.col("Days_To_LTCG") > 0)
                & (pl.col("Days_To_LTCG") <= 90)
                & (pl.col("P/L") > 0)
            )
            .then(pl.lit("WAIT_FOR_LTCG"))
            .otherwise(pl.lit("HOLD"))
            .alias("Harvest_Recommendation")
        )

        return lazy_df
