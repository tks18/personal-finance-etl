"""Investment analytics records and containers (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All investment domain records have migrated to `personal_finance_etl.domain.investments.contracts`.
"""

from personal_finance_etl.domain.common.calculation import XirrResult as XirrResult
from personal_finance_etl.domain.investments.contracts import (
    AcquisitionLot as AcquisitionLot,
)
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord as CashflowRecord,
)
from personal_finance_etl.domain.investments.contracts import (
    ISINProcessResult as ISINProcessResult,
)
from personal_finance_etl.domain.investments.contracts import (
    ISINTags as ISINTags,
)
from personal_finance_etl.domain.investments.contracts import (
    PipelineExecutionResult as PipelineExecutionResult,
)
from personal_finance_etl.domain.investments.contracts import (
    PortfolioResult as PortfolioResult,
)
from personal_finance_etl.domain.investments.contracts import (
    Purchase as Purchase,
)
from personal_finance_etl.domain.investments.contracts import (
    RealizedEvent as RealizedEvent,
)
from personal_finance_etl.domain.investments.contracts import (
    RealizedEventRecord as RealizedEventRecord,
)
from personal_finance_etl.domain.investments.contracts import (
    ReconciliationEvent as ReconciliationEvent,
)
from personal_finance_etl.domain.investments.contracts import (
    ReconciliationEventRecord as ReconciliationEventRecord,
)
from personal_finance_etl.domain.investments.contracts import (
    Sale as Sale,
)
from personal_finance_etl.domain.investments.contracts import (
    SnapshotRecord as SnapshotRecord,
)
from personal_finance_etl.domain.investments.contracts import (
    TaxLot as TaxLot,
)
from personal_finance_etl.domain.investments.contracts import (
    TerminalValueRecord as TerminalValueRecord,
)

__all__ = [
    "AcquisitionLot",
    "CashflowRecord",
    "ISINProcessResult",
    "ISINTags",
    "PipelineExecutionResult",
    "PortfolioResult",
    "Purchase",
    "RealizedEvent",
    "RealizedEventRecord",
    "ReconciliationEvent",
    "ReconciliationEventRecord",
    "Sale",
    "SnapshotRecord",
    "TaxLot",
    "TerminalValueRecord",
    "XirrResult",
]
