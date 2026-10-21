"""Portfolio and lot snapshot generation engine.

Owns
----
- SnapshotGenerator: Constructs daily per-lot valuation, unrealized gain/loss,
  tax-if-sold, holding period classification, benchmark counterfactual,
  and local currency / FX attribution snapshot records.
- LotValuationContext: Typed market and macroeconomic parameters for snapshot generation.

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


def _rounded_optional(value: float | None, digits: int = 8) -> float | None:
    """Safely round an optional float value to specified decimal digits."""
    return round(value, digits) if value is not None else None


@dataclass(frozen=True)
class LotValuationContext:
    """Market price, benchmark, and macroeconomic context for per-lot snapshot generation."""

    m_date: date
    m_price: float
    m_bm_price: float
    inst_metrics: InstrumentMetricsRecord
    fx_provider: FXRateProvider | None = None
    execution_residual: float = 0.0
    remaining_ltcg_exemption: float = 0.0


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


@dataclass
class _LotBenchmarkMetrics:
    """Counterfactual benchmark returns, relative performance alpha, and outperformance indicator."""

    bm_buy: float | None
    m_bm_price_inr: float
    lot_bm_ret: float
    lot_bm_cagr: float | None
    lot_bm_cagr_status: str
    lot_bm_cagr_local: float | None
    lot_alpha: float | None
    is_outperforming: bool


def _compute_lot_benchmark_metrics(
    lot: TaxLot,
    ctx: LotValuationContext,
    age: int,
    lot_cagr: float | None,
    default_curr: str,
) -> _LotBenchmarkMetrics:
    """Calculate benchmark shadow returns, local CAGR, and outperformance alpha for a lot.

    Parameters
    ----------
    lot : TaxLot
        Subject tax lot.
    ctx : LotValuationContext
        Valuation context with benchmark and FX information.
    age : int
        Lot age in calendar days.
    lot_cagr : float | None
        Native asset annualized return.
    default_curr : str
        Default base currency ID.

    Returns
    -------
    _LotBenchmarkMetrics
        Computed benchmark metrics and outperformance flag.
    """
    if lot.currency_id and lot.currency_id != default_curr and ctx.fx_provider:
        fx_rate_snap_lot = ctx.fx_provider.get_rate(ctx.m_date, lot.currency_id) or 1.0
    else:
        fx_rate_snap_lot = 1.0

    m_bm_price_inr = ctx.m_bm_price * fx_rate_snap_lot
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
        lot_bm_cagr_local = calculate_cagr(lbm_buy_local, ctx.m_bm_price, age).value
    else:
        lot_bm_cagr_local = lot_bm_cagr

    is_outperforming = False
    if lot_cagr is not None and lot_bm_cagr is not None:
        lot_alpha = lot_cagr - lot_bm_cagr
        if lot_alpha > 0:
            is_outperforming = True
    else:
        lot_alpha = None

    return _LotBenchmarkMetrics(
        bm_buy=lbm_buy,
        m_bm_price_inr=m_bm_price_inr,
        lot_bm_ret=lot_bm_ret,
        lot_bm_cagr=lot_bm_cagr,
        lot_bm_cagr_status=lot_bm_cagr_status,
        lot_bm_cagr_local=lot_bm_cagr_local,
        lot_alpha=lot_alpha,
        is_outperforming=is_outperforming,
    )


def _compute_foreign_fx_attribution(
    lot: TaxLot,
    ctx: LotValuationContext,
    age: int,
    buy_val_lot: float,
    pnl: float,
) -> _LotFxAttribution:
    """Decompose performance into asset and currency returns for foreign-currency holdings."""
    fx_rate_snap = (
        ctx.fx_provider.get_rate(ctx.m_date, str(lot.currency_id)) if ctx.fx_provider else None
    ) or 1.0
    m_price_local = ctx.m_price / fx_rate_snap if fx_rate_snap > 0 else ctx.m_price

    buy_val_local = lot.qty * lot.price_local
    close_val_local = lot.qty * m_price_local

    asset_pnl_local = (m_price_local - lot.price_local) * lot.qty
    asset_pnl = asset_pnl_local * fx_rate_snap
    forex_pnl = lot.price_local * (fx_rate_snap - lot.fx_rate_buy) * lot.qty

    lot_cagr_local = calculate_cagr(lot.price_local, m_price_local, age).value
    absolute_return_local = (
        (m_price_local - lot.price_local) / lot.price_local if lot.price_local > 0 else 0.0
    )
    asset_return_pct = asset_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
    forex_return_pct = forex_pnl / buy_val_lot if buy_val_lot != 0 else 0.0
    blended_fx_buy_rate = buy_val_lot / buy_val_local if buy_val_local != 0 else lot.fx_rate_buy
    curr_fx_rate = fx_rate_snap
    currency_appreciation_pct = (
        (curr_fx_rate / blended_fx_buy_rate) - 1.0 if blended_fx_buy_rate > 0 else 0.0
    )
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
        fx_rate_buy=lot.fx_rate_buy if lot.fx_rate_buy else 0.0,
        buy_price_local=lot.price_local if lot.price_local else 0.0,
        market_price_local=m_price_local,
        forex_contrib=forex_contrib,
    )


def _compute_domestic_fx_attribution(
    lot: TaxLot,
    ctx: LotValuationContext,
    buy_val_lot: float,
    close_val: float,
    pnl: float,
    lot_cagr: float | None,
    lot_return: float,
) -> _LotFxAttribution:
    """Return identity FX attribution metrics for base domestic currency holdings."""
    return _LotFxAttribution(
        buy_val_local=buy_val_lot,
        close_val_local=close_val,
        asset_pnl=pnl,
        forex_pnl=0.0,
        lot_cagr_local=lot_cagr,
        absolute_return_local=lot_return,
        asset_return_pct=lot_return,
        forex_return_pct=0.0,
        blended_fx_buy_rate=1.0,
        curr_fx_rate=1.0,
        currency_appreciation_pct=0.0,
        fx_rate_buy=1.0,
        buy_price_local=lot.price,
        market_price_local=ctx.m_price,
        forex_contrib=0.0,
    )


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
        context: LotValuationContext,
    ) -> list[SnapshotRecord]:
        """Construct daily snapshot records for all active lots of an instrument.

        Parameters
        ----------
        fifo : FIFOPortfolio
            Active tax lots portfolio tracker.
        context : LotValuationContext
            Daily market prices, benchmark levels, and macroeconomic parameters.

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

            snapshot, is_outperforming = self._build_lot_snapshot(lot, fifo, context)
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
        lot: TaxLot,
        ctx: LotValuationContext,
        age: int,
        buy_val_lot: float,
        close_val: float,
        pnl: float,
        lot_cagr: float | None,
        lot_return: float,
    ) -> _LotFxAttribution:
        """Decompose investment performance into native asset and foreign currency returns."""
        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        if lot.currency_id and lot.currency_id != default_curr and ctx.fx_provider:
            return _compute_foreign_fx_attribution(lot, ctx, age, buy_val_lot, pnl)
        return _compute_domestic_fx_attribution(
            lot, ctx, buy_val_lot, close_val, pnl, lot_cagr, lot_return
        )

    def _build_lot_snapshot(
        self,
        lot: TaxLot,
        fifo: FIFOPortfolio,
        ctx: LotValuationContext,
    ) -> tuple[SnapshotRecord, bool]:
        """Construct a strongly-typed snapshot record for a single active lot."""
        lbd = lot.date
        age = max((ctx.m_date - lbd).days, 1) if lbd else 1

        lot_return = (ctx.m_price - lot.price) / lot.price if lot.price > 0 else 0.0
        lot_cagr_res = calculate_cagr(lot.price, ctx.m_price, age)
        lot_cagr = lot_cagr_res.value
        lot_cagr_status = lot_cagr_res.status

        if lbd and lbd.year == ctx.m_date.year and lbd.month == ctx.m_date.month:
            day_weight = (ctx.m_date.day - lbd.day + 1) / max(1, ctx.m_date.day)
        else:
            day_weight = 1.0

        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        bm = _compute_lot_benchmark_metrics(lot, ctx, age, lot_cagr, default_curr)

        pnl = (ctx.m_price - lot.price) * lot.qty
        close_val = lot.qty * ctx.m_price
        buy_val_lot = lot.qty * lot.price

        tax = self._compute_tax_attributes(
            lot_date=lbd,
            m_date=ctx.m_date,
            pnl=pnl,
            close_val=close_val,
            remaining_ltcg_exemption=ctx.remaining_ltcg_exemption,
        )

        fx = self._compute_fx_attribution(
            lot=lot,
            ctx=ctx,
            age=age,
            buy_val_lot=buy_val_lot,
            close_val=close_val,
            pnl=pnl,
            lot_cagr=lot_cagr,
            lot_return=lot_return,
        )

        record = SnapshotRecord(
            Closing_Date=ctx.m_date,
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
            Execution_Residual=ctx.execution_residual,
            Buy_Price=lot.price,
            Market_Price=ctx.m_price,
            Buy_Value=round(buy_val_lot, 4),
            Close_Value=round(close_val, 4),
            Lot_CAGR=_rounded_optional(lot_cagr),
            Lot_CAGR_Status=lot_cagr_status,
            CAGR=_rounded_optional(ctx.inst_metrics.get("cagr")),
            CAGR_Status=ctx.inst_metrics.get("cagr_status", "UNDEFINED"),
            XIRR=_rounded_optional(ctx.inst_metrics.get("xirr")),
            XIRR_Status=ctx.inst_metrics.get("xirr_status", "INVALID_INPUT"),
            After_Tax_XIRR=_rounded_optional(ctx.inst_metrics.get("after_tax_xirr")),
            XIRR_Local=_rounded_optional(ctx.inst_metrics.get("xirr_local")),
            FX_XIRR_Impact=_rounded_optional(ctx.inst_metrics.get("fx_xirr_impact")),
            BM_Buy_Price=round(bm.bm_buy, 4) if bm.bm_buy else None,
            BM_Market_Price=round(ctx.m_bm_price, 4),
            Lot_BM_CAGR=_rounded_optional(bm.lot_bm_cagr),
            Lot_BM_CAGR_Status=bm.lot_bm_cagr_status,
            Lot_BM_CAGR_Local=_rounded_optional(bm.lot_bm_cagr_local),
            BM_CAGR=_rounded_optional(ctx.inst_metrics.get("bm_cagr")),
            BM_CAGR_Status=ctx.inst_metrics.get("bm_cagr_status", "UNDEFINED"),
            **{
                "P/L": round(pnl, 4),
            },
            Absolute_Return=round(lot_return, 8),
            Lot_BM_Return=round(bm.lot_bm_ret, 8),
            BM_XIRR=_rounded_optional(ctx.inst_metrics.get("bm_xirr")),
            BM_XIRR_Local=_rounded_optional(ctx.inst_metrics.get("bm_xirr_local")),
            Active_Return=_rounded_optional(ctx.inst_metrics.get("active_return")),
            Active_Return_Local=_rounded_optional(ctx.inst_metrics.get("active_return_local")),
            Lot_Alpha=_rounded_optional(bm.lot_alpha),
            Is_Lagging_Benchmark=ctx.inst_metrics.get("is_lagging"),
            Max_Drawdown=round(ctx.inst_metrics.get("max_drawdown", 0.0), 8),
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
            Lot_CAGR_Local=_rounded_optional(fx.lot_cagr_local),
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
        return record, bm.is_outperforming


__all__ = [
    "LotValuationContext",
    "SnapshotGenerator",
    "_raise_invariant",
]
