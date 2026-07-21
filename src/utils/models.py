"""
Shared dataclasses and enums for the App.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import polars as pl


class LogLevel(StrEnum):
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


class FileKey(StrEnum):
    PURCHASES = "p"
    SALES = "s"
    MARKET = "m"
    INVESTMENT = "i"
    BENCHMARK = "b"
    TAX = "t"


class ExportMode(StrEnum):
    CONSOLIDATED = "consolidated"
    INDIVIDUAL = "individual"


class AssetClass(StrEnum):
    EQUITY = "equity"
    DEBT = "debt"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class TaxLot:
    """Represents a single active purchase lot."""

    date: date | None
    qty: float
    price: float
    bm_buy: float | None
    shadow_qty: float


@dataclass
class ExtractionResult:
    zcategory: pl.LazyFrame
    assetgroup: pl.LazyFrame
    assets: pl.LazyFrame
    currency: pl.LazyFrame
    inoutcome: pl.LazyFrame
    mappings: dict[str, dict[str, str]]
    stg_mf_isin_mapping: pl.LazyFrame
    stg_benchmark_mapping: pl.LazyFrame
    mf_market_data_raw: pl.LazyFrame
    mf_transactions_raw: pl.LazyFrame
    stock_market_data_raw: pl.LazyFrame
    stock_transactions_raw: pl.LazyFrame
    raw_opening_balances: pl.LazyFrame
    raw_benchmark_master: pl.LazyFrame
    raw_tax_rates: pl.LazyFrame


@dataclass
class AssetPipelineResult:
    market_data: pl.LazyFrame
    market_data_ref: pl.LazyFrame
    purchase_ref: pl.LazyFrame
    sale_ref: pl.LazyFrame
    master_ref: pl.LazyFrame
