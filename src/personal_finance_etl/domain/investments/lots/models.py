"""Investment tax lot models and definitions.

Owns
----
- TaxLot and AcquisitionLot structured representations.
- LotAction categorical mutations.

Does not own
-------------
- FIFO queue mutation and tracking (owned by domain.investments.lots.fifo).
- Lot chronological sorting policies (owned by domain.investments.lots.ordering).
"""

from personal_finance_etl.domain.investments.contracts import (
    AcquisitionLot as AcquisitionLot,
)
from personal_finance_etl.domain.investments.contracts import (
    LotAction as LotAction,
)
from personal_finance_etl.domain.investments.contracts import (
    TaxLot as TaxLot,
)

__all__ = [
    "AcquisitionLot",
    "LotAction",
    "TaxLot",
]
