"""Legacy deactivation shim for backend.transform.currency_transformer.

Delegates completely to canonical domain.market.fx.
"""

from personal_finance_etl.domain.market.fx import (
    transform_currency_fx_rates as transform_currency_fx_rates,
)

__all__ = [
    "transform_currency_fx_rates",
]
