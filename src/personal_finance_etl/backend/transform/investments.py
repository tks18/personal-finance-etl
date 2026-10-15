"""Legacy deactivation shim for backend.transform.investments.

Delegates completely to canonical domain.investments.transforms.common.
"""

from personal_finance_etl.domain.investments.transforms.common import (
    _batch_compute_purchase_ids as _batch_compute_purchase_ids,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.domain.investments.transforms.common import (
    _batch_compute_sale_ids as _batch_compute_sale_ids,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.domain.investments.transforms.common import (
    _compute_purchase_id as _compute_purchase_id,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.domain.investments.transforms.common import (
    _compute_sale_id as _compute_sale_id,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_d_investment_master as get_d_investment_master,
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_f_tf_investment_purchase_data as get_f_tf_investment_purchase_data,
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_f_tf_investment_sale_data as get_f_tf_investment_sale_data,
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_purchase_reference as get_purchase_reference,
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_sale_reference as get_sale_reference,
)
from personal_finance_etl.domain.investments.transforms.common import (
    transform_stg_investment_market_data as transform_stg_investment_market_data,
)

__all__ = [
    "_batch_compute_purchase_ids",
    "_batch_compute_sale_ids",
    "_compute_purchase_id",
    "_compute_sale_id",
    "get_d_investment_master",
    "get_f_tf_investment_purchase_data",
    "get_f_tf_investment_sale_data",
    "get_purchase_reference",
    "get_sale_reference",
    "transform_stg_investment_market_data",
]
