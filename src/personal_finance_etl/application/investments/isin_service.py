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
from dataclasses import dataclass
from datetime import date
from typing import cast

import polars as pl

from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    CashflowRecord,
    InstrumentMetricsRecord,
    IsinMasterRecord,
    ISINProcessResult,
    ISINTags,
    PipelineExecutionResult,
    RealizedEventDict,
    ReconciliationEventDict,
    SnapshotRecord,
    TerminalValueDict,
    TerminalValueRecord,
    TradeRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio, LotBuyParameters
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.investments.performance.xirr import calculate_xirr
from personal_finance_etl.domain.investments.portfolio.snapshots import (
    LotValuationContext,
    SnapshotGenerator,
)
from personal_finance_etl.domain.investments.valuation.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXRateUnavailableError,
    FXValidationGate,
)
from personal_finance_etl.domain.market.fx import FXRateProvider
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


class _IsinState:
    """Internal mutable state tracking simulation variables for a single ISIN."""

    def __init__(
        self,
        first_p_date: date,
        fifo: FIFOPortfolio,
        bm_provider: BenchmarkPriceProvider,
        snapshot_generator: SnapshotGenerator,
        tax_type: str,
        tax_subtype: str,
        default_curr: str,
    ) -> None:
        self.first_p_date: date = first_p_date
        self.fifo: FIFOPortfolio = fifo
        self.bm_provider: BenchmarkPriceProvider = bm_provider
        self.snapshot_generator: SnapshotGenerator = snapshot_generator
        self.tax_type: str = tax_type
        self.tax_subtype: str = tax_subtype
        self.default_curr: str = default_curr
        self.p_idx: int = 0
        self.s_idx: int = 0
        self.running_peak_price: float = 0.0
        self.running_max_dd: float = 0.0
        self.cf_dates: list[date] = []
        self.cf_amounts: list[float] = []
        self.bm_cf_amounts: list[float] = []
        self.bm_cf_amounts_local: list[float] = []
        self.isin_cashflows: list[CashflowRecord] = []
        self.isin_terminals: dict[date, TerminalValueRecord] = {}
        self.isin_realized: list[RealizedEventDict] = []
        self.isin_recon_events: list[ReconciliationEventDict] = []
        self.isin_snapshots: list[SnapshotRecord] = []
        self.fx_cache: dict[tuple[date, str], float | None] = {}


@dataclass
class _DailyTerminals:
    """Terminal values and benchmark prices computed for a single date."""

    m_price: float
    m_bm_price: float
    m_bm_price_inr: float
    terminal_val: float
    shadow_terminal_val: float
    val_local: float
    shadow_terminal_val_local: float
    after_tax_terminal_val: float


class IsinProcessor:
    """Core chronological quantitative calculation engine for an individual ISIN."""

    def __init__(
        self,
        fy_table: FYMacroParametersTable,
        start_date: date | None,
        end_date: date | None,
        rules: FinancialRules,
        fx_provider: FXRateProvider | None = None,
    ) -> None:
        self.fy_table = fy_table
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules
        self.fx_provider = fx_provider

    def process(
        self,
        isin: str,
        p_inst: list[TradeRecord],
        s_inst: list[TradeRecord],
        m_inst: list[TradeRecord],
        master_row: IsinMasterRecord,
        bm_map: dict[date, float],
    ) -> ISINProcessResult | None:
        """Execute chronological FIFO simulation, metrics, and lot snapshots for a single ISIN.

        Parameters
        ----------
        isin : str
            Unique instrument ISIN code.
        p_inst : list[TradeRecord]
            Sorted chronological purchase trade records.
        s_inst : list[TradeRecord]
            Sorted chronological sale trade records.
        m_inst : list[TradeRecord]
            Daily closing market observations.
        master_row : IsinMasterRecord
            Instrument master reference metadata.
        bm_map : dict[date, float]
            Pre-computed benchmark daily closing prices.

        Returns
        -------
        ISINProcessResult | None
            Computed cashflows, terminal values, realized events, snapshots, and tags,
            or None if no market observations exist.
        """
        if not m_inst:
            return None

        logger.debug(f"[Processor] ISIN {isin} computing across {len(m_inst)} historical dates.")

        state = self._init_state(isin, master_row, bm_map, p_inst, m_inst)
        if not state:
            return None

        for m_row in m_inst:
            m_date = to_date_obj(m_row["Date"])
            if not m_date or m_date < state.first_p_date:
                continue

            self._apply_purchases(p_inst, m_date, state, isin, master_row)
            self._apply_sales(s_inst, m_date, state, isin, master_row)
            self._reconcile_market_observations(m_row, m_date, state, isin)

            if not self._should_skip_market_date(state, m_date):
                self._process_active_market_day(m_row, m_date, state, isin)

        # Apply any trailing trades after the last market date
        self._apply_purchases(p_inst, None, state, isin, master_row)
        self._apply_sales(s_inst, None, state, isin, master_row)

        return self._assemble_result(state, master_row)

    def _should_skip_market_date(self, state: _IsinState, m_date: date) -> bool:
        """Determine whether to skip lot snapshot calculation on a given evaluation date."""
        if not state.fifo.active_lots:
            return True
        if self.start_date and m_date < self.start_date:
            return True
        if self.end_date and m_date > self.end_date:
            return True
        return False

    def _process_active_market_day(
        self,
        m_row: TradeRecord,
        m_date: date,
        state: _IsinState,
        isin: str,
    ) -> None:
        """Calculate terminals, metrics, and lot snapshots for an active market day."""
        terminals = self._compute_daily_terminals(m_row, m_date, state, isin)
        metrics = self._compute_daily_metrics(m_date, terminals, state)

        execution_residual = float(m_row.get("Execution_Residual") or 0.0)
        remaining_ltcg = float(m_row.get("Equity_LTCG_Exemption") or 0.0)
        snapshot_ctx = LotValuationContext(
            m_date=m_date,
            m_price=terminals.m_price,
            m_bm_price=terminals.m_bm_price,
            inst_metrics=metrics,
            fx_provider=self.fx_provider,
            execution_residual=execution_residual,
            remaining_ltcg_exemption=remaining_ltcg,
        )
        new_snapshots = state.snapshot_generator.generate(state.fifo, snapshot_ctx)
        state.isin_snapshots.extend(new_snapshots)

    def _init_state(
        self,
        isin: str,
        master_row: IsinMasterRecord,
        bm_map: dict[date, float],
        p_inst: list[TradeRecord],
        m_inst: list[TradeRecord],
    ) -> _IsinState | None:
        """Initialize FIFO tracking, benchmark provider, and FX validation state."""
        tax_type = str(master_row.get("TAX_TYPE", "equity"))
        tax_subtype = str(master_row.get("TAX_SUBTYPE", "listed"))
        bench_id = master_row.get("BENCHMARK_ID")

        bm_provider = BenchmarkPriceProvider(bench_id, None, prebuilt_map=bm_map)
        snapshot_generator = SnapshotGenerator(self.fy_table, self.rules, isin, master_row)

        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        fifo = FIFOPortfolio(tax_type, tax_subtype, self.fy_table, default_curr, isin)

        first_p_date = (
            to_date_obj(p_inst[0]["Date"])
            if p_inst
            else (to_date_obj(m_inst[0]["Date"]) if m_inst else None)
        )
        if not first_p_date:
            return None

        # Pre-Quant FX gate: warn when an instrument is in a foreign currency but has no
        # FX provider or when the provider cannot supply a rate.
        FXValidationGate(self.rules, self.fx_provider).validate(isin, master_row, first_p_date)

        return _IsinState(
            first_p_date=first_p_date,
            fifo=fifo,
            bm_provider=bm_provider,
            snapshot_generator=snapshot_generator,
            tax_type=tax_type,
            tax_subtype=tax_subtype,
            default_curr=default_curr,
        )

    def _get_fx(
        self,
        state: _IsinState,
        isin: str,
        d: date,
        curr: str,
    ) -> float | None:
        """Fetch and cache foreign exchange rate to default portfolio currency."""
        key = (d, curr)
        if key not in state.fx_cache:
            rate = self.fx_provider.get_rate(d, curr) if self.fx_provider else None
            if rate is not None:
                rate = float(rate)
            if curr == state.default_curr:
                rate = 1.0
            if rate is None or not math.isfinite(rate) or rate <= 0:
                raise FXRateUnavailableError(
                    f"ISIN={isin} ({curr}): no valid FX rate available on {d}. "
                    "Refusing to continue with a fabricated or non-finite conversion."
                )
            state.fx_cache[key] = rate
        return state.fx_cache[key]

    def _record_purchase(
        self,
        row: TradeRecord,
        row_dt_obj: date,
        state: _IsinState,
        isin: str,
        master_row: IsinMasterRecord,
    ) -> None:
        """Register a single buy lot into FIFO portfolio and update cashflow states."""
        qty = float(row["Quantity"])
        b_price = float(row.get("Price") or 0.0)

        v_val = row.get("Value")
        buy_val = float(v_val) if v_val is not None else float(qty * b_price)

        bm_p_raw = state.bm_provider.get_bm_price(row_dt_obj)
        if not bm_p_raw or bm_p_raw <= 0:
            bm_p_raw = float("nan")

        _pl_val = row.get("Price_Local")
        price_local = float(_pl_val) if _pl_val is not None else b_price
        currency_id = str(
            row.get("CURRENCY_ID") or master_row.get("CURRENCY_ID") or state.default_curr
        )
        fx_rate_buy = (
            self._get_fx(state, isin, row_dt_obj, currency_id) if self.fx_provider else 1.0
        )
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

    def _apply_purchases(
        self,
        p_inst: list[TradeRecord],
        max_date: date | None,
        state: _IsinState,
        isin: str,
        master_row: IsinMasterRecord,
    ) -> None:
        """Process chronological purchases up to max_date into FIFO portfolio and cashflows."""
        while state.p_idx < len(p_inst):
            row_dt_obj = to_date_obj(p_inst[state.p_idx]["Date"])
            if not row_dt_obj:
                state.p_idx += 1
                continue
            if max_date is not None and row_dt_obj > max_date:
                break

            self._record_purchase(p_inst[state.p_idx], row_dt_obj, state, isin, master_row)
            state.p_idx += 1

    def _resolve_sale_prices(
        self,
        row: TradeRecord,
        row_dt_obj: date,
        isin: str,
        max_date: date | None,
    ) -> tuple[float, float, float, float, bool]:
        """Resolve and validate transaction price, local price, and proceeds for a sale."""
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

        return s_price, s_val, s_price_local, s_val_local, is_re_adjustment

    def _record_sale(
        self,
        row: TradeRecord,
        row_dt_obj: date,
        s_price: float,
        s_val: float,
        s_price_local: float,
        s_val_local: float,
        state: _IsinState,
        isin: str,
        master_row: IsinMasterRecord,
    ) -> None:
        """Register sale disposal into FIFO queue, match benchmark flows, and update cashflows."""
        s_qty = float(row["Quantity"])
        currency_id = str(
            row.get("CURRENCY_ID") or master_row.get("CURRENCY_ID") or state.default_curr
        )
        fx_rate_sell = (
            self._get_fx(state, isin, row_dt_obj, currency_id) if self.fx_provider else 1.0
        )
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

    def _apply_sales(
        self,
        s_inst: list[TradeRecord],
        max_date: date | None,
        state: _IsinState,
        isin: str,
        master_row: IsinMasterRecord,
    ) -> None:
        """Process chronological sales up to max_date into FIFO portfolio and cashflows."""
        while state.s_idx < len(s_inst):
            row_dt_obj = to_date_obj(s_inst[state.s_idx]["Date"])
            if not row_dt_obj:
                state.s_idx += 1
                continue
            if max_date is not None and row_dt_obj > max_date:
                break

            s_price, s_val, s_price_local, s_val_local, _ = self._resolve_sale_prices(
                s_inst[state.s_idx], row_dt_obj, isin, max_date
            )
            self._record_sale(
                s_inst[state.s_idx],
                row_dt_obj,
                s_price,
                s_val,
                s_price_local,
                s_val_local,
                state,
                isin,
                master_row,
            )
            state.s_idx += 1

    def _reconcile_market_observations(
        self,
        m_row: TradeRecord,
        m_date: date,
        state: _IsinState,
        isin: str,
    ) -> None:
        """Reconcile broker reported units and cost basis against reconstructed FIFO state."""
        q_cf, q_recon_events = state.fifo.reconcile_quantity(
            m_row.get("Quantity"), m_date, state.bm_provider.get_bm_price(m_date) or 0.0
        )
        for re in q_recon_events:
            re["ISIN"] = isin
        state.isin_recon_events.extend(q_recon_events)

        for cf in q_cf:
            cf_d = cf.get("date")
            amt = float(cf.get("amount") or 0.0)
            if cf_d:
                state.cf_dates.append(cf_d)
            state.cf_amounts.append(amt)
            state.bm_cf_amounts.append(amt)
            state.bm_cf_amounts_local.append(amt)
            if cf_d:
                state.isin_cashflows.append(
                    CashflowRecord(
                        date=cf_d,
                        amount=amt,
                        amount_local=amt,
                        benchmark_amount=0.0,
                        benchmark_amount_local=0.0,
                    )
                )

        cb_recon_events = state.fifo.reconcile_cost_basis(
            m_row.get("Buy_Value"), m_row.get("Buy_Value_Local"), m_date
        )
        for re in cb_recon_events:
            re["ISIN"] = isin
        state.isin_recon_events.extend(cb_recon_events)

    def _compute_terminal_val_local(
        self,
        state: _IsinState,
        isin: str,
        m_date: date,
        m_price: float,
    ) -> float:
        """Calculate local-currency terminal value across active lots."""
        terminal_val_local = 0.0
        for lot in state.fifo.active_lots:
            if lot.currency_id and lot.currency_id != state.default_curr and self.fx_provider:
                fx_rate_snap_lot = self._get_fx(state, isin, m_date, lot.currency_id)
                m_price_local = (
                    m_price / fx_rate_snap_lot
                    if (fx_rate_snap_lot is not None and fx_rate_snap_lot > 0)
                    else float("nan")
                )
                terminal_val_local += lot.qty * m_price_local
            else:
                terminal_val_local += lot.qty * m_price
        return terminal_val_local

    def _compute_after_tax_terminal_val(
        self,
        state: _IsinState,
        m_date: date,
        m_price: float,
        remaining_ltcg_exemption: float,
    ) -> float:
        """Calculate post-tax liquidating value accounting for accrued capital gains liability."""
        after_tax_val = 0.0
        for lot in state.fifo.active_lots:
            if lot.qty <= 1e-8:
                continue
            lbd = lot.date
            holding_type = self.fy_table.get_holding_type(
                state.tax_type, state.tax_subtype, lbd or m_date, m_date
            )
            ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
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

    def _compute_daily_terminals(
        self,
        m_row: TradeRecord,
        m_date: date,
        state: _IsinState,
        isin: str,
    ) -> _DailyTerminals:
        """Compute portfolio terminal values, shadow benchmark values, and after-tax terminal value."""
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
            and self.fx_provider
        ):
            fx_val = self._get_fx(state, isin, m_date, state.fifo.active_lots[0].currency_id)
            fx_rate_snap = fx_val if fx_val is not None else float("nan")

        m_bm_price_inr = m_bm_price * fx_rate_snap
        terminal_val = state.fifo.get_terminal_value(m_price)
        shadow_terminal_val = state.fifo.get_shadow_terminal_value(m_bm_price_inr)
        shadow_terminal_val_local = state.fifo.get_shadow_terminal_value(m_bm_price)

        val_local = self._compute_terminal_val_local(state, isin, m_date, m_price)
        after_tax_terminal_val = self._compute_after_tax_terminal_val(
            state, m_date, m_price, remaining_ltcg
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

    def _compute_cagr_and_drawdown(
        self,
        m_date: date,
        terminals: _DailyTerminals,
        state: _IsinState,
    ) -> tuple[float | None, str, float | None, str, float]:
        """Derive volume-weighted CAGR and running peak max drawdown."""
        closing_units = state.fifo.get_closing_units()
        inst_cagr: float | None = None
        inst_cagr_status: str = "UNDEFINED"
        inst_bm_cagr: float | None = None
        inst_bm_cagr_status: str = "UNDEFINED"

        if closing_units > 0:
            avg_cost = state.fifo.get_average_cost()
            avg_bm_cost = state.fifo.get_average_bm_cost()
            weighted_days = (
                sum(
                    lot.qty * (m_date - lot.date).days for lot in state.fifo.active_lots if lot.date
                )
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

    def _compute_local_xirr_metrics(
        self,
        m_date: date,
        terminals: _DailyTerminals,
        state: _IsinState,
    ) -> tuple[float | None, str, float | None, str]:
        """Derive local currency asset and benchmark XIRRs."""
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

    def _compute_daily_metrics(
        self,
        m_date: date,
        terminals: _DailyTerminals,
        state: _IsinState,
    ) -> InstrumentMetricsRecord:
        """Calculate XIRR, benchmark active return, CAGR, and drawdown metrics."""
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

        cagr, cagr_st, bm_cagr, bm_cagr_st, max_dd = self._compute_cagr_and_drawdown(
            m_date, terminals, state
        )
        xirr_loc, xirr_loc_st, bm_loc, bm_loc_st = self._compute_local_xirr_metrics(
            m_date, terminals, state
        )

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

    @staticmethod
    def _assemble_snapshots_df(isin_snapshots: list[SnapshotRecord]) -> pl.DataFrame | None:
        """Materialize snapshot records into typed Polars DataFrame with schema overrides."""
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

    def _assemble_result(
        self,
        state: _IsinState,
        master_row: IsinMasterRecord,
    ) -> ISINProcessResult:
        """Pack computed portfolio outputs into typed ISINProcessResult contract."""
        df = self._assemble_snapshots_df(state.isin_snapshots)
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
            cashflows=state.isin_cashflows,
            terminals=state.isin_terminals,
            realized_events=state.isin_realized,
            recon_events=state.isin_recon_events,
            tags=tags,
        )


def _process_isin_worker(
    task: tuple[
        str,
        list[TradeRecord],
        list[TradeRecord],
        list[TradeRecord],
        IsinMasterRecord,
        dict[date, float],
        FYMacroParametersTable,
        date | None,
        date | None,
        FinancialRules,
        FXRateProvider | None,
        str,
    ],
) -> tuple[
    bool,
    list[CashflowDict],
    dict[date, TerminalValueDict],
    list[RealizedEventDict],
    list[ReconciliationEventDict],
    dict[str, str],
    dict[str, str] | None,
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
            isin_cf = cast(
                "list[CashflowDict]", [c.model_dump(mode="python") for c in res.cashflows]
            )
            isin_pt = cast(
                "dict[date, TerminalValueDict]",
                {d: pt.model_dump(mode="python") for d, pt in res.terminals.items()},
            )
            tags = cast("dict[str, str]", res.tags.model_dump(by_alias=True))
            isin_re = cast(
                "list[RealizedEventDict]",
                [
                    r if isinstance(r, dict) else r.model_dump(by_alias=True)
                    for r in res.realized_events
                ],
            )
            isin_recon = cast(
                "list[ReconciliationEventDict]",
                [
                    r if isinstance(r, dict) else r.model_dump(by_alias=True)
                    for r in res.recon_events
                ],
            )

            if df is not None and not df.is_empty():
                df.write_parquet(os.path.join(tmp_dir, f"{isin.replace('/', '_')}.parquet"))
                return True, isin_cf, isin_pt, isin_re, isin_recon, tags, None
            return False, isin_cf, isin_pt, isin_re, isin_recon, tags, None
        return False, [], {}, [], [], {}, None
    except Exception as e:
        tb = traceback.format_exc()
        return False, [], {}, [], [], {}, {"isin": isin, "error": str(e), "traceback": tb}


class _DimensionAccumulator:
    """Container for dimensional cashflows, terminals, and realized events."""

    def __init__(self) -> None:
        self.cf: dict[str, list[CashflowDict]] = {}
        self.pt: dict[str, dict[date, dict[str, float]]] = {}
        self.re: dict[str, list[RealizedEventDict]] = {}


class _PipelineAccumulator:
    """Accumulates worker ISIN simulation outputs into multi-dimensional aggregation containers."""

    def __init__(self, default_curr: str) -> None:
        self.default_curr = default_curr
        self.global_cashflows: list[CashflowDict] = []
        self.portfolio_terminals: dict[date, dict[str, float]] = {}
        self.realized_events: list[RealizedEventDict] = []
        self.global_recon_events: list[ReconciliationEventDict] = []
        self.isin_cashflows: dict[str, list[CashflowDict]] = {}
        self.isin_terminals: dict[str, dict[date, TerminalValueDict]] = {}

        self.dim_class = _DimensionAccumulator()
        self.dim_subtype = _DimensionAccumulator()
        self.dim_instrument_type = _DimensionAccumulator()
        self.dim_sector = _DimensionAccumulator()
        self.dim_industry = _DimensionAccumulator()
        self.dim_geo = _DimensionAccumulator()
        self.dim_country = _DimensionAccumulator()
        self.dim_currency = _DimensionAccumulator()

    @staticmethod
    def _accumulate_group(
        key: str,
        target_cf: dict[str, list[CashflowDict]],
        target_pt: dict[str, dict[date, dict[str, float]]],
        isin_cf: list[CashflowDict],
        isin_pt: dict[date, TerminalValueDict],
    ) -> None:
        target_cf.setdefault(key, []).extend(isin_cf)
        pt_dict = target_pt.setdefault(key, {})
        for d, vals in isin_pt.items():
            entry = pt_dict.setdefault(
                d,
                {
                    "val": 0.0,
                    "shadow_val": 0.0,
                    "after_tax_val": 0.0,
                    "val_local": 0.0,
                    "shadow_val_local": 0.0,
                },
            )
            entry["val"] += vals.get("val", 0.0)
            entry["shadow_val"] += vals.get("shadow_val", 0.0)
            entry["after_tax_val"] += vals.get("after_tax_val", 0.0)
            entry["val_local"] += vals.get("val_local", 0.0)
            entry["shadow_val_local"] += vals.get("shadow_val_local", 0.0)

    def ingest_isin_result(
        self,
        isin: str,
        isin_cf: list[CashflowDict],
        isin_pt: dict[date, TerminalValueDict],
        isin_re: list[RealizedEventDict],
        isin_recon: list[ReconciliationEventDict],
        tags: dict[str, str],
    ) -> None:
        """Ingest individual ISIN worker result into global and group containers."""
        if isin_cf or isin_pt:
            self.isin_cashflows[isin] = isin_cf
            self.isin_terminals[isin] = isin_pt

        self.global_cashflows.extend(isin_cf)
        for d, vals in isin_pt.items():
            pt = self.portfolio_terminals.setdefault(
                d,
                {
                    "val": 0.0,
                    "shadow_val": 0.0,
                    "after_tax_val": 0.0,
                    "val_local": 0.0,
                    "shadow_val_local": 0.0,
                },
            )
            pt["val"] += vals.get("val", 0.0)
            pt["shadow_val"] += vals.get("shadow_val", 0.0)
            pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
            pt["val_local"] += vals.get("val_local", 0.0)
            pt["shadow_val_local"] += vals.get("shadow_val_local", 0.0)

        self.realized_events.extend(isin_re)
        self.global_recon_events.extend(isin_recon)

        if not tags:
            return

        cls = tags.get("class", "Unknown")
        sub = tags.get("subtype", "Unknown")
        inst_type = tags.get("instrument_type", "Unknown")
        sector = tags.get("sector", "Unknown")
        industry = tags.get("industry", "Unknown")
        geo = tags.get("geo", "Unknown")
        country = tags.get("country", "Unknown")
        currency = tags.get("currency", self.default_curr)

        self.dim_class.re.setdefault(cls, []).extend(isin_re)
        self._accumulate_group(cls, self.dim_class.cf, self.dim_class.pt, isin_cf, isin_pt)

        sub_key = f"{cls}___{sub}"
        self.dim_subtype.re.setdefault(sub_key, []).extend(isin_re)
        self._accumulate_group(sub_key, self.dim_subtype.cf, self.dim_subtype.pt, isin_cf, isin_pt)

        self._accumulate_group(
            inst_type, self.dim_instrument_type.cf, self.dim_instrument_type.pt, isin_cf, isin_pt
        )
        self._accumulate_group(sector, self.dim_sector.cf, self.dim_sector.pt, isin_cf, isin_pt)
        self._accumulate_group(
            industry, self.dim_industry.cf, self.dim_industry.pt, isin_cf, isin_pt
        )
        self._accumulate_group(geo, self.dim_geo.cf, self.dim_geo.pt, isin_cf, isin_pt)
        self._accumulate_group(country, self.dim_country.cf, self.dim_country.pt, isin_cf, isin_pt)

        self.dim_currency.re.setdefault(currency, []).extend(isin_re)
        self._accumulate_group(
            currency, self.dim_currency.cf, self.dim_currency.pt, isin_cf, isin_pt
        )

    def to_result(self, has_data: bool) -> PipelineExecutionResult:
        """Construct the immutable PipelineExecutionResult structure."""
        return PipelineExecutionResult(
            has_data=has_data,
            global_cf=self.global_cashflows,
            global_pt=self.portfolio_terminals,
            global_re=self.realized_events,
            global_recon_events=self.global_recon_events,
            isin_cf=self.isin_cashflows,
            isin_pt=self.isin_terminals,
            class_cf=self.dim_class.cf,
            class_pt=self.dim_class.pt,
            class_re=self.dim_class.re,
            subtype_cf=self.dim_subtype.cf,
            subtype_pt=self.dim_subtype.pt,
            subtype_re=self.dim_subtype.re,
            instrument_type_cf=self.dim_instrument_type.cf,
            instrument_type_pt=self.dim_instrument_type.pt,
            sector_cf=self.dim_sector.cf,
            sector_pt=self.dim_sector.pt,
            industry_cf=self.dim_industry.cf,
            industry_pt=self.dim_industry.pt,
            geo_cf=self.dim_geo.cf,
            geo_pt=self.dim_geo.pt,
            country_cf=self.dim_country.cf,
            country_pt=self.dim_country.pt,
            currency_cf=self.dim_currency.cf,
            currency_pt=self.dim_currency.pt,
            currency_re=self.dim_currency.re,
        )


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk."""

    def __init__(
        self,
        ctx: RunContext,
        isins: list[str],
        tmp_dir: str,
        status_queue: StatusQueue | None = None,
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

    @staticmethod
    def _accumulate_group(
        group_key: str,
        cf_dict: dict[str, list[CashflowDict]],
        pt_dict: dict[str, dict[date, dict[str, float]]],
        current_cf: list[CashflowDict],
        current_pt: dict[date, TerminalValueDict],
    ) -> None:
        """Accumulate cashflows and terminal values for a dimension grouping."""
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
            pt["val"] += vals.get("val", 0.0)
            pt["shadow_val"] += vals.get("shadow_val", 0.0)
            pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
            pt["val_local"] += vals.get("val_local", 0.0)
            pt["shadow_val_local"] += vals.get("shadow_val_local", 0.0)

    def _build_worker_tasks(
        self,
    ) -> list[
        tuple[
            str,
            list[TradeRecord],
            list[TradeRecord],
            list[TradeRecord],
            IsinMasterRecord,
            dict[date, float],
            FYMacroParametersTable,
            date | None,
            date | None,
            FinancialRules,
            FXRateProvider | None,
            str,
        ]
    ]:
        """Partition input trade frames and build task payloads for multiprocessing worker pool."""
        p_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                self.ctx.df_p.partition_by("ISIN", as_dict=True),
            )
            if not self.ctx.df_p.is_empty()
            else {}
        )
        s_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                self.ctx.df_s.partition_by("ISIN", as_dict=True),
            )
            if not self.ctx.df_s.is_empty()
            else {}
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

        m_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                m_grouped.partition_by("ISIN", as_dict=True),
            )
            if not m_grouped.is_empty()
            else {}
        )

        bm_maps: dict[str, dict[date, float]] = {}
        for _isin, row in self.ctx.isin_master.items():
            b_id = str(row.get("BENCHMARK_ID", ""))
            if b_id and b_id not in bm_maps:
                bm_maps[b_id] = BenchmarkPriceProvider(b_id, self.ctx.df_b).bm_price_map

        tasks: list[
            tuple[
                str,
                list[TradeRecord],
                list[TradeRecord],
                list[TradeRecord],
                IsinMasterRecord,
                dict[date, float],
                FYMacroParametersTable,
                date | None,
                date | None,
                FinancialRules,
                FXRateProvider | None,
                str,
            ]
        ] = []
        for isin in self.isins:
            p_df = p_dict_pl.get((isin,)) if (isin,) in p_dict_pl else p_dict_pl.get(isin)
            p_inst = cast(
                "list[TradeRecord]",
                p_df.sort("Date").to_dicts() if p_df is not None and not p_df.is_empty() else [],
            )

            s_df = s_dict_pl.get((isin,)) if (isin,) in s_dict_pl else s_dict_pl.get(isin)
            s_inst = cast(
                "list[TradeRecord]",
                s_df.sort("Date").to_dicts() if s_df is not None and not s_df.is_empty() else [],
            )

            m_df = m_dict_pl.get((isin,)) if (isin,) in m_dict_pl else m_dict_pl.get(isin)
            m_inst = cast(
                "list[TradeRecord]",
                m_df.to_dicts() if m_df is not None and not m_df.is_empty() else [],
            )

            master_row: IsinMasterRecord = self.ctx.isin_master.get(isin, {})
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
        return tasks

    def process_all(self) -> PipelineExecutionResult:
        """Execute parallel multi-process simulation across all configured ISIN instruments."""
        acc = _PipelineAccumulator(self.ctx.rules.DEFAULT_CURRENCY_ID)
        has_data = False
        total_inst = len(self.isins)
        tasks = self._build_worker_tasks()

        current_process = multiprocessing.current_process()
        is_daemon = current_process.daemon
        current_process.daemon = False
        worker_queue = start_worker_listener()

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
                    acc.ingest_isin_result(isin, isin_cf, isin_pt, isin_re, isin_recon, tags)
        finally:
            stop_worker_listener()
            current_process.daemon = is_daemon

        logger.info(
            f"  -> Quant Engine successfully processed {len(self.isins)} ISIN workloads across Process Pool."
        )
        return acc.to_result(has_data)


__all__ = [
    "IsinPipeline",
    "IsinProcessor",
    "_is_zero_proceeds_re_adjustment",
    "_process_isin_worker",
    "is_indian_rights_entitlement_isin",
]
