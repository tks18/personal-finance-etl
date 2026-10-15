"""DEPRECATED: Legacy tax base events module.

Superseded by `personal_finance_etl.domain.tax.events`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.tax.events import (
    TAX_EVENT_SCHEMA,
    BaseEventsBuilder,
    _batch_compute_tax_event_ids,
)

warnings.warn(
    "personal_finance_etl.backend.engines.tax.core.base_events is deprecated. "
    "Use personal_finance_etl.domain.tax.events instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "TAX_EVENT_SCHEMA",
    "BaseEventsBuilder",
    "_batch_compute_tax_event_ids",
]
