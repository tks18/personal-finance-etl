"""DEPRECATED: Legacy tax engine module.

Superseded by `personal_finance_etl.application.tax.tax_service`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.tax.tax_service import TaxEngine

warnings.warn(
    "personal_finance_etl.backend.engines.tax.tax_engine is deprecated. "
    "Use personal_finance_etl.application.tax.tax_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["TaxEngine"]
