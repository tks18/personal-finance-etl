"""Investment market valuation, benchmark, and FX valuation.

Owns
----
- Valuation models for instruments at historical snapshots.
- Benchmark counterfactual valuation and tracking.
- Local currency and INR FX valuation gates.
- Market state continuous daily series reconstruction.

Does not own
-------------
- Raw market data extraction (owned by infrastructure.providers.market).
- Lot FIFO state (owned by domain.investments.lots).
"""

from personal_finance_etl.domain.investments.valuation.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXProviderMissingError,
    FXRateUnavailableError,
    FXValidationGate,
)
from personal_finance_etl.domain.investments.valuation.market_state import (
    EMPTY_US_MARKET_SCHEMA,
    transform_us_market_data,
)

__all__ = [
    "BenchmarkPriceProvider",
    "EMPTY_US_MARKET_SCHEMA",
    "FXProviderMissingError",
    "FXRateUnavailableError",
    "FXValidationGate",
    "transform_us_market_data",
]

