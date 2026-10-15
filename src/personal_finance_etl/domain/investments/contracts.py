"""Investment domain contracts and structured records.

Owns
----
- Typed records for chronological events, lots, and quantitative results.
- TaxLot models and LotAction enumeration.
- CashflowRecord, TerminalValueRecord, RealizedEventRecord, ReconciliationEventRecord.
- ISINProcessResult, ISINTags, SnapshotRecord, and PipelineExecutionResult.

Does not own
-------------
- FIFO execution algorithms (owned by domain.investments.lots.fifo).
- External database tables or queries (owned by infrastructure.warehouse).
"""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from personal_finance_etl.domain.common.calculation import XirrResult as XirrResult


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


@dataclass(frozen=True, slots=True)
class TaxLot:
    """Represents a single active purchase lot in memory."""

    date: dt.date | None
    qty: float
    price: float
    bm_buy: float | None
    shadow_qty: float
    price_local: float = 0.0
    fx_rate_buy: float = 1.0
    currency_id: str | None = None
    bm_buy_local: float | None = None
    purchase_id: str | None = None
    lot_id: str | None = None
    lot_source_type: str = "PURCHASE"


# Canonical alias for TaxLot
AcquisitionLot = TaxLot


class Purchase(BaseModel):
    """Represents a purchase transaction record for an asset."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    isin: str = Field(alias="ISIN")
    date: dt.date = Field(alias="Date")
    quantity: float = Field(alias="Quantity")
    price: float = Field(alias="Price")
    value: float | None = Field(default=None, alias="Value")
    price_local: float | None = Field(default=None, alias="Price_Local")
    currency_id: str | None = Field(default=None, alias="CURRENCY_ID")
    purchase_id: str | None = Field(default=None, alias="Purchase_ID")


class Sale(BaseModel):
    """Represents a sale or disposal transaction record for an asset."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    isin: str = Field(alias="ISIN")
    date: dt.date = Field(alias="Date")
    quantity: float = Field(alias="Quantity")
    price: float | None = Field(default=None, alias="Price")
    sell_value: float | None = Field(default=None, alias="Sell_Value")
    sell_price_local: float | None = Field(default=None, alias="Sell_Price_Local")
    currency_id: str | None = Field(default=None, alias="CURRENCY_ID")
    sale_id: str | None = Field(default=None, alias="Sale_ID")


class CashflowRecord(BaseModel):
    """Represents a single cashflow event for an asset."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    date: dt.date
    amount: float
    amount_local: float = 0.0
    benchmark_amount: float | None = None
    benchmark_amount_local: float | None = None


class TerminalValueRecord(BaseModel):
    """Represents the terminal value of an asset at a specific date."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    val: float = 0.0
    shadow_val: float = 0.0
    after_tax_val: float = 0.0
    val_local: float = 0.0
    shadow_val_local: float = 0.0


class RealizedEventRecord(BaseModel):
    """Represents a realized sale event produced by FIFO disposal."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    realized_event_id: str = Field(default="", alias="Realized_Event_ID")
    sale_id: str | None = Field(default=None, alias="Sale_ID")
    lot_id: str | None = Field(default=None, alias="Lot_ID")
    purchase_id: str | None = Field(default=None, alias="Purchase_ID")
    isin: str = Field(default="", alias="ISIN")
    acquisition_date: dt.date | None = Field(default=None, alias="Acquisition_Date")
    disposal_date: dt.date = Field(alias="Disposal_Date")
    fy: str = Field(default="", alias="FY")
    quantity_disposed: float = Field(default=0.0, alias="Quantity_Disposed")
    acquisition_price: float = Field(default=0.0, alias="Acquisition_Price")
    disposed_cost_basis: float = Field(default=0.0, alias="Disposed_Cost_Basis")
    sale_price: float = Field(default=0.0, alias="Sale_Price")
    sale_proceeds: float = Field(default=0.0, alias="Sale_Proceeds")
    realized_gain_loss: float = Field(default=0.0, alias="Realized_Gain_Loss")
    holding_type: str = Field(default="", alias="Holding_Type")
    is_loss: bool = Field(default=False, alias="is_loss")
    tax_type: str = Field(default="", alias="Tax_Type")
    tax_subtype: str = Field(default="", alias="Tax_Subtype")
    lot_source_type: str = Field(default="PURCHASE", alias="Lot_Source_Type")
    currency_id: str | None = Field(default=None, alias="Currency_ID")
    asset_pnl_local: float = Field(default=0.0, alias="Asset_PnL_Local")
    asset_pnl: float = Field(default=0.0, alias="Asset_PnL")
    forex_pnl: float = Field(default=0.0, alias="Forex_PnL")
    applied_rate: float = Field(default=0.0, alias="Applied_Rate")
    estimated_tax: float = Field(default=0.0, alias="Estimated_Tax")
    shadow_qty_sold: float = Field(default=0.0, alias="shadow_qty_sold")

    @property
    def date(self) -> dt.date:
        return self.disposal_date

    @property
    def sell_qty(self) -> float:
        return self.quantity_disposed

    @property
    def sell_price(self) -> float:
        return self.sale_price

    @property
    def buy_date(self) -> dt.date | None:
        return self.acquisition_date

    @property
    def buy_price(self) -> float:
        return self.acquisition_price

    @property
    def realized_pnl(self) -> float:
        return self.realized_gain_loss


# Canonical alias for RealizedEventRecord
RealizedEvent = RealizedEventRecord


class ReconciliationEventRecord(BaseModel):
    """Represents a discrepancy event between reconstructed lots and broker evidence."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    recon_event_id: str = Field(default="", alias="Reconciliation_Event_ID")
    recon_group_id: str | None = Field(default=None, alias="Reconciliation_Group_ID")
    lot_id: str | None = Field(default=None, alias="Lot_ID")
    isin: str = Field(default="", alias="ISIN")
    recon_date: dt.date = Field(alias="Reconciliation_Date")
    adjustment_type: str = Field(default="", alias="Adjustment_Type")
    reconstructed_qty: float = Field(default=0.0, alias="Reconstructed_Quantity")
    observed_qty: float = Field(default=0.0, alias="Observed_Quantity")
    delta_qty: float = Field(default=0.0, alias="Delta_Quantity")
    reconstructed_cost_basis: float | None = Field(default=None, alias="Reconstructed_Cost_Basis")
    observed_cost_basis: float | None = Field(default=None, alias="Observed_Cost_Basis")
    delta_cost_basis: float | None = Field(default=None, alias="Delta_Cost_Basis")


# Canonical alias for ReconciliationEventRecord
ReconciliationEvent = ReconciliationEventRecord


class ISINTags(BaseModel):
    """Classification tags for an ISIN."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    instrument_class: str = Field(alias="class")
    subtype: str
    instrument_type: str = "Unknown"
    sector: str = "Unknown"
    industry: str = "Unknown"
    geo: str = "Unknown"
    country: str = "Unknown"
    currency: str = ""


class SnapshotRecord(BaseModel):
    """Represents a daily snapshot record for a single tax lot."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    Closing_Date: dt.date
    ISIN: str
    CURRENCY_ID: str
    BENCHMARK_ID: str | None
    Lot_ID: str
    Purchase_ID: str | None
    Lot_Source_Type: str
    TAX_TYPE: str
    TAX_SUBTYPE: str
    Buy_Date: dt.date | None
    Age_Days: int
    LTCG_Threshold_Days: int
    Days_To_LTCG: int
    Holding_Type: str
    Quantity: float
    Execution_Residual: float = 0.0
    Buy_Price: float
    Market_Price: float
    Buy_Value: float
    Close_Value: float
    P_L: float = Field(alias="P/L")
    Absolute_Return: float = 0.0
    Lot_Weight: float = 0.0
    Lot_CAGR: float | None = None
    Lot_CAGR_Status: str = "UNDEFINED"

    CAGR: float | None = None
    CAGR_Status: str = "UNDEFINED"
    XIRR: float | None
    XIRR_Status: str = "INVALID_INPUT"
    After_Tax_XIRR: float | None

    BM_Buy_Price: float | None
    BM_Market_Price: float
    Lot_BM_Return: float = 0.0
    Lot_BM_CAGR: float | None = None
    Lot_BM_CAGR_Status: str = "UNDEFINED"
    Lot_BM_CAGR_Local: float | None = None
    BM_CAGR: float | None = None
    BM_CAGR_Status: str = "UNDEFINED"
    BM_XIRR: float | None
    BM_XIRR_Local: float | None = None
    Active_Return: float | None
    Active_Return_Local: float | None = None
    Lot_Alpha: float | None = None
    Is_Lagging_Benchmark: bool | None
    XIRR_Local: float | None = None
    FX_XIRR_Impact: float | None = None

    Max_Drawdown: float = 0.0

    Tax_Rate: float
    Unrealized_LTCG: float
    Unrealized_STCG: float
    Unrealized_Gain: float
    Unrealized_LTCL: float
    Unrealized_STCL: float
    Unrealized_Loss: float
    LTCG_Tax_If_Sold: float
    STCG_Tax_If_Sold: float
    After_Tax_PL: float
    After_Tax_Close_Value: float
    Dietz_Day_Weight: float
    Outperforming_Lot_Ratio: float = 0.0
    Buy_Value_Local: float = 0.0
    Close_Value_Local: float = 0.0
    Asset_PnL: float = 0.0
    Forex_PnL: float = 0.0
    Forex_Contribution_Pct: float = 0.0
    Lot_CAGR_Local: float | None = None
    Absolute_Return_Local: float = 0.0
    Asset_Return_Pct: float = 0.0
    Forex_Return_Pct: float = 0.0
    Blended_FX_Buy_Rate: float = 0.0
    Buy_Price_Local: float = 0.0
    Market_Price_Local: float = 0.0
    FX_Rate_Buy: float = 0.0
    FX_Rate_Snap: float = 0.0
    Currency_Appreciation_Pct: float = 0.0


class ISINTaskPayload(BaseModel):
    """Payload representing a single ISIN processing task in the worker queue."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=False)

    isin: str
    p_inst: list[dict[str, Any]]
    s_inst: list[dict[str, Any]]
    m_inst: list[dict[str, Any]]
    master_row: dict[str, Any]
    bm_map: dict[str, Any]


class ISINProcessResult(BaseModel):
    """Complete result payload from processing a single ISIN."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    df_snapshots: Any | None = None
    cashflows: list[CashflowRecord]
    terminals: dict[dt.date, TerminalValueRecord]
    realized_events: list[dict[str, Any]]
    recon_events: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())
    tags: ISINTags


class PipelineExecutionResult(BaseModel):
    """Aggregate result from entire pipeline execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=False)

    has_data: bool
    global_cf: list[dict[str, Any]]
    global_pt: dict[dt.date, dict[str, float]]
    global_re: list[dict[str, Any]]
    global_recon_events: list[dict[str, Any]]
    isin_cf: dict[str, list[dict[str, Any]]]
    isin_pt: dict[str, dict[dt.date, dict[str, Any]]]
    class_cf: dict[str, list[dict[str, Any]]]
    class_pt: dict[str, dict[dt.date, dict[str, float]]]
    class_re: dict[str, list[dict[str, Any]]]
    subtype_cf: dict[str, list[dict[str, Any]]]
    subtype_pt: dict[str, dict[dt.date, dict[str, float]]]
    subtype_re: dict[str, list[dict[str, Any]]]
    instrument_type_cf: dict[str, list[dict[str, Any]]]
    instrument_type_pt: dict[str, dict[dt.date, dict[str, float]]]
    sector_cf: dict[str, list[dict[str, Any]]]
    sector_pt: dict[str, dict[dt.date, dict[str, float]]]
    industry_cf: dict[str, list[dict[str, Any]]]
    industry_pt: dict[str, dict[dt.date, dict[str, float]]]
    geo_cf: dict[str, list[dict[str, Any]]]
    geo_pt: dict[str, dict[dt.date, dict[str, float]]]
    country_cf: dict[str, list[dict[str, Any]]]
    country_pt: dict[str, dict[dt.date, dict[str, float]]]
    currency_cf: dict[str, list[dict[str, Any]]]
    currency_pt: dict[str, dict[dt.date, dict[str, float]]]
    currency_re: dict[str, list[dict[str, Any]]]


# Canonical alias for PipelineExecutionResult
PortfolioResult = PipelineExecutionResult

__all__ = [
    "AcquisitionLot",
    "CashflowRecord",
    "ISINProcessResult",
    "ISINTags",
    "ISINTaskPayload",
    "LotAction",
    "PipelineExecutionResult",
    "PortfolioResult",
    "Purchase",
    "RealizedEvent",
    "RealizedEventRecord",
    "ReconciliationAdjustmentType",
    "ReconciliationEvent",
    "ReconciliationEventRecord",
    "Sale",
    "SnapshotRecord",
    "TaxLot",
    "TerminalValueRecord",
]
