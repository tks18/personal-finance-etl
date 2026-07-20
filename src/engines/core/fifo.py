from collections import deque
from typing import cast
from datetime import date
from src.utils.models import TaxLot
from src.engines.rules.tax import FYTaxRateTable


class FIFOPortfolio:
    """Manages the FIFO tracking of a single instrument's lots."""

    def __init__(self, tax_type: str, tax_subtype: str, fy_table: FYTaxRateTable):
        self._active_lots: deque[TaxLot] = deque()
        self.tax_type = tax_type
        self.tax_subtype = tax_subtype
        self.fy_table = fy_table

    @property
    def active_lots(self) -> list[TaxLot]:
        return list(self._active_lots)
        """Read-only access to active lots."""
        return list(self._active_lots)

    def buy(self, buy_date: date, qty: float, price: float, shadow_qty: float, bm_price: float) -> None:
        """Register a new buy lot."""
        self._active_lots.append(
            TaxLot(date=buy_date, qty=qty, price=price,
                   shadow_qty=shadow_qty, bm_buy=bm_price)
        )

    def sell(self, sell_date: date, qty: float, price: float) -> list[dict]:
        """Process a sale via FIFO and return the realized gain events."""
        rem = qty
        realized_events = []

        while rem > 0 and self._active_lots:
            lot = self._active_lots[0]
            consumed = min(rem, lot.qty)

            lbd = lot.date
            age_sale = max((sell_date - lbd).days, 1) if lbd else 1
            ht_sale = self.fy_table.get_holding_type(
                age_sale, self.tax_type, self.tax_subtype, lbd or sell_date, sell_date
            )

            pnl = (price - lot.price) * consumed if lot.price > 0 else 0.0

            realized_events.append({
                "date": sell_date,
                "gain": pnl,
                "gain_type": ht_sale if pnl >= 0 else "LOSS",
                "tax_type": self.tax_type.strip().lower()
            })

            if lot.qty <= rem + 1e-8:
                rem -= lot.qty
                self._active_lots.popleft()
            else:
                new_shadow_qty = lot.shadow_qty - \
                    (lot.shadow_qty * (rem / lot.qty)) if lot.shadow_qty else 0
                self._active_lots[0] = TaxLot(
                    date=lot.date,
                    qty=lot.qty - rem,
                    price=lot.price,
                    shadow_qty=new_shadow_qty,
                    bm_buy=lot.bm_buy
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

    def reconcile_quantity(self, m_qty_val: float | None, m_date: date, bm_price: float) -> list[dict[str, date | float]]:
        """Reconcile portfolio units with broker units. Returns dummy cashflows if adjustments were made."""
        if m_qty_val is None or str(m_qty_val).strip() == "":
            return []

        m_qty = float(m_qty_val)
        current_units = self.get_closing_units()
        cf = []

        if m_qty > current_units + 1e-8:
            diff = m_qty - current_units
            self.buy(m_date, diff, 0.0, 0.0, bm_price)
            cf.append({"date": m_date, "amount": 0.0})
        elif m_qty < current_units - 1e-8:
            diff = current_units - m_qty
            while diff > 0 and self._active_lots:
                if self._active_lots[0].qty <= diff + 1e-8:
                    diff -= self._active_lots[0].qty
                    self._active_lots.popleft()
                else:
                    lot = self._active_lots[0]
                    r = diff / lot.qty
                    new_shadow_qty = lot.shadow_qty - \
                        (lot.shadow_qty * r) if lot.shadow_qty else 0
                    self._active_lots[0] = TaxLot(
                        date=lot.date,
                        qty=lot.qty - diff,
                        price=lot.price,
                        shadow_qty=new_shadow_qty,
                        bm_buy=lot.bm_buy
                    )
                    diff = 0
        return [cast(dict[str, date | float], c) for c in cf]

    def reconcile_cost_basis(self, m_buy_val: float | None) -> None:
        """Reconcile internal average cost with broker average cost."""
        current_units = self.get_closing_units()
        if m_buy_val is None or str(m_buy_val).strip() == "" or current_units <= 0:
            return

        target_avg = float(m_buy_val) / current_units
        our_avg = self.get_average_cost()

        if abs(our_avg - target_avg) > 0.01 and our_avg > 0:
            r = target_avg / our_avg
            for i in range(len(self._active_lots)):
                lot = self._active_lots[i]
                self._active_lots[i] = TaxLot(
                    date=lot.date,
                    qty=lot.qty,
                    price=lot.price * r,
                    shadow_qty=lot.shadow_qty,
                    bm_buy=lot.bm_buy
                )
