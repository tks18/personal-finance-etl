"""Legacy deactivation shim for backend.transform.us_stocks.

Delegates completely to canonical domain.investments.transforms.us_equity.
"""

from personal_finance_etl.domain.investments.transforms.us_equity import (
    get_base_us_stock_transactions as get_base_us_stock_transactions,
)
from personal_finance_etl.domain.investments.transforms.us_equity import (
    get_stg_us_stock_master_ref as get_stg_us_stock_master_ref,
)
from personal_finance_etl.domain.investments.transforms.us_equity import (
    transform_stg_us_stock_trades as transform_stg_us_stock_trades,
)

__all__ = [
    "get_base_us_stock_transactions",
    "get_stg_us_stock_master_ref",
    "transform_stg_us_stock_trades",
]
