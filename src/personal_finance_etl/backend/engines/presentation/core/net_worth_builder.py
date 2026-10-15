"""DEPRECATED: Legacy net worth builder module.

Superseded by `personal_finance_etl.domain.wealth.net_worth`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.wealth.net_worth import NetWorthBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.core.net_worth_builder is deprecated. "
    "Use personal_finance_etl.domain.wealth.net_worth instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["NetWorthBuilder"]
