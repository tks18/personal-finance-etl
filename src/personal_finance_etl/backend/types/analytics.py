import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from personal_finance_etl.backend.types.calculation import XirrResult as XirrResult


class CashflowRecord(BaseModel):
    """Represents a single cashflow event for an asset."""

    model_config = ConfigDict(strict=True, populate_by_name=True)
    date: datetime.date
    amount: float
    amount_local: float = 0.0


class TerminalValueRecord(BaseModel):
    """Represents the terminal value of an asset at a specific date."""

    model_config = ConfigDict(strict=True, populate_by_name=True)
    val: float = 0.0
    shadow_val: float = 0.0
    after_tax_val: float = 0.0
    val_local: float = 0.0
    shadow_val_local: float = 0.0


class RealizedEventRecord(BaseModel):
    """Represents a realized sell event."""

    model_config = ConfigDict(strict=False, populate_by_name=True)
    date: datetime.date
    sell_qty: float
    sell_price: float
    buy_date: datetime.date | None = None
    buy_price: float = 0.0
    realized_pnl: float = 0.0
    # Additional fields are sometimes returned by fifo.sell depending on tax logic


class ISINTags(BaseModel):
    """Classification tags for an ISIN."""

    model_config = ConfigDict(strict=True, populate_by_name=True)
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

    Closing_Date: datetime.date
    ISIN: str
    CURRENCY_ID: str
    BENCHMARK_ID: str | None
    Lot_ID: str
    Purchase_ID: str | None
    Lot_Source_Type: str
    TAX_TYPE: str
    TAX_SUBTYPE: str
    Buy_Date: datetime.date | None
    Age_Days: int
    LTCG_Threshold_Days: int
    Days_To_LTCG: int
    Holding_Type: str
    Quantity: float
    Execution_Residual: float = 0.0  # Units pending execution (qty ordered but not yet settled)
    Buy_Price: float
    Market_Price: float
    Buy_Value: float
    Close_Value: float
    P_L: float = Field(alias="P/L")
    Absolute_Return: float = 0.0
    Lot_Weight: float = 0.0
    Lot_CAGR: float

    CAGR: float
    XIRR: float
    XIRR_Status: str = "VALID"  # VALID | INVALID_INPUT | UNDEFINED | NON_CONVERGENT
    After_Tax_XIRR: float

    BM_Buy_Price: float | None
    BM_Market_Price: float
    Lot_BM_Return: float = 0.0
    Lot_BM_CAGR: float
    Lot_BM_CAGR_Local: float = 0.0
    BM_CAGR: float
    BM_XIRR: float
    BM_XIRR_Local: float = 0.0
    Active_Return: float
    Active_Return_Local: float = 0.0
    Lot_Alpha: float
    Is_Lagging_Benchmark: bool
    XIRR_Local: float = 0.0
    FX_XIRR_Impact: float = 0.0

    # Drawdown
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
    Lot_CAGR_Local: float = 0.0
    Absolute_Return_Local: float = 0.0
    Asset_Return_Pct: float = 0.0
    Forex_Return_Pct: float = 0.0
    Blended_FX_Buy_Rate: float = 0.0
    Buy_Price_Local: float = 0.0    # Acquisition price in the instrument's native currency
    Market_Price_Local: float = 0.0 # Market price in the instrument's native currency at snapshot date
    FX_Rate_Buy: float = 0.0        # FX rate (native → INR) at acquisition date
    FX_Rate_Snap: float = 0.0       # FX rate (native → INR) at snapshot date
    Currency_Appreciation_Pct: float = 0.0


class ISINProcessResult(BaseModel):
    """The complete result payload from processing a single ISIN."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # We allow Any here to safely pass the Polars DataFrame across boundaries
    df_snapshots: Any | None = None
    cashflows: list[CashflowRecord]
    terminals: dict[datetime.date, TerminalValueRecord]
    realized_events: list[dict[str, Any]]  # Flexibility for FIFO outputs before full enforcement
    recon_events: list[dict[str, Any]] = Field(default_factory=lambda: [])
    tags: ISINTags
