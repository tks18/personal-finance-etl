from collections import deque
from datetime import date
from typing import Any

from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.utils.identity import generate_deterministic_id
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import TaxLot


class FIFOPortfolio:
    """Manages the FIFO tracking of a single instrument's lots."""

    def __init__(
        self,
        tax_type: str,
        tax_subtype: str,
        fy_table: FYMacroParametersTable,
        default_currency_id: str,
    ):
        self._active_lots: deque[TaxLot] = deque()
        self.tax_type = tax_type
        self.tax_subtype = tax_subtype
        self.fy_table = fy_table
        self.default_currency_id = default_currency_id

    @property
    def active_lots(self) -> list[TaxLot]:
        """Read-only access to active lots."""
        return list(self._active_lots)

    def buy(
        self,
        buy_date: date,
        qty: float,
        price: float,
        shadow_qty: float,
        bm_price: float,
        price_local: float = 0.0,
        fx_rate_buy: float = 1.0,
        currency_id: str | None = None,
        bm_buy_local: float | None = None,
        purchase_id: str | None = None,
    ) -> None:
        """Register a new buy lot."""

        if currency_id is None:
            currency_id = self.default_currency_id

        lot_id = None
        if purchase_id:
            # Deterministically generate Lot_ID using the unique purchase_id and current qty in this execution context
            # (as partial executions or splits might happen).
            lot_fields = {
                "Purchase_ID": purchase_id,
                "Quantity": qty,
                "Date": buy_date,
            }
            lot_id = generate_deterministic_id("LOT", lot_fields)

        self._active_lots.append(
            TaxLot(
                date=buy_date,
                qty=qty,
                price=price,
                shadow_qty=shadow_qty,
                bm_buy=bm_price,
                price_local=price_local,
                fx_rate_buy=fx_rate_buy,
                currency_id=currency_id,
                bm_buy_local=bm_buy_local,
                purchase_id=purchase_id,
                lot_id=lot_id,
            )
        )

    def sell(
        self,
        sell_date: date,
        qty: float,
        price: float,
        price_local: float = 0.0,
        fx_rate_sell: float = 1.0,
        sale_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Process a sale via FIFO and return the realized gain events."""
        rem = qty
        realized_events: list[dict[str, Any]] = []

        while rem > 0 and self._active_lots:
            lot = self._active_lots[0]
            consumed = min(rem, lot.qty)

            lbd = lot.date
            ht_sale = self.fy_table.get_holding_type(
                self.tax_type, self.tax_subtype, lbd or sell_date, sell_date
            )

            if lot.price <= 0:
                logger.debug(
                    f"[QUANT:WARN] Tax lot acquired on {lbd} has zero-cost basis! PNL will be 0."
                )
                pnl = 0.0
                asset_pnl_local = 0.0
                asset_pnl = 0.0
                forex_pnl = 0.0
            else:
                pnl = (price - lot.price) * consumed
                if lot.currency_id and lot.currency_id != self.default_currency_id:
                    asset_pnl_local = (price_local - lot.price_local) * consumed
                    asset_pnl = asset_pnl_local * fx_rate_sell
                    forex_pnl = (lot.price_local * (fx_rate_sell - lot.fx_rate_buy)) * consumed
                else:
                    asset_pnl_local = pnl
                    asset_pnl = pnl
                    forex_pnl = 0.0

            realized_events.append(
                {
                    "date": sell_date,
                    "gain": pnl,
                    "gain_type": ht_sale,
                    "is_loss": pnl < 0,
                    "tax_type": self.tax_type.strip().lower(),
                    "asset_pnl_local": asset_pnl_local,
                    "asset_pnl": asset_pnl,
                    "forex_pnl": forex_pnl,
                    "currency_id": lot.currency_id,
                    "shadow_qty_sold": lot.shadow_qty
                    if lot.qty <= rem + 1e-8
                    else (lot.shadow_qty * (rem / lot.qty))
                    if lot.shadow_qty
                    else 0.0,
                    "sale_id": sale_id,
                    "purchase_id": lot.purchase_id,
                    "lot_id": lot.lot_id,
                }
            )

            if lot.qty <= rem + 1e-8:
                rem -= lot.qty
                self._active_lots.popleft()
            else:
                new_shadow_qty = (
                    lot.shadow_qty - (lot.shadow_qty * (rem / lot.qty)) if lot.shadow_qty else 0
                )
                self._active_lots[0] = TaxLot(
                    date=lot.date,
                    qty=lot.qty - rem,
                    price=lot.price,
                    shadow_qty=new_shadow_qty,
                    bm_buy=lot.bm_buy,
                    price_local=lot.price_local,
                    fx_rate_buy=lot.fx_rate_buy,
                    currency_id=lot.currency_id,
                    bm_buy_local=lot.bm_buy_local,
                    purchase_id=lot.purchase_id,
                    lot_id=lot.lot_id,
                )
                rem = 0

        return realized_events

    def get_closing_units(self) -> float:
        return sum(lot.qty for lot in self._active_lots)

    def get_closing_shadow_units(self) -> float:
        return sum(lot.shadow_qty for lot in self._active_lots)

    def get_terminal_value(self, m_price: float) -> float:
        return self.get_closing_units() * m_price

    def get_shadow_terminal_value(self, m_bm_price: float) -> float:
        return self.get_closing_shadow_units() * m_bm_price

    def get_average_cost(self) -> float:
        units = self.get_closing_units()
        return sum(lot.qty * lot.price for lot in self._active_lots) / units if units > 0 else 0.0

    def get_average_bm_cost(self) -> float:
        s_units = self.get_closing_shadow_units()
        total_cost = 0.0
        for lot in self._active_lots:
            if lot.bm_buy is not None:
                total_cost += lot.shadow_qty * lot.bm_buy
        return total_cost / s_units if s_units > 0 else 0.0

    def reconcile_quantity(
        self, m_qty_val: float | None, m_date: date, bm_price: float
    ) -> tuple[list[dict[str, date | float]], list[dict[str, Any]]]:
        """Reconcile portfolio units with broker units. Returns (dummy_cashflows, recon_events)."""
        if m_qty_val is None or str(m_qty_val).strip() == "":
            return [], []

        m_qty = float(m_qty_val)
        current_units = self.get_closing_units()
        cf: list[dict[str, date | float]] = []
        recon_events: list[dict[str, Any]] = []

        if m_qty > current_units + 1e-8:
            diff = m_qty - current_units
            self.buy(m_date, diff, 0.0, 0.0, bm_price)
            cf.append({"date": m_date, "amount": 0.0})

            # The newly added lot is at the end of the deque
            new_lot = self._active_lots[-1]

            recon_events.append(
                {
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
            )
        elif m_qty < current_units - 1e-8:
            diff = current_units - m_qty
            while diff > 0 and self._active_lots:
                lot = self._active_lots[0]
                if lot.qty <= diff + 1e-8:
                    removed = lot.qty
                    diff -= lot.qty
                    self._active_lots.popleft()
                else:
                    removed = diff
                    r = diff / lot.qty
                    new_shadow_qty = lot.shadow_qty - (lot.shadow_qty * r) if lot.shadow_qty else 0
                    self._active_lots[0] = TaxLot(
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
                    )
                    diff = 0

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
        return cf, recon_events

    def reconcile_cost_basis(
        self, m_buy_val: float | None, m_buy_val_local: float | None, m_date: date
    ) -> list[dict[str, Any]]:
        """Reconcile internal average cost with broker average cost."""
        current_units = self.get_closing_units()
        if m_buy_val is None or str(m_buy_val).strip() == "" or current_units <= 0:
            return []

        target_avg = float(m_buy_val) / current_units
        our_avg = self.get_average_cost()
        recon_events: list[dict[str, Any]] = []

        if abs(our_avg - target_avg) > 0.01 and our_avg > 0:
            r = target_avg / our_avg
            target_avg_local = (
                float(m_buy_val_local) / current_units
                if m_buy_val_local is not None and str(m_buy_val_local).strip() != ""
                else None
            )

            logger.debug(
                f"FIFO: Reconciling cost basis. Scaling {len(self._active_lots)} lots by {r:.4f}. "
                f"Original Avg: {our_avg:.2f}, Target Avg: {target_avg:.2f}"
            )

            our_avg_local = 0.0
            r_local = r
            if target_avg_local is not None:
                our_avg_local = (
                    sum(lot.qty * (lot.price_local or 0.0) for lot in self._active_lots)
                    / current_units
                )
                if our_avg_local > 0:
                    r_local = target_avg_local / our_avg_local

            for i in range(len(self._active_lots)):
                lot = self._active_lots[i]
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

                self._active_lots[i] = TaxLot(
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
                )
        return recon_events
