"""Legacy asset ingestion strategies shim.

DEACTIVATED: This module is superseded by application.ingestion.asset_strategies.
"""

from __future__ import annotations

from personal_finance_etl.application.ingestion.asset_strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)

__all__ = [
    "AssetPipeline",
    "MutualFundPipeline",
    "StockPipeline",
    "USStockPipeline",
]
