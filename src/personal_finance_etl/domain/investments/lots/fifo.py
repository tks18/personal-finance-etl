"""FIFO lot tracking and cost-basis accounting engine.

Owns
----
- Stateful FIFOPortfolio managing the in-memory queue of open acquisition tax lots.
- FIFO purchase lot registration with deterministic lot ID generation.
- Chronological lot disposal upon sales, calculating realized capital gains/losses,
  foreign exchange vs. asset price attribution, holding period classification (LTCG/STCG),
  and applicable tax estimates.
- Quantity and cost basis reconciliation against broker-reported snapshots.

Does not own
-------------
- Presentation rendering or DuckDB persistence (owned by presentation and infrastructure).
- Inter-process task execution or thread pooling (owned by application.investments).
"""

from collections import deque
from datetime import date

from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    RealizedEventDict,
    ReconciliationEventDict,
)
from personal_finance_etl.domain.investments.lots.models import LotBuyParameters, TaxLot
from personal_finance_etl.domain.investments.lots.reconciliation import LotReconciler
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


def _generate_lot_id(
    isin: str,
    buy_date: date,
    qty: float,
    price: float,
    currency_id: str,
    purchase_id: str | None,
    lot_source_type: str,
    reconciliation_group_id: str | None,
) -> str:
    """Generate a deterministic Lot_ID from purchase metadata or reconciliation identity."""
    if purchase_id:
        lot_fields = {
            "ISIN": isin,
            "Purchase_ID": purchase_id,
            "Quantity": qty,
            "Date": buy_date,
        }
    elif reconciliation_group_id is not None:
        lot_fields = {
            "ISIN": isin,
            "Event": lot_source_type,
            "Recon_Group": reconciliation_group_id,
        }
    else:
        lot_fields = {
            "ISIN": isin,
            "Date": buy_date,
            "Quantity": qty,
            "Price": price,
            "Currency": currency_id,
            "Event": lot_source_type,
        }
    return generate_deterministic_id("LOT", lot_fields)


def _compute_disposal_pnl(
    lot: TaxLot,
    price: float,
    price_local: float,
    fx_rate_sell: float,
    consumed: float,
    default_currency_id: str,
) -> tuple[float, float, float, float]:
    """Calculate nominal PnL, local asset PnL, converted asset PnL, and FX PnL."""
    if lot.price <= 0:
        return 0.0, 0.0, 0.0, 0.0

    pnl = (price - lot.price) * consumed
    if lot.currency_id and lot.currency_id != default_currency_id:
        asset_pnl_local = (price_local - lot.price_local) * consumed
        asset_pnl = asset_pnl_local * fx_rate_sell
        forex_pnl = (lot.price_local * (fx_rate_sell - lot.fx_rate_buy)) * consumed
    else:
        asset_pnl_local = pnl
        asset_pnl = pnl
        forex_pnl = 0.0

    return pnl, asset_pnl_local, asset_pnl, forex_pnl


class FIFOPortfolio:
    """Manages the FIFO tracking of a single instrument's lots."""

    def __init__(
        self,
        tax_type: str,
        tax_subtype: str,
        fy_table: FYMacroParametersTable,
        default_currency_id: str,
        isin: str,
    ):
        self._active_lots: deque[TaxLot] = deque()
        self.tax_type = tax_type
        self.tax_subtype = tax_subtype
        self.fy_table = fy_table
        self.default_currency_id = default_currency_id
        self.isin = isin
        self._reconciler = LotReconciler(isin)

    @property
    def active_lots(self) -> list[TaxLot]:
        """Read-only access to active lots."""
        return list(self._active_lots)

    def buy(self, params: LotBuyParameters) -> None:
        """Register a new buy lot via structured LotBuyParameters."""
        curr_id = params.currency_id if params.currency_id is not None else self.default_currency_id
        lot_id = _generate_lot_id(
            isin=self.isin,
            buy_date=params.buy_date,
            qty=params.qty,
            price=params.price,
            currency_id=curr_id,
            purchase_id=params.purchase_id,
            lot_source_type=params.lot_source_type,
            reconciliation_group_id=params.reconciliation_group_id,
        )

        self._active_lots.append(
            TaxLot(
                date=params.buy_date,
                qty=params.qty,
                price=params.price,
                shadow_qty=params.shadow_qty,
                bm_buy=params.bm_price,
                price_local=params.price_local,
                fx_rate_buy=params.fx_rate_buy,
                currency_id=curr_id,
                bm_buy_local=params.bm_buy_local,
                purchase_id=params.purchase_id,
                lot_id=lot_id,
                lot_source_type=params.lot_source_type,
            )
        )

    def _build_realized_event(
        self,
        lot: TaxLot,
        consumed: float,
        sell_date: date,
        price: float,
        price_local: float,
        fx_rate_sell: float,
        sale_id: str | None,
        rem: float,
    ) -> RealizedEventDict:
        """Create a realized disposal event record for a consumed lot fraction."""
        lbd = lot.date
        ht_sale = self.fy_table.get_holding_type(
            self.tax_type, self.tax_subtype, lbd or sell_date, sell_date
        )
        pnl, asset_pnl_local, asset_pnl, forex_pnl = _compute_disposal_pnl(
            lot, price, price_local, fx_rate_sell, consumed, self.default_currency_id
        )

        realized_event_id = generate_deterministic_id(
            "REALIZED",
            {
                "Sale_ID": sale_id,
                "Lot_ID": lot.lot_id,
            },
        )

        ltcg_rate, stcg_rate = self.fy_table.get_tax_rates(
            self.tax_type, self.tax_subtype, lbd or sell_date, sell_date
        )
        applied_rate = ltcg_rate if ht_sale == "LTCG" else stcg_rate
        estimated_tax = max(0.0, pnl) * applied_rate if pnl > 0 else 0.0

        shadow_qty_sold = (
            lot.shadow_qty
            if lot.qty <= rem + 1e-8
            else (lot.shadow_qty * (rem / lot.qty))
            if lot.shadow_qty
            else 0.0
        )

        return {
            "Realized_Event_ID": realized_event_id,
            "Sale_ID": sale_id,
            "Lot_ID": lot.lot_id,
            "Purchase_ID": lot.purchase_id,
            "ISIN": self.isin,
            "Acquisition_Date": lbd,
            "Disposal_Date": sell_date,
            "FY": self.fy_table.get_fy_string(sell_date),
            "Quantity_Disposed": consumed,
            "Acquisition_Price": lot.price,
            "Disposed_Cost_Basis": lot.price * consumed,
            "Sale_Price": price,
            "Sale_Proceeds": price * consumed,
            "Realized_Gain_Loss": pnl,
            "Holding_Type": ht_sale,
            "is_loss": pnl < 0,
            "Tax_Type": self.tax_type.strip().lower(),
            "Tax_Subtype": self.tax_subtype.strip().lower(),
            "Lot_Source_Type": lot.lot_source_type,
            "Currency_ID": lot.currency_id,
            "Asset_PnL_Local": asset_pnl_local,
            "Asset_PnL": asset_pnl,
            "Forex_PnL": forex_pnl,
            "Applied_Rate": applied_rate,
            "Estimated_Tax": estimated_tax,
            "shadow_qty_sold": shadow_qty_sold,
        }

    def sell(
        self,
        sell_date: date,
        qty: float,
        price: float,
        price_local: float = 0.0,
        fx_rate_sell: float = 1.0,
        sale_id: str | None = None,
    ) -> list[RealizedEventDict]:
        """Process a sale via FIFO and return the realized gain events."""
        rem = qty
        realized_events: list[RealizedEventDict] = []

        while rem > 0 and self._active_lots:
            lot = self._active_lots[0]
            consumed = min(rem, lot.qty)

            event = self._build_realized_event(
                lot=lot,
                consumed=consumed,
                sell_date=sell_date,
                price=price,
                price_local=price_local,
                fx_rate_sell=fx_rate_sell,
                sale_id=sale_id,
                rem=rem,
            )
            realized_events.append(event)

            if lot.qty <= rem + 1e-8:
                rem -= lot.qty
                self._active_lots.popleft()
            else:
                new_shadow_qty = (
                    lot.shadow_qty - (lot.shadow_qty * (rem / lot.qty)) if lot.shadow_qty else 0.0
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
                    lot_source_type=lot.lot_source_type,
                )
                rem = 0.0

        return realized_events

    def get_closing_units(self) -> float:
        """Return aggregate remaining physical units across all active tax lots."""
        return sum(lot.qty for lot in self._active_lots)

    def get_closing_shadow_units(self) -> float:
        """Return aggregate benchmark counterfactual shadow units across active lots."""
        return sum(lot.shadow_qty for lot in self._active_lots)

    def get_terminal_value(self, m_price: float) -> float:
        """Calculate mark-to-market valuation based on current market price."""
        return self.get_closing_units() * m_price

    def get_shadow_terminal_value(self, m_bm_price: float) -> float:
        """Calculate benchmark counterfactual valuation based on current benchmark price."""
        return self.get_closing_shadow_units() * m_bm_price

    def get_average_cost(self) -> float:
        """Calculate volume-weighted average acquisition price of remaining active lots."""
        units = self.get_closing_units()
        return sum(lot.qty * lot.price for lot in self._active_lots) / units if units > 0 else 0.0

    def get_average_bm_cost(self) -> float:
        """Calculate volume-weighted average benchmark price at purchase across active lots."""
        s_units = self.get_closing_shadow_units()
        total_cost = 0.0
        for lot in self._active_lots:
            if lot.bm_buy is not None:
                total_cost += lot.shadow_qty * lot.bm_buy
        return total_cost / s_units if s_units > 0 else 0.0

    def reconcile_quantity(
        self, m_qty_val: float | None, m_date: date, bm_price: float
    ) -> tuple[list[CashflowDict], list[ReconciliationEventDict]]:
        """Reconcile portfolio units with broker units. Returns (dummy_cashflows, recon_events)."""
        return self._reconciler.reconcile_quantity(
            self._active_lots, m_qty_val, m_date, bm_price, self.buy
        )

    def reconcile_cost_basis(
        self, m_buy_val: float | None, m_buy_val_local: float | None, m_date: date
    ) -> list[ReconciliationEventDict]:
        """Reconcile internal average cost with broker average cost."""
        return self._reconciler.reconcile_cost_basis(
            self._active_lots, m_buy_val, m_buy_val_local, m_date
        )


__all__ = [
    "FIFOPortfolio",
    "LotBuyParameters",
]
