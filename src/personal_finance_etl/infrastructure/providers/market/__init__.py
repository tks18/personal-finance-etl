"""Market data provider adapters.

Owns
----
- Currency FX historical rates acquisition (Yahoo Finance adapter).
- Benchmark historical price series acquisition adapter.
- US market historical price series acquisition adapter.

Does not own
-------------
- Currency normalization business logic (owned by domain.market.fx).
- Investment valuation formulas (owned by domain.investments.valuation).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.market.benchmark import (
    BenchmarkExtractor,
)
from personal_finance_etl.infrastructure.providers.market.currency import (
    CurrencyExtractor,
)
from personal_finance_etl.infrastructure.providers.market.us_market import (
    USMarketExtractor,
)

__all__ = [
    "BenchmarkExtractor",
    "CurrencyExtractor",
    "USMarketExtractor",
]
