"""DEPRECATED: Legacy inflation builder module.

Superseded by `personal_finance_etl.domain.fire.inflation`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.fire.inflation import InflationBuilder

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.core.inflation_builder is deprecated. "
    "Use personal_finance_etl.domain.fire.inflation instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["InflationBuilder"]
