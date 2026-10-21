"""Chronological purchase and sale transaction application to FIFO portfolio.

Owns
----
- apply_purchases: Apply historical buy transactions up to evaluation date into FIFO queue.
- record_purchase: Register buy lot, compute benchmark shadow units, and append cashflows.
- resolve_sale_prices: Determine transaction price, local price, and proceeds for a sale.
- apply_sales: Apply historical sell transactions up to evaluation date into FIFO queue.
- record_sale: Register sale disposal, match benchmark flows, and record realized events.

Does not own
-------------
- FIFO queue liquidation state (owned by domain.investments.lots.fifo).
- Market price simulation loop (owned by application.investments.isin_processor).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date

from personal_finance_etl.application.investments.isin_service.classifier import (
    is_zero_proceeds_re_adjustment,
)
from personal_finance_etl.application.investments.isin_service.state import _IsinState
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    IsinMasterRecord,
    TradeRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import LotBuyParameters
from personal_finance_etl.domain.market.fx import FXRateProvider

__all__ = [
    "apply_purchases",
    "apply_sales",
    "record_purchase",
    "record_sale",
    "resolve_sale_prices",
]


def record_purchase(
    row: TradeRecord,
    row_dt_obj: date,
    state: _IsinState,
    isin: str,
    master_row: IsinMasterRecord,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> None:
    """Register a single buy lot into FIFO portfolio and update cashflow states.

    Parameters
    ----------
    row : TradeRecord
        Purchase trade record.
    row_dt_obj : date
        Parsed transaction execution date.
    state : _IsinState
        Simulation state for current ISIN.
    isin : str
        Instrument ISIN code.
    master_row : IsinMasterRecord
        Instrument master reference dictionary.
    fx_provider : FXRateProvider | None
        Currency FX rate provider.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        Function resolving cached FX rates.
    """
    qty = float(row["Quantity"])
    b_price = float(row.get("Price") or 0.0)

    v_val = row.get("Value")
    buy_val = float(v_val) if v_val is not None else float(qty * b_price)

    bm_p_raw = state.bm_provider.get_bm_price(row_dt_obj)
    if not bm_p_raw or bm_p_raw <= 0:
        bm_p_raw = float("nan")

    _pl_val = row.get("Price_Local")
    price_local = float(_pl_val) if _pl_val is not None else b_price
    currency_id = str(row.get("CURRENCY_ID") or master_row.get("CURRENCY_ID") or state.default_curr)
    fx_rate_buy = get_fx_fn(state, isin, row_dt_obj, currency_id) if fx_provider else 1.0
    fx_rate_buy = fx_rate_buy if fx_rate_buy is not None else float("nan")

    bm_buy_local = float(bm_p_raw)
    bm_buy_inr = float(bm_p_raw * fx_rate_buy)
    shadow_q = buy_val / bm_buy_inr if bm_buy_inr > 0 else 0.0
    purchase_id = row.get("Purchase_ID")

    state.fifo.buy(
        LotBuyParameters(
            buy_date=row_dt_obj,
            qty=qty,
            price=b_price,
            shadow_qty=shadow_q,
            bm_price=bm_buy_inr,
            price_local=price_local,
            fx_rate_buy=fx_rate_buy,
            currency_id=currency_id,
            bm_buy_local=bm_buy_local,
            purchase_id=purchase_id,
        )
    )
    state.cf_dates.append(row_dt_obj)
    state.cf_amounts.append(-buy_val)
    state.bm_cf_amounts.append(-buy_val)
    buy_val_local = float(qty * price_local)
    state.bm_cf_amounts_local.append(-buy_val_local)
    state.isin_cashflows.append(
        CashflowRecord(
            date=row_dt_obj,
            amount=-buy_val,
            amount_local=-buy_val_local,
            benchmark_amount=-buy_val,
            benchmark_amount_local=-buy_val_local,
        )
    )


def apply_purchases(
    p_inst: list[TradeRecord],
    max_date: date | None,
    state: _IsinState,
    isin: str,
    master_row: IsinMasterRecord,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> None:
    """Process chronological purchases up to max_date into FIFO portfolio and cashflows.

    Parameters
    ----------
    p_inst : list[TradeRecord]
        List of chronological purchase trade records.
    max_date : date | None
        Upper date cutoff, or None to process all trailing trades.
    state : _IsinState
        Simulation state container.
    isin : str
        Instrument ISIN code.
    master_row : IsinMasterRecord
        Instrument master reference metadata.
    fx_provider : FXRateProvider | None
        Currency FX rate provider.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        Function resolving cached FX rates.
    """
    while state.p_idx < len(p_inst):
        row_dt_obj = to_date_obj(p_inst[state.p_idx]["Date"])
        if not row_dt_obj:
            state.p_idx += 1
            continue
        if max_date is not None and row_dt_obj > max_date:
            break

        record_purchase(
            p_inst[state.p_idx],
            row_dt_obj,
            state,
            isin,
            master_row,
            fx_provider,
            get_fx_fn,
        )
        state.p_idx += 1


def resolve_sale_prices(
    row: TradeRecord,
    row_dt_obj: date,
    isin: str,
    max_date: date | None,
) -> tuple[float, float, float, float, bool]:
    """Resolve and validate transaction price, local price, and proceeds for a sale.

    Parameters
    ----------
    row : TradeRecord
        Sale transaction record.
    row_dt_obj : date
        Parsed sale date.
    isin : str
        Instrument ISIN code.
    max_date : date | None
        Evaluation cutoff date.

    Returns
    -------
    tuple[float, float, float, float, bool]
        Tuple of (sale price, sale proceeds, sale price local, proceeds local, is_re_adjustment).
    """
    s_qty = float(row["Quantity"])
    row_p_val: float | None = row.get("Price")
    sv_val: float | None = row.get("Sell_Value")

    if row_p_val is not None:
        s_price = float(row_p_val)
    elif sv_val is not None and s_qty > 0:
        s_price = float(sv_val) / s_qty
    else:
        msg_suffix = (
            "refusing to substitute the market close."
            if max_date is not None
            else "refusing to create a zero-price sale."
        )
        raise ValueError(
            f"Sale price and proceeds are both missing for ISIN={isin} "
            f"on {row_dt_obj}; {msg_suffix}"
        )

    s_price = float(s_price)
    is_re_adj = is_zero_proceeds_re_adjustment(
        isin=isin,
        quantity=s_qty,
        price=s_price,
        proceeds=sv_val,
    )
    if (not math.isfinite(s_price) or s_price <= 0) and not is_re_adj:
        raise ValueError(f"Invalid sale price for ISIN={isin} on {row_dt_obj}: {s_price!r}")

    s_val = 0.0 if is_re_adj else float(sv_val) if sv_val is not None else float(s_qty * s_price)
    _spl_val = row.get("Sell_Price_Local")
    s_price_local = 0.0 if is_re_adj else float(_spl_val) if _spl_val is not None else s_price
    s_val_local = 0.0 if is_re_adj else float(s_qty * s_price_local)

    return s_price, s_val, s_price_local, s_val_local, is_re_adj


def record_sale(
    row: TradeRecord,
    row_dt_obj: date,
    s_price: float,
    s_val: float,
    s_price_local: float,
    s_val_local: float,
    state: _IsinState,
    isin: str,
    master_row: IsinMasterRecord,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> None:
    """Register sale disposal into FIFO queue, match benchmark flows, and update cashflows.

    Parameters
    ----------
    row : TradeRecord
        Sale trade record.
    row_dt_obj : date
        Sale transaction date.
    s_price : float
        Base currency unit price.
    s_val : float
        Base currency sale value.
    s_price_local : float
        Local currency unit price.
    s_val_local : float
        Local currency sale value.
    state : _IsinState
        Simulation state container.
    isin : str
        Instrument ISIN code.
    master_row : IsinMasterRecord
        Instrument master metadata.
    fx_provider : FXRateProvider | None
        Currency FX provider.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        Function resolving cached FX rates.
    """
    s_qty = float(row["Quantity"])
    currency_id = str(row.get("CURRENCY_ID") or master_row.get("CURRENCY_ID") or state.default_curr)
    fx_rate_sell = get_fx_fn(state, isin, row_dt_obj, currency_id) if fx_provider else 1.0
    fx_rate_sell = fx_rate_sell if fx_rate_sell is not None else float("nan")

    state.cf_dates.append(row_dt_obj)
    state.cf_amounts.append(s_val)

    sale_id = row.get("Sale_ID")
    events = state.fifo.sell(
        row_dt_obj,
        s_qty,
        s_price,
        price_local=s_price_local,
        fx_rate_sell=fx_rate_sell,
        sale_id=sale_id,
    )

    bm_sell_price_local = state.bm_provider.get_bm_price(row_dt_obj)
    bm_sell_price_local = (
        float(bm_sell_price_local) if bm_sell_price_local is not None else float("nan")
    )
    bm_sell_price_inr = bm_sell_price_local * fx_rate_sell
    shadow_qty_sold = float(sum(e.get("shadow_qty_sold", 0.0) or 0.0 for e in events))
    bm_sell_value_inr = shadow_qty_sold * bm_sell_price_inr
    bm_sell_value_local = shadow_qty_sold * bm_sell_price_local

    state.bm_cf_amounts.append(bm_sell_value_inr)
    state.bm_cf_amounts_local.append(bm_sell_value_local)
    state.isin_cashflows.append(
        CashflowRecord(
            date=row_dt_obj,
            amount=s_val,
            amount_local=s_val_local,
            benchmark_amount=bm_sell_value_inr,
            benchmark_amount_local=bm_sell_value_local,
        )
    )
    state.isin_realized.extend(events)


def apply_sales(
    s_inst: list[TradeRecord],
    max_date: date | None,
    state: _IsinState,
    isin: str,
    master_row: IsinMasterRecord,
    fx_provider: FXRateProvider | None,
    get_fx_fn: Callable[[_IsinState, str, date, str], float | None],
) -> None:
    """Process chronological sales up to max_date into FIFO portfolio and cashflows.

    Parameters
    ----------
    s_inst : list[TradeRecord]
        List of chronological sale trade records.
    max_date : date | None
        Upper date cutoff, or None to process all trailing trades.
    state : _IsinState
        Simulation state container.
    isin : str
        Instrument ISIN code.
    master_row : IsinMasterRecord
        Instrument master metadata.
    fx_provider : FXRateProvider | None
        Currency FX provider.
    get_fx_fn : Callable[[_IsinState, str, date, str], float | None]
        Function resolving cached FX rates.
    """
    while state.s_idx < len(s_inst):
        row_dt_obj = to_date_obj(s_inst[state.s_idx]["Date"])
        if not row_dt_obj:
            state.s_idx += 1
            continue
        if max_date is not None and row_dt_obj > max_date:
            break

        s_price, s_val, s_price_local, s_val_local, _ = resolve_sale_prices(
            s_inst[state.s_idx], row_dt_obj, isin, max_date
        )
        record_sale(
            s_inst[state.s_idx],
            row_dt_obj,
            s_price,
            s_val,
            s_price_local,
            s_val_local,
            state,
            isin,
            master_row,
            fx_provider,
            get_fx_fn,
        )
        state.s_idx += 1
