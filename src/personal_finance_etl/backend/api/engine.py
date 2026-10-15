"""Legacy PersonalFinanceEngine API facade module.

.. deprecated::
    personal_finance_etl.backend.api.engine is deprecated and will be removed in Phase 11.
    Use personal_finance_etl.application.facade instead.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.facade import PersonalFinanceEngine

warnings.warn(
    "personal_finance_etl.backend.api.engine is deprecated. "
    "Use personal_finance_etl.application.facade instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["PersonalFinanceEngine"]
