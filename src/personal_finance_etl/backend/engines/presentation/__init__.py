"""DEPRECATED: Legacy presentation package.

Superseded by `personal_finance_etl.application.wealth` and `personal_finance_etl.domain.household`,
`personal_finance_etl.domain.wealth`, and `personal_finance_etl.domain.fire`.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.wealth.wealth_service import (
    WealthPresentationEngine,
    WealthService,
)

warnings.warn(
    "personal_finance_etl.backend.engines.presentation is deprecated. "
    "Use personal_finance_etl.application.wealth instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["WealthPresentationEngine", "WealthService"]
