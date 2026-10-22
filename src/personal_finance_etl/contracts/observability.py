"""Canonical typed observability and telemetry contracts.

Owns
----
- EventCode: Standard enumeration of machine-readable operational event classifications.
- DiagnosticSeverity: Categorical severity levels for forensic and diagnostic traces.
- PresentationKind: Presentation intent for CLI and Desktop UI narratives.
- EventOutcome: Standard transition states (STARTED, COMPLETED, FAILED, SKIPPED).
- ErrorDetails: Immutable structured exception telemetry container.
- ObservabilityContext: Bounded, scalar context envelope propagated across spans.
- ObservabilityEvent: Immutable canonical event emitted once and projected to sinks.

Does not own
-------------
- Sink fan-out or span orchestration (owned by application.observability).
- File system JSONL appending or queue listener threads (owned by infrastructure.observability).
- Terminal formatting or GUI widget manipulation (owned by presentation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast

from personal_finance_etl.contracts.application import EngineStage, EngineStatusMessage
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.logging import LogLevel

__all__ = [
    "DiagnosticSeverity",
    "ErrorDetails",
    "EventCode",
    "EventOutcome",
    "NullObservabilitySink",
    "ObservabilityContext",
    "ObservabilityEvent",
    "ObservabilitySink",
    "PresentationKind",
]


class EventCode(StrEnum):
    """Categorical machine-readable codes for all lifecycle, pipeline, and diagnostic events."""

    # Pipeline Lifecycle
    RUN_START = "RUN_START"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_ABORTED = "RUN_ABORTED"
    RUN_RECOVERY = "RUN_RECOVERY"

    # Discovery & Ingestion
    DISCOVERY_START = "DISCOVERY_START"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"
    EXTRACTION_START = "EXTRACTION_START"
    EXTRACTION_BATCH = "EXTRACTION_BATCH"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"

    # Market Data Synchronization
    MARKET_FETCH_START = "MARKET_FETCH_START"
    MARKET_TICKER_SUCCESS = "MARKET_TICKER_SUCCESS"
    MARKET_TICKER_CACHE_HIT = "MARKET_TICKER_CACHE_HIT"
    MARKET_TICKER_RETRY = "MARKET_TICKER_RETRY"
    MARKET_TICKER_FAILED = "MARKET_TICKER_FAILED"
    MARKET_SYNC_COMPLETED = "MARKET_SYNC_COMPLETED"

    # Lakehouse & Storage Layers
    BRONZE_UPSERT = "BRONZE_UPSERT"
    BRONZE_REPLACE = "BRONZE_REPLACE"
    SILVER_REPLACE = "SILVER_REPLACE"
    GOLD_REPLACE = "GOLD_REPLACE"
    META_SNAPSHOT = "META_SNAPSHOT"
    DATABASE_VACUUM = "DATABASE_VACUUM"
    DATABASE_COMMIT = "DATABASE_COMMIT"
    DATABASE_ROLLBACK = "DATABASE_ROLLBACK"

    # Transformations & Financial Analytics
    TRANSFORMATION_STAGE = "TRANSFORMATION_STAGE"
    TRANSFORMATION_DAG_COMPLETED = "TRANSFORMATION_DAG_COMPLETED"
    QUANT_ENGINE_START = "QUANT_ENGINE_START"
    QUANT_ISIN_PROCESSED = "QUANT_ISIN_PROCESSED"
    QUANT_POOL_COMPLETED = "QUANT_POOL_COMPLETED"
    QUANT_LOT_MAPPED = "QUANT_LOT_MAPPED"
    TAX_ENGINE_START = "TAX_ENGINE_START"
    TAX_ENGINE_COMPLETED = "TAX_ENGINE_COMPLETED"
    PRESENTATION_DAG_START = "PRESENTATION_DAG_START"
    PRESENTATION_DAG_COMPLETED = "PRESENTATION_DAG_COMPLETED"

    # System, Diagnostics & Heartbeats
    SYSTEM_CONFIG_FINGERPRINT = "SYSTEM_CONFIG_FINGERPRINT"
    SYSTEM_MEMORY_SAMPLE = "SYSTEM_MEMORY_SAMPLE"
    SYSTEM_TEARDOWN = "SYSTEM_TEARDOWN"
    GENERIC_DIAGNOSTIC = "GENERIC_DIAGNOSTIC"


class DiagnosticSeverity(StrEnum):
    """Categorical severity levels for forensic and diagnostic traces."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PresentationKind(StrEnum):
    """Presentation intent and categorization for CLI and Desktop UI narratives."""

    STEP = "STEP"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    SKIP = "SKIP"
    WARNING = "WARNING"
    FAILURE = "FAILURE"
    RECOVERY = "RECOVERY"
    INTERNAL = "INTERNAL"


class EventOutcome(StrEnum):
    """Standard state transition outcomes for pipeline spans and operations."""

    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ObservabilitySink(Protocol):
    """Protocol for cross-boundary observability sinks consuming canonical events."""

    def emit(self, event: ObservabilityEvent) -> None:
        """Process and route one canonical ObservabilityEvent.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical structured event to consume.
        """
        ...

    def flush(self) -> None:
        """Flush any buffered events to the underlying destination."""
        ...


class NullObservabilitySink:
    """No-op observability sink used when no external sinks are attached."""

    def emit(self, event: ObservabilityEvent) -> None:
        """Discard the observability event."""

    def flush(self) -> None:
        """No-op flush."""


@dataclass(frozen=True)
class ErrorDetails:
    """Immutable structured exception telemetry container.

    Attributes
    ----------
    exception_type : str
        Fully qualified or class name of the raised exception.
    exception_message : str
        String message or error description associated with the exception.
    failure_domain : FailureDomain
        Architectural failure domain classifying the operational fault.
    traceback_summary : str
        Normalized or formatted traceback string.
    retryable : bool, default=False
        Whether the failure is transient and eligible for automatic retry.
    """

    exception_type: str
    exception_message: str
    failure_domain: FailureDomain
    traceback_summary: str
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        """Convert error details into a JSON-serializable dictionary."""
        return {
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "failure_domain": str(self.failure_domain),
            "traceback_summary": self.traceback_summary,
            "retryable": self.retryable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ErrorDetails:
        """Construct ErrorDetails from a serialized dictionary."""
        domain_str = str(data.get("failure_domain", FailureDomain.TRANSFORMATION))
        try:
            domain = FailureDomain(domain_str)
        except ValueError:
            domain = FailureDomain.TRANSFORMATION

        return cls(
            exception_type=str(data.get("exception_type", "UnknownException")),
            exception_message=str(data.get("exception_message", "")),
            failure_domain=domain,
            traceback_summary=str(data.get("traceback_summary", "")),
            retryable=bool(data.get("retryable", False)),
        )


@dataclass(frozen=True)
class ObservabilityContext:
    """Bounded, scalar contextual envelope propagated across spans and threads.

    Guarantees zero anonymous nested dictionaries and strict scalar bounds.

    Attributes
    ----------
    run_id : str
        Unique execution run identifier.
    stage : EngineStage, default=EngineStage.INITIALIZING
        Current high-level workflow execution stage.
    component : str, default=""
        Subsystem or architectural layer name (e.g. 'pipeline', 'isin_service').
    operation : str, default=""
        Specific operation or method being executed (e.g. 'extract', 'reconcile').
    operation_id : str, default=""
        Unique correlation identifier for the active span.
    parent_operation_id : str | None, default=None
        Correlation identifier of the enclosing parent span, if any.
    entity_type : str | None, default=None
        Domain entity classification (e.g. 'isin', 'ticker', 'file', 'table').
    entity_id : str | None, default=None
        Unique identifier of the entity being processed.
    duration_ms : float | None, default=None
        Elapsed execution time in milliseconds for completed operations.
    rows : int | None, default=None
        Number of dataset records or rows processed.
    attempt : int | None, default=None
        Retry attempt sequence number.
    provider : str | None, default=None
        External service or upstream data provider name.
    cache_hit : bool | None, default=None
        Whether the operation was satisfied from local cache.
    worker_id : str | None, default=None
        Process name or thread identifier executing the work.
    """

    run_id: str = ""
    stage: EngineStage = EngineStage.INITIALIZING
    component: str = ""
    operation: str = ""
    operation_id: str = ""
    parent_operation_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    duration_ms: float | None = None
    rows: int | None = None
    attempt: int | None = None
    provider: str | None = None
    cache_hit: bool | None = None
    worker_id: str | None = None

    def with_updates(
        self,
        stage: EngineStage | None = None,
        component: str | None = None,
        operation: str | None = None,
        operation_id: str | None = None,
        parent_operation_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        duration_ms: float | None = None,
        rows: int | None = None,
        attempt: int | None = None,
        provider: str | None = None,
        cache_hit: bool | None = None,
        worker_id: str | None = None,
    ) -> ObservabilityContext:
        """Create a new context instance with selected scalar updates."""
        return ObservabilityContext(
            run_id=self.run_id,
            stage=stage if stage is not None else self.stage,
            component=component if component is not None else self.component,
            operation=operation if operation is not None else self.operation,
            operation_id=operation_id if operation_id is not None else self.operation_id,
            parent_operation_id=(
                parent_operation_id if parent_operation_id is not None else self.parent_operation_id
            ),
            entity_type=entity_type if entity_type is not None else self.entity_type,
            entity_id=entity_id if entity_id is not None else self.entity_id,
            duration_ms=duration_ms if duration_ms is not None else self.duration_ms,
            rows=rows if rows is not None else self.rows,
            attempt=attempt if attempt is not None else self.attempt,
            provider=provider if provider is not None else self.provider,
            cache_hit=cache_hit if cache_hit is not None else self.cache_hit,
            worker_id=worker_id if worker_id is not None else self.worker_id,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert context attributes into a JSON-serializable dictionary."""
        out: dict[str, object] = {
            "run_id": self.run_id,
            "stage": str(self.stage),
            "component": self.component,
            "operation": self.operation,
            "operation_id": self.operation_id,
        }
        if self.parent_operation_id is not None:
            out["parent_operation_id"] = self.parent_operation_id
        if self.entity_type is not None:
            out["entity_type"] = self.entity_type
        if self.entity_id is not None:
            out["entity_id"] = self.entity_id
        if self.duration_ms is not None:
            out["duration_ms"] = self.duration_ms
        if self.rows is not None:
            out["rows"] = self.rows
        if self.attempt is not None:
            out["attempt"] = self.attempt
        if self.provider is not None:
            out["provider"] = self.provider
        if self.cache_hit is not None:
            out["cache_hit"] = self.cache_hit
        if self.worker_id is not None:
            out["worker_id"] = self.worker_id
        return out

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ObservabilityContext:
        """Construct ObservabilityContext from a serialized dictionary."""
        stage_str = str(data.get("stage", EngineStage.INITIALIZING))
        try:
            stage = EngineStage(stage_str)
        except ValueError:
            stage = EngineStage.INITIALIZING

        duration_val = data.get("duration_ms")
        duration_ms = float(duration_val) if isinstance(duration_val, (int, float)) else None

        rows_val = data.get("rows")
        rows = int(rows_val) if isinstance(rows_val, (int, float)) else None

        attempt_val = data.get("attempt")
        attempt = int(attempt_val) if isinstance(attempt_val, (int, float)) else None

        cache_val = data.get("cache_hit")
        cache_hit = bool(cache_val) if cache_val is not None else None

        return cls(
            run_id=str(data.get("run_id", "-")),
            stage=stage,
            component=str(data.get("component", "")),
            operation=str(data.get("operation", "")),
            operation_id=str(data.get("operation_id", "")),
            parent_operation_id=(
                str(data["parent_operation_id"]) if data.get("parent_operation_id") else None
            ),
            entity_type=str(data["entity_type"]) if data.get("entity_type") else None,
            entity_id=str(data["entity_id"]) if data.get("entity_id") else None,
            duration_ms=duration_ms,
            rows=rows,
            attempt=attempt,
            provider=str(data["provider"]) if data.get("provider") else None,
            cache_hit=cache_hit,
            worker_id=str(data["worker_id"]) if data.get("worker_id") else None,
        )


@dataclass(frozen=True)
class ObservabilityEvent:
    """Immutable canonical observability event emitted across the architecture.

    One event is produced and fan-out projected to User UI, Forensic JSONL, and Control Plane.

    Attributes
    ----------
    timestamp : datetime
        UTC timestamp when the event occurred.
    event_code : EventCode
        Categorical machine-readable event code.
    severity : DiagnosticSeverity
        Diagnostic severity level for forensic analysis.
    presentation_kind : PresentationKind
        Presentation intent for human-facing renderers.
    outcome : EventOutcome
        State transition outcome of the operation.
    context : ObservabilityContext
        Bounded scalar context associated with this event.
    message : str
        Human-readable narrative description.
    error : ErrorDetails | None, default=None
        Structured exception telemetry if the event represents an error.
    progress : float | None, default=None
        Normalized fractional progress marker between 0.0 and 1.0.
    """

    timestamp: datetime
    event_code: EventCode
    severity: DiagnosticSeverity
    presentation_kind: PresentationKind
    outcome: EventOutcome
    context: ObservabilityContext
    message: str
    error: ErrorDetails | None = None
    progress: float | None = None

    @classmethod
    def create(
        cls,
        event_code: EventCode,
        message: str,
        context: ObservabilityContext,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        presentation_kind: PresentationKind = PresentationKind.STEP,
        outcome: EventOutcome = EventOutcome.COMPLETED,
        error: ErrorDetails | None = None,
        progress: float | None = None,
        timestamp: datetime | None = None,
    ) -> ObservabilityEvent:
        """Construct a canonical ObservabilityEvent with UTC timestamp."""
        ts = timestamp if timestamp is not None else datetime.now(UTC)
        return cls(
            timestamp=ts,
            event_code=event_code,
            severity=severity,
            presentation_kind=presentation_kind,
            outcome=outcome,
            context=context,
            message=message,
            error=error,
            progress=progress,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize event into a JSON-serializable dictionary for JSONL sink."""
        out: dict[str, object] = {
            "timestamp": self.timestamp.isoformat(),
            "event_code": str(self.event_code),
            "severity": str(self.severity),
            "presentation_kind": str(self.presentation_kind),
            "outcome": str(self.outcome),
            "context": self.context.to_dict(),
            "message": self.message,
        }
        if self.error is not None:
            out["error"] = self.error.to_dict()
        if self.progress is not None:
            out["progress"] = self.progress
        return out

    def to_json(self) -> str:
        """Render event as a single-line JSON string without line breaks."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_status_message(self) -> EngineStatusMessage:
        """Project ObservabilityEvent into legacy EngineStatusMessage for backward compatibility.

        This compatibility adapter supports intermediate migration phases and will be
        demolished upon full retirement of legacy presentation interfaces.
        """
        if self.presentation_kind == PresentationKind.STEP:
            level = LogLevel.STEP
        elif self.presentation_kind == PresentationKind.SUCCESS:
            level = LogLevel.SUCCESS
        elif self.presentation_kind == PresentationKind.WARNING:
            level = LogLevel.WARNING
        elif self.presentation_kind == PresentationKind.FAILURE:
            level = LogLevel.ERROR
        else:
            level_map: dict[DiagnosticSeverity, LogLevel] = {
                DiagnosticSeverity.TRACE: LogLevel.INFO,
                DiagnosticSeverity.DEBUG: LogLevel.INFO,
                DiagnosticSeverity.INFO: LogLevel.INFO,
                DiagnosticSeverity.WARNING: LogLevel.WARNING,
                DiagnosticSeverity.ERROR: LogLevel.ERROR,
                DiagnosticSeverity.CRITICAL: LogLevel.ERROR,
            }
            level = level_map.get(self.severity, LogLevel.INFO)

        failure_domain = self.error.failure_domain if self.error is not None else None
        local_ts = self.timestamp.astimezone() if self.timestamp.tzinfo else self.timestamp

        return EngineStatusMessage(
            msg=self.message,
            level=level,
            progress=self.progress,
            data=None,
            stage=self.context.stage,
            failure_domain=failure_domain,
            timestamp=local_ts,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ObservabilityEvent:
        """Construct an ObservabilityEvent from a serialized dictionary."""
        ts_str = str(data.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            ts = datetime.now(UTC)

        raw_ctx = data.get("context")
        ctx: ObservabilityContext
        if isinstance(raw_ctx, dict):
            ctx = ObservabilityContext.from_dict(cast("dict[str, object]", raw_ctx))
        else:
            ctx = ObservabilityContext(run_id="-")

        raw_err = data.get("error")
        err: ErrorDetails | None = None
        if isinstance(raw_err, dict):
            err = ErrorDetails.from_dict(cast("dict[str, object]", raw_err))

        prog_val = data.get("progress")
        prog = float(prog_val) if isinstance(prog_val, (int, float)) else None

        return cls(
            timestamp=ts,
            event_code=EventCode(str(data.get("event_code", EventCode.GENERIC_DIAGNOSTIC))),
            severity=DiagnosticSeverity(str(data.get("severity", DiagnosticSeverity.INFO))),
            presentation_kind=PresentationKind(
                str(data.get("presentation_kind", PresentationKind.STEP))
            ),
            outcome=EventOutcome(str(data.get("outcome", EventOutcome.COMPLETED))),
            context=ctx,
            message=str(data.get("message", "")),
            error=err,
            progress=prog,
        )
