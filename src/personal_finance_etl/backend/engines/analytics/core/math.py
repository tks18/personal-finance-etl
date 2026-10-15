"""Analytics engine core math module (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All mathematical returns and XIRR algorithms have migrated to
`personal_finance_etl.domain.investments.performance.returns` and
`personal_finance_etl.domain.investments.performance.xirr`.
"""

from personal_finance_etl.domain.common.calculation import (
    CagrResult as CagrResult,
)
from personal_finance_etl.domain.common.calculation import (
    CalculationStatus as CalculationStatus,
)
from personal_finance_etl.domain.common.calculation import (
    XirrResult as XirrResult,
)
from personal_finance_etl.domain.investments.performance.returns import (
    calculate_cagr as calculate_cagr,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    calculate_xirr as calculate_xirr,
)

__all__ = [
    "CagrResult",
    "CalculationStatus",
    "XirrResult",
    "calculate_cagr",
    "calculate_xirr",
]
