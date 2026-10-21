"""Lot quantity and cost basis reconciliation against broker observations.

Owns
----
- LotReconciler: Adjusts active FIFO lots for broker quantity additions/removals and cost basis drift.

Does not own
-------------
- FIFO buy/sell execution (owned by domain.investments.lots.fifo).
- Instrument market state and pricing (owned by application.investments.isin_metrics).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import date

from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    ReconciliationEventDict,
    TaxLot,
)
from personal_finance_etl.domain.investments.lots.models import LotBuyParameters

__all__ = ["LotReconciler"]


class LotReconciler:
    """Reconciles reconstructed active FIFO lots against broker-reported quantities and costs.

    Parameters
    ----------
    isin : str
        Instrument ISIN code.
    """

    def __init__(self, isin: str) -> None:
        self.isin = isin

    def _reconcile_quantity_add(
        self,
        active_lots: deque[TaxLot],
        diff: float,
        current_units: float,
        m_qty: float,
        m_date: date,
        bm_price: float,
        buy_fn: Callable[[LotBuyParameters], None],
    ) -> tuple[list[CashflowDict], list[ReconciliationEventDict]]:
        """Add positive reconciliation lot to bridge shortfall against broker units."""
        recon_gid = generate_deterministic_id(
            "RECON_LOT_GROUP",
            {
                "ISIN": self.isin,
                "Reconciliation_Date": m_date,
                "Adjustment_Type": "QUANTITY_ADD",
                "Quantity": round(diff, 8),
            },
        )
        buy_fn(
            LotBuyParameters(
                buy_date=m_date,
                qty=diff,
                price=0.0,
                shadow_qty=0.0,
                bm_price=bm_price,
                lot_source_type="RECONCILIATION",
                reconciliation_group_id=recon_gid,
            )
        )
        new_lot = active_lots[-1]
        recon_event: ReconciliationEventDict = {
            "Reconciliation_Date": m_date,
            "Adjustment_Type": "QUANTITY_ADD",
            "Reason": "Broker quantity mismatch",
            "Lot_ID": new_lot.lot_id,
            "Purchase_ID": new_lot.purchase_id,
            "Broker_Quantity": m_qty,
            "Reconstructed_Quantity": current_units,
            "Quantity_Adjustment": diff,
            "Broker_Cost_Basis": 0.0,
            "Reconstructed_Cost_Basis": 0.0,
            "Cost_Basis_Adjustment": 0.0,
            "Original_Unit_Cost": 0.0,
            "Adjusted_Unit_Cost": 0.0,
        }
        return [{"date": m_date, "amount": 0.0}], [recon_event]

    def _reconcile_quantity_remove(
        self,
        active_lots: deque[TaxLot],
        diff: float,
        current_units: float,
        m_qty: float,
        m_date: date,
    ) -> list[ReconciliationEventDict]:
        """Prune active lots via FIFO to remove excess units against broker records."""
        recon_events: list[ReconciliationEventDict] = []
        while diff > 0 and active_lots:
            lot = active_lots[0]
            if lot.qty <= diff + 1e-8:
                removed = lot.qty
                diff -= lot.qty
                active_lots.popleft()
            else:
                removed = diff
                r = diff / lot.qty
                new_shadow_qty = lot.shadow_qty - (lot.shadow_qty * r) if lot.shadow_qty else 0.0
                active_lots[0] = TaxLot(
                    date=lot.date,
                    qty=lot.qty - diff,
                    price=lot.price,
                    shadow_qty=new_shadow_qty,
                    bm_buy=lot.bm_buy,
                    price_local=lot.price_local,
                    fx_rate_buy=lot.fx_rate_buy,
                    currency_id=lot.currency_id,
                    bm_buy_local=lot.bm_buy_local,
                    purchase_id=lot.purchase_id,
                    lot_id=lot.lot_id,
                    lot_source_type=lot.lot_source_type,
                )
                diff = 0.0

            recon_events.append(
                {
                    "Reconciliation_Date": m_date,
                    "Adjustment_Type": "QUANTITY_REMOVE",
                    "Reason": "Broker quantity mismatch",
                    "Lot_ID": lot.lot_id,
                    "Purchase_ID": lot.purchase_id,
                    "Broker_Quantity": m_qty,
                    "Reconstructed_Quantity": current_units,
                    "Quantity_Adjustment": -removed,
                    "Broker_Cost_Basis": 0.0,
                    "Reconstructed_Cost_Basis": 0.0,
                    "Cost_Basis_Adjustment": 0.0,
                    "Original_Unit_Cost": lot.price,
                    "Adjusted_Unit_Cost": lot.price,
                }
            )
        return recon_events

    def reconcile_quantity(
        self,
        active_lots: deque[TaxLot],
        m_qty_val: float | None,
        m_date: date,
        bm_price: float,
        buy_fn: Callable[[LotBuyParameters], None],
    ) -> tuple[list[CashflowDict], list[ReconciliationEventDict]]:
        """Reconcile portfolio units with broker units.

        Parameters
        ----------
        active_lots : deque[TaxLot]
            Current active FIFO tax lots deque.
        m_qty_val : float | None
            Broker reported total holding quantity.
        m_date : date
            Evaluation reconciliation date.
        bm_price : float
            Current benchmark price.
        buy_fn : Callable[[LotBuyParameters], None]
            Callback to register newly created reconciliation lots.

        Returns
        -------
        tuple[list[CashflowDict], list[ReconciliationEventDict]]
            Tuple of (cashflow adjustments, reconciliation events).
        """
        if m_qty_val is None or str(m_qty_val).strip() == "":
            return [], []

        m_qty = float(m_qty_val)
        current_units = sum(lot.qty for lot in active_lots)

        if m_qty > current_units + 1e-8:
            return self._reconcile_quantity_add(
                active_lots=active_lots,
                diff=m_qty - current_units,
                current_units=current_units,
                m_qty=m_qty,
                m_date=m_date,
                bm_price=bm_price,
                buy_fn=buy_fn,
            )
        if m_qty < current_units - 1e-8:
            events = self._reconcile_quantity_remove(
                active_lots=active_lots,
                diff=current_units - m_qty,
                current_units=current_units,
                m_qty=m_qty,
                m_date=m_date,
            )
            return [], events

        return [], []

    def _apply_cost_basis_scaling(
        self,
        active_lots: deque[TaxLot],
        r: float,
        r_local: float,
        m_buy_val: float,
        our_avg: float,
        current_units: float,
        m_date: date,
    ) -> list[ReconciliationEventDict]:
        """Proportionally reprice all active tax lots to conform with broker aggregate cost."""
        recon_events: list[ReconciliationEventDict] = []
        for i, lot in enumerate(active_lots):
            new_price_local = lot.price_local * r_local if lot.price_local else 0.0
            new_price = lot.price * r

            recon_events.append(
                {
                    "Reconciliation_Date": m_date,
                    "Adjustment_Type": "COST_BASIS_ADJUSTMENT",
                    "Reason": "Broker cost basis mismatch",
                    "Lot_ID": lot.lot_id,
                    "Purchase_ID": lot.purchase_id,
                    "Broker_Quantity": current_units,
                    "Reconstructed_Quantity": current_units,
                    "Quantity_Adjustment": 0.0,
                    "Broker_Cost_Basis": float(m_buy_val),
                    "Reconstructed_Cost_Basis": our_avg * current_units,
                    "Cost_Basis_Adjustment": (new_price - lot.price) * lot.qty,
                    "Original_Unit_Cost": lot.price,
                    "Adjusted_Unit_Cost": new_price,
                }
            )

            active_lots[i] = TaxLot(
                date=lot.date,
                qty=lot.qty,
                price=new_price,
                shadow_qty=lot.shadow_qty,
                bm_buy=lot.bm_buy,
                price_local=new_price_local,
                fx_rate_buy=lot.fx_rate_buy,
                currency_id=lot.currency_id,
                bm_buy_local=lot.bm_buy_local,
                purchase_id=lot.purchase_id,
                lot_id=lot.lot_id,
                lot_source_type=lot.lot_source_type,
            )
        return recon_events

    def reconcile_cost_basis(
        self,
        active_lots: deque[TaxLot],
        m_buy_val: float | None,
        m_buy_val_local: float | None,
        m_date: date,
    ) -> list[ReconciliationEventDict]:
        """Reconcile internal average cost with broker average cost.

        Parameters
        ----------
        active_lots : deque[TaxLot]
            Current active FIFO tax lots deque.
        m_buy_val : float | None
            Broker reported aggregate base currency cost basis.
        m_buy_val_local : float | None
            Broker reported aggregate local currency cost basis.
        m_date : date
            Reconciliation date.

        Returns
        -------
        list[ReconciliationEventDict]
            Generated cost basis adjustment events.
        """
        current_units = sum(lot.qty for lot in active_lots)
        if m_buy_val is None or str(m_buy_val).strip() == "" or current_units <= 0:
            return []

        target_avg = float(m_buy_val) / current_units
        our_avg = sum(lot.qty * lot.price for lot in active_lots) / current_units

        if abs(our_avg - target_avg) <= 0.01 or our_avg <= 0:
            return []

        r = target_avg / our_avg
        target_avg_local = (
            float(m_buy_val_local) / current_units
            if m_buy_val_local is not None and str(m_buy_val_local).strip() != ""
            else None
        )

        r_local = r
        if target_avg_local is not None:
            our_avg_local = (
                sum(lot.qty * (lot.price_local or 0.0) for lot in active_lots) / current_units
            )
            if our_avg_local > 0:
                r_local = target_avg_local / our_avg_local

        return self._apply_cost_basis_scaling(
            active_lots=active_lots,
            r=r,
            r_local=r_local,
            m_buy_val=float(m_buy_val),
            our_avg=our_avg,
            current_units=current_units,
            m_date=m_date,
        )
