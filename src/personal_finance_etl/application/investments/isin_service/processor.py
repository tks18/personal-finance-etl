"""Per-ISIN chronological FIFO simulation and lot reconstruction engine.

Owns
----
- IsinProcessor: Core chronological quant calculation engine for an individual ISIN instrument.

Does not own
-------------
- Rights entitlement pattern matching (owned by application.investments.isin_classifier).
- Trade purchase and sale execution (owned by application.investments.isin_trades).
- Daily valuation and metrics math (owned by application.investments.isin_metrics).
- Simulation state container (owned by application.investments.isin_state).
- Multiprocessing child worker orchestration (owned by application.investments.isin_worker).
- Multiprocessing process pool accumulation (owned by application.investments.isin_pipeline).
"""

from __future__ import annotations

import logging
import math
from datetime import date

from personal_finance_etl.application.investments.isin_service.metrics import (
    assemble_snapshots_df,
    compute_daily_metrics,
    compute_daily_terminals,
)
from personal_finance_etl.application.investments.isin_service.state import _IsinState
from personal_finance_etl.application.investments.isin_service.trades import (
    apply_purchases,
    apply_sales,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    IsinMasterRecord,
    ISINProcessResult,
    ISINTags,
    TradeRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
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

__all__ = ["IsinProcessor"]

logger = logging.getLogger(__name__)


class IsinProcessor:
    """Core chronological quantitative calculation engine for an individual ISIN.

    Parameters
    ----------
    fy_table : FYMacroParametersTable
        Tax parameters and holding period definitions table.
    start_date : date | None
        Beginning boundary date for snapshot generation.
    end_date : date | None
        Ending boundary date for snapshot generation.
    rules : FinancialRules
        System financial configuration parameters.
    fx_provider : FXRateProvider | None, optional
        Foreign exchange rate provider.
    """

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

        logger.debug(f"ISIN {isin} computing across {len(m_inst)} historical dates.")

        state = self._init_state(isin, master_row, bm_map, p_inst, m_inst)
        if not state:
            return None

        for m_row in m_inst:
            m_date = to_date_obj(m_row["Date"])
            if not m_date or m_date < state.first_p_date:
                continue

            apply_purchases(p_inst, m_date, state, isin, master_row, self.fx_provider, self._get_fx)
            apply_sales(s_inst, m_date, state, isin, master_row, self.fx_provider, self._get_fx)
            self._reconcile_market_observations(m_row, m_date, state, isin)

            if not self._should_skip_market_date(state, m_date):
                self._process_active_market_day(m_row, m_date, state, isin)

        # Apply any trailing trades after the last market date
        apply_purchases(p_inst, None, state, isin, master_row, self.fx_provider, self._get_fx)
        apply_sales(s_inst, None, state, isin, master_row, self.fx_provider, self._get_fx)

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
        terminals = compute_daily_terminals(
            m_row, m_date, state, isin, self.fy_table, self.fx_provider, self._get_fx
        )
        metrics = compute_daily_metrics(m_date, terminals, state)

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

    def _assemble_result(
        self,
        state: _IsinState,
        master_row: IsinMasterRecord,
    ) -> ISINProcessResult:
        """Pack computed portfolio outputs into typed ISINProcessResult contract."""
        df = assemble_snapshots_df(state.isin_snapshots)
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
