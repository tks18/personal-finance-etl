"""DEPRECATED: Legacy wealth risk analytics module.

Superseded by `personal_finance_etl.domain.fire.deterministic`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.fire.deterministic import WealthRiskAnalyticsBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.wealth_risk_analytics is deprecated. "
    "Use personal_finance_etl.domain.fire.deterministic instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["WealthRiskAnalyticsBuilder"]
