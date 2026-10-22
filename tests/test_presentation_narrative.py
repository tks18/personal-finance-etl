# pyright: reportPrivateUsage=false
"""Unit tests for human-facing CLI and Desktop observability presentation sinks.

Owns
----
- Verification of RichNarrativeSink console rendering and presentation filtering.
- Verification of DesktopNarrativeSink callback dispatching and tag mapping.
- Verification of metadata formatting (duration, row counts, cache hits, entity badges).
- Verification of failure panel presentation and zero stack trace leakage.
- Verification of backward compatibility with legacy status payloads.

Does not own
-------------
- JSONL forensic persistence verification (owned by test_forensic_pipeline.py).
- Central emitter span timing verification (owned by test_observability_emitter.py).
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from rich.console import Console

from personal_finance_etl.contracts.application import EngineStage, EngineStatusMessage
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.contracts.observability import (
    ErrorDetails,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.presentation.desktop.base_tab import BaseEngineTab
from personal_finance_etl.presentation.observability.cli_narrative import (
    RichNarrativeSink,
)
from personal_finance_etl.presentation.observability.desktop_sink import (
    DesktopNarrativeSink,
    format_event_narrative,
    format_failure_summary,
)


def _make_event(
    kind: PresentationKind,
    msg: str,
    duration_ms: float | None = None,
    rows: int | None = None,
    cache_hit: bool | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    error: ErrorDetails | None = None,
    progress: float | None = None,
) -> ObservabilityEvent:
    ctx = ObservabilityContext(
        run_id="run-test-1234",
        stage=EngineStage.DISCOVERING,
        component="test_component",
        operation="test_operation",
        operation_id="span-1",
        duration_ms=duration_ms,
        rows=rows,
        cache_hit=cache_hit,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return ObservabilityEvent.create(
        event_code=EventCode.EXTRACTION_COMPLETED,
        message=msg,
        context=ctx,
        presentation_kind=kind,
        error=error,
        progress=progress,
        timestamp=datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC),
    )


def test_rich_narrative_drops_internal_events() -> None:
    """Ensure internal diagnostic events produce zero console output."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    internal_event = _make_event(PresentationKind.INTERNAL, "Secret internal SQL trace")
    sink.emit(internal_event)

    assert sink.rendered_count == 0
    assert output.getvalue() == ""


def test_rich_narrative_renders_step_and_metadata() -> None:
    """Ensure STEP events render with prefix, message, entity badge, and row counts."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    event = _make_event(
        PresentationKind.STEP,
        "Scanned statement files from disk",
        rows=1627,
        entity_type="dir",
        entity_id="Statements",
    )
    sink.emit(event)

    rendered = output.getvalue()
    assert sink.rendered_count == 1
    assert ">> Scanned statement files from disk" in rendered
    assert "[dir:Statements]" in rendered
    assert "(1,627 items)" in rendered


def test_rich_narrative_renders_success_and_duration() -> None:
    """Ensure SUCCESS events format elapsed duration in seconds or milliseconds."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    event_ms = _make_event(PresentationKind.SUCCESS, "Validated schemas", duration_ms=0.79)
    sink.emit(event_ms)

    event_s = _make_event(PresentationKind.SUCCESS, "Phase 1 Complete", duration_ms=2500.0)
    sink.emit(event_s)

    rendered = output.getvalue()
    assert "✓ Validated schemas (0.8ms)" in rendered
    assert "✓ Phase 1 Complete (2.50s)" in rendered


def test_rich_narrative_renders_cache_hit_and_skip() -> None:
    """Ensure SKIP events annotate cache state cleanly."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    event = _make_event(
        PresentationKind.SKIP,
        "USDINR=X fully cached up to target date",
        cache_hit=True,
    )
    sink.emit(event)

    rendered = output.getvalue()
    assert "↷ USDINR=X fully cached up to target date" in rendered
    assert "(cache hit)" in rendered


def test_rich_narrative_failure_renders_actionable_panel_without_stacktrace() -> None:
    """Ensure FAILURE events present actionable diagnostics without raw tracebacks."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    err = ErrorDetails(
        exception_type="DatabaseLockedError",
        exception_message="sqlite3.OperationalError: database is locked",
        failure_domain=FailureDomain.SQLITE_COMMIT,
        traceback_summary='File "raw_store.py", line 42 in execute\nraise DatabaseLockedError',
        retryable=True,
    )
    event = _make_event(
        PresentationKind.FAILURE,
        "Failed to synchronize Raw Store database",
        error=err,
    )
    sink.emit(event)

    rendered = output.getvalue()
    assert "✗ FAILURE: Failed to synchronize Raw Store database" in rendered
    assert "Actionable Diagnostics" in rendered
    assert "Domain: SQLITE_COMMIT" in rendered
    assert "DatabaseLockedError: sqlite3.OperationalError: database is locked" in rendered
    assert "run-test-1234" in rendered
    assert "Transient failure eligible for automatic retry" in rendered
    # Must NOT expose raw traceback frame to normal users
    assert 'File "raw_store.py", line 42' not in rendered


def test_rich_narrative_legacy_status_compatibility() -> None:
    """Ensure backward-compatible rendering for legacy EngineStatusMessage."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    legacy_msg = EngineStatusMessage(
        msg="Initializing Quantitative Master Engine...",
        level=LogLevel.STEP,
        progress=0.1,
    )
    sink.render_status_message(legacy_msg)

    rendered = output.getvalue()
    assert ">> Initializing Quantitative Master Engine..." in rendered
    assert sink.rendered_count == 1


def test_desktop_sink_drops_internal_events() -> None:
    """Ensure DesktopNarrativeSink filters internal events from UI callbacks."""
    log_mock = MagicMock()
    prog_mock = MagicMock()
    sink = DesktopNarrativeSink(log_callback=log_mock, progress_callback=prog_mock)

    internal_event = _make_event(PresentationKind.INTERNAL, "Internal memory probe")
    sink.emit(internal_event)

    assert sink.emitted_count == 0
    log_mock.assert_not_called()
    prog_mock.assert_not_called()


def test_desktop_sink_dispatches_progress_and_tagged_log() -> None:
    """Ensure DesktopNarrativeSink maps kinds to UI tags and invokes progress callbacks."""
    log_mock = MagicMock()
    prog_mock = MagicMock()
    sink = DesktopNarrativeSink(log_callback=log_mock, progress_callback=prog_mock)

    event = _make_event(
        PresentationKind.SUCCESS,
        "Transformed 18 streams",
        progress=0.5,
        duration_ms=1200.0,
    )
    sink.emit(event)

    assert sink.emitted_count == 1
    prog_mock.assert_called_once_with(0.5)
    log_mock.assert_called_once()
    line, tag = log_mock.call_args[0]
    assert tag == "success"
    assert "✓ Transformed 18 streams (1.20s)" in line


def test_desktop_sink_failure_triggers_actionable_error_callback() -> None:
    """Ensure DesktopNarrativeSink triggers error callback with clean actionable summary."""
    log_mock = MagicMock()
    err_mock = MagicMock()
    sink = DesktopNarrativeSink(log_callback=log_mock, error_callback=err_mock)

    err = ErrorDetails(
        exception_type="SchemaViolationError",
        exception_message="Missing mandatory column: transaction_date",
        failure_domain=FailureDomain.SOURCE_VALIDATION,
        traceback_summary="Traceback ... in validate",
        retryable=False,
    )
    event = _make_event(
        PresentationKind.FAILURE,
        "Gatekeeper schema violation detected",
        error=err,
    )
    sink.emit(event)

    assert sink.emitted_count == 1
    err_mock.assert_called_once()
    title, summary = err_mock.call_args[0]
    assert title == "Execution Failure"
    assert "Domain: SOURCE_VALIDATION" in summary
    assert "SchemaViolationError - Missing mandatory column: transaction_date" in summary
    assert "Run ID: run-test-1234" in summary
    assert "Traceback" not in summary


def test_desktop_sink_delegates_to_status_consumer() -> None:
    """Ensure DesktopNarrativeSink delegates to status_consumer when provided."""
    consumer_mock = MagicMock()
    sink = DesktopNarrativeSink(status_consumer=consumer_mock)

    event = _make_event(PresentationKind.STEP, "Processing stage")
    sink.emit(event)

    assert sink.emitted_count == 1
    consumer_mock.assert_called_once_with(event)


def test_format_helpers() -> None:
    """Test format_event_narrative and format_failure_summary functions."""
    event = _make_event(
        PresentationKind.STEP,
        "Calculating ISIN alpha",
        entity_type="ISIN",
        entity_id="INF209K01157",
        rows=147,
        duration_ms=450.0,
    )
    narrative = format_event_narrative(event)
    assert ">> Calculating ISIN alpha [ISIN: INF209K01157] (147 items) (450.0ms)" == narrative

    no_err_event = _make_event(PresentationKind.FAILURE, "Simple failure")
    summary = format_failure_summary(no_err_event)
    assert "Simple failure" in summary
    assert "Run ID: run-test-1234" in summary


def test_base_engine_tab_process_observability_event_step() -> None:
    """Test BaseEngineTab processes ObservabilityEvent STEP without UI instantiation."""
    mock_tab = MagicMock()
    run_btn = MagicMock()

    event = _make_event(
        PresentationKind.STEP,
        "Harmonizing schema feeds",
        progress=0.3,
        duration_ms=15.0,
    )

    BaseEngineTab._process_observability_event(mock_tab, run_btn, event)

    mock_tab._set_progress.assert_called_once_with(0.3)
    mock_tab._log.assert_called_once()
    msg, tag = mock_tab._log.call_args[0]
    assert tag == "step"
    assert ">> Harmonizing schema feeds (15.0ms)" in msg


def test_base_engine_tab_process_observability_event_internal_dropped() -> None:
    """Ensure BaseEngineTab ignores internal events."""
    mock_tab = MagicMock()
    run_btn = MagicMock()

    event = _make_event(PresentationKind.INTERNAL, "Underlying buffer flushed")

    BaseEngineTab._process_observability_event(mock_tab, run_btn, event)

    mock_tab._log.assert_not_called()
    mock_tab._set_progress.assert_not_called()


def test_base_engine_tab_process_observability_event_failure() -> None:
    """Ensure BaseEngineTab shows error dialog and re-enables run button on FAILURE."""
    mock_tab = MagicMock()
    mock_tab._run_btn_text = "▶  Run Pipeline"
    run_btn = MagicMock()

    err = ErrorDetails(
        exception_type="InvariantViolation",
        exception_message="Negative cash balance detected",
        failure_domain=FailureDomain.FINANCIAL_INVARIANT,
        traceback_summary="traceback frame",
        retryable=False,
    )
    event = _make_event(PresentationKind.FAILURE, "Reconciliation failed", error=err)

    with patch(
        "personal_finance_etl.presentation.desktop.base_tab.messagebox.showerror"
    ) as mock_box:
        BaseEngineTab._process_observability_event(mock_tab, run_btn, event)

        mock_tab._log.assert_called_once()
        msg, tag = mock_tab._log.call_args[0]
        assert tag == "error"
        assert "✗ FAILURE: Reconciliation failed" in msg

        run_btn.configure.assert_called_with(state="normal", text="▶  Run Pipeline")
        mock_box.assert_called_once()
        title, text = mock_box.call_args[0]
        assert title == "Execution Failure"
        assert "Domain: FINANCIAL_INVARIANT" in text
        assert "run-test-1234" in text
