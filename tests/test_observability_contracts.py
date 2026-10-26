"""Unit tests for Phase 1 canonical observability contracts.

Owns
----
- Invariant testing for EventCode, DiagnosticSeverity, PresentationKind, EventOutcome enums.
- Serialization and deserialization round-trip validation for ObservabilityEvent, ObservabilityContext, ErrorDetails.
- Verification of bounded context attributes (batch_id, commit_state, settings_fingerprint, rules_fingerprint).
- Backward compatibility projection testing for to_status_message() adapter.
- Immutability and bounding validation for context containers.
- Semantic independence verification (event meaning requires zero message parsing).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from personal_finance_etl.contracts import (
    CommitState,
    DiagnosticSeverity,
    EngineStage,
    EngineStatusMessage,
    ErrorDetails,
    ErrorDetailsDict,
    EventCode,
    EventOutcome,
    FailureDomain,
    LogLevel,
    ObservabilityContext,
    ObservabilityContextDict,
    ObservabilityEvent,
    ObservabilityEventDict,
    PresentationKind,
)


def test_observability_enums() -> None:
    """Verify that observability enums contain expected members and are StrEnum instances."""
    # Pipeline Lifecycle
    assert EventCode.RUN_START == "RUN_START"
    assert EventCode.RUN_COMPLETED == "RUN_COMPLETED"
    assert EventCode.RUN_FAILED == "RUN_FAILED"
    assert EventCode.RUN_ABORTED == "RUN_ABORTED"
    assert EventCode.RUN_RECOVERY == "RUN_RECOVERY"
    assert EventCode.RECOVERY_SNAPSHOT == "RECOVERY_SNAPSHOT"
    assert EventCode.RECOVERY_RESTORE == "RECOVERY_RESTORE"

    # Discovery & Providers
    assert EventCode.DISCOVERY_START == "DISCOVERY_START"
    assert EventCode.DISCOVERY_COMPLETED == "DISCOVERY_COMPLETED"
    assert EventCode.EXTRACTION_START == "EXTRACTION_START"
    assert EventCode.EXTRACTION_BATCH == "EXTRACTION_BATCH"
    assert EventCode.EXTRACTION_COMPLETED == "EXTRACTION_COMPLETED"
    assert EventCode.SCHEMA_VALIDATION == "SCHEMA_VALIDATION"
    assert EventCode.PROVIDER_DISCOVERY == "PROVIDER_DISCOVERY"
    assert EventCode.PROVIDER_BATCH_INGEST == "PROVIDER_BATCH_INGEST"
    assert EventCode.PROVIDER_FILE_ERROR == "PROVIDER_FILE_ERROR"

    # Market
    assert EventCode.MARKET_FETCH_START == "MARKET_FETCH_START"
    assert EventCode.MARKET_TICKER_SUCCESS == "MARKET_TICKER_SUCCESS"
    assert EventCode.MARKET_TICKER_CACHE_HIT == "MARKET_TICKER_CACHE_HIT"
    assert EventCode.MARKET_TICKER_RETRY == "MARKET_TICKER_RETRY"
    assert EventCode.MARKET_TICKER_FAILED == "MARKET_TICKER_FAILED"
    assert EventCode.MARKET_SYNC_COMPLETED == "MARKET_SYNC_COMPLETED"

    # Lakehouse & Storage
    assert EventCode.BRONZE_UPSERT == "BRONZE_UPSERT"
    assert EventCode.BRONZE_REPLACE == "BRONZE_REPLACE"
    assert EventCode.SILVER_REPLACE == "SILVER_REPLACE"
    assert EventCode.GOLD_REPLACE == "GOLD_REPLACE"
    assert EventCode.META_SNAPSHOT == "META_SNAPSHOT"
    assert EventCode.DATABASE_VACUUM == "DATABASE_VACUUM"
    assert EventCode.DATABASE_CHECKPOINT == "DATABASE_CHECKPOINT"
    assert EventCode.DATABASE_COMMIT == "DATABASE_COMMIT"
    assert EventCode.DATABASE_ROLLBACK == "DATABASE_ROLLBACK"

    # Analytics & Engines
    assert EventCode.TRANSFORMATION_STAGE == "TRANSFORMATION_STAGE"
    assert EventCode.TRANSFORMATION_DAG_COMPLETED == "TRANSFORMATION_DAG_COMPLETED"
    assert EventCode.QUANT_ENGINE_START == "QUANT_ENGINE_START"
    assert EventCode.QUANT_ISIN_PROCESSED == "QUANT_ISIN_PROCESSED"
    assert EventCode.QUANT_POOL_COMPLETED == "QUANT_POOL_COMPLETED"
    assert EventCode.QUANT_LOT_MAPPED == "QUANT_LOT_MAPPED"
    assert EventCode.TAX_ENGINE_START == "TAX_ENGINE_START"
    assert EventCode.TAX_ENGINE_COMPLETED == "TAX_ENGINE_COMPLETED"
    assert EventCode.WEALTH_ENGINE_START == "WEALTH_ENGINE_START"
    assert EventCode.WEALTH_ENGINE_COMPLETED == "WEALTH_ENGINE_COMPLETED"
    assert EventCode.FIRE_ENGINE_START == "FIRE_ENGINE_START"
    assert EventCode.FIRE_ENGINE_COMPLETED == "FIRE_ENGINE_COMPLETED"
    assert EventCode.PRESENTATION_DAG_START == "PRESENTATION_DAG_START"
    assert EventCode.PRESENTATION_DAG_COMPLETED == "PRESENTATION_DAG_COMPLETED"

    # Raw telemetry & system
    assert EventCode.RAW_STDOUT == "RAW_STDOUT"
    assert EventCode.RAW_STDERR == "RAW_STDERR"
    assert EventCode.SYSTEM_CONFIG_FINGERPRINT == "SYSTEM_CONFIG_FINGERPRINT"
    assert EventCode.SYSTEM_MEMORY_SAMPLE == "SYSTEM_MEMORY_SAMPLE"
    assert EventCode.SYSTEM_TEARDOWN == "SYSTEM_TEARDOWN"
    assert EventCode.GENERIC_DIAGNOSTIC == "GENERIC_DIAGNOSTIC"

    # Severity
    assert DiagnosticSeverity.TRACE == "TRACE"
    assert DiagnosticSeverity.DEBUG == "DEBUG"
    assert DiagnosticSeverity.INFO == "INFO"
    assert DiagnosticSeverity.WARNING == "WARNING"
    assert DiagnosticSeverity.ERROR == "ERROR"
    assert DiagnosticSeverity.CRITICAL == "CRITICAL"

    # Presentation
    assert PresentationKind.STEP == "STEP"
    assert PresentationKind.PROGRESS == "PROGRESS"
    assert PresentationKind.SUCCESS == "SUCCESS"
    assert PresentationKind.SKIP == "SKIP"
    assert PresentationKind.WARNING == "WARNING"
    assert PresentationKind.FAILURE == "FAILURE"
    assert PresentationKind.RECOVERY == "RECOVERY"
    assert PresentationKind.INTERNAL == "INTERNAL"

    # Outcomes
    assert EventOutcome.STARTED == "STARTED"
    assert EventOutcome.COMPLETED == "COMPLETED"
    assert EventOutcome.FAILED == "FAILED"
    assert EventOutcome.SKIPPED == "SKIPPED"


def test_error_details_serialization_round_trip() -> None:
    """Verify ErrorDetails serializes and deserializes accurately with FailureDomain."""
    err = ErrorDetails(
        exception_type="ValueError",
        exception_message="Invalid ticker quote syntax",
        failure_domain=FailureDomain.EXTERNAL_PROVIDER,
        traceback_summary="Traceback: line 42 in fetch_quote",
        retryable=True,
    )
    raw: ErrorDetailsDict = err.to_dict()
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
        batch_id="batch-042",
        commit_state=CommitState.STARTED,
        settings_fingerprint="sha_settings_123",
        rules_fingerprint="sha_rules_456",
    )
    assert ctx.run_id == "run-2026-test"
    assert ctx.rows == 1000
    assert ctx.batch_id == "batch-042"
    assert ctx.commit_state == CommitState.STARTED
    assert ctx.settings_fingerprint == "sha_settings_123"
    assert ctx.rules_fingerprint == "sha_rules_456"

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
        commit_state=CommitState.DUCKDB_COMMITTED,
    )
    assert updated.run_id == ctx.run_id
    assert updated.stage == EngineStage.ANALYZING
    assert updated.operation_id == "op-2"
    assert updated.parent_operation_id == "op-1"
    assert updated.rows == 1500
    assert updated.duration_ms == 45.2
    assert updated.batch_id == "batch-042"
    assert updated.commit_state == CommitState.DUCKDB_COMMITTED
    assert updated.settings_fingerprint == "sha_settings_123"

    # Round trip dict
    ctx_dict: ObservabilityContextDict = updated.to_dict()
    assert ctx_dict["run_id"] == "run-2026-test"
    assert ctx_dict["stage"] == "ANALYZING"
    assert ctx_dict.get("commit_state") == "DUCKDB_COMMITTED"
    assert ctx_dict.get("batch_id") == "batch-042"
    assert ctx_dict.get("settings_fingerprint") == "sha_settings_123"
    assert ctx_dict.get("rules_fingerprint") == "sha_rules_456"

    restored = ObservabilityContext.from_dict(ctx_dict)
    assert restored.run_id == updated.run_id
    assert restored.stage == EngineStage.ANALYZING
    assert restored.duration_ms == 45.2
    assert restored.commit_state == CommitState.DUCKDB_COMMITTED
    assert restored.batch_id == "batch-042"
    assert restored.settings_fingerprint == "sha_settings_123"
    assert restored.rules_fingerprint == "sha_rules_456"


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
        commit_state=CommitState.STARTED,
        settings_fingerprint="a1b2c3d4",
        rules_fingerprint="e5f6g7h8",
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
    assert parsed["context"]["commit_state"] == "STARTED"
    assert parsed["context"]["settings_fingerprint"] == "a1b2c3d4"
    assert parsed["progress"] == 0.35

    # Deserialization
    reconstructed = ObservabilityEvent.from_dict(parsed)
    assert reconstructed.event_code == EventCode.MARKET_TICKER_CACHE_HIT
    assert reconstructed.severity == DiagnosticSeverity.INFO
    assert reconstructed.presentation_kind == PresentationKind.SKIP
    assert reconstructed.context.entity_id == "USDINR=X"
    assert reconstructed.context.commit_state == CommitState.STARTED
    assert reconstructed.context.settings_fingerprint == "a1b2c3d4"
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


def test_event_semantics_independent_of_message_prose() -> None:
    """Verify that event semantics are determined entirely by machine contracts, not message text."""
    ctx = ObservabilityContext(run_id="run-sem-01", stage=EngineStage.PUBLISHING)

    # An event with confusing/inverted words in its message MUST preserve machine semantics
    event = ObservabilityEvent.create(
        event_code=EventCode.RUN_COMPLETED,
        message="Failure is not an option: successfully finished all 46 nodes.",
        context=ctx,
        severity=DiagnosticSeverity.INFO,
        presentation_kind=PresentationKind.SUCCESS,
        outcome=EventOutcome.COMPLETED,
    )
    assert event.event_code == EventCode.RUN_COMPLETED
    assert event.presentation_kind == PresentationKind.SUCCESS
    assert event.outcome == EventOutcome.COMPLETED

    event_dict: ObservabilityEventDict = event.to_dict()
    assert event_dict["event_code"] == "RUN_COMPLETED"
    assert event_dict["presentation_kind"] == "SUCCESS"


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
