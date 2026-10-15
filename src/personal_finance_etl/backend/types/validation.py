"""Financial source validation exceptions (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
Validation types have migrated to `personal_finance_etl.domain.common.validation`.
"""

from personal_finance_etl.domain.common.validation import (
    FinancialSourceValidationError,
)

__all__ = [
    "FinancialSourceValidationError",
]
