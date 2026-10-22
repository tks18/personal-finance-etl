"""Unit tests for Phase 1 canonical observability contracts.

Owns
----
- Invariant testing for EventCode, DiagnosticSeverity, PresentationKind, EventOutcome enums.
- Serialization and deserialization round-trip validation for ObservabilityEvent, ObservabilityContext, ErrorDetails.
- Backward compatibility projection testing for to_status_message() adapter.
- Immutability and bounding validation for context containers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from personal_finance_etl.contracts import (
    DiagnosticSeverity,
    EngineStage,
    EngineStatusMessage,
    ErrorDetails,
    EventCode,
    EventOutcome,
    FailureDomain,
    LogLevel,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)


def test_observability_enums() -> None:
    """Verify that observability enums contain expected members and are StrEnum instances."""
    assert isinstance(EventCode.RUN_START, str)
    assert EventCode.RUN_START == "RUN_START"
    assert EventCode.DISCOVERY_COMPLETED == "DISCOVERY_COMPLETED"
    assert EventCode.BRONZE_UPSERT == "BRONZE_UPSERT"
    assert EventCode.QUANT_ENGINE_START == "QUANT_ENGINE_START"

    assert DiagnosticSeverity.DEBUG == "DEBUG"
    assert DiagnosticSeverity.TRACE == "TRACE"
    assert DiagnosticSeverity.ERROR == "ERROR"

    assert PresentationKind.STEP == "STEP"
    assert PresentationKind.SUCCESS == "SUCCESS"
    assert PresentationKind.FAILURE == "FAILURE"

    assert EventOutcome.STARTED == "STARTED"
    assert EventOutcome.COMPLETED == "COMPLETED"
    assert EventOutcome.FAILED == "FAILED"


def test_error_details_serialization_round_trip() -> None:
    """Verify ErrorDetails serializes and deserializes accurately with FailureDomain."""
    err = ErrorDetails(
        exception_type="ValueError",
        exception_message="Invalid ticker quote syntax",
        failure_domain=FailureDomain.EXTERNAL_PROVIDER,
        traceback_summary="Traceback: line 42 in fetch_quote",
        retryable=True,
    )
    raw = err.to_dict()
    assert raw["exception_type"] == "ValueError"
    assert raw["failure_domain"] == "EXTERNAL_PROVIDER"
    assert raw["retryable"] is True

    reconstructed = ErrorDetails.from_dict(raw)
    assert reconstructed.exception_type == err.exception_type
    assert reconstructed.failure_domain == FailureDomain.EXTERNAL_PROVIDER
    assert reconstructed.retryable is True
    assert reconstructed == err


def test_observability_context_immutability_and_updates() -> None:
    """Verify ObservabilityContext is immutable and with_updates returns a new copy."""
    ctx = ObservabilityContext(
        run_id="run-2026-test",
        stage=EngineStage.TRANSFORMING,
        component="pipeline",
        operation="transform_dag",
        operation_id="op-1",
        rows=1000,
    )
    assert ctx.run_id == "run-2026-test"
    assert ctx.rows == 1000

    # Immutability check
    with pytest.raises(AttributeError):
        ctx.rows = 2000  # type: ignore[misc]

    # with_updates check
    updated = ctx.with_updates(
        stage=EngineStage.ANALYZING,
        operation_id="op-2",
        parent_operation_id="op-1",
        rows=1500,
        duration_ms=45.2,
    )
    assert updated.run_id == ctx.run_id
    assert updated.stage == EngineStage.ANALYZING
    assert updated.operation_id == "op-2"
    assert updated.parent_operation_id == "op-1"
    assert updated.rows == 1500
    assert updated.duration_ms == 45.2

    # Round trip dict
    ctx_dict = updated.to_dict()
    assert ctx_dict["run_id"] == "run-2026-test"
    assert ctx_dict["stage"] == "ANALYZING"

    restored = ObservabilityContext.from_dict(ctx_dict)
    assert restored.run_id == updated.run_id
    assert restored.stage == EngineStage.ANALYZING
    assert restored.duration_ms == 45.2


def test_observability_event_serialization_and_json() -> None:
    """Verify ObservabilityEvent serialization to JSON and JSONL round trip."""
    ctx = ObservabilityContext(
        run_id="run-jsonl-001",
        stage=EngineStage.EXTRACTING,
        component="market_sync",
        operation="fetch_currency",
        operation_id="span-curr-01",
        entity_type="ticker",
        entity_id="USDINR=X",
        provider="yfinance",
        cache_hit=True,
        duration_ms=12.5,
    )

    now = datetime(2026, 10, 22, 19, 30, 0, tzinfo=UTC)
    event = ObservabilityEvent.create(
        event_code=EventCode.MARKET_TICKER_CACHE_HIT,
        message="USDINR=X currency rate loaded from local lake cache.",
        context=ctx,
        severity=DiagnosticSeverity.INFO,
        presentation_kind=PresentationKind.SKIP,
        outcome=EventOutcome.COMPLETED,
        progress=0.35,
        timestamp=now,
    )

    # Immutability check
    with pytest.raises(AttributeError):
        event.message = "mutated"  # type: ignore[misc]

    # JSON rendering
    json_str = event.to_json()
    assert "\n" not in json_str
    parsed = json.loads(json_str)
    assert parsed["event_code"] == "MARKET_TICKER_CACHE_HIT"
    assert parsed["severity"] == "INFO"
    assert parsed["presentation_kind"] == "SKIP"
    assert parsed["context"]["entity_id"] == "USDINR=X"
    assert parsed["progress"] == 0.35

    # Deserialization
    reconstructed = ObservabilityEvent.from_dict(parsed)
    assert reconstructed.event_code == EventCode.MARKET_TICKER_CACHE_HIT
    assert reconstructed.severity == DiagnosticSeverity.INFO
    assert reconstructed.presentation_kind == PresentationKind.SKIP
    assert reconstructed.context.entity_id == "USDINR=X"
    assert reconstructed.progress == 0.35
    assert reconstructed.timestamp == now


def test_observability_event_error_containment() -> None:
    """Verify ObservabilityEvent captures structured ErrorDetails on failure."""
    ctx = ObservabilityContext(run_id="run-err-01", stage=EngineStage.TRANSFORMING)
    err = ErrorDetails(
        exception_type="KeyError",
        exception_message="'UnknownISIN'",
        failure_domain=FailureDomain.TRANSFORMATION,
        traceback_summary="Traceback: line 99 in transform",
    )
    event = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Pipeline failed during transformation phase.",
        context=ctx,
        severity=DiagnosticSeverity.CRITICAL,
        presentation_kind=PresentationKind.FAILURE,
        outcome=EventOutcome.FAILED,
        error=err,
    )

    assert event.error is not None
    assert event.error.failure_domain == FailureDomain.TRANSFORMATION

    json_str = event.to_json()
    reconstructed = ObservabilityEvent.from_dict(json.loads(json_str))
    assert reconstructed.error is not None
    assert reconstructed.error.exception_type == "KeyError"
    assert reconstructed.error.failure_domain == FailureDomain.TRANSFORMATION


def test_backward_compatibility_status_message_bridge() -> None:
    """Verify to_status_message() adapter correctly bridges into legacy EngineStatusMessage."""
    ctx = ObservabilityContext(run_id="run-compat-01", stage=EngineStage.ANALYZING)
    event_step = ObservabilityEvent.create(
        event_code=EventCode.QUANT_ENGINE_START,
        message="Starting Investment Quant Engine...",
        context=ctx,
        presentation_kind=PresentationKind.STEP,
        progress=0.6,
    )
    msg_step = event_step.to_status_message()
    assert isinstance(msg_step, EngineStatusMessage)
    assert msg_step.msg == "Starting Investment Quant Engine..."
    assert msg_step.level == LogLevel.STEP
    assert msg_step.progress == 0.6
    assert msg_step.stage == EngineStage.ANALYZING
    assert msg_step.data is None

    # Error event mapping
    err = ErrorDetails(
        exception_type="RuntimeError",
        exception_message="DuckDB disk lock",
        failure_domain=FailureDomain.DUCKDB_COMMIT,
        traceback_summary="lock error",
    )
    event_err = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Fatal database failure",
        context=ctx,
        severity=DiagnosticSeverity.ERROR,
        presentation_kind=PresentationKind.FAILURE,
        error=err,
    )
    msg_err = event_err.to_status_message()
    assert msg_err.level == LogLevel.ERROR
    assert msg_err.failure_domain == FailureDomain.DUCKDB_COMMIT
