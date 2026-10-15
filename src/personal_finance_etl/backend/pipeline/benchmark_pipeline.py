"""Legacy BenchmarkPipeline shim.

DEACTIVATED: This module is superseded by application.ingestion.market_sync.
"""

from __future__ import annotations

from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
)

__all__ = ["BenchmarkPipeline"]
