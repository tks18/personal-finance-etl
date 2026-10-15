"""Machine-readable failure taxonomy for personal-finance-etl (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
Failure contracts have migrated to `personal_finance_etl.contracts.lifecycle`.
"""

from personal_finance_etl.contracts.lifecycle import (
    FailureDomain,
    classify_failure_domain,
)

__all__ = [
    "FailureDomain",
    "classify_failure_domain",
]
