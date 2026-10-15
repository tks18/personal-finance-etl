"""Typed result for FX rate provider lookups (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
FX types have migrated to `personal_finance_etl.domain.market.fx`.
"""

from personal_finance_etl.domain.market.fx import (
    FXObservation,
)

__all__ = [
    "FXObservation",
]
