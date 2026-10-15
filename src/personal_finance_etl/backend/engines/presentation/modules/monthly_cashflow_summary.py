"""DEPRECATED: Legacy monthly cashflow summary builder module.

Superseded by `personal_finance_etl.domain.household.cashflow`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.cashflow import MonthlyCashflowSummaryBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.monthly_cashflow_summary is deprecated. "
    "Use personal_finance_etl.domain.household.cashflow instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MonthlyCashflowSummaryBuilder"]
