"""DEPRECATED: Legacy investment analytics builder module.

Superseded by `personal_finance_etl.domain.wealth.analytics`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.investment_analytics is deprecated. "
    "Use personal_finance_etl.domain.wealth.analytics instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["InvestmentAnalyticsBuilder"]
