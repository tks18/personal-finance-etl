"""Tax domain logic, normalization, classification, and presentation marts.

Owns
----
- Normalizing ledger and Quant realized events into canonical TaxEvents.
- Income head and sub-head classification.
- Indicative tax liability estimates.
- Tax event reconciliation and audit trails.

Does not own
-------------
- Realized gain computation (owned by domain.investments).
- Tax rules configuration models (owned by config.financial_rules).
- Gold Tax table persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.domain.tax.classification import TaxClassifier
from personal_finance_etl.domain.tax.estimates import TaxEstimator
from personal_finance_etl.domain.tax.events import (
    TAX_EVENT_SCHEMA,
    BaseEventsBuilder,
    TaxEventDict,
    TaxEventNormalizer,
    _batch_compute_tax_event_ids,
    normalize_quant_realized_events,
)
from personal_finance_etl.domain.tax.reconciliation import (
    TaxGoldFormatter,
    TaxReconciler,
)

__all__ = [
    "TAX_EVENT_SCHEMA",
    "BaseEventsBuilder",
    "TaxClassifier",
    "TaxEstimator",
    "TaxEventDict",
    "TaxEventNormalizer",
    "TaxGoldFormatter",
    "TaxReconciler",
    "_batch_compute_tax_event_ids",
    "normalize_quant_realized_events",
]
