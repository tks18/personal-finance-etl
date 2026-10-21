"""Lot-level performance, benchmark counterfactuals, and FX attribution calculations.

Owns
----
- LotValuationContext: Context bundle with market prices, benchmark levels, and macro parameters.
- _LotTaxAttributes: Data container for lot tax rates and accrued liabilities.
- _LotFxAttribution: Data container for foreign exchange vs asset return attribution.
- _LotBenchmarkMetrics: Data container for shadow benchmark return and relative alpha.
- compute_lot_benchmark_metrics: Counterfactual benchmark returns and alpha for a single lot.
- compute_foreign_fx_attribution: Dual-currency decomposition for foreign assets.
- compute_domestic_fx_attribution: Identity attribution for base currency assets.

Does not own
-------------
- Daily snapshot orchestration loop (owned by domain.investments.portfolio.snapshots).
- FIFO queue liquidation state (owned by domain.investments.lots.fifo).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from personal_finance_etl.domain.investments.contracts import (
    InstrumentMetricsRecord,
    TaxLot,
)
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.market.fx import FXRateProvider

__all__ = [
    "LotValuationContext",
    "_LotBenchmarkMetrics",
    "_LotFxAttribution",
    "_LotTaxAttributes",
    "compute_domestic_fx_attribution",
    "compute_foreign_fx_attribution",
    "compute_lot_benchmark_metrics",
]


@dataclass(frozen=True)
class LotValuationContext:
    """Market price, benchmark, and macroeconomic context for per-lot snapshot generation.

    Parameters
    ----------
    m_date : date
        Evaluation market date.
    m_price : float
        Current asset closing price.
    m_bm_price : float
        Current benchmark price.
    inst_metrics : InstrumentMetricsRecord
        Pre-calculated instrument-level performance metrics.
    fx_provider : FXRateProvider | None, optional
        Foreign exchange rate provider.
    execution_residual : float, default=0.0
        Broker execution residual.
    remaining_ltcg_exemption : float, default=0.0
        Unutilized annual LTCG exemption.
    """

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


def compute_lot_benchmark_metrics(
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


def compute_foreign_fx_attribution(
    lot: TaxLot,
    ctx: LotValuationContext,
    age: int,
    buy_val_lot: float,
    pnl: float,
) -> _LotFxAttribution:
    """Decompose performance into asset and currency returns for foreign-currency holdings.

    Parameters
    ----------
    lot : TaxLot
        Subject tax lot.
    ctx : LotValuationContext
        Valuation context with foreign exchange rates.
    age : int
        Lot holding period age in calendar days.
    buy_val_lot : float
        Total base currency acquisition value.
    pnl : float
        Total nominal base currency profit/loss.

    Returns
    -------
    _LotFxAttribution
        Decomposed local currency, asset, and forex attribution metrics.
    """
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


def compute_domestic_fx_attribution(
    lot: TaxLot,
    ctx: LotValuationContext,
    buy_val_lot: float,
    close_val: float,
    pnl: float,
    lot_cagr: float | None,
    lot_return: float,
) -> _LotFxAttribution:
    """Return identity FX attribution metrics for base domestic currency holdings.

    Parameters
    ----------
    lot : TaxLot
        Subject tax lot.
    ctx : LotValuationContext
        Valuation context.
    buy_val_lot : float
        Total acquisition value in base currency.
    close_val : float
        Total market value in base currency.
    pnl : float
        Nominal profit/loss.
    lot_cagr : float | None
        Lot annualized return.
    lot_return : float
        Total holding period percentage return.

    Returns
    -------
    _LotFxAttribution
        Identity attribution metrics with zero currency impact.
    """
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
