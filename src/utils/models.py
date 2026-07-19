"""
Shared dataclasses and enums for the App.
"""

from dataclasses import dataclass
from enum import Enum
from datetime import date
import polars as pl


class LogLevel(str, Enum):
    INFO = "info"
    STEP = "step"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class EngineStatus:
    """Structured message for the UI status queue."""
    msg: str
    data: pl.DataFrame | None = None
    progress: float | None = None
    level: LogLevel = LogLevel.INFO


class FileKey(str, Enum):
    PURCHASES = "p"
    SALES = "s"
    MARKET = "m"
    INVESTMENT = "i"
    BENCHMARK = "b"
    TAX = "t"


class ExportMode(str, Enum):
    CONSOLIDATED = "consolidated"
    INDIVIDUAL = "individual"


class AssetClass(str, Enum):
    EQUITY = "equity"
    DEBT = "debt"
    DEFAULT = "default"


@dataclass
class TaxLot:
    """Represents a single active purchase lot."""
    date: date | None
    qty: float
    price: float
    bm_buy: float | None
    shadow_qty: float
