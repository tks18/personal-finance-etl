"""Reconciliation comparison and discrepancy detection engine.

Owns
----
- ReconciliationEngine: Validates broker observed units and cost basis against
  reconstructed portfolio state.
- Reconciliation tolerances and adjustment classification.

Does not own
-------------
- FIFO queue state mutation (delegated to domain.investments.lots.fifo).
- External database reading (owned by infrastructure.warehouse).
"""

from datetime import date

from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    ReconciliationEventDict,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.reconciliation.models import (
    ReconciliationAdjustmentType,
    ReconciliationEventRecord,
)

QUANTITY_TOLERANCE: float = 1e-8
COST_BASIS_TOLERANCE: float = 0.01


class ReconciliationEngine:
    """Coordinates broker-evidence reconciliation against internal reconstructed state."""

    @staticmethod
    def should_reconcile_quantity(broker_qty: float | None, reconstructed_qty: float) -> bool:
        """Return whether a meaningful quantity discrepancy exists."""
        if broker_qty is None:
            return False
        return abs(broker_qty - reconstructed_qty) > QUANTITY_TOLERANCE

    @staticmethod
    def should_reconcile_basis(
        broker_buy_val: float | None,
        reconstructed_avg: float,
        current_units: float,
    ) -> bool:
        """Return whether a meaningful cost basis discrepancy exists."""
        if broker_buy_val is None or current_units <= 0 or reconstructed_avg <= 0:
            return False
        target_avg = float(broker_buy_val) / current_units
        return abs(reconstructed_avg - target_avg) > COST_BASIS_TOLERANCE

    @staticmethod
    def reconcile(
        fifo: FIFOPortfolio,
        m_date: date,
        broker_qty: float | None,
        broker_buy_val: float | None,
        broker_buy_val_local: float | None,
        bm_price: float,
    ) -> tuple[list[CashflowDict], list[ReconciliationEventDict]]:
        """Perform full quantity and cost-basis reconciliation on a FIFOPortfolio.

        Returns
        -------
        tuple[list[CashflowDict], list[ReconciliationEventDict]]
            (dummy_cashflows, recon_events)
        """
        dummy_cf, q_events = fifo.reconcile_quantity(broker_qty, m_date, bm_price)
        cb_events = fifo.reconcile_cost_basis(broker_buy_val, broker_buy_val_local, m_date)
        return dummy_cf, q_events + cb_events


__all__ = [
    "COST_BASIS_TOLERANCE",
    "QUANTITY_TOLERANCE",
    "ReconciliationAdjustmentType",
    "ReconciliationEngine",
    "ReconciliationEventRecord",
]
