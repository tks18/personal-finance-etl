"""DEPRECATED: Legacy tax gold formatter module.

Superseded by `personal_finance_etl.domain.tax.reconciliation`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.tax.reconciliation import TaxGoldFormatter

warnings.warn(
    "personal_finance_etl.backend.engines.tax.core.gold_formatter is deprecated. "
    "Use personal_finance_etl.domain.tax.reconciliation instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["TaxGoldFormatter"]
