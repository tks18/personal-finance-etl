"""Legacy delegation shim for per-ISIN chronological quant processor.

Superseded by personal_finance_etl.application.investments.isin_service.
"""

from personal_finance_etl.application.investments.isin_service import (
    IsinProcessor as IsinProcessor,
)
from personal_finance_etl.application.investments.isin_service import (
    _is_zero_proceeds_re_adjustment as _is_zero_proceeds_re_adjustment,
)
from personal_finance_etl.application.investments.isin_service import (
    is_indian_rights_entitlement_isin as is_indian_rights_entitlement_isin,
)

__all__ = [
    "IsinProcessor",
    "_is_zero_proceeds_re_adjustment",
    "is_indian_rights_entitlement_isin",
]
