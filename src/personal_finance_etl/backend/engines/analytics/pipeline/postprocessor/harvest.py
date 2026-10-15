"""Harvest recommendation calculator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All tax harvesting recommendation calculations have migrated to
`personal_finance_etl.domain.investments.portfolio.analytics`.
"""

from personal_finance_etl.domain.investments.portfolio.analytics import (
    HarvestRecommendationCalculator as HarvestRecommendationCalculator,
)

__all__ = ["HarvestRecommendationCalculator"]
