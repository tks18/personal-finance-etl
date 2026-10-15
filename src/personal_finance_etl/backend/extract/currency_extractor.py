"""Legacy Currency Extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.market.currency.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.market.currency import (
    CurrencyExtractor,
)

__all__ = ["CurrencyExtractor"]
