from datetime import date

from src.engines.analytics.core.fifo import FIFOPortfolio
from src.engines.analytics.core.math import calculate_cagr
from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.rules.tax import get_ltcg_threshold
from src.utils.helpers import to_date_obj


class SnapshotGenerator:
    def __init__(self, ctx: RunContext, isin: str, master_row: dict):
        self.ctx = ctx
        self.isin = isin
        self.tax_type = str(master_row.get("TAX_TYPE", "equity"))
        self.tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        self.bench_id = master_row.get("BENCHMARK_ID")
        self.fy_table = ctx.fy_table

    def generate(
        self,
        fifo: FIFOPortfolio,
        m_date: date,
        m_price: float,
        m_bm_price: float,
        risk_metrics: tuple,
        inst_metrics: dict,
    ) -> list[dict]:
        beta, t_err_ann, up_c, down_c = risk_metrics
        inst_cagr = inst_metrics.get("cagr", 0.0)
        inst_bm_cagr = inst_metrics.get("bm_cagr", 0.0)
        inst_xirr = inst_metrics.get("xirr", 0.0)
        bm_xirr_val = inst_metrics.get("bm_xirr", 0.0)
        inst_active_return = inst_metrics.get("active_return", 0.0)
        is_lagging = inst_metrics.get("is_lagging", False)
        info_ratio = inst_metrics.get("info_ratio", 0.0)

        outperform_cnt = 0
        lot_count = len(fifo.active_lots)
        buffer = []

        for lot in fifo.active_lots:
            if lot.qty <= 1e-8:
                continue

            lbd = to_date_obj(lot.date)
            age = max((m_date - lbd).days, 1) if lbd else 1

            ltcg_thr = get_ltcg_threshold(self.tax_type, self.tax_subtype)
            holding_type = self.fy_table.get_holding_type(
                age, self.tax_type, self.tax_subtype, lbd or m_date, m_date
            )
            days_to_ltcg = max(0, ltcg_thr - age) if holding_type == "STCG" else 0
            ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
                self.tax_type, self.tax_subtype, lbd or m_date, m_date
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
                    "ISIN": self.isin,
                    "BENCHMARK_ID": self.bench_id,
                    "TAX_TYPE": self.tax_type,
                    "TAX_SUBTYPE": self.tax_subtype,
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

        return buffer
