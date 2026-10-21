"""Investment tax lot models and definitions.

Owns
----
- TaxLot and AcquisitionLot structured representations.
- LotBuyParameters: Parameter bundle for recording lot purchases.
- LotAction categorical mutations.

Does not own
-------------
- FIFO queue mutation and tracking (owned by domain.investments.lots.fifo).
- Lot chronological sorting policies (owned by domain.investments.lots.ordering).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
    "LotBuyParameters",
    "TaxLot",
]


@dataclass(frozen=True)
class LotBuyParameters:
    """Structured parameters required to execute a buy acquisition into FIFO portfolio.

    Parameters
    ----------
    buy_date : date
        Transaction settlement date.
    qty : float
        Purchased instrument quantity.
    price : float
        Unit acquisition price in base currency.
    shadow_qty : float
        Benchmark units purchased counterfactually.
    bm_price : float
        Benchmark unit price at acquisition.
    price_local : float, default=0.0
        Unit acquisition price in native trade currency.
    fx_rate_buy : float, default=1.0
        FX exchange rate on transaction date.
    currency_id : str | None, optional
        Native trade currency identifier.
    bm_buy_local : float | None, optional
        Benchmark unit price in native local currency.
    purchase_id : str | None, optional
        Source transaction purchase identifier.
    lot_source_type : str, default="BUY"
        Acquisition origin category.
    reconciliation_group_id : str | None, optional
        Optional deterministic grouping identifier for synthetic reconciliation lots.
    """

    buy_date: date
    qty: float
    price: float
    shadow_qty: float
    bm_price: float
    price_local: float = 0.0
    fx_rate_buy: float = 1.0
    currency_id: str | None = None
    bm_buy_local: float | None = None
    purchase_id: str | None = None
    lot_source_type: str = "PURCHASE"
    reconciliation_group_id: str | None = None
