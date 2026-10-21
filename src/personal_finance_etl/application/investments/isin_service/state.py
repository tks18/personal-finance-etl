"""Simulation state tracking container for chronological ISIN quant processing.

Owns
----
- _IsinState: Mutable simulation state tracking holdings, cashflows, terminals, and drawdown.

Does not own
-------------
- Chronological simulation logic (owned by application.investments.isin_processor).
- Metrics computation (owned by application.investments.isin_metrics).
"""

from __future__ import annotations

from datetime import date

from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    RealizedEventDict,
    ReconciliationEventDict,
    SnapshotRecord,
    TerminalValueRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.portfolio.snapshots import SnapshotGenerator
from personal_finance_etl.domain.investments.valuation.benchmark import BenchmarkPriceProvider

__all__ = ["_IsinState"]


class _IsinState:
    """Internal mutable state tracking simulation variables for a single ISIN.

    Parameters
    ----------
    first_p_date : date
        Earliest purchase or transaction date for the instrument.
    fifo : FIFOPortfolio
        FIFO queue tracking open lots and liquidations.
    bm_provider : BenchmarkPriceProvider
        Provider for daily benchmark closing prices.
    snapshot_generator : SnapshotGenerator
        Generator constructing daily lot-level snapshots.
    tax_type : str
        Tax classification category (e.g. 'equity').
    tax_subtype : str
        Tax sub-category (e.g. 'listed').
    default_curr : str
        Portfolio base reporting currency identifier.
    """

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
