"""Reconciliation data models and structured discrepancy records.

Owns
----
- ReconciliationEvent structured model.
- ReconciliationAdjustmentType categorical operation definitions.

Does not own
-------------
- Reconciliation algorithms and state modification (owned by domain.investments.reconciliation.engine).
- External broker statement parsing (owned by infrastructure.providers).
"""

from personal_finance_etl.domain.investments.contracts import (
    ReconciliationAdjustmentType as ReconciliationAdjustmentType,
)
from personal_finance_etl.domain.investments.contracts import (
    ReconciliationEvent as ReconciliationEvent,
)
from personal_finance_etl.domain.investments.contracts import (
    ReconciliationEventRecord as ReconciliationEventRecord,
)

__all__ = [
    "ReconciliationAdjustmentType",
    "ReconciliationEvent",
    "ReconciliationEventRecord",
]
