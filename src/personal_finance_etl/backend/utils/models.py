"""Shared dataclasses and enums for the App."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from personal_finance_etl.contracts.extraction import (
    AssetPipelineResult as AssetPipelineResult,
)
from personal_finance_etl.contracts.extraction import (
    ExtractionResult as ExtractionResult,
)
from personal_finance_etl.contracts.logging import LogLevel as LogLevel
from personal_finance_etl.domain.investments.contracts import TaxLot as TaxLot


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
