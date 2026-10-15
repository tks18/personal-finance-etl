"""Portfolio weights calculator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All portfolio and lot weighting calculations have migrated to
`personal_finance_etl.domain.investments.portfolio.aggregation`.
"""

from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PortfolioWeightsCalculator as PortfolioWeightsCalculator,
)

__all__ = ["PortfolioWeightsCalculator"]
