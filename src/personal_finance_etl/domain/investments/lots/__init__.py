"""Tax lot tracking, FIFO disposal, and lot ordering.

Owns
----
- State-preserving FIFOPortfolio class and active lot queue.
- TaxLot models and chronological ordering rules.
- Lot disposal, realized gain/loss computation, and lot-level cost basis.

Does not own
-------------
- Statutory tax head classification (owned by domain.tax).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.domain.investments.lots.fifo import (
    FIFOPortfolio,
    LotBuyParameters,
)
from personal_finance_etl.domain.investments.lots.models import (
    AcquisitionLot,
    LotAction,
    TaxLot,
)
from personal_finance_etl.domain.investments.lots.ordering import (
    CanonicalOrderPolicy,
    sort_purchases,
    sort_sales,
)

__all__ = [
    "AcquisitionLot",
    "CanonicalOrderPolicy",
    "FIFOPortfolio",
    "LotAction",
    "LotBuyParameters",
    "TaxLot",
    "sort_purchases",
    "sort_sales",
]
