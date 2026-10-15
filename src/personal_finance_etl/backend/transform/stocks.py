"""Legacy deactivation shim for backend.transform.stocks.

Delegates completely to canonical domain.investments.transforms.indian_equity.
"""

from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_base_stock_transactions as get_base_stock_transactions,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_stg_stock_market_data as get_stg_stock_market_data,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_stg_stock_market_data_ref as get_stg_stock_market_data_ref,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_stg_stock_master_ref as get_stg_stock_master_ref,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    transform_stg_stock_trades as transform_stg_stock_trades,
)

__all__ = [
    "get_base_stock_transactions",
    "get_stg_stock_market_data",
    "get_stg_stock_market_data_ref",
    "get_stg_stock_master_ref",
    "transform_stg_stock_trades",
]
