"""Architectural cross-boundary contracts.

Owns
----
- Typed messages and results crossing architectural and process boundaries.
- Pipeline lifecycle state enums (CommitState, FailureDomain).
- Tabular data transport contract (EngineDataTransport).
- Canonical dataset identifiers (DatasetId).
- Source identity and provider contracts (SourceId, ProviderType, validate_source_id).
- Extraction batch and entity outcomes (ExtractionBatchResult, ExtractorEntityResult).
- Snapshot and restore outcome contracts (SnapshotResult, RestoreResult).
- Canonical event transport queue contracts.
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
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import EventQueue, NullEventQueue
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
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    ErrorDetailsDict,
    EventCode,
    EventEmitter,
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
from personal_finance_etl.contracts.sources import (
    ProviderType,
    SourceId,
    validate_source_id,
)

__all__ = [
    "CommitState",
    "DatasetId",
    "DiagnosticSeverity",
    "EngineDataTransport",
    "EngineExecutionResult",
    "EngineStage",
    "ErrorDetails",
    "ErrorDetailsDict",
    "EventCode",
    "EventEmitter",
    "EventOutcome",
    "ExtractionBatchResult",
    "ExtractionCompletenessError",
    "ExtractionProviderRequest",
    "ExtractorEntityResult",
    "ExtractorEntityStatus",
    "FailureDomain",
    "EventQueue",
    "NullEventQueue",
    "NullObservabilitySink",
    "ObservabilityContext",
    "ObservabilityContextDict",
    "ObservabilityEvent",
    "ObservabilityEventDict",
    "ObservabilitySink",
    "PresentationKind",
    "ProviderType",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
    "SourceId",
    "SyncSummaryRecord",
    "classify_failure_domain",
    "validate_source_id",
]
