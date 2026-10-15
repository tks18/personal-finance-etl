"""Portfolio XIRR calculator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All portfolio XIRR post-processing algorithms have migrated to
`personal_finance_etl.domain.investments.performance.xirr`.
"""

from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator as PortfolioXIRRCalculator,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    calculate_xirr as calculate_xirr,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    numeric_value as _numeric_value,
)

__all__ = [
    "PortfolioXIRRCalculator",
    "_numeric_value",
    "calculate_xirr",
]
