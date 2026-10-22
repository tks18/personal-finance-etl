"""Unit tests for Phase 2 central event emitter, context scoping, and span timing.

Owns
----
- Testing sink registration, unregistration, and fan-out dispatch.
- Verifying automatic duration timing, correlation IDs, and nested span propagation.
- Validating exception enrichment and FailureDomain mapping during failures.
- Checking sink error isolation and thread safety.
"""

from __future__ import annotations

import concurrent.futures

import pytest

from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    get_current_context,
    reset_current_context,
    set_current_context,
)
from personal_finance_etl.contracts import (
    DiagnosticSeverity,
    EngineStage,
    EventCode,
    EventOutcome,
    FailureDomain,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)


class MockRecordingSink:
    """In-memory test sink recording received events."""

    def __init__(self, raise_on_emit: bool = False) -> None:
        self.events: list[ObservabilityEvent] = []
        self.flushed: bool = False
        self.raise_on_emit = raise_on_emit

    def emit(self, event: ObservabilityEvent) -> None:
        if self.raise_on_emit:
            raise RuntimeError("Simulated sink crash")
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True


def test_emitter_sink_registration_and_fanout() -> None:
    """Verify emitter dispatches events to multiple registered sinks and handles errors gracefully."""
    sink1 = MockRecordingSink()
    sink2 = MockRecordingSink()
    bad_sink = MockRecordingSink(raise_on_emit=True)

    emitter = ObservabilityEmitter()
    emitter.register_sink(sink1)
    emitter.register_sink(bad_sink)
    emitter.register_sink(sink2)

    event = ObservabilityEvent.create(
        event_code=EventCode.DISCOVERY_START,
        message="Starting discovery",
        context=ObservabilityContext(run_id="run-100"),
    )
    # emit must not raise even if bad_sink raises
    emitter.emit(event)

    assert len(sink1.events) == 1
    assert sink1.events[0].event_code == EventCode.DISCOVERY_START
    assert len(sink2.events) == 1
    assert sink2.events[0].event_code == EventCode.DISCOVERY_START

    emitter.flush()
    assert sink1.flushed is True
    assert sink2.flushed is True

    emitter.unregister_sink(sink1)
    emitter.emit(event)
    assert len(sink1.events) == 1  # Unregistered, count did not increase
    assert len(sink2.events) == 2


def test_span_timing_and_outcomes() -> None:
    """Verify SpanContext produces START and SUCCESS events with measured duration."""
    sink = MockRecordingSink()
    emitter = ObservabilityEmitter(sinks=[sink])

    ctx = ObservabilityContext(run_id="run-span-1", stage=EngineStage.TRANSFORMING)
    token = set_current_context(ctx)

    try:
        with emitter.span(
            operation="test_transform",
            component="transformer",
            event_code=EventCode.TRANSFORMATION_STAGE,
            presentation_kind=PresentationKind.STEP,
        ) as span:
            span.set_rows(450)
            span.set_entity("table", "dim_account")
            span.set_cache_hit(False)
    finally:
        reset_current_context(token)

    assert len(sink.events) == 2
    start_ev = sink.events[0]
    succ_ev = sink.events[1]

    assert start_ev.outcome == EventOutcome.STARTED
    assert start_ev.event_code == EventCode.TRANSFORMATION_STAGE
    assert start_ev.context.operation == "test_transform"

    assert succ_ev.outcome == EventOutcome.COMPLETED
    assert succ_ev.event_code == EventCode.TRANSFORMATION_STAGE
    assert succ_ev.context.rows == 450
    assert succ_ev.context.entity_type == "table"
    assert succ_ev.context.entity_id == "dim_account"
    assert succ_ev.context.duration_ms is not None
    assert succ_ev.context.duration_ms >= 0.0


def test_nested_spans_and_correlation_ids() -> None:
    """Verify nested spans propagate parent_operation_id and restore context on exit."""
    sink = MockRecordingSink()
    emitter = ObservabilityEmitter(sinks=[sink])

    root_ctx = ObservabilityContext(run_id="run-hierarchical", stage=EngineStage.ANALYZING)
    token = set_current_context(root_ctx)

    try:
        with emitter.span("outer_phase", component="analytics"):
            outer_op_id = get_current_context().operation_id
            assert outer_op_id.startswith("op_")

            with emitter.span("inner_step", component="quant") as inner:
                inner_ctx = get_current_context()
                assert inner_ctx.operation == "inner_step"
                assert inner_ctx.parent_operation_id == outer_op_id
                inner.set_rows(120)

            # After inner span exit, context should restore to outer
            restored_outer = get_current_context()
            assert restored_outer.operation == "outer_phase"
            assert restored_outer.operation_id == outer_op_id

        # After outer span exit, context restores to root
        assert get_current_context().run_id == "run-hierarchical"
        assert get_current_context().operation == ""
    finally:
        reset_current_context(token)

    assert len(sink.events) == 4
    # Event 0: outer START
    # Event 1: inner START
    # Event 2: inner SUCCESS
    # Event 3: outer SUCCESS
    inner_succ = sink.events[2]
    outer_succ = sink.events[3]

    assert inner_succ.context.operation == "inner_step"
    assert inner_succ.context.rows == 120
    assert outer_succ.context.operation == "outer_phase"


def test_span_exception_capture_and_failure_domain() -> None:
    """Verify exceptions inside span trigger FAILURE event with structured ErrorDetails."""
    sink = MockRecordingSink()
    emitter = ObservabilityEmitter(sinks=[sink])

    ctx = ObservabilityContext(run_id="run-fail-1", stage=EngineStage.PUBLISHING)
    token = set_current_context(ctx)

    try:
        with pytest.raises(KeyError) as exc_info:
            with emitter.span("save_lakehouse", component="warehouse") as span:
                span.set_rows(50)
                raise KeyError("Missing primary key column")
    finally:
        reset_current_context(token)

    assert "Missing primary key" in str(exc_info.value)

    assert len(sink.events) == 2
    start_ev = sink.events[0]
    fail_ev = sink.events[1]

    assert start_ev.outcome == EventOutcome.STARTED
    assert fail_ev.outcome == EventOutcome.FAILED
    assert fail_ev.severity == DiagnosticSeverity.ERROR
    assert fail_ev.presentation_kind == PresentationKind.FAILURE
    assert fail_ev.error is not None
    assert fail_ev.error.exception_type == "KeyError"
    assert "Missing primary key" in fail_ev.error.exception_message
    assert fail_ev.error.failure_domain in (
        FailureDomain.TRANSFORMATION,
        FailureDomain.PUBLICATION,
    )
    assert fail_ev.context.duration_ms is not None


def test_concurrent_thread_context_isolation() -> None:
    """Verify ContextVar preserves context isolation across concurrent worker threads."""

    def _worker(thread_id: int) -> tuple[str, str]:
        ctx = ObservabilityContext(run_id=f"run-{thread_id}", operation=f"op_{thread_id}")
        token = set_current_context(ctx)
        try:
            curr = get_current_context()
            return curr.run_id, curr.operation
        finally:
            reset_current_context(token)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_worker, i) for i in range(10)]
        results = [f.result() for f in futures]

    for i, (run_id, op) in enumerate(results):
        assert run_id == f"run-{i}"
        assert op == f"op_{i}"
