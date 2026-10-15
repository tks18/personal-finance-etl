"""DEPRECATED: Legacy forecasting helper module.

Superseded by `personal_finance_etl.domain.fire.forecasting`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.fire.forecasting import calculate_budget_forecast

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.helpers.forecasting is deprecated. "
    "Use personal_finance_etl.domain.fire.forecasting instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["calculate_budget_forecast"]
