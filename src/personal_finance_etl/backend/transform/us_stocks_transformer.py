"""Legacy deactivation shim for backend.transform.us_stocks_transformer.

Delegates completely to canonical domain.investments.valuation.market_state.
"""

from personal_finance_etl.domain.investments.valuation.market_state import (
    EMPTY_US_MARKET_SCHEMA as EMPTY_US_MARKET_SCHEMA,
)
from personal_finance_etl.domain.investments.valuation.market_state import (
    transform_us_market_data as transform_us_market_data,
)

__all__ = [
    "EMPTY_US_MARKET_SCHEMA",
    "transform_us_market_data",
]
