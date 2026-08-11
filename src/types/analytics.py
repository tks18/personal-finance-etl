import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CashflowRecord(BaseModel):
    """Represents a single cashflow event for an asset."""

    model_config = ConfigDict(strict=True, populate_by_name=True)
    date: datetime.date
    amount: float


class TerminalValueRecord(BaseModel):
    """Represents the terminal value of an asset at a specific date."""

    model_config = ConfigDict(strict=True, populate_by_name=True)
    val: float = 0.0
    shadow_val: float = 0.0
    after_tax_val: float = 0.0


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


class SnapshotRecord(BaseModel):
    """Represents a daily snapshot record for a single tax lot."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    Closing_Date: datetime.date
    ISIN: str
    BENCHMARK_ID: str | None
    TAX_TYPE: str
    TAX_SUBTYPE: str
    Buy_Date: datetime.date | None
    Age_Days: int
    LTCG_Threshold_Days: int
    Days_To_LTCG: int
    Holding_Type: str
    Quantity: float
    Buy_Price: float
    Market_Price: float
    Buy_Value: float
    Close_Value: float
    P_L: float = Field(alias="P/L")
    Returns_pct: float = Field(alias="Returns_%")
    Lot_CAGR: float
    CAGR: float
    XIRR: float
    After_Tax_XIRR: float
    BM_Buy_Price: float | None
    BM_Market_Price: float
    Lot_BM_Returns_pct: float = Field(alias="Lot_BM_Returns_%")
    Lot_BM_CAGR: float
    BM_CAGR: float
    BM_XIRR: float
    Active_Return: float
    Lot_Alpha: float
    Is_Lagging_Benchmark: bool
    Beta: float
    Tracking_Error: float
    Information_Ratio: float
    Upside_Capture: float
    Downside_Capture: float
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
    Outperformance_Probability: float = 0.0


class ISINProcessResult(BaseModel):
    """The complete result payload from processing a single ISIN."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    # We allow Any here to safely pass the Polars DataFrame across boundaries
    df_snapshots: Any | None = None
    cashflows: list[CashflowRecord]
    terminals: dict[datetime.date, TerminalValueRecord]
    realized_events: list[dict[str, Any]]  # Flexibility for FIFO outputs before full enforcement
    tags: ISINTags
