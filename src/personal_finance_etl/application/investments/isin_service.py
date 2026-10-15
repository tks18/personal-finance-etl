"""Per-ISIN processing and multiprocessing orchestration service.

Owns
----
- IsinProcessor: Core per-ISIN chronological quant engine constructing daily lot snapshots,
  cash flows, terminal values, realized gain events, and reconciliation events.
- IsinPipeline: Orchestrates worker tasks across concurrent.futures.ProcessPoolExecutor,
  writing intermediate per-ISIN Parquet partitions and aggregating portfolio partitions.
- _process_isin_worker: Top-level picklable multiprocessing worker entry point.
- is_indian_rights_entitlement_isin, _is_zero_proceeds_re_adjustment classification helpers.

Does not own
-------------
- FIFO queue state mutation (owned by domain.investments.lots.fifo).
- Presentation layer post-processing (owned by application.investments.aggregation_service).
"""

import concurrent.futures
import math
import multiprocessing
import os
import time
import traceback
from datetime import date
from typing import Any, cast

import polars as pl

from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    ISINProcessResult,
    ISINTags,
    PipelineExecutionResult,
    SnapshotRecord,
    TerminalValueRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.investments.performance.xirr import calculate_xirr
from personal_finance_etl.domain.investments.portfolio.snapshots import SnapshotGenerator
from personal_finance_etl.domain.investments.valuation.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXRateUnavailableError,
    FXValidationGate,
)
from personal_finance_etl.domain.market.macro import FYMacroParametersTable
from personal_finance_etl.infrastructure.logging.setup import (
    logger,
    setup_worker_logging,
    start_worker_listener,
    stop_worker_listener,
)


def is_indian_rights_entitlement_isin(isin: str | None) -> bool:
    """Return whether an Indian ISIN matches the observed RE code pattern.

    The ``20`` substring is a candidate classifier (Python slice [7:9]), not
    proof of an expiry event. Transaction-level checks are still required.
    """
    if not isin:
        return False

    normalized = isin.strip().upper()
    return len(normalized) == 12 and normalized.startswith("INE") and normalized[7:9] == "20"


def _is_zero_proceeds_re_adjustment(
    isin: str,
    quantity: float,
    price: float,
    proceeds: float | None,
) -> bool:
    """Recognize a zero-proceeds adjustment for a candidate Indian RE ISIN.

    Require an explicit zero proceeds value. Missing proceeds are not enough
    evidence to bypass normal sale-price validation.
    """
    if not is_indian_rights_entitlement_isin(isin) or quantity <= 0:
        return False
    if not math.isfinite(price) or price != 0.0 or proceeds is None:
        return False

    try:
        proceeds_value = float(proceeds)
    except (TypeError, ValueError):
        return False

    return math.isfinite(proceeds_value) and proceeds_value == 0.0


class IsinProcessor:
    """Core chronological quantitative calculation engine for an individual ISIN."""

    def __init__(
        self,
        fy_table: FYMacroParametersTable,
        start_date: date | None,
        end_date: date | None,
        rules: FinancialRules,
        fx_provider: Any = None,
    ) -> None:
        self.fy_table = fy_table
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules
        self.fx_provider = fx_provider

    def process(
        self,
        isin: str,
        p_inst: list[dict[str, Any]],
        s_inst: list[dict[str, Any]],
        m_inst: list[dict[str, Any]],
        master_row: dict[str, Any],
        bm_map: dict[date, float],
    ) -> ISINProcessResult | None:
        if not m_inst:
            return None

        logger.debug(f"[Processor] ISIN {isin} computing across {len(m_inst)} historical dates.")

        tax_type = str(master_row.get("TAX_TYPE", "equity"))
        tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        bench_id = master_row.get("BENCHMARK_ID")

        bm_provider = BenchmarkPriceProvider(bench_id, None, prebuilt_map=bm_map)
        snapshot_generator = SnapshotGenerator(self.fy_table, self.rules, isin, master_row)

        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        fifo = FIFOPortfolio(tax_type, tax_subtype, self.fy_table, default_curr, isin)
        cf_dates: list[date] = []
        cf_amounts: list[float] = []
        bm_cf_amounts: list[float] = []
        bm_cf_amounts_local: list[float] = []

        first_p_date = (
            to_date_obj(p_inst[0]["Date"])
            if p_inst
            else (to_date_obj(m_inst[0]["Date"]) if m_inst else None)
        )
        if not first_p_date:
            return None

        p_idx = s_idx = 0
        isin_cashflows: list[CashflowRecord] = []
        isin_terminals: dict[date, TerminalValueRecord] = {}
        isin_realized: list[dict[str, Any]] = []
        isin_recon_events: list[dict[str, Any]] = []
        isin_snapshots: list[SnapshotRecord] = []
        running_peak_price = 0.0
        running_max_dd = 0.0

        # Pre-Quant FX gate: warn when an instrument is in a foreign currency but has no
        # FX provider or when the provider cannot supply a rate.
        FXValidationGate(self.rules, self.fx_provider).validate(isin, master_row, first_p_date)

        _fx_cache: dict[tuple[date, str], float | None] = {}

        def _get_fx(d: date, curr: str) -> float | None:
            key = (d, curr)
            if key not in _fx_cache:
                rate = self.fx_provider.get_rate(d, curr) if self.fx_provider else None
                if rate is not None:
                    rate = float(rate)
                if curr == default_curr:
                    rate = 1.0
                if rate is None or not math.isfinite(rate) or rate <= 0:
                    raise FXRateUnavailableError(
                        f"ISIN={isin} ({curr}): no valid FX rate available on {d}. "
                        "Refusing to continue with a fabricated or non-finite conversion."
                    )
                _fx_cache[key] = rate
            return _fx_cache[key]

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

                bm_p_raw = bm_provider.get_bm_price(row_dt_obj)
                if not bm_p_raw or bm_p_raw <= 0:
                    bm_p_raw = float("nan")

                _pl_val = row.get("Price_Local")
                price_local = float(_pl_val) if _pl_val is not None else b_price
                currency_id = str(
                    row.get("CURRENCY_ID")
                    or master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                )
                fx_rate_buy = _get_fx(row_dt_obj, currency_id) if self.fx_provider else 1.0
                fx_rate_buy = fx_rate_buy if fx_rate_buy is not None else float("nan")

                bm_buy_local = float(bm_p_raw)
                bm_buy_inr = float(bm_p_raw * fx_rate_buy)
                shadow_q = buy_val / bm_buy_inr if bm_buy_inr > 0 else 0.0
                purchase_id = row.get("Purchase_ID")

                fifo.buy(
                    row_dt_obj,
                    qty,
                    b_price,
                    shadow_q,
                    bm_buy_inr,
                    price_local=price_local,
                    fx_rate_buy=fx_rate_buy,
                    currency_id=currency_id,
                    bm_buy_local=bm_buy_local,
                    purchase_id=purchase_id,
                )
                cf_dates.append(row_dt_obj)
                cf_amounts.append(-buy_val)
                bm_cf_amounts.append(-buy_val)
                buy_val_local = float(qty * price_local)
                bm_cf_amounts_local.append(-buy_val_local)
                isin_cashflows.append(
                    CashflowRecord(
                        date=row_dt_obj,
                        amount=-buy_val,
                        amount_local=-buy_val_local,
                        benchmark_amount=-buy_val,
                        benchmark_amount_local=-buy_val_local,
                    )
                )
                p_idx += 1

            while s_idx < len(s_inst):
                row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
                if row_dt_obj is None or row_dt_obj > m_date:
                    break
                row = s_inst[s_idx]
                s_qty = float(row["Quantity"])

                row_p_val: float | None = row.get("Price")
                sv_val: float | None = row.get("Sell_Value")

                if row_p_val is not None:
                    s_price = float(row_p_val)
                elif sv_val is not None and s_qty > 0:
                    s_price = float(sv_val) / s_qty
                else:
                    raise ValueError(
                        f"Sale price and proceeds are both missing for ISIN={isin} "
                        f"on {row_dt_obj}; refusing to substitute the market close."
                    )

                s_price = float(s_price)
                is_re_adjustment = _is_zero_proceeds_re_adjustment(
                    isin=isin,
                    quantity=s_qty,
                    price=s_price,
                    proceeds=sv_val,
                )
                if (not math.isfinite(s_price) or s_price <= 0) and not is_re_adjustment:
                    raise ValueError(
                        f"Invalid sale price for ISIN={isin} on {row_dt_obj}: {s_price!r}"
                    )
                s_val = (
                    0.0
                    if is_re_adjustment
                    else float(sv_val)
                    if sv_val is not None
                    else float(s_qty * s_price)
                )

                _spl_val = row.get("Sell_Price_Local")
                s_price_local = (
                    0.0
                    if is_re_adjustment
                    else float(_spl_val)
                    if _spl_val is not None
                    else s_price
                )
                s_val_local = 0.0 if is_re_adjustment else float(s_qty * s_price_local)
                currency_id = str(
                    row.get("CURRENCY_ID")
                    or master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                )
                fx_rate_sell = _get_fx(row_dt_obj, currency_id) if self.fx_provider else 1.0
                fx_rate_sell = fx_rate_sell if fx_rate_sell is not None else float("nan")

                cf_dates.append(row_dt_obj)
                cf_amounts.append(s_val)

                sale_id = row.get("Sale_ID")
                events = fifo.sell(
                    row_dt_obj,
                    s_qty,
                    s_price,
                    price_local=s_price_local,
                    fx_rate_sell=fx_rate_sell,
                    sale_id=sale_id,
                )

                bm_sell_price_local = bm_provider.get_bm_price(row_dt_obj)
                bm_sell_price_local = (
                    float(bm_sell_price_local) if bm_sell_price_local is not None else float("nan")
                )
                bm_sell_price_inr = bm_sell_price_local * fx_rate_sell
                shadow_qty_sold = float(sum(e.get("shadow_qty_sold", 0.0) or 0.0 for e in events))
                bm_sell_value_inr = shadow_qty_sold * bm_sell_price_inr
                bm_sell_value_local = shadow_qty_sold * bm_sell_price_local

                bm_cf_amounts.append(bm_sell_value_inr)
                bm_cf_amounts_local.append(bm_sell_value_local)
                isin_cashflows.append(
                    CashflowRecord(
                        date=row_dt_obj,
                        amount=s_val,
                        amount_local=s_val_local,
                        benchmark_amount=bm_sell_value_inr,
                        benchmark_amount_local=bm_sell_value_local,
                    )
                )

                isin_realized.extend(events)
                s_idx += 1

            # Units reconciliation
            q_cf, q_recon_events = fifo.reconcile_quantity(
                m_row.get("Quantity"), m_date, bm_provider.get_bm_price(m_date) or 0.0
            )
            for re in q_recon_events:
                re["ISIN"] = isin
            isin_recon_events.extend(q_recon_events)

            for cf in q_cf:
                cf_dates.append(cast(date, cf["date"]))
                amt = float(cast(float, cf["amount"]))
                cf_amounts.append(amt)
                bm_cf_amounts.append(amt)
                bm_cf_amounts_local.append(amt)
                isin_cashflows.append(
                    CashflowRecord(
                        date=cast(date, cf["date"]),
                        amount=amt,
                        amount_local=amt,
                        benchmark_amount=0.0,
                        benchmark_amount_local=0.0,
                    )
                )

            cb_recon_events = fifo.reconcile_cost_basis(
                m_row.get("Buy_Value"), m_row.get("Buy_Value_Local"), m_date
            )
            for re in cb_recon_events:
                re["ISIN"] = isin
            isin_recon_events.extend(cb_recon_events)

            if not fifo.active_lots:
                continue

            if self.start_date and m_date < self.start_date:
                continue
            if self.end_date and m_date > self.end_date:
                continue

            m_price = float(m_row["Closing_Price"])
            remaining_ltcg_exemption = float(m_row.get("Equity_LTCG_Exemption") or 0.0)
            m_bm_price = bm_provider.get_bm_price(m_date)
            if not m_bm_price or m_bm_price <= 0:
                m_bm_price = float("nan")

            fx_rate_snap = 1.0
            if (
                fifo.active_lots
                and fifo.active_lots[0].currency_id
                and fifo.active_lots[0].currency_id
                != getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                and self.fx_provider
            ):
                fx_val = _get_fx(m_date, fifo.active_lots[0].currency_id)
                fx_rate_snap = fx_val if fx_val is not None else float("nan")

            m_bm_price_inr = m_bm_price * fx_rate_snap

            closing_units = fifo.get_closing_units()
            terminal_val = fifo.get_terminal_value(m_price)
            shadow_terminal_val = fifo.get_shadow_terminal_value(m_bm_price_inr)
            shadow_terminal_val_local = fifo.get_shadow_terminal_value(m_bm_price)

            terminal_val_local = 0.0
            for lot in fifo.active_lots:
                if (
                    lot.currency_id
                    and lot.currency_id != getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                    and self.fx_provider
                ):
                    fx_rate_snap_lot = _get_fx(m_date, lot.currency_id)
                    m_price_local = (
                        m_price / fx_rate_snap_lot
                        if (fx_rate_snap_lot is not None and fx_rate_snap_lot > 0)
                        else float("nan")
                    )
                    terminal_val_local += lot.qty * m_price_local
                else:
                    terminal_val_local += lot.qty * m_price

            pt = isin_terminals.setdefault(m_date, TerminalValueRecord())
            pt.val += terminal_val
            pt.shadow_val += shadow_terminal_val
            pt.val_local += terminal_val_local
            pt.shadow_val_local += shadow_terminal_val_local

            after_tax_terminal_val = 0.0
            for lot in fifo.active_lots:
                if lot.qty <= 1e-8:
                    continue
                lbd = lot.date
                holding_type = self.fy_table.get_holding_type(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )
                ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
                    tax_type, tax_subtype, lbd or m_date, m_date
                )
                pnl = (m_price - lot.price) * lot.qty
                unreal_ltcg = max(0.0, pnl) if holding_type == "LTCG" else 0.0
                unreal_stcg = max(0.0, pnl) if holding_type == "STCG" else 0.0
                taxable_ltcg = max(0.0, unreal_ltcg - remaining_ltcg_exemption)
                ltcg_tax = taxable_ltcg * ltcg_rate
                stcg_tax = unreal_stcg * stcg_rate
                after_tax_terminal_val += (lot.qty * m_price) - (ltcg_tax + stcg_tax)

            pt.after_tax_val += after_tax_terminal_val

            inst_xirr_result = calculate_xirr(cf_dates + [m_date], cf_amounts + [terminal_val])
            bm_xirr_result = calculate_xirr(
                cf_dates + [m_date], bm_cf_amounts + [shadow_terminal_val]
            )
            inst_after_tax_xirr_result = calculate_xirr(
                cf_dates + [m_date], cf_amounts + [after_tax_terminal_val]
            )
            inst_xirr = inst_xirr_result.value
            bm_xirr_val = bm_xirr_result.value
            inst_after_tax_xirr = inst_after_tax_xirr_result.value

            inst_active_return = (
                inst_xirr - bm_xirr_val
                if inst_xirr is not None and bm_xirr_val is not None
                else None
            )
            is_lagging = (
                inst_xirr < bm_xirr_val
                if inst_xirr is not None and bm_xirr_val is not None
                else None
            )

            inst_cagr: float | None = None
            inst_cagr_status: str = "UNDEFINED"
            inst_bm_cagr: float | None = None
            inst_bm_cagr_status: str = "UNDEFINED"
            if closing_units > 0:
                avg_cost = fifo.get_average_cost()
                avg_bm_cost = fifo.get_average_bm_cost()

                weighted_days = (
                    sum(lot.qty * (m_date - lot.date).days for lot in fifo.active_lots if lot.date)
                    / closing_units
                )
                inst_age = max(int(weighted_days), 1)

                if avg_cost > 0:
                    inst_cagr_res = calculate_cagr(avg_cost, m_price, inst_age)
                    inst_cagr = inst_cagr_res.value
                    inst_cagr_status = inst_cagr_res.status
                if avg_bm_cost > 0:
                    inst_bm_cagr_res = calculate_cagr(avg_bm_cost, m_bm_price_inr, inst_age)
                    inst_bm_cagr = inst_bm_cagr_res.value
                    inst_bm_cagr_status = inst_bm_cagr_res.status

            if m_price > running_peak_price:
                running_peak_price = m_price

            if running_peak_price > 0:
                current_dd = (m_price - running_peak_price) / running_peak_price
                if current_dd < running_max_dd:
                    running_max_dd = current_dd

            inst_max_dd = running_max_dd

            inst_metrics = {
                "cagr": inst_cagr,
                "cagr_status": inst_cagr_status,
                "bm_cagr": inst_bm_cagr,
                "bm_cagr_status": inst_bm_cagr_status,
                "xirr": inst_xirr,
                "xirr_status": inst_xirr_result.status,
                "bm_xirr": bm_xirr_val,
                "bm_xirr_status": bm_xirr_result.status,
                "after_tax_xirr": inst_after_tax_xirr,
                "after_tax_xirr_status": inst_after_tax_xirr_result.status,
                "active_return": inst_active_return,
                "is_lagging": is_lagging,
                "max_drawdown": inst_max_dd,
            }

            # Local XIRR Calculation
            cf_dates_local = [c.date for c in isin_cashflows if c.date <= m_date]
            cf_amounts_local = [c.amount_local for c in isin_cashflows if c.date <= m_date]
            inst_xirr_local_result = calculate_xirr(
                cf_dates_local + [m_date], cf_amounts_local + [terminal_val_local]
            )

            bm_cf_dates_local = cf_dates_local
            bm_cf_local = bm_cf_amounts_local[: len(cf_dates_local)]
            inst_bm_xirr_local_result = calculate_xirr(
                bm_cf_dates_local + [m_date], bm_cf_local + [shadow_terminal_val_local]
            )
            inst_xirr_local = inst_xirr_local_result.value
            inst_bm_xirr_local = inst_bm_xirr_local_result.value

            inst_metrics["xirr_local"] = inst_xirr_local
            inst_metrics["xirr_local_status"] = inst_xirr_local_result.status
            inst_metrics["bm_xirr_local"] = inst_bm_xirr_local
            inst_metrics["bm_xirr_local_status"] = inst_bm_xirr_local_result.status
            inst_metrics["active_return_local"] = (
                inst_xirr_local - inst_bm_xirr_local
                if inst_xirr_local is not None and inst_bm_xirr_local is not None
                else None
            )
            inst_metrics["fx_xirr_impact"] = (
                inst_xirr - inst_xirr_local
                if inst_xirr is not None and inst_xirr_local is not None
                else None
            )

            exec_res_raw = m_row.get("Execution_Residual")
            execution_residual = float(exec_res_raw) if exec_res_raw is not None else 0.0
            new_snapshots = snapshot_generator.generate(
                fifo,
                m_date,
                m_price,
                m_bm_price,
                inst_metrics,
                fx_provider=self.fx_provider,
                execution_residual=execution_residual,
                remaining_ltcg_exemption=remaining_ltcg_exemption,
            )
            isin_snapshots.extend(new_snapshots)

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

            bm_p_raw = bm_provider.get_bm_price(row_dt_obj)
            if not bm_p_raw or bm_p_raw <= 0:
                bm_p_raw = float("nan")

            _pl_val = row.get("Price_Local")
            price_local = float(_pl_val) if _pl_val is not None else b_price
            currency_id = str(
                row.get("CURRENCY_ID")
                or master_row.get("CURRENCY_ID")
                or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
            )
            fx_rate_buy = (
                self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
            )
            fx_rate_buy = fx_rate_buy if fx_rate_buy is not None else float("nan")

            bm_buy_local = float(bm_p_raw)
            bm_buy_inr = float(bm_p_raw * fx_rate_buy)
            shadow_q = buy_val / bm_buy_inr if bm_buy_inr > 0 else 0.0
            purchase_id = row.get("Purchase_ID")

            fifo.buy(
                row_dt_obj,
                qty,
                b_price,
                shadow_q,
                bm_buy_inr,
                price_local=price_local,
                fx_rate_buy=fx_rate_buy,
                currency_id=currency_id,
                bm_buy_local=bm_buy_local,
                purchase_id=purchase_id,
            )
            cf_dates.append(row_dt_obj)
            cf_amounts.append(-buy_val)
            bm_cf_amounts.append(-buy_val)
            buy_val_local = float(qty * price_local)
            bm_cf_amounts_local.append(-buy_val_local)
            isin_cashflows.append(
                CashflowRecord(
                    date=row_dt_obj,
                    amount=-buy_val,
                    amount_local=-buy_val_local,
                    benchmark_amount=-buy_val,
                    benchmark_amount_local=-buy_val_local,
                )
            )
            p_idx += 1

        while s_idx < len(s_inst):
            row_dt_obj = to_date_obj(s_inst[s_idx]["Date"])
            if not row_dt_obj:
                s_idx += 1
                continue
            row = s_inst[s_idx]
            s_qty = float(row["Quantity"])
            row_p_val = row.get("Price")
            sv_val = row.get("Sell_Value")

            if row_p_val is not None:
                s_price = float(row_p_val)
            elif sv_val is not None and s_qty > 0:
                s_price = float(sv_val) / s_qty
            else:
                raise ValueError(
                    f"Sale price and proceeds are both missing for ISIN={isin} "
                    f"on {row_dt_obj}; refusing to create a zero-price sale."
                )

            s_price = float(s_price)
            is_re_adjustment = _is_zero_proceeds_re_adjustment(
                isin=isin,
                quantity=s_qty,
                price=s_price,
                proceeds=sv_val,
            )
            if (not math.isfinite(s_price) or s_price <= 0) and not is_re_adjustment:
                raise ValueError(f"Invalid sale price for ISIN={isin} on {row_dt_obj}: {s_price!r}")
            s_val = (
                0.0
                if is_re_adjustment
                else float(sv_val)
                if sv_val is not None
                else float(s_qty * s_price)
            )

            _spl_val = row.get("Sell_Price_Local")
            s_price_local = (
                0.0 if is_re_adjustment else float(_spl_val) if _spl_val is not None else s_price
            )
            s_val_local = 0.0 if is_re_adjustment else float(s_qty * s_price_local)
            currency_id = str(
                row.get("CURRENCY_ID")
                or master_row.get("CURRENCY_ID")
                or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
            )
            fx_rate_sell = (
                self.fx_provider.get_rate(row_dt_obj, currency_id) if self.fx_provider else 1.0
            )
            fx_rate_sell = fx_rate_sell if fx_rate_sell is not None else float("nan")

            cf_dates.append(row_dt_obj)
            cf_amounts.append(s_val)

            sale_id = row.get("Sale_ID")
            events = fifo.sell(
                row_dt_obj,
                s_qty,
                s_price,
                price_local=s_price_local,
                fx_rate_sell=fx_rate_sell,
                sale_id=sale_id,
            )

            bm_sell_price_local = bm_provider.get_bm_price(row_dt_obj)
            bm_sell_price_local = (
                float(bm_sell_price_local) if bm_sell_price_local is not None else float("nan")
            )
            bm_sell_price_inr = bm_sell_price_local * fx_rate_sell
            shadow_qty_sold = float(sum(e.get("shadow_qty_sold", 0.0) or 0.0 for e in events))
            bm_sell_value_inr = shadow_qty_sold * bm_sell_price_inr
            bm_sell_value_local = shadow_qty_sold * bm_sell_price_local

            bm_cf_amounts.append(bm_sell_value_inr)
            bm_cf_amounts_local.append(bm_sell_value_local)
            isin_cashflows.append(
                CashflowRecord(
                    date=row_dt_obj,
                    amount=s_val,
                    amount_local=s_val_local,
                    benchmark_amount=bm_sell_value_inr,
                    benchmark_amount_local=bm_sell_value_local,
                )
            )

            isin_realized.extend(events)
            s_idx += 1

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
        df = (
            pl.DataFrame(
                [s.model_dump(by_alias=True) for s in isin_snapshots],
                schema_overrides=schema_overrides,
                infer_schema_length=None,
            )
            if isin_snapshots
            else None
        )

        tags = ISINTags(
            **{
                "class": str(master_row.get("INSTRUMENT_CLASS", "Unknown")),
                "subtype": str(master_row.get("INSTRUMENT_SUBTYPE", "Unknown")),
                "instrument_type": str(master_row.get("INSTRUMENT_TYPE", "Unknown")),
                "sector": str(master_row.get("SECTOR", "Unknown")),
                "industry": str(master_row.get("INDUSTRY", "Unknown")),
                "geo": str(master_row.get("GEO", "Unknown")),
                "country": str(master_row.get("COUNTRY", "Unknown")),
                "currency": str(
                    master_row.get("CURRENCY_ID")
                    or getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
                ),
            }
        )
        return ISINProcessResult(
            df_snapshots=df,
            cashflows=isin_cashflows,
            terminals=isin_terminals,
            realized_events=isin_realized,
            recon_events=isin_recon_events,
            tags=tags,
        )


def _process_isin_worker(
    task: tuple[
        str,
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
        dict[date, float],
        Any,
        Any,
        Any,
        Any,
        Any,
        str,
    ],
) -> tuple[
    bool,
    list[dict[str, Any]],
    dict[date, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any] | None,
]:
    (
        isin,
        p_inst,
        s_inst,
        m_inst,
        master_row,
        bm_map,
        fy_table,
        start_date,
        end_date,
        rules,
        fx_provider,
        tmp_dir,
    ) = task

    logger.debug(
        f"[Worker] Starting processing for ISIN: {isin} with {len(p_inst)} purchases, {len(s_inst)} sales, and {len(m_inst)} market quotes",
        extra={"isin": isin, "stage": "QuantWorker"},
    )

    processor = IsinProcessor(fy_table, start_date, end_date, rules, fx_provider)
    try:
        worker_id = multiprocessing.current_process().name
        logger.debug(
            f"[ENGINE:POOL] {worker_id} started processing ISIN '{isin}'",
            extra={"isin": isin, "stage": "QuantWorker"},
        )
        t0 = time.perf_counter()

        res = processor.process(isin, p_inst, s_inst, m_inst, master_row, bm_map)

        logger.debug(
            f"[ENGINE:POOL] {worker_id} finished ISIN '{isin}' in {(time.perf_counter() - t0) * 1000:.2f}ms",
            extra={"isin": isin, "stage": "QuantWorker"},
        )

        if res is not None:
            df = res.df_snapshots
            isin_cf = [c.model_dump(mode="python") for c in res.cashflows]
            isin_pt = {d: pt.model_dump(mode="python") for d, pt in res.terminals.items()}
            tags = res.tags.model_dump(by_alias=True)
            isin_re = res.realized_events
            isin_recon = res.recon_events

            if df is not None and not df.is_empty():
                df.write_parquet(os.path.join(tmp_dir, f"{isin.replace('/', '_')}.parquet"))
                return True, isin_cf, isin_pt, isin_re, isin_recon, tags, None
            return False, isin_cf, isin_pt, isin_re, isin_recon, tags, None
        return False, [], {}, [], [], {}, None
    except Exception as e:
        tb = traceback.format_exc()
        return False, [], {}, [], [], {}, {"isin": isin, "error": str(e), "traceback": tb}


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk."""

    def __init__(
        self,
        ctx: RunContext,
        isins: list[str],
        tmp_dir: str,
        status_queue: StatusQueue | Any | None = None,
    ):
        self.ctx = ctx
        self.isins = isins
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue

    def _report_step(self, progress: float) -> None:
        if self.status_queue:
            self.status_queue.put(
                EngineStatusMessage(msg="", progress=progress, level=LogLevel.STEP)
            )

    def process_all(self) -> PipelineExecutionResult:
        global_cashflows: list[dict[str, Any]] = []
        portfolio_terminals: dict[date, dict[str, float]] = {}
        realized_events: list[dict[str, Any]] = []
        isin_cashflows: dict[str, list[dict[str, Any]]] = {}
        isin_terminals: dict[str, dict[date, dict[str, Any]]] = {}

        class_cf: dict[str, list[dict[str, Any]]] = {}
        class_pt: dict[str, dict[date, dict[str, float]]] = {}
        class_re: dict[str, list[dict[str, Any]]] = {}

        subtype_cf: dict[str, list[dict[str, Any]]] = {}
        subtype_pt: dict[str, dict[date, dict[str, float]]] = {}
        subtype_re: dict[str, list[dict[str, Any]]] = {}

        instrument_type_cf: dict[str, list[dict[str, Any]]] = {}
        instrument_type_pt: dict[str, dict[date, dict[str, float]]] = {}

        sector_cf: dict[str, list[dict[str, Any]]] = {}
        sector_pt: dict[str, dict[date, dict[str, float]]] = {}

        industry_cf: dict[str, list[dict[str, Any]]] = {}
        industry_pt: dict[str, dict[date, dict[str, float]]] = {}

        geo_cf: dict[str, list[dict[str, Any]]] = {}
        geo_pt: dict[str, dict[date, dict[str, float]]] = {}

        country_cf: dict[str, list[dict[str, Any]]] = {}
        country_pt: dict[str, dict[date, dict[str, float]]] = {}

        currency_cf: dict[str, list[dict[str, Any]]] = {}
        currency_pt: dict[str, dict[date, dict[str, float]]] = {}
        currency_re: dict[str, list[dict[str, Any]]] = {}

        has_data = False
        total_inst = len(self.isins)

        p_dict_pl: dict[Any, pl.DataFrame] = (
            self.ctx.df_p.partition_by("ISIN", as_dict=True) if not self.ctx.df_p.is_empty() else {}
        )
        s_dict_pl: dict[Any, pl.DataFrame] = (
            self.ctx.df_s.partition_by("ISIN", as_dict=True) if not self.ctx.df_s.is_empty() else {}
        )

        m_grouped = (
            (
                self.ctx.df_m.sort(["ISIN", "Date"])
                .group_by(["ISIN", "Date"], maintain_order=True)
                .agg(
                    [
                        pl.col("Quantity").sum().alias("Quantity"),
                        pl.col("Closing_Price").last().alias("Closing_Price"),
                        pl.col("Buy_Value").sum().alias("Buy_Value"),
                        (
                            pl.col("Buy_Value_Local").sum().alias("Buy_Value_Local")
                            if "Buy_Value_Local" in self.ctx.df_m.columns
                            else pl.lit(None).cast(pl.Float64).alias("Buy_Value_Local")
                        ),
                    ]
                )
            )
            if not self.ctx.df_m.is_empty()
            else pl.DataFrame()
        )

        m_dict_pl: dict[Any, pl.DataFrame] = (
            m_grouped.partition_by("ISIN", as_dict=True) if not m_grouped.is_empty() else {}
        )

        bm_maps: dict[str, dict[date, float]] = {}
        for _isin, row in self.ctx.isin_master.items():
            b_id = str(row.get("BENCHMARK_ID", ""))
            if b_id and b_id not in bm_maps:
                bm_maps[b_id] = BenchmarkPriceProvider(b_id, self.ctx.df_b).bm_price_map

        tasks: list[
            tuple[
                str,
                list[dict[str, Any]],
                list[dict[str, Any]],
                list[dict[str, Any]],
                dict[str, Any],
                dict[date, float],
                Any,
                Any,
                Any,
                Any,
                Any,
                str,
            ]
        ] = []
        for isin in self.isins:
            p_df = p_dict_pl.get((isin,)) if (isin,) in p_dict_pl else p_dict_pl.get(isin)
            p_inst = (
                p_df.sort("Date").to_dicts() if p_df is not None and not p_df.is_empty() else []
            )

            s_df = s_dict_pl.get((isin,)) if (isin,) in s_dict_pl else s_dict_pl.get(isin)
            s_inst = (
                s_df.sort("Date").to_dicts() if s_df is not None and not s_df.is_empty() else []
            )

            m_df = m_dict_pl.get((isin,)) if (isin,) in m_dict_pl else m_dict_pl.get(isin)
            m_inst = m_df.to_dicts() if m_df is not None and not m_df.is_empty() else []

            master_row = self.ctx.isin_master.get(isin, {})
            b_id = str(master_row.get("BENCHMARK_ID", ""))
            bm_map = bm_maps.get(b_id, {})

            tasks.append(
                (
                    isin,
                    p_inst,
                    s_inst,
                    m_inst,
                    master_row,
                    bm_map,
                    self.ctx.fy_table,
                    self.ctx.start_date,
                    self.ctx.end_date,
                    self.ctx.rules,
                    self.ctx.fx_provider,
                    self.tmp_dir,
                )
            )

        current_process = multiprocessing.current_process()
        is_daemon = current_process.daemon
        current_process.daemon = False
        worker_queue = start_worker_listener()
        global_recon_events: list[dict[str, Any]] = []

        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=min(4, os.cpu_count() or 1),
                initializer=setup_worker_logging,
                initargs=(worker_queue,),
            ) as executor:
                future_to_isin = {
                    executor.submit(_process_isin_worker, task): task[0] for task in tasks
                }

                for i, future in enumerate(concurrent.futures.as_completed(future_to_isin)):
                    isin = future_to_isin[future]
                    self._report_step(0.05 + 0.8 * (i / total_inst))

                    try:
                        success, isin_cf, isin_pt, isin_re, isin_recon, tags, error_info = (
                            future.result()
                        )
                    except Exception as e:
                        error_msg = f"Process-boundary failure: {type(e).__name__} - {str(e)}"
                        logger.error(
                            f"ISIN Processing Failed for {isin}: {error_msg}\n{traceback.format_exc()}"
                        )
                        raise RuntimeError(f"ISIN_FAILURE|{isin}|{error_msg}") from e

                    if error_info is not None:
                        failed_isin = error_info.get("isin", isin)
                        error_msg = error_info.get("error", "Unknown Error")
                        tb = error_info.get("traceback", "")
                        logger.error(f"ISIN Processing Failed for {failed_isin}: {error_msg}\n{tb}")
                        raise RuntimeError(f"ISIN_FAILURE|{failed_isin}|{error_msg}")

                    if success:
                        has_data = True
                    if isin_cf or isin_pt:
                        isin_cashflows[isin] = isin_cf
                        isin_terminals[isin] = isin_pt

                    global_cashflows.extend(isin_cf)
                    for d, vals in isin_pt.items():
                        pt = portfolio_terminals.setdefault(
                            d,
                            {
                                "val": 0.0,
                                "shadow_val": 0.0,
                                "after_tax_val": 0.0,
                                "val_local": 0.0,
                                "shadow_val_local": 0.0,
                            },
                        )
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
                        pt["val_local"] += vals.get("val_local", 0.0)
                        pt["shadow_val_local"] += vals["shadow_val_local"]
                    realized_events.extend(isin_re)
                    global_recon_events.extend(isin_recon)

                    if not tags:
                        continue

                    cls = tags.get("class", "Unknown")
                    sub = tags.get("subtype", "Unknown")
                    inst_type = tags.get("instrument_type", "Unknown")
                    sector = tags.get("sector", "Unknown")
                    industry = tags.get("industry", "Unknown")
                    geo = tags.get("geo", "Unknown")
                    country = tags.get("country", "Unknown")
                    currency = tags.get("currency", (self.ctx.rules.DEFAULT_CURRENCY_ID))

                    class_cf.setdefault(cls, []).extend(isin_cf)
                    class_re.setdefault(cls, []).extend(isin_re)
                    cp = class_pt.setdefault(cls, {})
                    for d, vals in isin_pt.items():
                        pt = cp.setdefault(
                            d,
                            {
                                "val": 0.0,
                                "shadow_val": 0.0,
                                "after_tax_val": 0.0,
                                "val_local": 0.0,
                                "shadow_val_local": 0.0,
                            },
                        )
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
                        pt["val_local"] += vals.get("val_local", 0.0)
                        pt["shadow_val_local"] += vals["shadow_val_local"]

                    sub_key = f"{cls}___{sub}"
                    subtype_cf.setdefault(sub_key, []).extend(isin_cf)
                    subtype_re.setdefault(sub_key, []).extend(isin_re)

                    sp = subtype_pt.setdefault(sub_key, {})
                    for d, vals in isin_pt.items():
                        pt = sp.setdefault(
                            d,
                            {
                                "val": 0.0,
                                "shadow_val": 0.0,
                                "after_tax_val": 0.0,
                                "val_local": 0.0,
                                "shadow_val_local": 0.0,
                            },
                        )
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
                        pt["val_local"] += vals.get("val_local", 0.0)
                        pt["shadow_val_local"] += vals["shadow_val_local"]

                    def _update_group(
                        group_key: str,
                        cf_dict: dict[str, Any],
                        pt_dict: dict[str, Any],
                        current_cf: list[Any],
                        current_pt: dict[date, Any],
                    ) -> None:
                        cf_dict.setdefault(group_key, []).extend(current_cf)
                        gp = pt_dict.setdefault(group_key, {})
                        for d, vals in current_pt.items():
                            pt = gp.setdefault(
                                d,
                                {
                                    "val": 0.0,
                                    "shadow_val": 0.0,
                                    "after_tax_val": 0.0,
                                    "val_local": 0.0,
                                    "shadow_val_local": 0.0,
                                },
                            )
                            pt["val"] += vals["val"]
                            pt["shadow_val"] += vals["shadow_val"]
                            pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
                            pt["val_local"] += vals.get("val_local", 0.0)
                            pt["shadow_val_local"] += vals["shadow_val_local"]

                    _update_group(
                        inst_type, instrument_type_cf, instrument_type_pt, isin_cf, isin_pt
                    )
                    _update_group(sector, sector_cf, sector_pt, isin_cf, isin_pt)
                    _update_group(industry, industry_cf, industry_pt, isin_cf, isin_pt)
                    _update_group(geo, geo_cf, geo_pt, isin_cf, isin_pt)
                    _update_group(country, country_cf, country_pt, isin_cf, isin_pt)

                    currency_re.setdefault(currency, []).extend(isin_re)
                    _update_group(currency, currency_cf, currency_pt, isin_cf, isin_pt)
        finally:
            stop_worker_listener()
            current_process.daemon = is_daemon

        logger.info(
            f"  -> Quant Engine successfully processed {len(self.isins)} ISIN workloads across Process Pool."
        )

        return PipelineExecutionResult(
            has_data=has_data,
            global_cf=global_cashflows,
            global_pt=portfolio_terminals,
            global_re=realized_events,
            global_recon_events=global_recon_events,
            isin_cf=isin_cashflows,
            isin_pt=isin_terminals,
            class_cf=class_cf,
            class_pt=class_pt,
            class_re=class_re,
            subtype_cf=subtype_cf,
            subtype_pt=subtype_pt,
            subtype_re=subtype_re,
            instrument_type_cf=instrument_type_cf,
            instrument_type_pt=instrument_type_pt,
            sector_cf=sector_cf,
            sector_pt=sector_pt,
            industry_cf=industry_cf,
            industry_pt=industry_pt,
            geo_cf=geo_cf,
            geo_pt=geo_pt,
            country_cf=country_cf,
            country_pt=country_pt,
            currency_cf=currency_cf,
            currency_pt=currency_pt,
            currency_re=currency_re,
        )


__all__ = [
    "IsinPipeline",
    "IsinProcessor",
    "_is_zero_proceeds_re_adjustment",
    "_process_isin_worker",
    "is_indian_rights_entitlement_isin",
]
