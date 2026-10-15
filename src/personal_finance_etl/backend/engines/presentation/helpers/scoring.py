"""DEPRECATED: Legacy health scoring module.

Superseded by `personal_finance_etl.domain.wealth.scoring`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.wealth.scoring import (
    HealthScorer,
    calculate_budget_health_score,
)

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.helpers.scoring is deprecated. "
    "Use personal_finance_etl.domain.wealth.scoring instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["HealthScorer", "calculate_budget_health_score"]
