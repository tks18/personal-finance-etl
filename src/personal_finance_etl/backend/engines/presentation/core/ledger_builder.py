"""DEPRECATED: Legacy ledger builder module.

Superseded by `personal_finance_etl.domain.household.ledger`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.ledger import LedgerBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.core.ledger_builder is deprecated. "
    "Use personal_finance_etl.domain.household.ledger instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["LedgerBuilder"]
