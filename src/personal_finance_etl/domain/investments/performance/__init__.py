"""Investment performance, returns, and attribution calculations.

Owns
----
- Pure XIRR and CAGR mathematical solvers and statuses.
- Period returns, active returns, and alpha calculations.
- Asset vs Forex performance attribution.

Does not own
-------------
- Stateful lot iteration (owned by domain.investments.lots).
- Aggregation across multiprocessing batches (owned by application.investments).
"""

from personal_finance_etl.domain.investments.performance.attribution import (
    RealizedGainsCalculator as RealizedGainsCalculator,
)
from personal_finance_etl.domain.investments.performance.returns import (
    CagrResult as CagrResult,
)
from personal_finance_etl.domain.investments.performance.returns import (
    CalculationStatus as CalculationStatus,
)
from personal_finance_etl.domain.investments.performance.returns import (
    calculate_cagr as calculate_cagr,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator as PortfolioXIRRCalculator,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    XirrResult as XirrResult,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    calculate_xirr as calculate_xirr,
)

__all__ = [
    "CagrResult",
    "CalculationStatus",
    "PortfolioXIRRCalculator",
    "RealizedGainsCalculator",
    "XirrResult",
    "calculate_cagr",
    "calculate_xirr",
]
