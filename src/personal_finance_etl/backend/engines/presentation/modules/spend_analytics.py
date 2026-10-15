"""DEPRECATED: Legacy spend analytics builder module.

Superseded by `personal_finance_etl.domain.household.budget`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.budget import SpendAnalyticsBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.spend_analytics is deprecated. "
    "Use personal_finance_etl.domain.household.budget instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SpendAnalyticsBuilder"]
