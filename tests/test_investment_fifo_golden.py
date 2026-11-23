"""Golden assertions verifying deterministic FIFO lot matching, depletion order, and PnL accounting.

Owns
----
- Two-lot + partial-sale deterministic FIFO accounting verification.
- Exact assertions for lot IDs, quantity depletion order, and disposed cost basis.
- Realized gain/loss split across LTCG (>365D) and STCG (<=365D).
- Remaining open lot quantity, cost basis, shadow units, and market value.
- Reconciliation tolerance thresholds for quantity and cost basis.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio, LotBuyParameters
from personal_finance_etl.domain.investments.reconciliation.engine import (
    ReconciliationEngine,
)
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


def test_fifo_two_lot_partial_sale_exact_accounting(mock_rules: FinancialRules) -> None:
    """Verify two-lot purchase + partial-sale FIFO exhaustion, cost basis, and LTCG/STCG classification."""
    df_fy = pl.DataFrame(
        {
            "FY": ["2022-2023", "2023-2024"],
            "FY_Start_Date": ["2022-04-01", "2023-04-01"],
            "FY_End_Date": ["2023-03-31", "2024-03-31"],
            "Equity_Listed_LTCG": [0.10, 0.125],
            "Equity_Listed_STCG": [0.15, 0.20],
            "Default_LTCG": [0.10, 0.125],
            "Default_STCG": [0.15, 0.20],
            "Cess_Rate": [0.04, 0.04],
        }
    )
    fy_table = FYMacroParametersTable(df_fy, rules=mock_rules)

    fifo = FIFOPortfolio(
        tax_type="EQUITY",
        tax_subtype="LISTED",
        fy_table=fy_table,
        default_currency_id="INR_INR",
        isin="INE002A01018",
    )

    # 1. Lot 1: Buy 100 shares @ 100 on 2023-01-01 (Purchase ID: P1)
    fifo.buy(
        LotBuyParameters(
            buy_date=date(2023, 1, 1),
            qty=100.0,
            price=100.0,
            shadow_qty=10.0,
            bm_price=1000.0,
            purchase_id="P1",
        )
    )
    assert fifo.get_closing_units() == 100.0
    assert fifo.get_closing_shadow_units() == 10.0
    assert len(fifo.active_lots) == 1
    lot1 = fifo.active_lots[0]
    assert lot1.lot_id is not None and lot1.lot_id.startswith("LOT_")
    assert lot1.purchase_id == "P1"

    # 2. Lot 2: Buy 50 shares @ 120 on 2023-06-01 (Purchase ID: P2)
    fifo.buy(
        LotBuyParameters(
            buy_date=date(2023, 6, 1),
            qty=50.0,
            price=120.0,
            shadow_qty=5.0,
            bm_price=1200.0,
            purchase_id="P2",
        )
    )
    assert fifo.get_closing_units() == 150.0
    assert fifo.get_closing_shadow_units() == 15.0
    assert len(fifo.active_lots) == 2
    lot2 = fifo.active_lots[1]
    assert lot2.purchase_id == "P2"

    # 3. Sell 120 shares @ 150 on 2024-02-01 (Sale ID: S1)
    events = fifo.sell(
        sell_date=date(2024, 2, 1),
        qty=120.0,
        price=150.0,
        sale_id="S1",
    )

    # Must produce 2 disposal events (100 from Lot 1 + 20 from Lot 2)
    assert len(events) == 2

    # Event 1: Entire Lot 1 exhausted (396 days holding -> LTCG)
    ev1 = events[0]
    assert ev1.get("Quantity_Disposed") == 100.0
    assert ev1.get("Disposed_Cost_Basis") == 10000.0  # 100 * 100
    assert ev1.get("Sale_Proceeds") == 15000.0  # 100 * 150
    assert ev1.get("Realized_Gain_Loss") == 5000.0  # 15000 - 10000
    assert ev1.get("Holding_Type") == "LTCG"
    d_disp1 = ev1.get("Disposal_Date")
    d_acq1 = ev1.get("Acquisition_Date")
    assert isinstance(d_disp1, date) and isinstance(d_acq1, date)
    assert (d_disp1 - d_acq1).days == 396
    assert ev1.get("Lot_ID") == lot1.lot_id

    # Event 2: Partial Lot 2 depletion (245 days holding -> STCG)
    ev2 = events[1]
    assert ev2.get("Quantity_Disposed") == 20.0
    assert ev2.get("Disposed_Cost_Basis") == 2400.0  # 20 * 120
    assert ev2.get("Sale_Proceeds") == 3000.0  # 20 * 150
    assert ev2.get("Realized_Gain_Loss") == 600.0  # 3000 - 2400
    assert ev2.get("Holding_Type") == "STCG"
    d_disp2 = ev2.get("Disposal_Date")
    d_acq2 = ev2.get("Acquisition_Date")
    assert isinstance(d_disp2, date) and isinstance(d_acq2, date)
    assert (d_disp2 - d_acq2).days == 245
    assert ev2.get("Lot_ID") == lot2.lot_id

    # 4. Remaining Lot 2 state
    assert fifo.get_closing_units() == 30.0  # 50 - 20
    assert fifo.get_average_cost() == 120.0
    assert len(fifo.active_lots) == 1
    rem_lot = fifo.active_lots[0]
    assert rem_lot.qty == 30.0
    assert rem_lot.price == 120.0
    assert rem_lot.qty * rem_lot.price == 3600.0  # 30 * 120
    assert pytest.approx(fifo.get_closing_shadow_units(), abs=1e-6) == 3.0  # 5.0 * (30/50)


def test_reconciliation_tolerances() -> None:
    """Verify position reconciliation quantity (1e-8) and cost basis (0.01) tolerances."""
    # Quantity tolerance check
    assert ReconciliationEngine.should_reconcile_quantity(100.000000001, 100.0) is False
    assert ReconciliationEngine.should_reconcile_quantity(100.01, 100.0) is True

    # Cost basis tolerance check
    assert ReconciliationEngine.should_reconcile_basis(3600.005, 30.0, 120.0) is False
    assert ReconciliationEngine.should_reconcile_basis(3605.0, 30.0, 120.0) is True
