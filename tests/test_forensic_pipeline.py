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
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import (
    AsyncObservabilityListener,
    JsonlForensicSink,
    ObservabilityQueueSink,
)


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
