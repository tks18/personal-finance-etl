"""Investment analytics records and containers (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All investment domain records have migrated to `personal_finance_etl.domain.investments.contracts`.
"""

from personal_finance_etl.domain.common.calculation import XirrResult as XirrResult
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    ISINProcessResult,
    ISINTags,
    RealizedEventRecord,
    SnapshotRecord,
    TerminalValueRecord,
)

__all__ = [
    "CashflowRecord",
    "ISINProcessResult",
    "ISINTags",
    "RealizedEventRecord",
    "SnapshotRecord",
    "TerminalValueRecord",
    "XirrResult",
]
