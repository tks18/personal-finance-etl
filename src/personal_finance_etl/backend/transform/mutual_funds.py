"""Legacy deactivation shim for backend.transform.mutual_funds.

Delegates completely to canonical domain.investments.transforms.mutual_funds.
"""

from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_base_mf_transactions as get_base_mf_transactions,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_stg_mf_market_data as get_stg_mf_market_data,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_stg_mf_market_data_ref as get_stg_mf_market_data_ref,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    get_stg_mf_master_ref as get_stg_mf_master_ref,
)
from personal_finance_etl.domain.investments.transforms.mutual_funds import (
    transform_stg_mf_trades as transform_stg_mf_trades,
)

__all__ = [
    "get_base_mf_transactions",
    "get_stg_mf_market_data",
    "get_stg_mf_market_data_ref",
    "get_stg_mf_master_ref",
    "transform_stg_mf_trades",
]
