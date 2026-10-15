"""Legacy US Market Extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.market.us_market.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.market.us_market import (
    USMarketExtractor,
)

__all__ = ["USMarketExtractor"]
