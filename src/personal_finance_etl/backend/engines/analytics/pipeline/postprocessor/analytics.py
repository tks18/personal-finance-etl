"""Advanced analytics calculator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All portfolio drawdown and return tracking calculations have migrated to
`personal_finance_etl.domain.investments.portfolio.analytics`.
"""

from personal_finance_etl.domain.investments.portfolio.analytics import (
    AdvancedAnalyticsCalculator as AdvancedAnalyticsCalculator,
)

__all__ = ["AdvancedAnalyticsCalculator"]
