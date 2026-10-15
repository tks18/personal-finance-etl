"""DEPRECATED: Legacy tax engines module.

Superseded by `personal_finance_etl.application.tax`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.tax.tax_service import TaxEngine

warnings.warn(
    "personal_finance_etl.backend.engines.tax is deprecated. "
    "Use personal_finance_etl.application.tax instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["TaxEngine"]
