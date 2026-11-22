"""Investment domain enumerations and TypedDict interfaces.

Owns
----
- LotAction: Categorical actions applied to investment tax lots.
- ReconciliationAdjustmentType: Broker reconciliation adjustment classification.
- TypedDict records for normalized trade rows, cashflows, terminal values, realized events, reconciliation events, instrument metrics, and market spines.

Does not own
-------------
- Pydantic domain models or dataclasses (owned by domain.investments.contracts.models).
- FIFO execution algorithms (owned by domain.investments.lots.fifo).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Required, TypedDict

__all__ = [
    "CashflowDict",
    "InstrumentMetricsRecord",
    "IsinMasterRecord",
    "LotAction",
    "MarketSpineRecord",
    "RealizedEventDict",
    "ReconciliationAdjustmentType",
    "ReconciliationEventDict",
    "TerminalValueDict",
    "TradeRecord",
]


class LotAction(StrEnum):
    """Categorical actions applied to investment tax lots."""

    BUY = "BUY"
    SELL = "SELL"
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DIVIDEND_REINVEST = "DIVIDEND_REINVEST"
    RECONCILIATION = "RECONCILIATION"


class ReconciliationAdjustmentType(StrEnum):
    """Categorical types of lot adjustments during broker reconciliation."""

    QUANTITY_ADD = "QUANTITY_ADD"
    QUANTITY_REMOVE = "QUANTITY_REMOVE"
    COST_BASIS_ADJUSTMENT = "COST_BASIS_ADJUSTMENT"


class IsinMasterRecord(TypedDict, total=False):
    """Normalized master metadata row for an investment instrument."""

    ISIN: str
    NAME: str
    SYMBOL: str
    CURRENCY_ID: str | None
    BENCHMARK_ID: str | None
    TAX_TYPE: str
    TAX_SUBTYPE: str
    INSTRUMENT_CLASS: str
    INSTRUMENT_SUBTYPE: str
    INSTRUMENT_TYPE: str
    SECTOR: str
    INDUSTRY: str
    GEO: str
    COUNTRY: str


class TradeRecord(TypedDict, total=False):
    """Normalized trade transaction record (purchases, sales, or mutual fund holdings)."""

    ISIN: Required[str]
    Date: Required[dt.date]
    Quantity: Required[float]
    Price: float | None
    Value: float | None
    Price_Local: float | None
    Value_Local: float | None
    Sell_Price: float | None
    Sell_Value: float | None
    Sell_Price_Local: float | None
    Sell_Value_Local: float | None
    Closing_Price: float | None
    Buy_Value: float | None
    Buy_Value_Local: float | None
    CURRENCY_ID: str | None
    Currency_ID: str | None
    Purchase_ID: str | None
    Sale_ID: str | None
    Equity_LTCG_Exemption: float | None
    Execution_Residual: float | None


class CashflowDict(TypedDict, total=False):
    """Dictionary representation of a cashflow event for serialization and fast aggregation."""

    date: dt.date
    amount: float
    amount_local: float
    benchmark_amount: float | None
    benchmark_amount_local: float | None


class TerminalValueDict(TypedDict, total=False):
    """Dictionary representation of mark-to-market terminal valuations across time."""

    val: Required[float]
    shadow_val: Required[float]
    after_tax_val: float
    val_local: float
    shadow_val_local: Required[float]


class RealizedEventDict(TypedDict, total=False):
    """Dictionary representation of a FIFO realized sale event."""

    Realized_Event_ID: str
    Sale_ID: str | None
    Lot_ID: str | None
    Purchase_ID: str | None
    ISIN: str
    Acquisition_Date: dt.date | None
    Disposal_Date: dt.date
    FY: str
    Quantity_Disposed: float
    Acquisition_Price: float
    Disposed_Cost_Basis: float
    Sale_Price: float
    Sale_Proceeds: float
    Realized_Gain_Loss: float
    Holding_Type: str
    is_loss: bool
    Tax_Type: str
    Tax_Subtype: str
    Lot_Source_Type: str
    Currency_ID: str | None
    Asset_PnL_Local: float
    Asset_PnL: float
    Forex_PnL: float
    Applied_Rate: float
    Estimated_Tax: float
    shadow_qty_sold: float


class ReconciliationEventDict(TypedDict, total=False):
    """Dictionary representation of a reconciliation discrepancy event."""

    Reconciliation_Event_ID: str
    Reconciliation_Group_ID: str | None
    Lot_ID: str | None
    Purchase_ID: str | None
    ISIN: str
    Reconciliation_Date: dt.date
    Adjustment_Type: str
    Reason: str
    Reconstructed_Quantity: float
    Observed_Quantity: float
    Broker_Quantity: float
    Delta_Quantity: float
    Quantity_Adjustment: float
    Reconstructed_Cost_Basis: float | None
    Observed_Cost_Basis: float | None
    Broker_Cost_Basis: float | None
    Delta_Cost_Basis: float | None
    Cost_Basis_Adjustment: float | None
    Original_Unit_Cost: float | None
    Adjusted_Unit_Cost: float | None
    Run_ID: str


class InstrumentMetricsRecord(TypedDict, total=False):
    """Performance, XIRR, CAGR, and benchmark attribution metrics for an instrument."""

    cagr: float | None
    cagr_status: str
    bm_cagr: float | None
    bm_cagr_status: str
    xirr: float | None
    xirr_status: str
    bm_xirr: float | None
    bm_xirr_status: str
    after_tax_xirr: float | None
    after_tax_xirr_status: str
    active_return: float | None
    is_lagging: bool | None
    max_drawdown: float
    xirr_local: float | None
    xirr_local_status: str
    bm_xirr_local: float | None
    bm_xirr_local_status: str
    active_return_local: float | None
    fx_xirr_impact: float | None
    # Upper-case aliases for contract flexibility
    CAGR: float | None
    CAGR_Status: str
    BM_CAGR: float | None
    BM_CAGR_Status: str
    XIRR: float | None
    XIRR_Status: str
    BM_XIRR: float | None
    After_Tax_XIRR: float | None
    Active_Return: float | None
    Active_Return_Local: float | None
    Is_Lagging_Benchmark: bool | None
    Max_Drawdown: float
    XIRR_Local: float | None
    FX_XIRR_Impact: float | None


class MarketSpineRecord(TypedDict, total=False):
    """Valuation spine record for daily US market holdings."""

    Date: dt.date
    ISIN: str
    CURRENCY_ID: str
    Quantity: float
    Buy_Value_Local: float
    Buy_Value_INR: float
    Buy_Price_Local: float
    Buy_Price_INR: float
