"""Daily terminal values, returns, drawdown, and performance metrics computation.

Owns
----
- _DailyTerminals: Container for daily asset and shadow benchmark valuation outputs.
- compute_terminal_val_local: Evaluation of local-currency terminal value.
- compute_after_tax_terminal_val: Post-tax liquidation valuation.
- compute_daily_terminals: Daily valuation and shadow benchmark computation.
- compute_cagr_and_drawdown: Volume-weighted CAGR and peak drawdown derivation.
- compute_local_xirr_metrics: Local currency XIRR and benchmark metrics.
- compute_daily_metrics: Full performance metrics aggregation.
- assemble_snapshots_df: DataFrame conversion for daily lot snapshots.

Does not own
-------------
- FIFO queue liquidation state (owned by domain.investments.lots.fifo).
- Simulation orchestrator loop (owned by application.investments.isin_processor).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import polars as pl

from personal_finance_etl.application.investments.isin_service.state import _IsinState
from personal_finance_etl.domain.investments.contracts import (
    InstrumentMetricsRecord,
    SnapshotRecord,
    TerminalValueRecord,
    TradeRecord,
)
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.investments.performance.xirr import calculate_xirr
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import FYMacroParametersTable

__all__ = [
    "_DailyTerminals",
    "assemble_snapshots_df",
    "compute_after_tax_terminal_val",
    "compute_cagr_and_drawdown",
    "compute_daily_metrics",
    "compute_daily_terminals",
    "compute_local_xirr_metrics",
    "compute_terminal_val_local",
]


@dataclass
class _DailyTerminals:
    """Terminal values and benchmark prices computed for a single date.

    Parameters
    ----------
    m_price : float
        Observed asset closing price.
    m_bm_price : float
        Observed benchmark price in local currency.
    m_bm_price_inr : float
        Observed benchmark price converted to portfolio base currency.
    terminal_val : float
        Total asset terminal value in base currency.
    shadow_terminal_val : float
        Total shadow benchmark terminal value in base currency.
    val_local : float
        Total asset terminal value in local currency.
    shadow_terminal_val_local : float
        Total shadow benchmark terminal value in local currency.
    after_tax_terminal_val : float
        Estimated liquidating value net of accrued capital gains tax.
    """

    m_price: float
    m_bm_price: float
    m_bm_price_inr: float
    terminal_val: float
    shadow_terminal_val: float
    val_local: float
    shadow_terminal_val_local: float
    after_tax_terminal_val: float


def compute_terminal_val_local(
    state: _IsinState,
    isin: str,
    m_date: date,
    m_price: float,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> float:
    """Calculate local-currency terminal value across active lots.

    Parameters
    ----------
    state : _IsinState
        Current simulation state for the instrument.
    isin : str
        Instrument ISIN code.
    m_date : date
        Evaluation date.
    m_price : float
        Base currency closing price.
    fx_provider : FXRateProvider | None
        Provider for converting between currencies.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        Cached exchange rate resolver function.

    Returns
    -------
    float
        Aggregated local currency terminal value.
    """
    terminal_val_local = 0.0
    for lot in state.fifo.active_lots:
        if lot.currency_id and lot.currency_id != state.default_curr and fx_provider:
            fx_rate_snap_lot = get_fx_fn(state, isin, m_date, lot.currency_id)
            m_price_local = (
                m_price / fx_rate_snap_lot
                if (fx_rate_snap_lot is not None and fx_rate_snap_lot > 0)
                else float("nan")
            )
            terminal_val_local += lot.qty * m_price_local
        else:
            terminal_val_local += lot.qty * m_price
    return terminal_val_local


def compute_after_tax_terminal_val(
    state: _IsinState,
    fy_table: FYMacroParametersTable,
    m_date: date,
    m_price: float,
    remaining_ltcg_exemption: float,
) -> float:
    """Calculate post-tax liquidating value accounting for accrued capital gains liability.

    Parameters
    ----------
    state : _IsinState
        Current simulation state.
    fy_table : FYMacroParametersTable
        Tax rules and macroeconomic parameters table.
    m_date : date
        Current evaluation date.
    m_price : float
        Current closing price.
    remaining_ltcg_exemption : float
        Unutilized annual LTCG exemption amount.

    Returns
    -------
    float
        Net liquidating value after accrued tax deductions.
    """
    after_tax_val = 0.0
    for lot in state.fifo.active_lots:
        if lot.qty <= 1e-8:
            continue
        lbd = lot.date
        holding_type = fy_table.get_holding_type(
            state.tax_type, state.tax_subtype, lbd or m_date, m_date
        )
        ltcg_rate, stcg_rate = fy_table.get_tax_rates(
            state.tax_type, state.tax_subtype, lbd or m_date, m_date
        )
        pnl = (m_price - lot.price) * lot.qty
        unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
        unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
        taxable_ltcg = max(0.0, unreal_ltcg - remaining_ltcg_exemption)
        ltcg_tax = taxable_ltcg * ltcg_rate
        stcg_tax = unreal_stcg * stcg_rate
        after_tax_val += (lot.qty * m_price) - (ltcg_tax + stcg_tax)
    return after_tax_val


def compute_daily_terminals(
    m_row: TradeRecord,
    m_date: date,
    state: _IsinState,
    isin: str,
    fy_table: FYMacroParametersTable,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> _DailyTerminals:
    """Compute portfolio terminal values, shadow benchmark values, and after-tax terminal value.

    Parameters
    ----------
    m_row : TradeRecord
        Market observation record for current day.
    m_date : date
        Current market date.
    state : _IsinState
        Simulation state container.
    isin : str
        Instrument ISIN code.
    fy_table : FYMacroParametersTable
        Macro tax parameter lookup table.
    fx_provider : FXRateProvider | None
        Currency FX provider.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        FX rate retriever function.

    Returns
    -------
    _DailyTerminals
        Calculated valuation and benchmark prices bundle.
    """
    m_price = float(m_row.get("Closing_Price") or 0.0)
    remaining_ltcg = float(m_row.get("Equity_LTCG_Exemption") or 0.0)
    m_bm_price = state.bm_provider.get_bm_price(m_date)
    if not m_bm_price or m_bm_price <= 0:
        m_bm_price = float("nan")

    fx_rate_snap = 1.0
    if (
        state.fifo.active_lots
        and state.fifo.active_lots[0].currency_id
        and state.fifo.active_lots[0].currency_id != state.default_curr
        and fx_provider
    ):
        fx_val = get_fx_fn(state, isin, m_date, state.fifo.active_lots[0].currency_id)
        fx_rate_snap = fx_val if fx_val is not None else float("nan")

    m_bm_price_inr = m_bm_price * fx_rate_snap
    terminal_val = state.fifo.get_terminal_value(m_price)
    shadow_terminal_val = state.fifo.get_shadow_terminal_value(m_bm_price_inr)
    shadow_terminal_val_local = state.fifo.get_shadow_terminal_value(m_bm_price)

    val_local = compute_terminal_val_local(state, isin, m_date, m_price, fx_provider, get_fx_fn)
    after_tax_terminal_val = compute_after_tax_terminal_val(
        state, fy_table, m_date, m_price, remaining_ltcg
    )

    pt = state.isin_terminals.setdefault(m_date, TerminalValueRecord())
    pt.val += terminal_val
    pt.shadow_val += shadow_terminal_val
    pt.val_local += val_local
    pt.shadow_val_local += shadow_terminal_val_local
    pt.after_tax_val += after_tax_terminal_val

    return _DailyTerminals(
        m_price=m_price,
        m_bm_price=m_bm_price,
        m_bm_price_inr=m_bm_price_inr,
        terminal_val=terminal_val,
        shadow_terminal_val=shadow_terminal_val,
        val_local=val_local,
        shadow_terminal_val_local=shadow_terminal_val_local,
        after_tax_terminal_val=after_tax_terminal_val,
    )


def compute_cagr_and_drawdown(
    m_date: date,
    terminals: _DailyTerminals,
    state: _IsinState,
) -> tuple[float | None, str, float | None, str, float]:
    """Derive volume-weighted CAGR and running peak max drawdown.

    Parameters
    ----------
    m_date : date
        Evaluation date.
    terminals : _DailyTerminals
        Daily price and valuation container.
    state : _IsinState
        Simulation state tracking holdings and peak prices.

    Returns
    -------
    tuple[float | None, str, float | None, str, float]
        Tuple of (instrument CAGR, status, benchmark CAGR, status, running max drawdown).
    """
    closing_units = state.fifo.get_closing_units()
    inst_cagr: float | None = None
    inst_cagr_status: str = "UNDEFINED"
    inst_bm_cagr: float | None = None
    inst_bm_cagr_status: str = "UNDEFINED"

    if closing_units > 0:
        avg_cost = state.fifo.get_average_cost()
        avg_bm_cost = state.fifo.get_average_bm_cost()
        weighted_days = (
            sum(lot.qty * (m_date - lot.date).days for lot in state.fifo.active_lots if lot.date)
            / closing_units
        )
        inst_age = max(int(weighted_days), 1)

        if avg_cost > 0:
            inst_cagr_res = calculate_cagr(avg_cost, terminals.m_price, inst_age)
            inst_cagr = inst_cagr_res.value
            inst_cagr_status = inst_cagr_res.status
        if avg_bm_cost > 0:
            inst_bm_cagr_res = calculate_cagr(avg_bm_cost, terminals.m_bm_price_inr, inst_age)
            inst_bm_cagr = inst_bm_cagr_res.value
            inst_bm_cagr_status = inst_bm_cagr_res.status

    if terminals.m_price > state.running_peak_price:
        state.running_peak_price = terminals.m_price

    if state.running_peak_price > 0:
        current_dd = (terminals.m_price - state.running_peak_price) / state.running_peak_price
        if current_dd < state.running_max_dd:
            state.running_max_dd = current_dd

    return (
        inst_cagr,
        inst_cagr_status,
        inst_bm_cagr,
        inst_bm_cagr_status,
        state.running_max_dd,
    )


def compute_local_xirr_metrics(
    m_date: date,
    terminals: _DailyTerminals,
    state: _IsinState,
) -> tuple[float | None, str, float | None, str]:
    """Derive local currency asset and benchmark XIRRs.

    Parameters
    ----------
    m_date : date
        Evaluation date.
    terminals : _DailyTerminals
        Daily terminal valuations.
    state : _IsinState
        Simulation state with cashflow history.

    Returns
    -------
    tuple[float | None, str, float | None, str]
        Tuple of (local XIRR, status, benchmark local XIRR, status).
    """
    cf_dates_local = [c.date for c in state.isin_cashflows if c.date <= m_date]
    cf_amounts_local = [c.amount_local for c in state.isin_cashflows if c.date <= m_date]
    xirr_local_res = calculate_xirr(
        cf_dates_local + [m_date], cf_amounts_local + [terminals.val_local]
    )
    bm_cf_local = state.bm_cf_amounts_local[: len(cf_dates_local)]
    bm_xirr_local_res = calculate_xirr(
        cf_dates_local + [m_date], bm_cf_local + [terminals.shadow_terminal_val_local]
    )
    return (
        xirr_local_res.value,
        xirr_local_res.status,
        bm_xirr_local_res.value,
        bm_xirr_local_res.status,
    )


def compute_daily_metrics(
    m_date: date,
    terminals: _DailyTerminals,
    state: _IsinState,
) -> InstrumentMetricsRecord:
    """Calculate XIRR, benchmark active return, CAGR, and drawdown metrics.

    Parameters
    ----------
    m_date : date
        Evaluation date.
    terminals : _DailyTerminals
        Computed terminal values.
    state : _IsinState
        Current simulation state.

    Returns
    -------
    InstrumentMetricsRecord
        Typed dictionary containing performance metrics for the date.
    """
    inst_xirr_res = calculate_xirr(
        state.cf_dates + [m_date], state.cf_amounts + [terminals.terminal_val]
    )
    bm_xirr_res = calculate_xirr(
        state.cf_dates + [m_date], state.bm_cf_amounts + [terminals.shadow_terminal_val]
    )
    after_tax_res = calculate_xirr(
        state.cf_dates + [m_date], state.cf_amounts + [terminals.after_tax_terminal_val]
    )

    inst_xirr = inst_xirr_res.value
    bm_xirr_val = bm_xirr_res.value
    inst_active_return = (
        inst_xirr - bm_xirr_val if inst_xirr is not None and bm_xirr_val is not None else None
    )
    is_lagging = (
        inst_xirr < bm_xirr_val if inst_xirr is not None and bm_xirr_val is not None else None
    )

    cagr, cagr_st, bm_cagr, bm_cagr_st, max_dd = compute_cagr_and_drawdown(m_date, terminals, state)
    xirr_loc, xirr_loc_st, bm_loc, bm_loc_st = compute_local_xirr_metrics(m_date, terminals, state)

    return {
        "cagr": cagr,
        "cagr_status": cagr_st,
        "bm_cagr": bm_cagr,
        "bm_cagr_status": bm_cagr_st,
        "xirr": inst_xirr,
        "xirr_status": inst_xirr_res.status,
        "bm_xirr": bm_xirr_val,
        "bm_xirr_status": bm_xirr_res.status,
        "after_tax_xirr": after_tax_res.value,
        "after_tax_xirr_status": after_tax_res.status,
        "active_return": inst_active_return,
        "is_lagging": is_lagging,
        "max_drawdown": max_dd,
        "xirr_local": xirr_loc,
        "xirr_local_status": xirr_loc_st,
        "bm_xirr_local": bm_loc,
        "bm_xirr_local_status": bm_loc_st,
        "active_return_local": (
            xirr_loc - bm_loc if xirr_loc is not None and bm_loc is not None else None
        ),
        "fx_xirr_impact": (
            inst_xirr - xirr_loc if inst_xirr is not None and xirr_loc is not None else None
        ),
    }


def assemble_snapshots_df(isin_snapshots: list[SnapshotRecord]) -> pl.DataFrame | None:
    """Materialize snapshot records into typed Polars DataFrame with schema overrides.

    Parameters
    ----------
    isin_snapshots : list[SnapshotRecord]
        List of generated snapshot records.

    Returns
    -------
    pl.DataFrame | None
        Materialized Polars DataFrame, or None if snapshot list is empty.
    """
    if not isin_snapshots:
        return None
    schema_overrides = {
        "BM_Buy_Price": pl.Float64,
        "BENCHMARK_ID": pl.String,
        "Lot_ID": pl.String,
        "Purchase_ID": pl.String,
        "Lot_Source_Type": pl.String,
        "Buy_Date": pl.Date,
        "Lot_CAGR": pl.Float64,
        "Lot_CAGR_Status": pl.String,
        "Lot_CAGR_Local": pl.Float64,
        "CAGR": pl.Float64,
        "CAGR_Status": pl.String,
        "Lot_BM_CAGR": pl.Float64,
        "Lot_BM_CAGR_Status": pl.String,
        "Lot_BM_CAGR_Local": pl.Float64,
        "BM_CAGR": pl.Float64,
        "BM_CAGR_Status": pl.String,
        "Lot_Alpha": pl.Float64,
        "XIRR": pl.Float64,
        "After_Tax_XIRR": pl.Float64,
        "BM_XIRR": pl.Float64,
        "BM_XIRR_Local": pl.Float64,
        "Active_Return": pl.Float64,
        "Active_Return_Local": pl.Float64,
        "Is_Lagging_Benchmark": pl.Boolean,
        "XIRR_Local": pl.Float64,
        "FX_XIRR_Impact": pl.Float64,
    }
    return pl.DataFrame(
        [s.model_dump(by_alias=True) for s in isin_snapshots],
        schema_overrides=schema_overrides,
        infer_schema_length=None,
    )
