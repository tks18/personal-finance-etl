"""Architectural cross-boundary contracts.

Owns
----
- Typed messages and results crossing architectural and process boundaries.
- Pipeline lifecycle state enums (CommitState, FailureDomain).
- Tabular data transport contract (EngineDataTransport).
- Extraction batch and entity outcomes (ExtractionBatchResult, ExtractorEntityResult).
- Snapshot and restore outcome contracts (SnapshotResult, RestoreResult).
- Categorical log levels (LogLevel).
- Canonical typed observability and telemetry contracts (ObservabilityEvent, EventCode).

Does not own
-------------
- Domain-internal calculation records (owned by domain.*).
- Database table DDL or SQL schemas (owned by infrastructure.warehouse.schema).
- UI widget state (owned by presentation).
"""

from personal_finance_etl.contracts.application import (
    EngineDataTransport,
    EngineExecutionResult,
    EngineStage,
)
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractionCompletenessError,
    ExtractionProviderRequest,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    SyncSummaryRecord,
    classify_failure_domain,
)
from personal_finance_etl.contracts.logging import ILogger, LogLevel, StatusQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    ErrorDetailsDict,
    EventCode,
    EventOutcome,
    NullObservabilitySink,
    ObservabilityContext,
    ObservabilityContextDict,
    ObservabilityEvent,
    ObservabilityEventDict,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.contracts.recovery import (
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)

__all__ = [
    "CommitState",
    "DiagnosticSeverity",
    "EngineDataTransport",
    "EngineExecutionResult",
    "EngineStage",
    "ErrorDetails",
    "ErrorDetailsDict",
    "EventCode",
    "EventOutcome",
    "ExtractionBatchResult",
    "ExtractionCompletenessError",
    "ExtractionProviderRequest",
    "ExtractorEntityResult",
    "ExtractorEntityStatus",
    "FailureDomain",
    "ILogger",
    "LogLevel",
    "NullObservabilitySink",
    "ObservabilityContext",
    "ObservabilityContextDict",
    "ObservabilityEvent",
    "ObservabilityEventDict",
    "ObservabilitySink",
    "PresentationKind",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
    "StatusQueue",
    "SyncSummaryRecord",
    "classify_failure_domain",
]
