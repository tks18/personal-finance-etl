"""Legacy deactivation shim for backend.utils.ordering.

Delegates completely to canonical domain.investments.lots.ordering.
"""

from personal_finance_etl.domain.investments.lots.ordering import (
    CanonicalOrderPolicy as CanonicalOrderPolicy,
)
from personal_finance_etl.domain.investments.lots.ordering import (
    sort_purchases as sort_purchases,
)
from personal_finance_etl.domain.investments.lots.ordering import (
    sort_sales as sort_sales,
)

__all__ = [
    "CanonicalOrderPolicy",
    "sort_purchases",
    "sort_sales",
]
