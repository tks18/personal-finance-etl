from datetime import date
from typing import cast

import polars as pl

from src.engines.analytics.core.fifo import FIFOPortfolio
from src.engines.analytics.core.math import calculate_cagr, calculate_xirr
from src.engines.analytics.pipeline.processor.benchmark import BenchmarkPriceProvider
from src.engines.analytics.pipeline.processor.risk import RiskMetricsProvider
from src.engines.analytics.pipeline.processor.snapshot import SnapshotGenerator
from src.utils.helpers import to_date_obj
from src.utils.logger import logger


class IsinProcessor:
    def __init__(self, fy_table, start_date, end_date, rules):
        self.fy_table = fy_table
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules

    def process(
        self,
        isin: str,
        p_inst: list[dict],
        s_inst: list[dict],
        m_inst: list[dict],
        master_row: dict,
        bm_map: dict,
    ) -> tuple[pl.DataFrame | None, list[dict], dict, list[dict], dict[str, str]]:
        if not m_inst:
            return None, [], {}, [], {}

        logger.debug(f"[Processor] ISIN {isin} computing across {len(m_inst)} historical dates.")

        tax_type = str(master_row.get("TAX_TYPE", "equity"))
        tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        bench_id = master_row.get("BENCHMARK_ID")

        bm_provider = BenchmarkPriceProvider(bench_id, None, prebuilt_map=bm_map)
        risk_provider = RiskMetricsProvider(m_inst, bm_provider)
        snapshot_generator = SnapshotGenerator(self.fy_table, self.rules, isin, master_row)

        fifo = FIFOPortfolio(tax_type, tax_subtype, self.fy_table)
        cf_dates: list[date] = []
        cf_amounts: list[float] = []

        first_p_date = (
            to_date_obj(p_inst[0]["Date"])
            if p_inst
            else (to_date_obj(m_inst[0]["Date"]) if m_inst else None)
        )
        if not first_p_date:
            return None, [], {}, [], {}

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

                bm_p = bm_provider.get_bm_price(row_dt_obj)
                if not bm_p or bm_p <= 0:
                    bm_p = b_price
                shadow_q = buy_val / bm_p if bm_p > 0 else 0.0

                fifo.buy(row_dt_obj, qty, b_price, shadow_q, float(bm_p))
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
                sv_val: float | None = row.get("Sell Value")
                
                if row_p_val is not None:
                    s_price = float(row_p_val)
                elif sv_val is not None and s_qty > 0:
                    s_price = float(sv_val) / s_qty
                else:
                    s_price = float(m_row.get("Closing Price", 0.0))

                s_val = float(sv_val) if sv_val is not None else float(s_qty * s_price)

                cf_dates.append(row_dt_obj)
                cf_amounts.append(s_val)
                isin_cashflows.append({"date": row_dt_obj, "amount": s_val})

                events = fifo.sell(row_dt_obj, s_qty, s_price)
                isin_realized.extend(events)
                s_idx += 1

            m_recon_bm_price = bm_provider.get_bm_price(m_date)
            if not m_recon_bm_price or m_recon_bm_price <= 0:
                m_recon_bm_price = float(m_row.get("Closing Price", 1.0))
            cf_recon = fifo.reconcile_quantity(
                m_row.get("Quantity"), m_date, m_recon_bm_price
            )
            for cf in cf_recon:
                cf_dates.append(cast(date, cf["date"]))
                cf_amounts.append(cast(float, cf["amount"]))

            fifo.reconcile_cost_basis(m_row.get("Buy Value"))

            if not fifo.active_lots:
                continue

            if self.start_date and m_date < self.start_date:
                continue
            if self.end_date and m_date > self.end_date:
                continue

            m_price = float(m_row["Closing Price"])
            m_bm_price = bm_provider.get_bm_price(m_date)
            if not m_bm_price or m_bm_price <= 0:
                m_bm_price = m_price

            closing_units = fifo.get_closing_units()
            terminal_val = fifo.get_terminal_value(m_price)
            shadow_terminal_val = fifo.get_shadow_terminal_value(m_bm_price)

            pt = isin_terminals.setdefault(
                m_date, {"val": 0.0, "shadow_val": 0.0, "after_tax_val": 0.0}
            )
            pt["val"] += terminal_val
            pt["shadow_val"] += shadow_terminal_val

            after_tax_terminal_val = 0.0
            for lot in fifo.active_lots:
                if lot.qty <= 1e-8:
                    continue
                lbd = lot.date
                age = max((m_date - lbd).days, 1) if lbd else 1
                holding_type = self.fy_table.get_holding_type(
                    age, tax_type, tax_subtype, lbd or m_date, m_date
                )
                ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )
                pnl = (m_price - lot.price) * lot.qty
                unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
                unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
                ltcg_tax = unreal_ltcg * ltcg_rate
                stcg_tax = unreal_stcg * stcg_rate
                after_tax_terminal_val += (lot.qty * m_price) - (ltcg_tax + stcg_tax)

            pt["after_tax_val"] += after_tax_terminal_val

            inst_xirr = calculate_xirr(cf_dates + [m_date], cf_amounts + [terminal_val])
            bm_xirr_val = calculate_xirr(cf_dates + [m_date], cf_amounts + [shadow_terminal_val])
            inst_after_tax_xirr = calculate_xirr(
                cf_dates + [m_date], cf_amounts + [after_tax_terminal_val]
            )

            inst_active_return = inst_xirr - bm_xirr_val
            is_lagging = inst_xirr < bm_xirr_val

            inst_cagr = inst_bm_cagr = 0.0
            if closing_units > 0:
                avg_cost = fifo.get_average_cost()
                avg_bm_cost = fifo.get_average_bm_cost()

                weighted_days = (
                    sum(lot.qty * (m_date - lot.date).days for lot in fifo.active_lots if lot.date)
                    / closing_units
                )
                inst_age = max(int(weighted_days), 1)

                if avg_cost > 0:
                    inst_cagr = calculate_cagr(avg_cost, m_price, inst_age)
                if avg_bm_cost > 0:
                    inst_bm_cagr = calculate_cagr(avg_bm_cost, m_bm_price, inst_age)

            risk_metrics = risk_provider.calculate_risk(first_p_date, m_date)
            t_err_ann = risk_metrics[1]
            info_ratio = (inst_active_return / t_err_ann) if t_err_ann != 0 else 0.0

            inst_metrics = {
                "cagr": inst_cagr,
                "bm_cagr": inst_bm_cagr,
                "xirr": inst_xirr,
                "bm_xirr": bm_xirr_val,
                "after_tax_xirr": inst_after_tax_xirr,
                "active_return": inst_active_return,
                "is_lagging": is_lagging,
                "info_ratio": info_ratio,
            }

            snapshots = snapshot_generator.generate(
                fifo, m_date, m_price, m_bm_price, risk_metrics, inst_metrics
            )
            isin_snapshots.extend(snapshots)

        while p_idx < len(p_inst):
            row_dt_obj = to_date_obj(p_inst[p_idx]["Date"])
            if not row_dt_obj:
                p_idx += 1
                continue
            row = p_inst[p_idx]
            qty = float(row["Quantity"])
            b_price = float(row["Price"])
            v_val = row.get("Value")
            buy_val = float(v_val) if v_val is not None else float(qty * b_price)
            
            bm_p = bm_provider.get_bm_price(row_dt_obj)
            if not bm_p or bm_p <= 0:
                bm_p = b_price
            shadow_q = buy_val / bm_p if bm_p > 0 else 0.0

            fifo.buy(row_dt_obj, qty, b_price, shadow_q, float(bm_p))
            cf_dates.append(row_dt_obj)
            cf_amounts.append(-buy_val)
            isin_cashflows.append({"date": row_dt_obj, "amount": -buy_val})
            p_idx += 1

        while s_idx < len(s_inst):
            row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
            if not row_dt_obj:
                s_idx += 1
                continue
            row = s_inst[s_idx]
            s_qty = float(row["Quantity"])
            row_p_val: float | None = row.get("Price")
            sv_val: float | None = row.get("Sell Value")
            
            if row_p_val is not None:
                s_price = float(row_p_val)
            elif sv_val is not None and s_qty > 0:
                s_price = float(sv_val) / s_qty
            else:
                s_price = 0.0
                
            s_val = float(sv_val) if sv_val is not None else float(s_qty * s_price)

            cf_dates.append(row_dt_obj)
            cf_amounts.append(s_val)
            isin_cashflows.append({"date": row_dt_obj, "amount": s_val})

            events = fifo.sell(row_dt_obj, s_qty, s_price)
            isin_realized.extend(events)
            s_idx += 1

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

        tags = {
            "class": str(master_row.get("INSTRUMENT_CLASS", "Unknown")),
            "subtype": str(master_row.get("INSTRUMENT_SUBTYPE", "Unknown")),
        }
        return df, isin_cashflows, isin_terminals, isin_realized, tags
