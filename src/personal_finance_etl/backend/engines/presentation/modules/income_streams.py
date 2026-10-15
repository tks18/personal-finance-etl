"""DEPRECATED: Legacy income streams builder module.

Superseded by `personal_finance_etl.domain.household.income`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.income import IncomeStreamsBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.income_streams is deprecated. "
    "Use personal_finance_etl.domain.household.income instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["IncomeStreamsBuilder"]
