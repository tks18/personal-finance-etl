from datetime import date
from typing import Any

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.analytics.core.fifo import FIFOPortfolio
from personal_finance_etl.backend.engines.analytics.core.math import calculate_cagr
from personal_finance_etl.backend.engines.analytics.rules.macro import (
    FYMacroParametersTable,
    add_months,
    get_ltcg_threshold_months,
)
from personal_finance_etl.backend.types.analytics import SnapshotRecord


def _raise_invariant(msg: str) -> str:
    """Raise a ValueError from inside an expression (e.g. a dataclass field assignment)."""
    raise ValueError(msg)


class SnapshotGenerator:
    def __init__(
        self,
        fy_table: FYMacroParametersTable,
        rules: FinancialRules,
        isin: str,
        master_row: dict[str, Any],
    ) -> None:
        self.rules = rules
        self.isin = isin
        self.tax_type = str(master_row.get("TAX_TYPE", "equity"))
        self.tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        self.bench_id = master_row.get("BENCHMARK_ID")
        self.fy_table = fy_table

    def generate(
        self,
        fifo: FIFOPortfolio,
        m_date: date,
        m_price: float,
        m_bm_price: float,
        inst_metrics: dict[str, Any],
        fx_provider: Any = None,
        execution_residual: float = 0.0,
        remaining_ltcg_exemption: float = 0.0,
    ) -> list[SnapshotRecord]:
        inst_cagr = inst_metrics.get("cagr", 0.0)
        inst_bm_cagr = inst_metrics.get("bm_cagr", 0.0)
        inst_xirr = inst_metrics.get("xirr")
        inst_xirr_status = inst_metrics.get("xirr_status", "INVALID_INPUT")
        inst_after_tax_xirr = inst_metrics.get("after_tax_xirr")
        bm_xirr_val = inst_metrics.get("bm_xirr")
        inst_active_return = inst_metrics.get("active_return")
        is_lagging = inst_metrics.get("is_lagging")
        inst_max_dd = inst_metrics.get("max_drawdown", 0.0)
        inst_xirr_local = inst_metrics.get("xirr_local")
        bm_xirr_local = inst_metrics.get("bm_xirr_local")
        fx_xirr_impact = inst_metrics.get("fx_xirr_impact")

        def rounded_optional(value: float | None, digits: int = 8) -> float | None:
            return round(value, digits) if value is not None else None

        outperform_cnt = 0
        lot_count = len(fifo.active_lots)
        buffer: list[SnapshotRecord] = []

        for lot in fifo.active_lots:
            if lot.qty <= 1e-8:
                continue

            lbd = lot.date
            age = max((m_date - lbd).days, 1) if lbd else 1

            threshold_months = get_ltcg_threshold_months(
                self.tax_type, self.tax_subtype, self.rules
            )
            boundary_date = add_months(lbd or m_date, threshold_months)
            ltcg_thr = (boundary_date - (lbd or m_date)).days

            holding_type = self.fy_table.get_holding_type(
                self.tax_type, self.tax_subtype, lbd or m_date, m_date
            )
            days_to_ltcg = max(0, (boundary_date - m_date).days) if holding_type == "STCG" else 0
            ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
                self.tax_type, self.tax_subtype, lbd or m_date, m_date
            )

            lot_return = (m_price - lot.price) / lot.price if lot.price > 0 else 0.0
            lot_cagr = calculate_cagr(lot.price, m_price, age)

            if lbd and lbd.year == m_date.year and lbd.month == m_date.month:
                day_weight = (m_date.day - lbd.day + 1) / max(1, m_date.day)
            else:
                day_weight = 1.0

            if (
                lot.currency_id
                and lot.currency_id != (getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR"))
                and fx_provider
            ):
                fx_rate_snap_lot = fx_provider.get_rate(m_date, lot.currency_id)
            else:
                fx_rate_snap_lot = 1.0

            m_bm_price_inr = m_bm_price * fx_rate_snap_lot

            lbm_buy = lot.bm_buy
            if lbm_buy and lbm_buy > 0:
                lot_bm_ret = (m_bm_price_inr - lbm_buy) / lbm_buy
                lot_bm_cagr = calculate_cagr(lbm_buy, m_bm_price_inr, age)
            else:
                lbm_buy = None
                lot_bm_ret = 0.0
                lot_bm_cagr = 0.0

            lbm_buy_local = lot.bm_buy_local
            if lbm_buy_local and lbm_buy_local > 0:
                lot_bm_cagr_local = calculate_cagr(lbm_buy_local, m_bm_price, age)
            else:
                lot_bm_cagr_local = lot_bm_cagr

            lot_alpha = lot_cagr - lot_bm_cagr
            if lot_alpha > 0:
                outperform_cnt += 1

            pnl = (m_price - lot.price) * lot.qty
            close_val = lot.qty * m_price
            buy_val_lot = lot.qty * lot.price

            unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
            unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
            unreal_gain = max(0.0, pnl)
            unreal_ltcl = min(0.0, pnl) if holding_type == "LTCG" else 0.0
            unreal_stcl = min(0.0, pnl) if holding_type == "STCG" else 0.0
            unreal_loss = min(0.0, pnl)

            # Deduct remaining LTCG exemption before computing tax-if-sold.
            # Only Indian listed equity is eligible for the Rs 1.25L exemption (Section 112A).
            # Foreign equity and other asset classes retain full tax on LTCG.
            taxable_ltcg = max(0.0, unreal_ltcg - remaining_ltcg_exemption)
            ltcg_tax = taxable_ltcg * ltcg_rate
            stcg_tax = unreal_stcg * stcg_rate
            after_tax_pl = pnl - (ltcg_tax + stcg_tax)
            after_tax_cv = close_val - (ltcg_tax + stcg_tax)

            if (
                lot.currency_id
                and lot.currency_id != (getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR"))
                and fx_provider
            ):
                fx_rate_snap = fx_provider.get_rate(m_date, lot.currency_id)
                m_price_local = m_price / fx_rate_snap if fx_rate_snap > 0 else m_price

                buy_val_local = lot.qty * lot.price_local
                close_val_local = lot.qty * m_price_local

                asset_pnl_local = (m_price_local - lot.price_local) * lot.qty
                asset_pnl = asset_pnl_local * fx_rate_snap
                forex_pnl = lot.price_local * (fx_rate_snap - lot.fx_rate_buy) * lot.qty

                lot_cagr_local = calculate_cagr(lot.price_local, m_price_local, age)
                absolute_return_local = (
                    (m_price_local - lot.price_local) / lot.price_local
                    if lot.price_local > 0
                    else 0.0
                )
                asset_return_pct = asset_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
                forex_return_pct = forex_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
                blended_fx_buy_rate = (
                    buy_val_lot / buy_val_local if buy_val_local != 0 else lot.fx_rate_buy
                )
                curr_fx_rate = fx_rate_snap
                fx_rate_buy = lot.fx_rate_buy if lot.fx_rate_buy else 0.0
                buy_price_local = lot.price_local if lot.price_local else 0.0
                market_price_local = m_price_local
                currency_appreciation_pct = (
                    (curr_fx_rate / blended_fx_buy_rate) - 1.0 if blended_fx_buy_rate > 0 else 0.0
                )
            else:
                buy_val_local = buy_val_lot
                close_val_local = close_val
                asset_pnl = pnl
                forex_pnl = 0.0
                lot_cagr_local = lot_cagr
                absolute_return_local = lot_return
                asset_return_pct = lot_return
                forex_return_pct = 0.0
                blended_fx_buy_rate = 1.0
                curr_fx_rate = 1.0
                currency_appreciation_pct = 0.0
                fx_rate_buy = 1.0
                buy_price_local = lot.price
                market_price_local = m_price

            forex_contrib = forex_pnl / pnl if pnl != 0 else 0.0

            buffer.append(
                SnapshotRecord(
                    Closing_Date=m_date,
                    ISIN=self.isin,
                    CURRENCY_ID=(
                        fifo.active_lots[0].currency_id
                        if fifo.active_lots and fifo.active_lots[0].currency_id
                        else getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                    ),
                    BENCHMARK_ID=self.bench_id,
                    Lot_ID=lot.lot_id
                    if lot.lot_id is not None
                    else _raise_invariant(
                        f"[SNAPSHOT] FIFO invariant: lot_id is None — "
                        f"ISIN={self.isin}, Buy_Date={lbd}, qty={lot.qty}. "
                        "lot_id must always be set inside fifo.buy()."
                    ),
                    Purchase_ID=lot.purchase_id,
                    Lot_Source_Type=lot.lot_source_type,
                    TAX_TYPE=self.tax_type,
                    TAX_SUBTYPE=self.tax_subtype,
                    Buy_Date=lbd,
                    Age_Days=age,
                    LTCG_Threshold_Days=ltcg_thr,
                    Days_To_LTCG=days_to_ltcg,
                    Holding_Type=holding_type,
                    Quantity=lot.qty,
                    Execution_Residual=execution_residual,
                    Buy_Price=lot.price,
                    Market_Price=m_price,
                    Buy_Value=round(buy_val_lot, 4),
                    Close_Value=round(close_val, 4),
                    Lot_CAGR=round(lot_cagr, 8),
                    CAGR=round(inst_cagr, 8),
                    XIRR=rounded_optional(inst_xirr),
                    XIRR_Status=inst_xirr_status,
                    After_Tax_XIRR=rounded_optional(inst_after_tax_xirr),
                    XIRR_Local=rounded_optional(inst_xirr_local),
                    FX_XIRR_Impact=rounded_optional(fx_xirr_impact),
                    BM_Buy_Price=round(lbm_buy, 4) if lbm_buy else None,
                    BM_Market_Price=round(m_bm_price, 4),
                    Lot_BM_CAGR=round(lot_bm_cagr, 8),
                    Lot_BM_CAGR_Local=round(lot_bm_cagr_local, 8),
                    BM_CAGR=round(inst_bm_cagr, 8),
                    **{
                        "P/L": round(pnl, 4),
                    },
                    Absolute_Return=round(lot_return, 8),
                    Lot_BM_Return=round(lot_bm_ret, 8),
                    BM_XIRR=rounded_optional(bm_xirr_val),
                    BM_XIRR_Local=rounded_optional(bm_xirr_local),
                    Active_Return=rounded_optional(inst_active_return),
                    Active_Return_Local=rounded_optional(inst_metrics.get("active_return_local")),
                    Lot_Alpha=round(lot_alpha, 8),
                    Is_Lagging_Benchmark=is_lagging,
                    Max_Drawdown=round(inst_max_dd, 8),
                    Tax_Rate=ltcg_rate if holding_type == "LTCG" else stcg_rate,
                    Unrealized_LTCG=round(unreal_ltcg, 4),
                    Unrealized_STCG=round(unreal_stcg, 4),
                    Unrealized_Gain=round(unreal_gain, 4),
                    Unrealized_LTCL=round(unreal_ltcl, 4),
                    Unrealized_STCL=round(unreal_stcl, 4),
                    Unrealized_Loss=round(unreal_loss, 4),
                    LTCG_Tax_If_Sold=round(ltcg_tax, 4),
                    STCG_Tax_If_Sold=round(stcg_tax, 4),
                    After_Tax_PL=round(after_tax_pl, 4),
                    After_Tax_Close_Value=round(after_tax_cv, 4),
                    Dietz_Day_Weight=round(day_weight, 6),
                    Buy_Value_Local=round(buy_val_local, 4),
                    Close_Value_Local=round(close_val_local, 4),
                    Asset_PnL=round(asset_pnl, 4),
                    Forex_PnL=round(forex_pnl, 4),
                    Forex_Contribution_Pct=round(forex_contrib, 6),
                    Lot_CAGR_Local=round(lot_cagr_local, 8),
                    Absolute_Return_Local=round(absolute_return_local, 8),
                    Asset_Return_Pct=round(asset_return_pct, 6),
                    Forex_Return_Pct=round(forex_return_pct, 6),
                    Blended_FX_Buy_Rate=round(blended_fx_buy_rate, 6),
                    Buy_Price_Local=round(buy_price_local, 6),
                    Market_Price_Local=round(market_price_local, 6),
                    FX_Rate_Buy=round(fx_rate_buy, 6),
                    FX_Rate_Snap=round(curr_fx_rate, 6),
                    Currency_Appreciation_Pct=round(currency_appreciation_pct, 6),
                )
            )

        opt_prob = (outperform_cnt / lot_count) if lot_count > 0 else 0.0
        for row in buffer:
            row.Outperforming_Lot_Ratio = round(opt_prob, 8)

        return buffer
