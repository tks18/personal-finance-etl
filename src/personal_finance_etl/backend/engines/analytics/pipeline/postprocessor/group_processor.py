"""Group level analytics processor (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All group aggregation logic has migrated to
`personal_finance_etl.domain.investments.portfolio.aggregation`.
"""

from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PORTFOLIO_COL_RENAMES as PORTFOLIO_COL_RENAMES,
)
from personal_finance_etl.domain.investments.portfolio.aggregation import (
    GroupProcessor as GroupProcessor,
)

__all__ = [
    "GroupProcessor",
    "PORTFOLIO_COL_RENAMES",
]
