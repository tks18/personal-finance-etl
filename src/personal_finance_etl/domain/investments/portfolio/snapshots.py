"""Portfolio and lot snapshot generation engine.

Owns
----
- SnapshotGenerator: Constructs daily per-lot valuation, unrealized gain/loss,
  tax-if-sold, holding period classification, benchmark counterfactual,
  and local currency / FX attribution snapshot records.

Does not own
-------------
- FIFO queue state mutation (owned by domain.investments.lots.fifo).
- Presentation layer formatting or persistence (owned by presentation and infrastructure).
"""

from dataclasses import dataclass
from datetime import date

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.investments.contracts import (
    InstrumentMetricsRecord,
    IsinMasterRecord,
    SnapshotRecord,
    TaxLot,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import (
    FYMacroParametersTable,
    add_months,
    get_ltcg_threshold_months,
)


def _raise_invariant(msg: str) -> str:
    """Raise a ValueError from inside an expression (e.g. a dataclass field assignment)."""
    raise ValueError(msg)


@dataclass
class _LotTaxAttributes:
    """Holding classification, tax rates, taxable capital gains, and after-tax values."""

    holding_type: str
    ltcg_rate: float
    stcg_rate: float
    ltcg_thr: int
    days_to_ltcg: int
    unreal_ltcg: float
    unreal_stcg: float
    unreal_gain: float
    unreal_ltcl: float
    unreal_stcl: float
    unreal_loss: float
    ltcg_tax: float
    stcg_tax: float
    after_tax_pl: float
    after_tax_cv: float


@dataclass
class _LotFxAttribution:
    """Attribution metrics decomposing native asset and foreign currency returns."""

    buy_val_local: float
    close_val_local: float
    asset_pnl: float
    forex_pnl: float
    lot_cagr_local: float | None
    absolute_return_local: float
    asset_return_pct: float
    forex_return_pct: float
    blended_fx_buy_rate: float
    curr_fx_rate: float
    currency_appreciation_pct: float
    fx_rate_buy: float
    buy_price_local: float
    market_price_local: float
    forex_contrib: float


class SnapshotGenerator:
    """Constructs daily per-lot valuation and attribution snapshot records."""

    def __init__(
        self,
        fy_table: FYMacroParametersTable,
        rules: FinancialRules,
        isin: str,
        master_row: IsinMasterRecord,
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
        inst_metrics: InstrumentMetricsRecord,
        fx_provider: FXRateProvider | None = None,
        execution_residual: float = 0.0,
        remaining_ltcg_exemption: float = 0.0,
    ) -> list[SnapshotRecord]:
        """Construct daily snapshot records for all active lots of an instrument.

        Parameters
        ----------
        fifo : FIFOPortfolio
            Active tax lots portfolio tracker.
        m_date : date
            Snapshot valuation date.
        m_price : float
            Closing market price per unit.
        m_bm_price : float
            Closing benchmark price.
        inst_metrics : InstrumentMetricsRecord
            Computed instrument-level CAGR, XIRR, drawdown, and relative performance metrics.
        fx_provider : FXRateProvider | None, optional
            FX lookup provider for foreign-currency instruments, by default None.
        execution_residual : float, optional
            Residual cash drag from unexecuted orders, by default 0.0.
        remaining_ltcg_exemption : float, optional
            Remaining Section 112A equity exemption for the current financial year, by default 0.0.

        Returns
        -------
        list[SnapshotRecord]
            List of strongly-typed per-lot snapshot records.
        """
        outperform_cnt = 0
        lot_count = len(fifo.active_lots)
        buffer: list[SnapshotRecord] = []

        for lot in fifo.active_lots:
            if lot.qty <= 1e-8:
                continue

            snapshot, is_outperforming = self._build_lot_snapshot(
                lot=lot,
                fifo=fifo,
                m_date=m_date,
                m_price=m_price,
                m_bm_price=m_bm_price,
                inst_metrics=inst_metrics,
                fx_provider=fx_provider,
                execution_residual=execution_residual,
                remaining_ltcg_exemption=remaining_ltcg_exemption,
            )
            buffer.append(snapshot)
            if is_outperforming:
                outperform_cnt += 1

        opt_prob = (outperform_cnt / lot_count) if lot_count > 0 else 0.0
        for row in buffer:
            row.Outperforming_Lot_Ratio = round(opt_prob, 8)

        return buffer

    def _compute_tax_attributes(
        self,
        lot_date: date | None,
        m_date: date,
        pnl: float,
        close_val: float,
        remaining_ltcg_exemption: float,
    ) -> _LotTaxAttributes:
        """Compute holding classification, tax rates, taxable capital gains, and after-tax values."""
        threshold_months = get_ltcg_threshold_months(self.tax_type, self.tax_subtype, self.rules)
        boundary_date = add_months(lot_date or m_date, threshold_months)
        ltcg_thr = (boundary_date - (lot_date or m_date)).days

        holding_type = self.fy_table.get_holding_type(
            self.tax_type, self.tax_subtype, lot_date or m_date, m_date
        )
        days_to_ltcg = max(0, (boundary_date - m_date).days) if holding_type == "STCG" else 0
        ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
            self.tax_type, self.tax_subtype, lot_date or m_date, m_date
        )

        unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
        unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
        unreal_gain = max(0.0, pnl)
        unreal_ltcl = min(0.0, pnl) if holding_type == "LTCG" else 0.0
        unreal_stcl = min(0.0, pnl) if holding_type == "STCG" else 0.0
        unreal_loss = min(0.0, pnl)

        taxable_ltcg = max(0.0, unreal_ltcg - remaining_ltcg_exemption)
        ltcg_tax = taxable_ltcg * ltcg_rate
        stcg_tax = unreal_stcg * stcg_rate
        after_tax_pl = pnl - (ltcg_tax + stcg_tax)
        after_tax_cv = close_val - (ltcg_tax + stcg_tax)

        return _LotTaxAttributes(
            holding_type=holding_type,
            ltcg_rate=ltcg_rate,
            stcg_rate=stcg_rate,
            ltcg_thr=ltcg_thr,
            days_to_ltcg=days_to_ltcg,
            unreal_ltcg=unreal_ltcg,
            unreal_stcg=unreal_stcg,
            unreal_gain=unreal_gain,
            unreal_ltcl=unreal_ltcl,
            unreal_stcl=unreal_stcl,
            unreal_loss=unreal_loss,
            ltcg_tax=ltcg_tax,
            stcg_tax=stcg_tax,
            after_tax_pl=after_tax_pl,
            after_tax_cv=after_tax_cv,
        )

    def _compute_fx_attribution(
        self,
        lot_currency_id: str | None,
        lot_qty: float,
        lot_price: float,
        lot_price_local: float,
        lot_fx_rate_buy: float,
        buy_val_lot: float,
        close_val: float,
        pnl: float,
        m_date: date,
        m_price: float,
        age: int,
        lot_cagr: float | None,
        lot_return: float,
        fx_provider: FXRateProvider | None,
    ) -> _LotFxAttribution:
        """Decompose investment performance into native asset and foreign currency returns."""
        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        if lot_currency_id and lot_currency_id != default_curr and fx_provider:
            fx_rate_snap = fx_provider.get_rate(m_date, lot_currency_id) or 1.0
            m_price_local = m_price / fx_rate_snap if fx_rate_snap > 0 else m_price

            buy_val_local = lot_qty * lot_price_local
            close_val_local = lot_qty * m_price_local

            asset_pnl_local = (m_price_local - lot_price_local) * lot_qty
            asset_pnl = asset_pnl_local * fx_rate_snap
            forex_pnl = lot_price_local * (fx_rate_snap - lot_fx_rate_buy) * lot_qty

            lot_cagr_local = calculate_cagr(lot_price_local, m_price_local, age).value
            absolute_return_local = (
                (m_price_local - lot_price_local) / lot_price_local if lot_price_local > 0 else 0.0
            )
            asset_return_pct = asset_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
            forex_return_pct = forex_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
            blended_fx_buy_rate = (
                buy_val_lot / buy_val_local if buy_val_local != 0 else lot_fx_rate_buy
            )
            curr_fx_rate = fx_rate_snap
            fx_rate_buy = lot_fx_rate_buy if lot_fx_rate_buy else 0.0
            buy_price_local = lot_price_local if lot_price_local else 0.0
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
            buy_price_local = lot_price
            market_price_local = m_price

        forex_contrib = forex_pnl / pnl if pnl != 0 else 0.0

        return _LotFxAttribution(
            buy_val_local=buy_val_local,
            close_val_local=close_val_local,
            asset_pnl=asset_pnl,
            forex_pnl=forex_pnl,
            lot_cagr_local=lot_cagr_local,
            absolute_return_local=absolute_return_local,
            asset_return_pct=asset_return_pct,
            forex_return_pct=forex_return_pct,
            blended_fx_buy_rate=blended_fx_buy_rate,
            curr_fx_rate=curr_fx_rate,
            currency_appreciation_pct=currency_appreciation_pct,
            fx_rate_buy=fx_rate_buy,
            buy_price_local=buy_price_local,
            market_price_local=market_price_local,
            forex_contrib=forex_contrib,
        )

    def _build_lot_snapshot(
        self,
        lot: TaxLot,
        fifo: FIFOPortfolio,
        m_date: date,
        m_price: float,
        m_bm_price: float,
        inst_metrics: InstrumentMetricsRecord,
        fx_provider: FXRateProvider | None,
        execution_residual: float,
        remaining_ltcg_exemption: float,
    ) -> tuple[SnapshotRecord, bool]:
        """Construct a strongly-typed snapshot record for a single active lot."""
        lbd = lot.date
        age = max((m_date - lbd).days, 1) if lbd else 1

        lot_return = (m_price - lot.price) / lot.price if lot.price > 0 else 0.0
        lot_cagr_res = calculate_cagr(lot.price, m_price, age)
        lot_cagr = lot_cagr_res.value
        lot_cagr_status = lot_cagr_res.status

        if lbd and lbd.year == m_date.year and lbd.month == m_date.month:
            day_weight = (m_date.day - lbd.day + 1) / max(1, m_date.day)
        else:
            day_weight = 1.0

        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        if lot.currency_id and lot.currency_id != default_curr and fx_provider:
            fx_rate_snap_lot = fx_provider.get_rate(m_date, lot.currency_id) or 1.0
        else:
            fx_rate_snap_lot = 1.0

        m_bm_price_inr = m_bm_price * fx_rate_snap_lot

        lbm_buy = lot.bm_buy
        if lbm_buy and lbm_buy > 0:
            lot_bm_ret = (m_bm_price_inr - lbm_buy) / lbm_buy
            lot_bm_cagr_res = calculate_cagr(lbm_buy, m_bm_price_inr, age)
            lot_bm_cagr = lot_bm_cagr_res.value
            lot_bm_cagr_status = lot_bm_cagr_res.status
        else:
            lbm_buy = None
            lot_bm_ret = 0.0
            lot_bm_cagr = None
            lot_bm_cagr_status = "UNDEFINED"

        lbm_buy_local = lot.bm_buy_local
        if lbm_buy_local and lbm_buy_local > 0:
            lot_bm_cagr_local = calculate_cagr(lbm_buy_local, m_bm_price, age).value
        else:
            lot_bm_cagr_local = lot_bm_cagr

        is_outperforming = False
        if lot_cagr is not None and lot_bm_cagr is not None:
            lot_alpha = lot_cagr - lot_bm_cagr
            if lot_alpha > 0:
                is_outperforming = True
        else:
            lot_alpha = None

        pnl = (m_price - lot.price) * lot.qty
        close_val = lot.qty * m_price
        buy_val_lot = lot.qty * lot.price

        tax = self._compute_tax_attributes(
            lot_date=lbd,
            m_date=m_date,
            pnl=pnl,
            close_val=close_val,
            remaining_ltcg_exemption=remaining_ltcg_exemption,
        )

        fx = self._compute_fx_attribution(
            lot_currency_id=lot.currency_id,
            lot_qty=lot.qty,
            lot_price=lot.price,
            lot_price_local=lot.price_local,
            lot_fx_rate_buy=lot.fx_rate_buy,
            buy_val_lot=buy_val_lot,
            close_val=close_val,
            pnl=pnl,
            m_date=m_date,
            m_price=m_price,
            age=age,
            lot_cagr=lot_cagr,
            lot_return=lot_return,
            fx_provider=fx_provider,
        )

        def rounded_optional(value: float | None, digits: int = 8) -> float | None:
            """Safely round an optional float value to specified decimal digits."""
            return round(value, digits) if value is not None else None

        record = SnapshotRecord(
            Closing_Date=m_date,
            ISIN=self.isin,
            CURRENCY_ID=(
                fifo.active_lots[0].currency_id
                if fifo.active_lots and fifo.active_lots[0].currency_id
                else default_curr
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
            LTCG_Threshold_Days=tax.ltcg_thr,
            Days_To_LTCG=tax.days_to_ltcg,
            Holding_Type=tax.holding_type,
            Quantity=lot.qty,
            Execution_Residual=execution_residual,
            Buy_Price=lot.price,
            Market_Price=m_price,
            Buy_Value=round(buy_val_lot, 4),
            Close_Value=round(close_val, 4),
            Lot_CAGR=rounded_optional(lot_cagr),
            Lot_CAGR_Status=lot_cagr_status,
            CAGR=rounded_optional(inst_metrics.get("cagr")),
            CAGR_Status=inst_metrics.get("cagr_status", "UNDEFINED"),
            XIRR=rounded_optional(inst_metrics.get("xirr")),
            XIRR_Status=inst_metrics.get("xirr_status", "INVALID_INPUT"),
            After_Tax_XIRR=rounded_optional(inst_metrics.get("after_tax_xirr")),
            XIRR_Local=rounded_optional(inst_metrics.get("xirr_local")),
            FX_XIRR_Impact=rounded_optional(inst_metrics.get("fx_xirr_impact")),
            BM_Buy_Price=round(lbm_buy, 4) if lbm_buy else None,
            BM_Market_Price=round(m_bm_price, 4),
            Lot_BM_CAGR=rounded_optional(lot_bm_cagr),
            Lot_BM_CAGR_Status=lot_bm_cagr_status,
            Lot_BM_CAGR_Local=rounded_optional(lot_bm_cagr_local),
            BM_CAGR=rounded_optional(inst_metrics.get("bm_cagr")),
            BM_CAGR_Status=inst_metrics.get("bm_cagr_status", "UNDEFINED"),
            **{
                "P/L": round(pnl, 4),
            },
            Absolute_Return=round(lot_return, 8),
            Lot_BM_Return=round(lot_bm_ret, 8),
            BM_XIRR=rounded_optional(inst_metrics.get("bm_xirr")),
            BM_XIRR_Local=rounded_optional(inst_metrics.get("bm_xirr_local")),
            Active_Return=rounded_optional(inst_metrics.get("active_return")),
            Active_Return_Local=rounded_optional(inst_metrics.get("active_return_local")),
            Lot_Alpha=rounded_optional(lot_alpha),
            Is_Lagging_Benchmark=inst_metrics.get("is_lagging"),
            Max_Drawdown=round(inst_metrics.get("max_drawdown", 0.0), 8),
            Tax_Rate=tax.ltcg_rate if tax.holding_type == "LTCG" else tax.stcg_rate,
            Unrealized_LTCG=round(tax.unreal_ltcg, 4),
            Unrealized_STCG=round(tax.unreal_stcg, 4),
            Unrealized_Gain=round(tax.unreal_gain, 4),
            Unrealized_LTCL=round(tax.unreal_ltcl, 4),
            Unrealized_STCL=round(tax.unreal_stcl, 4),
            Unrealized_Loss=round(tax.unreal_loss, 4),
            LTCG_Tax_If_Sold=round(tax.ltcg_tax, 4),
            STCG_Tax_If_Sold=round(tax.stcg_tax, 4),
            After_Tax_PL=round(tax.after_tax_pl, 4),
            After_Tax_Close_Value=round(tax.after_tax_cv, 4),
            Dietz_Day_Weight=round(day_weight, 6),
            Buy_Value_Local=round(fx.buy_val_local, 4),
            Close_Value_Local=round(fx.close_val_local, 4),
            Asset_PnL=round(fx.asset_pnl, 4),
            Forex_PnL=round(fx.forex_pnl, 4),
            Forex_Contribution_Pct=round(fx.forex_contrib, 6),
            Lot_CAGR_Local=rounded_optional(fx.lot_cagr_local),
            Absolute_Return_Local=round(fx.absolute_return_local, 8),
            Asset_Return_Pct=round(fx.asset_return_pct, 6),
            Forex_Return_Pct=round(fx.forex_return_pct, 6),
            Blended_FX_Buy_Rate=round(fx.blended_fx_buy_rate, 6),
            Buy_Price_Local=round(fx.buy_price_local, 6),
            Market_Price_Local=round(fx.market_price_local, 6),
            FX_Rate_Buy=round(fx.fx_rate_buy, 6),
            FX_Rate_Snap=round(fx.curr_fx_rate, 6),
            Currency_Appreciation_Pct=round(fx.currency_appreciation_pct, 6),
        )
        return record, is_outperforming


__all__ = [
    "SnapshotGenerator",
    "_raise_invariant",
]
