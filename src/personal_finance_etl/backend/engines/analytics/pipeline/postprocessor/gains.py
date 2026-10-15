"""Realized gains calculator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All FY realized capital gains and attribution calculations have migrated to
`personal_finance_etl.domain.investments.performance.attribution`.
"""

from personal_finance_etl.domain.investments.performance.attribution import (
    RealizedGainsCalculator as RealizedGainsCalculator,
)

__all__ = ["RealizedGainsCalculator"]
