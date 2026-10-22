"""Central observability event emitter and scoped execution span coordinator.

Owns
----
- ObservabilityEmitter: Central application-facing emitter managing multi-sink fan-out.
- SpanContext: Scoped context manager capturing execution durations, outcomes, and errors.
- Automatic correlation ID tracking across nested synchronous and asynchronous spans.
- Standardized exception enrichment using classify_failure_domain.

Does not own
-------------
- Concrete forensic storage writing (owned by infrastructure.observability).
- Presentation rendering widgets (owned by presentation).
- Domain calculation mathematics (owned by domain).
"""

from __future__ import annotations

import contextvars
import threading
import time
import traceback
import uuid
from types import TracebackType
from typing import Literal

from personal_finance_etl.application.observability.context import (
    get_current_context,
    reset_current_context,
    set_current_context,
)
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import (
    FailureDomain,
    classify_failure_domain,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventOutcome,
    ObservabilityContext,
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)

__all__ = [
    "ObservabilityEmitter",
    "SpanContext",
    "get_global_emitter",
    "set_global_emitter",
]


class SpanContext:
    """Scoped context manager measuring execution duration and state transitions.

    Automatically emits START and SUCCESS or FAILURE events while maintaining
    hierarchical operation correlation IDs.
    """

    def __init__(
        self,
        emitter: ObservabilityEmitter,
        operation: str,
        component: str = "",
        event_code: EventCode = EventCode.GENERIC_DIAGNOSTIC,
        presentation_kind: PresentationKind = PresentationKind.STEP,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        entity_type: str | None = None,
        entity_id: str | None = None,
        rows: int | None = None,
        provider: str | None = None,
        cache_hit: bool | None = None,
        message: str = "",
        log_start: bool = True,
    ) -> None:
        self.emitter = emitter
        self.operation = operation
        self.component = component
        self.event_code = event_code
        self.presentation_kind = presentation_kind
        self.severity = severity
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.rows = rows
        self.provider = provider
        self.cache_hit = cache_hit
        self.message = message
        self.log_start = log_start

        self.start_ns: int = 0
        self.token: contextvars.Token[ObservabilityContext] | None = None

    def set_rows(self, rows: int) -> None:
        """Update the processed row count for the current span."""
        self.rows = rows

    def set_entity(self, entity_type: str, entity_id: str) -> None:
        """Update the targeted entity classification and identifier."""
        self.entity_type = entity_type
        self.entity_id = entity_id

    def set_cache_hit(self, cache_hit: bool) -> None:
        """Record whether the operation was served from cache."""
        self.cache_hit = cache_hit

    def set_message(self, message: str) -> None:
        """Update the human-readable narrative description for the span outcome."""
        self.message = message

    def __enter__(self) -> SpanContext:
        """Enter the execution span, bind child context, and emit START event."""
        self.start_ns = time.perf_counter_ns()
        parent_ctx = get_current_context()

        op_id = f"op_{uuid.uuid4().hex[:10]}"
        child_ctx = parent_ctx.with_updates(
            component=self.component or parent_ctx.component,
            operation=self.operation,
            operation_id=op_id,
            parent_operation_id=parent_ctx.operation_id if parent_ctx.operation_id else None,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            rows=self.rows,
            provider=self.provider,
            cache_hit=self.cache_hit,
        )
        self.token = set_current_context(child_ctx)

        if self.log_start:
            start_msg = self.message or f"Starting {self.operation}..."
            event = ObservabilityEvent.create(
                event_code=self.event_code,
                message=start_msg,
                context=child_ctx,
                severity=self.severity,
                presentation_kind=self.presentation_kind,
                outcome=EventOutcome.STARTED,
            )
            self.emitter.emit(event)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        """Exit the execution span, calculate duration, and emit SUCCESS or FAILURE."""
        elapsed_ms = (time.perf_counter_ns() - self.start_ns) / 1_000_000.0
        current_ctx = get_current_context().with_updates(
            duration_ms=round(elapsed_ms, 3),
            rows=self.rows,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            cache_hit=self.cache_hit,
        )

        try:
            if exc_val is not None:
                domain = classify_failure_domain(
                    stage=str(current_ctx.stage),
                    error=exc_val,
                )
                if domain == FailureDomain.UNKNOWN:
                    domain = FailureDomain.TRANSFORMATION

                err_details = ErrorDetails(
                    exception_type=type(exc_val).__name__,
                    exception_message=str(exc_val),
                    failure_domain=domain,
                    traceback_summary=traceback.format_exc(),
                    retryable=False,
                )
                fail_msg = self.message or f"Failed {self.operation}: {exc_val}"
                fail_event = ObservabilityEvent.create(
                    event_code=self.event_code,
                    message=fail_msg,
                    context=current_ctx,
                    severity=DiagnosticSeverity.ERROR,
                    presentation_kind=PresentationKind.FAILURE,
                    outcome=EventOutcome.FAILED,
                    error=err_details,
                )
                self.emitter.emit(fail_event)
            else:
                success_msg = self.message or f"Completed {self.operation} in {elapsed_ms:.2f}ms"
                succ_event = ObservabilityEvent.create(
                    event_code=self.event_code,
                    message=success_msg,
                    context=current_ctx,
                    severity=self.severity,
                    presentation_kind=self.presentation_kind,
                    outcome=EventOutcome.COMPLETED,
                )
                self.emitter.emit(succ_event)
        finally:
            if self.token is not None:
                reset_current_context(self.token)

        return False


class ObservabilityEmitter:
    """Central event emitter managing multi-sink fan-out and span orchestration."""

    def __init__(self, sinks: list[ObservabilitySink] | None = None) -> None:
        self._sinks: list[ObservabilitySink] = list(sinks or [])
        self._lock = threading.Lock()

    def register_sink(self, sink: ObservabilitySink) -> None:
        """Register a new observability sink for event fan-out.

        Parameters
        ----------
        sink : ObservabilitySink
            The sink implementation to register.
        """
        with self._lock:
            if sink not in self._sinks:
                self._sinks.append(sink)

    def unregister_sink(self, sink: ObservabilitySink) -> None:
        """Remove a previously registered sink.

        Parameters
        ----------
        sink : ObservabilitySink
            The sink implementation to remove.
        """
        with self._lock:
            if sink in self._sinks:
                self._sinks.remove(sink)

    def clear_sinks(self) -> None:
        """Remove all currently registered sinks."""
        with self._lock:
            self._sinks.clear()

    def emit(self, event: ObservabilityEvent) -> None:
        """Fan-out an ObservabilityEvent to all registered sinks safely.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical event to dispatch.
        """
        with self._lock:
            targets = list(self._sinks)

        for sink in targets:
            try:
                sink.emit(event)
            except Exception:
                # Sinks must not compromise pipeline execution integrity
                pass

    def emit_event(
        self,
        event_code: EventCode,
        message: str,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        presentation_kind: PresentationKind = PresentationKind.STEP,
        outcome: EventOutcome = EventOutcome.COMPLETED,
        error: ErrorDetails | None = None,
        progress: float | None = None,
        stage: EngineStage | None = None,
        component: str | None = None,
        operation: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        rows: int | None = None,
        duration_ms: float | None = None,
        provider: str | None = None,
        cache_hit: bool | None = None,
    ) -> ObservabilityEvent:
        """Construct and emit an event using current ambient context.

        Parameters
        ----------
        event_code : EventCode
            Categorical event identifier.
        message : str
            Human-readable message.
        severity : DiagnosticSeverity, default=DiagnosticSeverity.INFO
            Diagnostic trace severity.
        presentation_kind : PresentationKind, default=PresentationKind.STEP
            UI narrative category.
        outcome : EventOutcome, default=EventOutcome.COMPLETED
            Operational transition outcome.
        error : ErrorDetails | None, default=None
            Optional structured error context.
        progress : float | None, default=None
            Fractional progress marker between 0.0 and 1.0.
        stage : EngineStage | None, default=None
            Optional stage override.
        component : str | None, default=None
            Optional component override.
        operation : str | None, default=None
            Optional operation override.
        entity_type : str | None, default=None
            Optional entity classification.
        entity_id : str | None, default=None
            Optional entity identifier.
        rows : int | None, default=None
            Optional row count.
        duration_ms : float | None, default=None
            Optional duration in milliseconds.
        provider : str | None, default=None
            Optional provider name.
        cache_hit : bool | None, default=None
            Optional cache hit flag.

        Returns
        -------
        ObservabilityEvent
            The constructed and emitted event.
        """
        ambient = get_current_context()
        ctx = ambient.with_updates(
            stage=stage,
            component=component,
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            rows=rows,
            duration_ms=duration_ms,
            provider=provider,
            cache_hit=cache_hit,
        )
        event = ObservabilityEvent.create(
            event_code=event_code,
            message=message,
            context=ctx,
            severity=severity,
            presentation_kind=presentation_kind,
            outcome=outcome,
            error=error,
            progress=progress,
        )
        self.emit(event)
        return event

    def span(
        self,
        operation: str,
        component: str = "",
        event_code: EventCode = EventCode.GENERIC_DIAGNOSTIC,
        presentation_kind: PresentationKind = PresentationKind.STEP,
        severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
        entity_type: str | None = None,
        entity_id: str | None = None,
        rows: int | None = None,
        provider: str | None = None,
        cache_hit: bool | None = None,
        message: str = "",
        log_start: bool = True,
    ) -> SpanContext:
        """Create a scoped execution span measuring duration and outcome.

        Parameters
        ----------
        operation : str
            Name of the operation being executed.
        component : str, default=""
            Subsystem or module name.
        event_code : EventCode, default=EventCode.GENERIC_DIAGNOSTIC
            Canonical event code for start/finish events.
        presentation_kind : PresentationKind, default=PresentationKind.STEP
            UI narrative intent.
        severity : DiagnosticSeverity, default=DiagnosticSeverity.INFO
            Diagnostic severity level.
        entity_type : str | None, default=None
            Target entity classification.
        entity_id : str | None, default=None
            Target entity identifier.
        rows : int | None, default=None
            Optional row count.
        provider : str | None, default=None
            Optional provider name.
        cache_hit : bool | None, default=None
            Optional cache hit flag.
        message : str, default=""
            Optional narrative message description.
        log_start : bool, default=True
            Whether to emit a START event upon entering the span.

        Returns
        -------
        SpanContext
            The execution span context manager.
        """
        return SpanContext(
            emitter=self,
            operation=operation,
            component=component,
            event_code=event_code,
            presentation_kind=presentation_kind,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            rows=rows,
            provider=provider,
            cache_hit=cache_hit,
            message=message,
            log_start=log_start,
        )

    def flush(self) -> None:
        """Flush all registered sinks."""
        with self._lock:
            targets = list(self._sinks)

        for sink in targets:
            try:
                sink.flush()
            except Exception:
                pass


_global_emitter: ObservabilityEmitter = ObservabilityEmitter()


def get_global_emitter() -> ObservabilityEmitter:
    """Retrieve the application-wide global ObservabilityEmitter instance.

    Returns
    -------
    ObservabilityEmitter
        The global emitter singleton.
    """
    return _global_emitter


def set_global_emitter(emitter: ObservabilityEmitter) -> None:
    """Set the application-wide global ObservabilityEmitter instance.

    Parameters
    ----------
    emitter : ObservabilityEmitter
        The new emitter instance to activate globally.
    """
    global _global_emitter
    _global_emitter = emitter
