"""DEPRECATED: Legacy budget forecast builder module.

Superseded by `personal_finance_etl.domain.household.budget`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.budget import BudgetForecastBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.budget_forecast is deprecated. "
    "Use personal_finance_etl.domain.household.budget instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["BudgetForecastBuilder"]
