"""DEPRECATED: Legacy cashflow statement builder module.

Superseded by `personal_finance_etl.domain.household.cashflow`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.household.cashflow import CashflowStatementBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.modules.cashflow_statement_builder is deprecated. "
    "Use personal_finance_etl.domain.household.cashflow instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["CashflowStatementBuilder"]
