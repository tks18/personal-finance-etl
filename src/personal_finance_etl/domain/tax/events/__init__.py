"""Tax events domain subpackage.

Owns
----
- BaseEventsBuilder, TaxEventNormalizer: Normalizes ledger income, tax credits, and Quant FIFO events.
- normalize_quant_realized_events: Quant FIFO realized events normalization.
- TAX_EVENT_SCHEMA, TaxEventDict: Strict schema and typing for tax events.
- _batch_compute_tax_event_ids: Deterministic identity hashing.

Does not own
-------------
- Income head classification (owned by domain.tax.classification).
- Tax rate resolution (owned by domain.tax.estimates).
- Presentation aggregations (owned by domain.tax.reconciliation).
"""

from __future__ import annotations

from personal_finance_etl.domain.tax.events.builder import (
    BaseEventsBuilder,
    TaxEventNormalizer,
)
from personal_finance_etl.domain.tax.events.hashing import _batch_compute_tax_event_ids
from personal_finance_etl.domain.tax.events.quant import normalize_quant_realized_events
from personal_finance_etl.domain.tax.events.schema import TAX_EVENT_SCHEMA, TaxEventDict

__all__ = [
    "TAX_EVENT_SCHEMA",
    "BaseEventsBuilder",
    "TaxEventDict",
    "TaxEventNormalizer",
    "_batch_compute_tax_event_ids",
    "normalize_quant_realized_events",
]
