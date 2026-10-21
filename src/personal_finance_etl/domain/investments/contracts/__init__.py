"""Investment domain contracts and structured records facade.

Owns
----
- Re-exports of all Enums, TypedDicts, dataclasses, and Pydantic models for investment domain.

Does not own
-------------
- FIFO execution algorithms (owned by domain.investments.lots.fifo).
- External database tables or queries (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.domain.investments.contracts.models import (
    AcquisitionLot,
    CashflowRecord,
    ISINProcessResult,
    ISINTags,
    ISINTaskPayload,
    PipelineExecutionResult,
    PortfolioResult,
    Purchase,
    RealizedEvent,
    RealizedEventRecord,
    ReconciliationEvent,
    ReconciliationEventRecord,
    Sale,
    SnapshotRecord,
    TaxLot,
    TerminalValueRecord,
)
from personal_finance_etl.domain.investments.contracts.types import (
    CashflowDict,
    InstrumentMetricsRecord,
    IsinMasterRecord,
    LotAction,
    MarketSpineRecord,
    RealizedEventDict,
    ReconciliationAdjustmentType,
    ReconciliationEventDict,
    TerminalValueDict,
    TradeRecord,
)

__all__ = [
    "AcquisitionLot",
    "CashflowDict",
    "CashflowRecord",
    "ISINProcessResult",
    "ISINTags",
    "ISINTaskPayload",
    "InstrumentMetricsRecord",
    "IsinMasterRecord",
    "LotAction",
    "MarketSpineRecord",
    "PipelineExecutionResult",
    "PortfolioResult",
    "Purchase",
    "RealizedEvent",
    "RealizedEventDict",
    "RealizedEventRecord",
    "ReconciliationAdjustmentType",
    "ReconciliationEvent",
    "ReconciliationEventDict",
    "ReconciliationEventRecord",
    "Sale",
    "SnapshotRecord",
    "TaxLot",
    "TerminalValueDict",
    "TerminalValueRecord",
    "TradeRecord",
]
