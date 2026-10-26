"""Unit tests for Phase 3 forensic debug pipeline, async queue listeners, and Polars queryability.

Owns
----
- Testing JsonlForensicSink append-only file persistence and single-writer file integrity.
- Testing AsyncObservabilityListener background daemon thread queue draining and shutdown.
- Validating direct Polars ndjson queryability, schema inference, and unnested context analysis.
- Multi-processing queue coordination and child worker log collection.
- Settings configuration for forensic log paths and retention count.
"""

from __future__ import annotations

import multiprocessing
import queue
import time
from pathlib import Path

import polars as pl

from personal_finance_etl.application.observability import ObservabilityEmitter
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts import (
    DiagnosticSeverity,
    EngineStage,
    ErrorDetails,
    EventCode,
    EventOutcome,
    FailureDomain,
    ObservabilityContext,
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import (
    AsyncObservabilityListener,
    JsonlForensicSink,
    ObservabilityQueueSink,
    create_forensic_pipeline,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


def test_settings_log_configuration(tmp_path: Path) -> None:
    """Verify Settings defines default log directory and retention, resolving relative paths."""
    cfg = Settings()
    assert cfg.LOGS_DIRECTORY == "logs/runs"
    assert cfg.RETAIN_LAST_N_RUNS == 12

    # Without target base path
    assert cfg.resolve_logs_dir() == Path("logs/runs")

    # With target base path
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    assert cfg.resolve_logs_dir() == tmp_path / "logs/runs"


def test_jsonl_forensic_sink_direct_write_and_polars_read(tmp_path: Path) -> None:
    """Verify JsonlForensicSink writes append-only JSONL files readable directly by Polars."""
    log_file = tmp_path / "forensic_trace.jsonl"
    sink = JsonlForensicSink(log_file)

    ctx1 = ObservabilityContext(
        run_id="run-forensic-01",
        stage=EngineStage.DISCOVERING,
        component="coordinator",
        operation="scan_files",
        rows=1627,
        duration_ms=12.4,
    )
    event1 = ObservabilityEvent.create(
        event_code=EventCode.DISCOVERY_COMPLETED,
        message="Scanned 1627 active statement files.",
        context=ctx1,
    )

    err = ErrorDetails(
        exception_type="FileNotFoundError",
        exception_message="Missing statement file",
        failure_domain=FailureDomain.SOURCE_DISCOVERY,
        traceback_summary="Traceback: line 12",
    )
    event2 = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Discovery halted.",
        context=ctx1,
        severity=DiagnosticSeverity.ERROR,
        presentation_kind=PresentationKind.FAILURE,
        outcome=EventOutcome.FAILED,
        error=err,
    )

    sink.emit(event1)
    sink.emit(event2)
    sink.close()

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    # Verify Polars direct ndjson reading
    df = pl.read_ndjson(log_file)
    assert df.height == 2
    assert "event_code" in df.columns
    assert "context" in df.columns
    assert "message" in df.columns

    # Unnest context for structured analytics
    unnested = df.unnest("context")
    assert "run_id" in unnested.columns
    assert "rows" in unnested.columns
    assert "duration_ms" in unnested.columns

    rows_val = unnested.filter(pl.col("event_code") == "DISCOVERY_COMPLETED")["rows"].item()
    assert rows_val == 1627


def test_async_observability_listener_queue_drain(tmp_path: Path) -> None:
    """Verify AsyncObservabilityListener consumes queued events and flushes to sinks."""
    log_file = tmp_path / "async_trace.jsonl"
    file_sink = JsonlForensicSink(log_file)

    event_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()
    queue_sink = ObservabilityQueueSink(event_queue)

    listener = AsyncObservabilityListener(event_queue, sinks=[file_sink])
    listener.start()

    ctx = ObservabilityContext(run_id="run-async-01", stage=EngineStage.TRANSFORMING)
    for i in range(25):
        ev = ObservabilityEvent.create(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message=f"Transformed chunk {i}",
            context=ctx,
        )
        queue_sink.emit(ev)

    listener.stop(timeout=3.0)

    # All 25 events must be drained and written
    assert log_file.exists()
    df = pl.read_ndjson(log_file)
    assert df.height == 25


def _mp_worker(
    worker_id: int,
    out_queue: multiprocessing.Queue[ObservabilityEvent | None],
) -> None:
    """Child worker process emitting events to the shared queue."""
    sink = ObservabilityQueueSink(out_queue)
    ctx = ObservabilityContext(
        run_id="run-mp-01",
        stage=EngineStage.ANALYZING,
        component="quant_worker",
        worker_id=f"worker-{worker_id}",
    )
    for i in range(5):
        ev = ObservabilityEvent.create(
            event_code=EventCode.QUANT_ISIN_PROCESSED,
            message=f"Worker {worker_id} processed ISIN batch {i}",
            context=ctx,
        )
        sink.emit(ev)


def test_multiprocessing_queue_listener(tmp_path: Path) -> None:
    """Verify multi-process worker logs are successfully gathered and persisted."""
    log_file = tmp_path / "mp_trace.jsonl"
    file_sink = JsonlForensicSink(log_file)

    mp_queue: multiprocessing.Queue[ObservabilityEvent | None] = multiprocessing.Queue()
    listener = AsyncObservabilityListener(mp_queue, sinks=[file_sink])
    listener.start()

    procs: list[multiprocessing.Process] = []
    for w in range(2):
        p = multiprocessing.Process(target=_mp_worker, args=(w, mp_queue))
        p.start()
        procs.append(p)

    for p in procs:
        p.join(timeout=5.0)

    # Let queue flush
    time.sleep(0.1)
    listener.stop(timeout=3.0)

    assert log_file.exists()
    df = pl.read_ndjson(log_file)
    # 2 workers * 5 events = 10 events
    assert df.height == 10
    unnested = df.unnest("context")
    workers_found = set(unnested["worker_id"].to_list())
    assert workers_found == {"worker-0", "worker-1"}


def test_async_observability_listener_is_alive_and_flush(tmp_path: Path) -> None:
    """Verify is_alive reflects thread state and flush executes on all sinks."""
    log_file = tmp_path / "lifecycle_trace.jsonl"
    file_sink = JsonlForensicSink(log_file, buffer_size=100)
    event_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()

    listener = AsyncObservabilityListener(event_queue, sinks=[file_sink])
    assert not listener.is_alive()

    listener.start()
    assert listener.is_alive()

    ctx = ObservabilityContext(run_id="run-flush-01")
    event = ObservabilityEvent.create(
        event_code=EventCode.DISCOVERY_START,
        message="Discovery init",
        context=ctx,
    )
    event_queue.put(event)

    time.sleep(0.1)

    listener.flush()
    assert log_file.exists()
    assert log_file.stat().st_size > 0

    listener.stop(timeout=3.0)
    assert not listener.is_alive()


def test_async_observability_listener_immediate_flush_on_error_or_failure(tmp_path: Path) -> None:
    """Verify listener flushes sinks immediately upon encountering ERROR or FAILED events."""
    log_file = tmp_path / "error_flush_trace.jsonl"
    file_sink = JsonlForensicSink(log_file, buffer_size=200)
    event_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()
    queue_sink = ObservabilityQueueSink(event_queue)

    listener = AsyncObservabilityListener(event_queue, sinks=[file_sink])
    listener.start()

    ctx = ObservabilityContext(run_id="run-err-01")
    info_event = ObservabilityEvent.create(
        event_code=EventCode.DISCOVERY_START,
        message="Standard info event",
        context=ctx,
        severity=DiagnosticSeverity.INFO,
    )
    queue_sink.emit(info_event)
    time.sleep(0.1)

    err = ErrorDetails(
        exception_type="RuntimeError",
        exception_message="Fatal processing failure",
        failure_domain=FailureDomain.WORKER,
        traceback_summary="Traceback: line 10",
    )
    error_event = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Fatal pipeline error",
        context=ctx,
        severity=DiagnosticSeverity.ERROR,
        outcome=EventOutcome.FAILED,
        error=err,
    )
    queue_sink.emit(error_event)

    time.sleep(0.15)

    assert log_file.exists()
    df = pl.read_ndjson(log_file)
    assert df.height == 2

    listener.stop(timeout=3.0)


class _MockStatusQueue:
    """Mock queue capturing status items."""

    def put(
        self,
        status: object,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        del status, block, timeout


def test_run_lifecycle_coordinator_async_pipeline_wiring(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator wires queue sink to emitter and drains on teardown."""
    cfg = Settings()
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    cfg.TARGET_DB_NAME = "async_test.duckdb"
    cfg.RAW_DOCUMENT_STORE_NAME = "async_test_raw.db"
    cfg.LOGS_DIRECTORY = "logs/runs"

    db_path = str(tmp_path / "async_test.duckdb")
    db_mgr = DuckDBManager(db_path)
    mock_q = _MockStatusQueue()
    emitter = ObservabilityEmitter()

    coordinator = RunLifecycleCoordinator(
        cfg=cfg,
        status_queue=mock_q,
        db_manager=db_mgr,
        emitter=emitter,
    )

    _cp, run_id, _ = coordinator.initialize()

    assert coordinator.forensic_sink is not None
    assert isinstance(coordinator.forensic_sink, JsonlForensicSink)
    assert coordinator.async_listener is not None
    assert coordinator.async_listener.is_alive()
    assert coordinator.queue_sink is not None
    assert coordinator.queue_sink in emitter._sinks  # pyright: ignore[reportPrivateUsage]
    assert coordinator.forensic_sink not in emitter._sinks  # pyright: ignore[reportPrivateUsage]

    emitter.emit_event(
        event_code=EventCode.DISCOVERY_START,
        message="Scanning 100 statements",
        presentation_kind=PresentationKind.STEP,
        rows=100,
    )
    emitter.emit_event(
        event_code=EventCode.EXTRACTION_COMPLETED,
        message="Extraction finished cleanly",
        presentation_kind=PresentationKind.SUCCESS,
        rows=100,
    )

    coordinator.commit()
    coordinator.teardown()

    assert coordinator.forensic_sink is None
    assert coordinator.queue_sink is None
    assert coordinator.async_listener is None
    assert len(emitter._sinks) == 0  # pyright: ignore[reportPrivateUsage]

    trace_file = tmp_path / "logs" / "runs" / f"trace_{run_id}.jsonl"
    assert trace_file.exists()
    df = pl.read_ndjson(trace_file)
    event_codes = df["event_code"].to_list()
    assert EventCode.DISCOVERY_START.value in event_codes
    assert EventCode.EXTRACTION_COMPLETED.value in event_codes
    assert EventCode.SYSTEM_TEARDOWN.value in event_codes


class _FailingSink(ObservabilitySink):
    """Sink that deliberately raises exceptions during emit and flush."""

    def emit(self, event: ObservabilityEvent) -> None:
        del event
        raise OSError("Simulated disk device failure")

    def flush(self) -> None:
        raise OSError("Simulated flush write error")


def test_sink_failure_resilience(tmp_path: Path) -> None:
    """Verify sink exceptions do not terminate listener thread or crash the pipeline."""
    del tmp_path
    failing_sink = _FailingSink()
    event_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()
    queue_sink = ObservabilityQueueSink(event_queue)

    listener = AsyncObservabilityListener(event_queue, sinks=[failing_sink])
    listener.start()

    ctx = ObservabilityContext(run_id="run-resilience-01")
    for i in range(10):
        ev = ObservabilityEvent.create(
            event_code=EventCode.GENERIC_DIAGNOSTIC,
            message=f"Event {i}",
            context=ctx,
        )
        queue_sink.emit(ev)

    err_ev = ObservabilityEvent.create(
        event_code=EventCode.RUN_FAILED,
        message="Error event during disk error",
        context=ctx,
        severity=DiagnosticSeverity.ERROR,
    )
    queue_sink.emit(err_ev)

    time.sleep(0.1)
    assert listener.is_alive()

    listener.stop(timeout=2.0)
    assert not listener.is_alive()


def test_high_volume_burst_drain_zero_loss(tmp_path: Path) -> None:
    """Verify zero event loss when draining a high-volume burst of events during shutdown."""
    log_file = tmp_path / "burst_trace.jsonl"
    file_sink = JsonlForensicSink(log_file, buffer_size=50)
    event_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()
    queue_sink = ObservabilityQueueSink(event_queue)

    listener = AsyncObservabilityListener(event_queue, sinks=[file_sink])
    listener.start()

    total_events = 500
    for i in range(total_events):
        ctx = ObservabilityContext(run_id="run-burst-01", rows=i)
        ev = ObservabilityEvent.create(
            event_code=EventCode.QUANT_ISIN_PROCESSED,
            message=f"Processed ISIN batch {i}",
            context=ctx,
        )
        queue_sink.emit(ev)

    listener.stop(timeout=5.0)

    assert log_file.exists()
    df = pl.read_ndjson(log_file)
    assert df.height == total_events


def test_create_forensic_pipeline_helper(tmp_path: Path) -> None:
    """Verify create_forensic_pipeline constructs properly wired queue, listener, and sink."""
    log_file = tmp_path / "helper_trace.jsonl"
    q_sink, listener, f_sink = create_forensic_pipeline(log_file, buffer_size=25)

    assert isinstance(q_sink, ObservabilityQueueSink)
    assert isinstance(listener, AsyncObservabilityListener)
    assert isinstance(f_sink, JsonlForensicSink)
    assert f_sink in listener.sinks
    assert f_sink.buffer_size == 25

