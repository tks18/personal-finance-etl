"""
Pipeline Processor.
Handles the per-ISIN processing logic.
"""

from datetime import date, datetime, timedelta
from typing import cast

import polars as pl

from src.engines.core.fifo import FIFOPortfolio
from src.engines.core.math import calculate_cagr, calculate_risk_metrics, calculate_xirr
from src.engines.pipeline.context import RunContext
from src.engines.rules.tax import get_ltcg_threshold
from src.utils.helpers import to_date_obj


class IsinProcessor:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def process(self, isin: str) -> tuple[pl.DataFrame | None, list[dict], dict, list[dict]]:
        """
        Processes a single ISIN.
        Returns:
            - snapshot_df: A Polars DataFrame with the snapshot rows for this ISIN, or None.
            - isin_cashflows: list of cashflow dicts {"date": dt, "amount": val}
            - isin_terminals: dict mapping dates to {"val": val, "shadow_val": s_val}
            - isin_realized: list of realized event dicts
        """
        df_p = self.ctx.df_p
        df_s = self.ctx.df_s
        df_m = self.ctx.df_m
        df_b = self.ctx.df_b
        isin_master = self.ctx.isin_master
        fy_table = self.ctx.fy_table

        p_inst = df_p.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()
        s_inst = df_s.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()

        m_inst = (
            df_m.filter(pl.col("ISIN") == isin)
            .sort("Date")
            .group_by("Date", maintain_order=True)
            .agg(
                [
                    pl.col("Quantity").sum().alias("Quantity"),
                    pl.col("Closing Price").last().alias("Closing Price"),
                    pl.col("Buy Value").sum().alias("Buy Value"),
                ]
            )
            .to_dicts()
        )
        if not m_inst:
            return None, [], {}, []

        master_row = isin_master.get(isin, {})
        tax_type = str(master_row.get("TAX_TYPE", "equity"))
        tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        bench_id = master_row.get("BENCHMARK_ID")

        bm_price_map: dict[date, float] = {}
        if df_b is not None and bench_id and str(bench_id).strip():
            try:
                b_subset = df_b.filter(pl.col("ID").cast(pl.String) == str(bench_id).strip()).sort(
                    "Date"
                )
                last_date, last_price = None, None
                for row in b_subset.select(["Date", "Close"]).to_dicts():
                    d_val = row["Date"]
                    if not isinstance(d_val, date):
                        d_val = to_date_obj(d_val)
                    if d_val:
                        p_val = float(row["Close"])
                        if last_date is not None and last_price is not None:
                            curr = last_date + timedelta(days=1)
                            while curr < d_val:
                                bm_price_map[curr] = last_price
                                curr += timedelta(days=1)
                        bm_price_map[d_val] = p_val
                        last_date, last_price = d_val, p_val
            except Exception:
                pass

        def get_bm_price(dt: date) -> float | None:
            dt_val = (
                dt if isinstance(dt, date) and not isinstance(dt, datetime) else to_date_obj(dt)
            )
            if dt_val is None:
                return None
            return bm_price_map.get(dt_val)

        inst_px: dict[date, float] = {}
        for m_row in m_inst:
            d = to_date_obj(m_row["Date"])
            if d:
                inst_px[d] = float(m_row["Closing Price"])
        valid_dates = sorted(inst_px.keys())

        inst_ret_map: dict[date, float] = {}
        bm_ret_map: dict[date, float] = {}
        if len(valid_dates) > 1:
            for k in range(1, len(valid_dates)):
                d_c, d_p = valid_dates[k], valid_dates[k - 1]
                pc, pp = inst_px[d_c], inst_px[d_p]
                bmc, bmp = get_bm_price(d_c), get_bm_price(d_p)
                if pp > 0 and bmc and bmp and bmp > 0:
                    inst_ret_map[d_c] = (pc - pp) / pp
                    bm_ret_map[d_c] = (bmc - bmp) / bmp

        if len(valid_dates) > 1:
            span_days = (valid_dates[-1] - valid_dates[0]).days
            avg_gap = span_days / (len(valid_dates) - 1)
            periods_per_year = 365.0 / max(avg_gap, 0.5)
        else:
            periods_per_year = 252.0

        fifo = FIFOPortfolio(tax_type, tax_subtype, fy_table)
        cf_dates: list[date] = []
        cf_amounts: list[float] = []

        first_p_date = (
            to_date_obj(p_inst[0]["Date"])
            if p_inst
            else (to_date_obj(m_inst[0]["Date"]) if m_inst else None)
        )
        if not first_p_date:
            return None, [], {}, []

        p_idx = s_idx = 0

        isin_cashflows: list[dict[str, float | date]] = []
        isin_terminals: dict[date, dict[str, float]] = {}
        isin_realized: list[dict[str, float | date]] = []
        isin_snapshots: list[dict[str, float | date]] = []

        for m_row in m_inst:
            m_date = to_date_obj(m_row["Date"])
            if not m_date or m_date < first_p_date:
                continue

            while p_idx < len(p_inst):
                row_dt_obj = to_date_obj(p_inst[p_idx]["Date"])
                if row_dt_obj is None or row_dt_obj > m_date:
                    break
                row = p_inst[p_idx]
                qty = float(row["Quantity"])
                b_price = float(row["Price"])

                v_val = row.get("Value")
                buy_val = float(v_val) if v_val is not None else float(qty * b_price)

                bm_p = get_bm_price(row_dt_obj)
                shadow_q = buy_val / bm_p if (bm_p and bm_p > 0) else 0.0

                fifo.buy(row_dt_obj, qty, b_price, shadow_q, float(bm_p or 0.0))
                cf_dates.append(row_dt_obj)
                cf_amounts.append(-buy_val)
                isin_cashflows.append({"date": row_dt_obj, "amount": -buy_val})
                p_idx += 1

            while s_idx < len(s_inst):
                row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
                if row_dt_obj is None or row_dt_obj > m_date:
                    break
                row = s_inst[s_idx]
                s_qty = float(row["Quantity"])

                row_p_val: float | None = row.get("Price")
                s_price = (
                    float(row_p_val) if row_p_val is not None else float(m_row["Closing Price"])
                )

                sv_val: float | None = row.get("Sell Value")
                s_val = float(sv_val) if sv_val is not None else float(s_qty * s_price)

                cf_dates.append(row_dt_obj)
                cf_amounts.append(s_val)
                isin_cashflows.append({"date": row_dt_obj, "amount": s_val})

                events = fifo.sell(row_dt_obj, s_qty, s_price)
                isin_realized.extend(events)
                s_idx += 1

            cf_recon = fifo.reconcile_quantity(
                m_row.get("Quantity"), m_date, get_bm_price(m_date) or 1.0
            )
            for cf in cf_recon:
                cf_dates.append(cast(date, cf["date"]))
                cf_amounts.append(cast(float, cf["amount"]))

            fifo.reconcile_cost_basis(m_row.get("Buy Value"))

            if not fifo.active_lots:
                continue

            if self.ctx.start_date and m_date < self.ctx.start_date:
                continue
            if self.ctx.end_date and m_date > self.ctx.end_date:
                continue

            m_price = float(m_row["Closing Price"])
            m_bm_price = get_bm_price(m_date) or 1.0

            closing_units = fifo.get_closing_units()
            terminal_val = fifo.get_terminal_value(m_price)
            shadow_terminal_val = fifo.get_shadow_terminal_value(m_bm_price)

            pt = isin_terminals.setdefault(m_date, {"val": 0.0, "shadow_val": 0.0})
            pt["val"] += terminal_val
            pt["shadow_val"] += shadow_terminal_val

            inst_xirr = calculate_xirr(cf_dates + [m_date], cf_amounts + [terminal_val])
            bm_xirr_val = calculate_xirr(cf_dates + [m_date], cf_amounts + [shadow_terminal_val])

            inst_active_return = inst_xirr - bm_xirr_val
            is_lagging = inst_xirr < bm_xirr_val

            inst_cagr = inst_bm_cagr = 0.0
            if closing_units > 0:
                avg_cost = fifo.get_average_cost()
                avg_bm_cost = fifo.get_average_bm_cost()
                inst_age = max((m_date - first_p_date).days, 1)

                if avg_cost > 0:
                    inst_cagr = calculate_cagr(avg_cost, m_price, inst_age)
                if avg_bm_cost > 0:
                    inst_bm_cagr = calculate_cagr(avg_bm_cost, m_bm_price, inst_age)

            past_dates = [d for d in valid_dates if first_p_date <= d <= m_date]
            beta, t_err_ann, up_c, down_c = calculate_risk_metrics(
                inst_ret_map, bm_ret_map, past_dates, periods_per_year
            )

            info_ratio = (inst_active_return / t_err_ann) if t_err_ann != 0 else 0.0

            outperform_cnt = 0
            lot_count = len(fifo.active_lots)
            buffer = []

            for lot in fifo.active_lots:
                if lot.qty <= 1e-8:
                    continue

                lbd = to_date_obj(lot.date)
                age = max((m_date - lbd).days, 1) if lbd else 1

                ltcg_thr = get_ltcg_threshold(tax_type, tax_subtype)
                holding_type = fy_table.get_holding_type(
                    age, tax_type, tax_subtype, lbd or m_date, m_date
                )
                days_to_ltcg = max(0, ltcg_thr - age) if holding_type == "STCG" else 0
                ltcg_rate, stcg_rate = fy_table.get_tax_rates(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )

                lot_return = (m_price - lot.price) / lot.price if lot.price > 0 else 0.0
                lot_cagr = calculate_cagr(lot.price, m_price, age)

                lbm_buy = lot.bm_buy
                if lbm_buy and lbm_buy > 0:
                    lot_bm_ret = (m_bm_price - lbm_buy) / lbm_buy
                    lot_bm_cagr = calculate_cagr(lbm_buy, m_bm_price, age)
                else:
                    lbm_buy = None
                    lot_bm_ret = 0.0
                    lot_bm_cagr = 0.0

                lot_alpha = lot_cagr - lot_bm_cagr
                if lot_alpha > 0:
                    outperform_cnt += 1

                pnl = (m_price - lot.price) * lot.qty
                close_val = lot.qty * m_price
                buy_val_lot = lot.qty * lot.price

                unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
                unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
                unreal_loss = min(0.0, pnl)

                ltcg_tax = unreal_ltcg * ltcg_rate
                stcg_tax = unreal_stcg * stcg_rate
                after_tax_pl = pnl - (ltcg_tax + stcg_tax)
                after_tax_cv = close_val - (ltcg_tax + stcg_tax)

                buffer.append(
                    {
                        "Closing_Date": m_date,
                        "ISIN": isin,
                        "BENCHMARK_ID": bench_id,
                        "TAX_TYPE": tax_type,
                        "TAX_SUBTYPE": tax_subtype,
                        "Buy_Date": lbd,
                        "Age_Days": age,
                        "LTCG_Threshold_Days": ltcg_thr,
                        "Days_To_LTCG": days_to_ltcg,
                        "Holding_Type": holding_type,
                        "Quantity": lot.qty,
                        "Buy_Price": lot.price,
                        "Market_Price": m_price,
                        "Buy_Value": round(buy_val_lot, 4),
                        "Close_Value": round(close_val, 4),
                        "P/L": round(pnl, 4),
                        "Returns_%": round(lot_return, 8),
                        "Lot_CAGR": round(lot_cagr, 8),
                        "CAGR": round(inst_cagr, 8),
                        "XIRR": round(inst_xirr, 8),
                        "BM_Buy_Price": round(lbm_buy, 4) if lbm_buy else None,
                        "BM_Market_Price": round(m_bm_price, 4),
                        "Lot_BM_Returns_%": round(lot_bm_ret, 8),
                        "Lot_BM_CAGR": round(lot_bm_cagr, 8),
                        "BM_CAGR": round(inst_bm_cagr, 8),
                        "BM_XIRR": round(bm_xirr_val, 8),
                        "Active_Return": round(inst_active_return, 8),
                        "Lot_Alpha": round(lot_alpha, 8),
                        "Is_Lagging_Benchmark": is_lagging,
                        "Beta": round(beta, 8),
                        "Tracking_Error": round(t_err_ann, 8),
                        "Information_Ratio": round(info_ratio, 8),
                        "Upside_Capture": round(up_c, 8),
                        "Downside_Capture": round(down_c, 8),
                        "Tax_Rate": ltcg_rate if holding_type == "LTCG" else stcg_rate,
                        "Unrealized_LTCG": round(unreal_ltcg, 4),
                        "Unrealized_STCG": round(unreal_stcg, 4),
                        "Unrealized_Loss": round(unreal_loss, 4),
                        "LTCG_Tax_If_Sold": round(ltcg_tax, 4),
                        "STCG_Tax_If_Sold": round(stcg_tax, 4),
                        "After_Tax_PL": round(after_tax_pl, 4),
                        "After_Tax_Close_Value": round(after_tax_cv, 4),
                    }
                )

            opt_prob = (outperform_cnt / lot_count) if lot_count > 0 else 0.0
            for row in buffer:
                row["Outperformance_Probability"] = round(opt_prob, 8)
                isin_snapshots.append(row)

        schema_overrides = {
            "BM_Buy_Price": pl.Float64,
            "BENCHMARK_ID": pl.String,
            "Buy_Date": pl.Date,
        }
        df = (
            pl.DataFrame(isin_snapshots, schema_overrides=schema_overrides)
            if isin_snapshots
            else None
        )
        return df, isin_cashflows, isin_terminals, isin_realized
