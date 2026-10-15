"""Legacy Benchmark Extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.market.benchmark.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.market.benchmark import (
    BenchmarkExtractor,
)

__all__ = ["BenchmarkExtractor"]
