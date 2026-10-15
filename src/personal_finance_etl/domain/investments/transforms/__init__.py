"""Investment canonical Polars transformations.

Owns
----
- Mutual fund transaction and holdings transformations.
- Indian equity transaction and market transformations.
- US equity transaction and market transformations.
- Common investment transformation helpers.

Does not own
-------------
- Stateful FIFO lot matching (owned by domain.investments.lots).
- Physical table insertion (owned by infrastructure.warehouse).
"""

from personal_finance_etl.domain.investments.transforms.common import (
    get_d_investment_master,
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
    get_purchase_reference,
    get_sale_reference,
    transform_stg_investment_market_data,
)
from personal_finance_etl.domain.investments.transforms.indian_equity import (
    get_base_stock_transactions,
    get_stg_stock_market_data,
    get_stg_stock_market_data_ref,
    get_stg_stock_master_ref,
    transform_stg_stock_trades,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_base_mf_transactions,
    get_stg_mf_market_data,
    get_stg_mf_market_data_ref,
    get_stg_mf_master_ref,
    transform_stg_mf_trades,
)
from personal_finance_etl.domain.investments.transforms.us_equity import (
    get_base_us_stock_transactions,
    get_stg_us_stock_master_ref,
    transform_stg_us_stock_trades,
)

__all__ = [
    "get_base_mf_transactions",
    "get_base_stock_transactions",
    "get_base_us_stock_transactions",
    "get_d_investment_master",
    "get_f_tf_investment_purchase_data",
    "get_f_tf_investment_sale_data",
    "get_purchase_reference",
    "get_sale_reference",
    "get_stg_mf_market_data",
    "get_stg_mf_market_data_ref",
    "get_stg_mf_master_ref",
    "get_stg_stock_market_data",
    "get_stg_stock_market_data_ref",
    "get_stg_stock_master_ref",
    "get_stg_us_stock_master_ref",
    "transform_stg_investment_market_data",
    "transform_stg_mf_trades",
    "transform_stg_stock_trades",
    "transform_stg_us_stock_trades",
]
