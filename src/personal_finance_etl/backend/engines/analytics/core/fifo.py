"""FIFO lot tracking engine (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All FIFO state and lot tracking logic has migrated to
`personal_finance_etl.domain.investments.lots.fifo`.
"""

from personal_finance_etl.domain.investments.lots.fifo import (
    FIFOPortfolio as FIFOPortfolio,
)

__all__ = ["FIFOPortfolio"]
