"""DEPRECATED: Legacy tax core module.

Superseded by `personal_finance_etl.domain.tax`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.tax.events import BaseEventsBuilder
from personal_finance_etl.domain.tax.reconciliation import TaxGoldFormatter

warnings.warn(
    "personal_finance_etl.backend.engines.tax.core is deprecated. "
    "Use personal_finance_etl.domain.tax instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["BaseEventsBuilder", "TaxGoldFormatter"]
