"""Investment portfolio aggregation and snapshot analytics.

Owns
----
- Portfolio daily snapshot construction.
- Portfolio, asset-class, subtype, geography, and sector aggregation.
- Tax harvest analytics and outperforming lot analytics.

Does not own
-------------
- Multiprocessing coordination (owned by application.investments).
- UI reporting charts (owned by presentation).
"""

from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PORTFOLIO_COL_RENAMES as PORTFOLIO_COL_RENAMES,
)
from personal_finance_etl.domain.investments.portfolio.aggregation import (
    GroupProcessor as GroupProcessor,
)
from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PortfolioWeightsCalculator as PortfolioWeightsCalculator,
)
from personal_finance_etl.domain.investments.portfolio.analytics import (
    AdvancedAnalyticsCalculator as AdvancedAnalyticsCalculator,
)
from personal_finance_etl.domain.investments.portfolio.analytics import (
    HarvestRecommendationCalculator as HarvestRecommendationCalculator,
)
from personal_finance_etl.domain.investments.portfolio.snapshots import (
    LotValuationContext as LotValuationContext,
)
from personal_finance_etl.domain.investments.portfolio.snapshots import (
    SnapshotGenerator as SnapshotGenerator,
)

__all__ = [
    "AdvancedAnalyticsCalculator",
    "GroupProcessor",
    "HarvestRecommendationCalculator",
    "LotValuationContext",
    "PORTFOLIO_COL_RENAMES",
    "PortfolioWeightsCalculator",
    "SnapshotGenerator",
]
