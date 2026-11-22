"""Canonical typed observability and telemetry contracts.

Owns
----
- EventCode: Standard enumeration of machine-readable operational event classifications.
- DiagnosticSeverity: Categorical severity levels for forensic and diagnostic traces.
- PresentationKind: Presentation intent for CLI and Desktop UI narratives.
- EventOutcome: Standard transition states (STARTED, COMPLETED, FAILED, SKIPPED).
- ErrorDetails: Immutable structured exception telemetry container.
- ErrorDetailsDict: Strongly-typed serialized dictionary contract for exception telemetry.
- ObservabilityContext: Bounded, scalar context envelope propagated across spans.
- ObservabilityContextDict: Strongly-typed serialized dictionary contract for context envelopes.
- ObservabilityEvent: Immutable canonical event emitted once and projected to sinks.
- ObservabilityEventDict: Strongly-typed serialized dictionary contract for canonical events.

Does not own
-------------
- Sink fan-out or span orchestration (owned by infrastructure.observability).
- File system JSONL appending or queue listener threads (owned by infrastructure.observability).
- Terminal formatting or GUI widget manipulation (owned by presentation).
"""

from __future__ import annotations

import json
import traceback
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import NotRequired, Protocol, TypedDict, cast

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import CommitState, FailureDomain

__all__ = [
    "DiagnosticSeverity",
    "ErrorDetails",
    "ErrorDetailsDict",
    "EventCode",
    "EventEmitter",
    "EventOutcome",
    "NullObservabilitySink",
    "ObservabilityContext",
    "ObservabilityContextDict",
    "ObservabilityEvent",
    "ObservabilityEventDict",
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
    RECOVERY_SNAPSHOT = "RECOVERY_SNAPSHOT"
    RECOVERY_RESTORE = "RECOVERY_RESTORE"

    # Discovery & Ingestion / Providers
    DISCOVERY_START = "DISCOVERY_START"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"
    EXTRACTION_START = "EXTRACTION_START"
    EXTRACTION_BATCH = "EXTRACTION_BATCH"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    SCHEMA_VALIDATION = "SCHEMA_VALIDATION"
    PROVIDER_DISCOVERY = "PROVIDER_DISCOVERY"
    PROVIDER_BATCH_INGEST = "PROVIDER_BATCH_INGEST"
    PROVIDER_FILE_ERROR = "PROVIDER_FILE_ERROR"

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
    DATABASE_CHECKPOINT = "DATABASE_CHECKPOINT"
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
    WEALTH_ENGINE_START = "WEALTH_ENGINE_START"
    WEALTH_ENGINE_COMPLETED = "WEALTH_ENGINE_COMPLETED"
    FIRE_ENGINE_START = "FIRE_ENGINE_START"
    FIRE_ENGINE_COMPLETED = "FIRE_ENGINE_COMPLETED"
    PRESENTATION_DAG_START = "PRESENTATION_DAG_START"
    PRESENTATION_DAG_COMPLETED = "PRESENTATION_DAG_COMPLETED"

    # System, Diagnostics & Raw Stream Telemetry
    SYSTEM_CONFIG_FINGERPRINT = "SYSTEM_CONFIG_FINGERPRINT"
    SYSTEM_MEMORY_SAMPLE = "SYSTEM_MEMORY_SAMPLE"
    SYSTEM_TEARDOWN = "SYSTEM_TEARDOWN"
    RAW_STDOUT = "RAW_STDOUT"
    RAW_STDERR = "RAW_STDERR"
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


class EventEmitter(Protocol):
    """Protocol for cross-boundary event emission capability.

    Owns
    ----
    - Capability contract for routing or dispatching canonical ObservabilityEvents.
    - Enables decoupled event producers without forcing a dependency on concrete emitter classes.
    """

    def emit(self, event: ObservabilityEvent) -> object:
        """Process, dispatch, or sequence one canonical ObservabilityEvent.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical structured event to dispatch.

        Returns
        -------
        object
            Implementation-defined return value (e.g. sequenced event or None).
        """
        ...


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


class ErrorDetailsDict(TypedDict):
    """JSON-serializable representation of ErrorDetails."""

    exception_type: str
    exception_message: str
    failure_domain: str
    traceback_summary: str
    retryable: bool
    context_variables: dict[str, str | int | float | bool]
    remediation_hint: str
    failing_stage: str
    failing_entity: str


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
    context_variables : dict[str, str | int | float | bool]
        Diagnostic key-value state context capturing values active at failure time.
    remediation_hint : str, default=""
        Actionable operational guidance or instructions to remediate the failure.
    failing_stage : str, default=""
        Pipeline or engine stage where the fault occurred.
    failing_entity : str, default=""
        Identifier of the specific domain entity being processed when failure occurred.
    """

    exception_type: str
    exception_message: str
    failure_domain: FailureDomain
    traceback_summary: str
    retryable: bool = False
    context_variables: dict[str, str | int | float | bool] = field(
        default_factory=lambda: cast(dict[str, str | int | float | bool], {})
    )
    remediation_hint: str = ""
    failing_stage: str = ""
    failing_entity: str = ""

    def to_dict(self) -> ErrorDetailsDict:
        """Convert error details into a JSON-serializable dictionary."""
        return {
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "failure_domain": str(self.failure_domain),
            "traceback_summary": self.traceback_summary,
            "retryable": self.retryable,
            "context_variables": dict(self.context_variables),
            "remediation_hint": self.remediation_hint,
            "failing_stage": self.failing_stage,
            "failing_entity": self.failing_entity,
        }

    @classmethod
    def create(
        cls,
        exc: BaseException,
        failure_domain: FailureDomain,
        stage: str = "",
        entity: str = "",
        hint: str = "",
        retryable: bool = False,
        context_variables: Mapping[str, str | int | float | bool] | None = None,
        **extra_vars: str | int | float | bool,
    ) -> ErrorDetails:
        """Construct ErrorDetails from an active exception and contextual attributes.

        Parameters
        ----------
        exc : BaseException
            The raised exception instance.
        failure_domain : FailureDomain
            Architectural failure classification domain.
        stage : str, default=""
            Pipeline stage where exception was raised.
        entity : str, default=""
            Domain entity or table associated with the fault.
        hint : str, default=""
            Actionable troubleshooting guidance.
        retryable : bool, default=False
            Whether the failure is eligible for automatic retry.
        context_variables : Mapping[str, str | int | float | bool] | None, default=None
            Diagnostic key-value state context capturing values active at failure time.
        **extra_vars : str | int | float | bool
            Additional key-value diagnostic state variables.

        Returns
        -------
        ErrorDetails
            Structured immutable error telemetry container.
        """
        merged_vars: dict[str, str | int | float | bool] = {}
        if context_variables:
            merged_vars.update(context_variables)
        if extra_vars:
            merged_vars.update(extra_vars)

        return cls(
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            failure_domain=failure_domain,
            traceback_summary=traceback.format_exc(),
            retryable=retryable,
            context_variables=merged_vars,
            remediation_hint=hint,
            failing_stage=stage,
            failing_entity=entity,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ErrorDetails:
        """Construct ErrorDetails from a serialized dictionary.

        Parameters
        ----------
        data : Mapping[str, object]
            Serialized key-value mapping representing error details.

        Returns
        -------
        ErrorDetails
            Reconstructed immutable error telemetry instance.
        """
        domain_str = str(data.get("failure_domain", FailureDomain.TRANSFORMATION))
        try:
            domain = FailureDomain(domain_str)
        except ValueError:
            domain = FailureDomain.TRANSFORMATION

        raw_ctx = data.get("context_variables")
        ctx_vars: dict[str, str | int | float | bool] = {}
        if isinstance(raw_ctx, Mapping):
            raw_map = cast(Mapping[object, object], raw_ctx)
            for k, v in raw_map.items():
                k_str = str(k)
                if isinstance(v, (str, int, float, bool)):
                    ctx_vars[k_str] = v
                else:
                    ctx_vars[k_str] = str(v)

        return cls(
            exception_type=str(data.get("exception_type", "UnknownException")),
            exception_message=str(data.get("exception_message", "")),
            failure_domain=domain,
            traceback_summary=str(data.get("traceback_summary", "")),
            retryable=bool(data.get("retryable", False)),
            context_variables=ctx_vars,
            remediation_hint=str(data.get("remediation_hint", "")),
            failing_stage=str(data.get("failing_stage", "")),
            failing_entity=str(data.get("failing_entity", "")),
        )


class ObservabilityContextDict(TypedDict):
    """JSON-serializable representation of ObservabilityContext."""

    run_id: str
    stage: str
    component: str
    operation: str
    operation_id: str
    parent_operation_id: NotRequired[str | None]
    entity_type: NotRequired[str | None]
    entity_id: NotRequired[str | None]
    duration_ms: NotRequired[float | None]
    rows: NotRequired[int | None]
    attempt: NotRequired[int | None]
    provider: NotRequired[str | None]
    cache_hit: NotRequired[bool | None]
    worker_id: NotRequired[str | None]
    batch_id: NotRequired[str | None]
    commit_state: NotRequired[str | None]
    settings_fingerprint: NotRequired[str | None]
    rules_fingerprint: NotRequired[str | None]


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
    batch_id : str | None, default=None
        Unique batch identifier for bulk processing and ISIN work distribution.
    commit_state : CommitState | None, default=None
        Coordinated transaction commit state at the time of emission.
    settings_fingerprint : str | None, default=None
        Cryptographic SHA-256 fingerprint digest of active Settings configuration.
    rules_fingerprint : str | None, default=None
        Cryptographic SHA-256 fingerprint digest of active FinancialRules policies.
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
    batch_id: str | None = None
    commit_state: CommitState | None = None
    settings_fingerprint: str | None = None
    rules_fingerprint: str | None = None

    def with_updates(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
        batch_id: str | None = None,
        commit_state: CommitState | None = None,
        settings_fingerprint: str | None = None,
        rules_fingerprint: str | None = None,
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
            batch_id=batch_id if batch_id is not None else self.batch_id,
            commit_state=commit_state if commit_state is not None else self.commit_state,
            settings_fingerprint=(
                settings_fingerprint
                if settings_fingerprint is not None
                else self.settings_fingerprint
            ),
            rules_fingerprint=(
                rules_fingerprint if rules_fingerprint is not None else self.rules_fingerprint
            ),
        )

    def to_dict(self) -> ObservabilityContextDict:
        """Convert context attributes into a JSON-serializable dictionary."""
        out: ObservabilityContextDict = {
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
        if self.batch_id is not None:
            out["batch_id"] = self.batch_id
        if self.commit_state is not None:
            out["commit_state"] = str(self.commit_state)
        if self.settings_fingerprint is not None:
            out["settings_fingerprint"] = self.settings_fingerprint
        if self.rules_fingerprint is not None:
            out["rules_fingerprint"] = self.rules_fingerprint
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ObservabilityContext:
        """Construct ObservabilityContext from a serialized dictionary.

        Parameters
        ----------
        data : Mapping[str, object]
            Serialized key-value mapping representing context fields.

        Returns
        -------
        ObservabilityContext
            Reconstructed immutable context envelope.
        """
        stage_str = str(data.get("stage", EngineStage.INITIALIZING))
        try:
            stage = EngineStage(stage_str)
        except ValueError:
            stage = EngineStage.INITIALIZING

        commit_state_val = data.get("commit_state")
        commit_state: CommitState | None = None
        if commit_state_val is not None:
            try:
                commit_state = CommitState(str(commit_state_val))
            except ValueError:
                commit_state = None

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
            batch_id=str(data["batch_id"]) if data.get("batch_id") else None,
            commit_state=commit_state,
            settings_fingerprint=(
                str(data["settings_fingerprint"]) if data.get("settings_fingerprint") else None
            ),
            rules_fingerprint=(
                str(data["rules_fingerprint"]) if data.get("rules_fingerprint") else None
            ),
        )


class ObservabilityEventDict(TypedDict):
    """JSON-serializable representation of ObservabilityEvent."""

    schema_version: int
    event_id: str
    sequence: int
    timestamp: str
    event_code: str
    severity: str
    presentation_kind: str
    outcome: str
    context: ObservabilityContextDict
    message: str
    error: NotRequired[ErrorDetailsDict]
    progress: NotRequired[float | None]


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
    schema_version: int = 1
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    sequence: int = 0
    error: ErrorDetails | None = None
    progress: float | None = None

    @classmethod
    def create(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        cls,
        event_code: EventCode,
        message: str,
        context: ObservabilityContext | None = None,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        presentation_kind: PresentationKind = PresentationKind.STEP,
        outcome: EventOutcome = EventOutcome.COMPLETED,
        error: ErrorDetails | None = None,
        progress: float | None = None,
        timestamp: datetime | None = None,
        stage: EngineStage | None = None,
    ) -> ObservabilityEvent:
        """Construct a canonical ObservabilityEvent with UTC timestamp.

        Parameters
        ----------
        event_code : EventCode
            Categorical machine-readable code for the event.
        message : str
            Human-readable presentation narrative describing the event.
        context : ObservabilityContext | None, default=None
            Rich structural context metadata; if None, defaults to blank context.
        severity : DiagnosticSeverity, default=DiagnosticSeverity.INFO
            Categorical severity level.
        presentation_kind : PresentationKind, default=PresentationKind.STEP
            Presentation intent and visual formatting style.
        outcome : EventOutcome, default=EventOutcome.COMPLETED
            State transition outcome.
        error : ErrorDetails | None, default=None
            Exception and diagnostic error envelope if applicable.
        progress : float | None, default=None
            Progress metric from 0.0 to 1.0.
        timestamp : datetime | None, default=None
            UTC timestamp; if None, captures current UTC time.
        stage : EngineStage | None, default=None
            Optional stage override to update on context if provided.

        Returns
        -------
        ObservabilityEvent
            Immutable canonical event instance.
        """
        ts = timestamp if timestamp is not None else datetime.now(UTC)
        ctx = context if context is not None else ObservabilityContext()
        if stage is not None:
            ctx = ctx.with_updates(stage=stage)
        return cls(
            schema_version=1,
            event_id=f"evt_{uuid.uuid4().hex}",
            sequence=0,
            timestamp=ts,
            event_code=event_code,
            severity=severity,
            presentation_kind=presentation_kind,
            outcome=outcome,
            context=ctx,
            message=message,
            error=error,
            progress=progress,
        )

    def to_dict(self) -> ObservabilityEventDict:
        """Serialize event into a JSON-serializable dictionary for JSONL sink."""
        out: ObservabilityEventDict = {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "sequence": self.sequence,
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

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ObservabilityEvent:
        """Construct an ObservabilityEvent from a serialized dictionary.

        Parameters
        ----------
        data : Mapping[str, object]
            Serialized key-value mapping representing the event.

        Returns
        -------
        ObservabilityEvent
            Reconstructed immutable canonical observability event.
        """
        ts_str = str(data.get("timestamp", ""))
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            ts = datetime.now(UTC)

        raw_ctx = data.get("context")
        ctx: ObservabilityContext
        if isinstance(raw_ctx, Mapping):
            ctx = ObservabilityContext.from_dict(cast("Mapping[str, object]", raw_ctx))
        else:
            ctx = ObservabilityContext(run_id="-")

        raw_err = data.get("error")
        err: ErrorDetails | None = None
        if isinstance(raw_err, Mapping):
            err = ErrorDetails.from_dict(cast("Mapping[str, object]", raw_err))

        prog_val = data.get("progress")
        prog = float(prog_val) if isinstance(prog_val, (int, float)) else None

        raw_schema = data.get("schema_version", 1)
        schema_ver = int(raw_schema) if isinstance(raw_schema, (int, str)) else 1

        raw_seq = data.get("sequence", 0)
        seq_val = int(raw_seq) if isinstance(raw_seq, (int, str)) else 0

        return cls(
            schema_version=schema_ver,
            event_id=str(data.get("event_id", f"evt_{uuid.uuid4().hex}")),
            sequence=seq_val,
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
