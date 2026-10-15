"""DEPRECATED: Legacy wealth presentation engine module.

Superseded by `personal_finance_etl.application.wealth.wealth_service`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.wealth.wealth_service import (
    WealthPresentationEngine,
    WealthService,
)

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.wealth_engine is deprecated. "
    "Use personal_finance_etl.application.wealth.wealth_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["WealthPresentationEngine", "WealthService"]
