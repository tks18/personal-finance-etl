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

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import FailureDomain
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
    event_code: EventCode = EventCode.EXTRACTION_COMPLETED,
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
        event_code=event_code,
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


def test_rich_narrative_skips_empty_progress_message() -> None:
    """Ensure pure progress ticks with empty message do not render empty lines."""
    output = io.StringIO()
    console = Console(file=output, color_system=None, width=120)
    sink = RichNarrativeSink(console=console, show_timestamps=False)

    event = _make_event(
        PresentationKind.PROGRESS,
        "",
        progress=0.45,
    )
    sink.emit(event)

    rendered = output.getvalue()
    assert rendered == ""
    assert sink.rendered_count == 0


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


def test_rich_narrative_suppresses_repetitive_per_entity_success() -> None:
    """Verify RichNarrativeSink suppresses repetitive per-entity ticker/ISIN lines."""
    buf = io.StringIO()
    console = Console(file=buf, color_system=None, width=120)
    sink = RichNarrativeSink(
        console=console, show_timestamps=False, suppress_per_entity_success=True
    )

    event_cached = ObservabilityEvent.create(
        event_code=EventCode.MARKET_TICKER_CACHE_HIT,
        message="USDINR=X fully cached",
        presentation_kind=PresentationKind.STEP,
        progress=0.5,
    )
    sink.emit(event_cached)
    assert sink.rendered_count == 0
    assert buf.getvalue() == ""

    # When suppression is disabled, line is rendered
    sink_verbose = RichNarrativeSink(
        console=console, show_timestamps=False, suppress_per_entity_success=False
    )
    sink_verbose.emit(event_cached)
    assert sink_verbose.rendered_count == 1
    assert "USDINR=X fully cached" in buf.getvalue()


def test_rich_narrative_renders_ticker_failure_even_when_suppression_active() -> None:
    """Verify failed ticker events are always rendered even when per-entity suppression is active."""
    buf = io.StringIO()
    console = Console(file=buf, color_system=None, width=120)
    sink = RichNarrativeSink(
        console=console, show_timestamps=False, suppress_per_entity_success=True
    )

    err = ErrorDetails(
        exception_type="HttpError",
        exception_message="503 Service Unavailable",
        failure_domain=FailureDomain.EXTERNAL_PROVIDER,
        traceback_summary="",
    )
    event_fail = ObservabilityEvent.create(
        event_code=EventCode.MARKET_TICKER_FAILED,
        message="Failed to fetch NVDA",
        presentation_kind=PresentationKind.FAILURE,
        error=err,
    )
    sink.emit(event_fail)
    assert sink.rendered_count == 1
    assert "FAILURE: Failed to fetch NVDA" in buf.getvalue()


def test_desktop_narrative_sink_suppresses_repetitive_per_entity_success() -> None:
    """Verify DesktopNarrativeSink suppresses repetitive per-entity ticks from log callback."""
    log_mock = MagicMock()
    prog_mock = MagicMock()
    sink = DesktopNarrativeSink(
        log_callback=log_mock,
        progress_callback=prog_mock,
        suppress_per_entity_success=True,
    )

    event_cached = ObservabilityEvent.create(
        event_code=EventCode.MARKET_TICKER_CACHE_HIT,
        message="USDINR=X fully cached",
        presentation_kind=PresentationKind.STEP,
        progress=0.45,
    )
    sink.emit(event_cached)
    log_mock.assert_not_called()
    prog_mock.assert_called_once_with(0.45)


def test_narrative_density_within_target_bounds() -> None:
    """Verify standard successful 5-phase run renders within target narrative density (20-42 events)."""
    buf = io.StringIO()
    console = Console(file=buf, color_system=None, width=120)
    sink = RichNarrativeSink(
        console=console, show_timestamps=False, suppress_per_entity_success=True
    )

    milestone_events = [
        _make_event(
            PresentationKind.STEP,
            "Initializing Personal Finance ETL...",
            event_code=EventCode.RUN_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Pipeline execution started.",
            event_code=EventCode.RUN_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 1/5: Discovery & Sync",
            event_code=EventCode.EXTRACTION_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Injected 8 dynamic configuration assets",
            event_code=EventCode.EXTRACTION_COMPLETED,
            rows=8,
        ),
        _make_event(
            PresentationKind.STEP,
            "Initializing extraction from Raw Store payloads...",
            event_code=EventCode.EXTRACTION_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Pulled 0 binary payloads from Raw Store",
            event_code=EventCode.EXTRACTION_BATCH,
            rows=0,
        ),
        _make_event(
            PresentationKind.STEP,
            "Running Gatekeeper Schema Validation...",
            event_code=EventCode.SCHEMA_VALIDATION,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Gatekeeper validated 18 schemas",
            event_code=EventCode.SCHEMA_VALIDATION,
            duration_ms=1.5,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Phase 1 Complete - Actionable streams loaded",
            event_code=EventCode.EXTRACTION_COMPLETED,
            duration_ms=450.0,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 2/5: Upserting new datasets into Bronze Lakehouse",
            event_code=EventCode.BRONZE_UPSERT,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Phase 2 Complete - Bronze layer synchronized",
            event_code=EventCode.BRONZE_UPSERT,
            duration_ms=0.5,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 3/5: Transforming and harmonizing data streams",
            event_code=EventCode.TRANSFORMATION_STAGE,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Phase 3 Complete - DAG mapped 18 base tables",
            event_code=EventCode.TRANSFORMATION_DAG_COMPLETED,
            rows=18,
            duration_ms=620.0,
        ),
        _make_event(
            PresentationKind.STEP,
            "Starting Currency FX Pipeline...",
            event_code=EventCode.MARKET_FETCH_START,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Upserting Delta into Bronze Currency Lake...",
            event_code=EventCode.BRONZE_UPSERT,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Transforming continuous Currency FX series...",
            event_code=EventCode.TRANSFORMATION_STAGE,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Currency FX Pipeline Completed.",
            event_code=EventCode.MARKET_SYNC_COMPLETED,
        ),
        _make_event(
            PresentationKind.STEP,
            "Starting US Market Data Pipeline...",
            event_code=EventCode.MARKET_FETCH_START,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Upserting Delta into Bronze US Market Lake...",
            event_code=EventCode.BRONZE_UPSERT,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Transforming continuous US Market series...",
            event_code=EventCode.TRANSFORMATION_STAGE,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "US Market Pipeline Completed.",
            event_code=EventCode.MARKET_SYNC_COMPLETED,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 3.5: Dynamic Benchmark Extraction...",
            event_code=EventCode.MARKET_FETCH_START,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Upserting Delta into Bronze Benchmark Lake...",
            event_code=EventCode.BRONZE_UPSERT,
        ),
        _make_event(
            PresentationKind.PROGRESS,
            "Transforming Bronze Benchmark Data into Silver...",
            event_code=EventCode.TRANSFORMATION_STAGE,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Benchmark Pipeline Completed.",
            event_code=EventCode.MARKET_SYNC_COMPLETED,
            rows=11784,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 4/5: Executing Advanced Analytics...",
            event_code=EventCode.QUANT_ENGINE_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Starting Investment Quant Engine...",
            event_code=EventCode.QUANT_ENGINE_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Quant Engine initialized context spanning market dates...",
            event_code=EventCode.QUANT_ENGINE_START,
            rows=147,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Processing Complete — generated 13 analytics tables",
            event_code=EventCode.QUANT_POOL_COMPLETED,
            rows=13,
        ),
        _make_event(
            PresentationKind.STEP,
            "Quant Engine mapped 341 open tax lots across portfolio",
            event_code=EventCode.QUANT_LOT_MAPPED,
            rows=341,
        ),
        _make_event(
            PresentationKind.STEP,
            "Executing Tax Engine...",
            event_code=EventCode.TAX_ENGINE_START,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Tax Engine completed — generated 4 tax tables",
            event_code=EventCode.TAX_ENGINE_COMPLETED,
            rows=4,
        ),
        _make_event(
            PresentationKind.STEP,
            "Starting Presentation Layer Engines...",
            event_code=EventCode.PRESENTATION_DAG_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Building core wealth models...",
            event_code=EventCode.WEALTH_ENGINE_START,
        ),
        _make_event(
            PresentationKind.STEP,
            "Starting FIRE Monte Carlo simulation engine...",
            event_code=EventCode.FIRE_ENGINE_START,
            rows=1000,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "FIRE Monte Carlo simulations complete",
            event_code=EventCode.FIRE_ENGINE_COMPLETED,
            rows=2,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Wealth presentation models assembled",
            event_code=EventCode.WEALTH_ENGINE_COMPLETED,
            rows=10,
        ),
        _make_event(
            PresentationKind.STEP,
            "Spawning 10 concurrent Polars streaming graphs...",
            event_code=EventCode.PRESENTATION_DAG_START,
            rows=10,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Phase 4 Complete - Presentation logic built 46 total tables",
            event_code=EventCode.PRESENTATION_DAG_COMPLETED,
            rows=46,
            duration_ms=27800.0,
        ),
        _make_event(
            PresentationKind.STEP,
            "Phase 5/5: Fully replacing Silver and Gold analytical layers",
            event_code=EventCode.GOLD_REPLACE,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Phase 5 Complete - Disk synchronization successful",
            event_code=EventCode.GOLD_REPLACE,
            duration_ms=2110.0,
        ),
        _make_event(
            PresentationKind.SUCCESS,
            "Pipeline Execution Successful in 32.66 seconds.",
            event_code=EventCode.RUN_COMPLETED,
            duration_ms=32660.0,
        ),
    ]

    routine_ticker_events = [
        _make_event(
            PresentationKind.STEP,
            f"TICKER_{i} fully cached",
            event_code=EventCode.MARKET_TICKER_CACHE_HIT,
            progress=i / 20.0,
        )
        for i in range(20)
    ]

    for ev in milestone_events + routine_ticker_events:
        sink.emit(ev)

    assert 20 <= sink.rendered_count <= 45
    assert sink.rendered_count == len(milestone_events)
