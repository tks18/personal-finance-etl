"""Architectural cross-boundary contracts.

Owns
----
- Typed messages and results crossing architectural and process boundaries.
- Pipeline lifecycle state enums (CommitState, FailureDomain).
- Cross-process worker status messages (EngineStatusMessage).
- Extraction batch and entity outcomes (ExtractionBatchResult, ExtractorEntityResult).
- Snapshot and restore outcome contracts (SnapshotResult, RestoreResult).
- Categorical log levels (LogLevel).

Does not own
-------------
- Domain-internal calculation records (owned by domain.*).
- Database table DDL or SQL schemas (owned by infrastructure.warehouse.schema).
- UI widget state (owned by presentation).
"""

from personal_finance_etl.contracts.application import (
    EngineExecutionResult,
    EngineStage,
    EngineStatusMessage,
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
    classify_failure_domain,
)
from personal_finance_etl.contracts.logging import ILogger, LogLevel, StatusQueue
from personal_finance_etl.contracts.recovery import (
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)

__all__ = [
    "CommitState",
    "EngineExecutionResult",
    "EngineStage",
    "EngineStatusMessage",
    "ExtractionBatchResult",
    "ExtractionCompletenessError",
    "ExtractionProviderRequest",
    "ExtractorEntityResult",
    "ExtractorEntityStatus",
    "FailureDomain",
    "ILogger",
    "LogLevel",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
    "StatusQueue",
    "classify_failure_domain",
]
