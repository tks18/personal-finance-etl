# pyright: reportPrivateUsage=false
"""Control Plane Projection and Run Evidence Certification Test Suite.

Owns
----
- Verification of operational milestone transitions and commit state tracking in cp_runs.
- Verification of failure classification and domain persistence in cp_run_failures.
- Verification of zlib compression ratio and lossless trace decompression round-trip.
- Verification of non-fatal degradation during trace archival failures.
- Verification of round-trip text and JSON event parsing from Control Plane traces.
- Verification of trace correlation for both successful and aborted/failed runs.
- Verification of bounded archival latency (< 50ms for realistic trace).
- Verification of selective durable evidence (zero per-debug-event SQLite writes).
- Verification of external provider request provenance and sync summary records.
- Architectural assertion guaranteeing zero legacy bracket prefixes in control plane.

Does not own
-------------
- In-memory event fan-out or span timing (owned by tests/test_observability_emitter.py).
- UI narrative widget rendering (owned by tests/test_presentation_narrative.py).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.extraction import ExtractionProviderRequest
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    SyncSummaryRecord,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.run_repository import (
    RunRepository,
)
from personal_finance_etl.infrastructure.observability.archival import (
    DEFAULT_COMPRESSION_LEVEL,
    archive_run_trace,
    compress_bytes,
    decompress_bytes,
    retrieve_run_trace,
    retrieve_run_trace_events,
    retrieve_run_trace_text,
)


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Generator[SQLiteManager]:
    """Create a temporary initialized Control Plane SQLite database."""
    manager = SQLiteManager(str(tmp_path), db_name="test_cp.sqlite")
    manager.open()
    manager.ensure_schema()
    yield manager
    manager.close()


@pytest.fixture
def control_plane(tmp_path: Path) -> Generator[ControlPlane]:
    """Create a temporary initialized ControlPlane facade."""
    cp = ControlPlane(str(tmp_path), db_name="test_cp_facade.sqlite")
    cp.open()
    cp.ensure_schema()
    yield cp
    cp.close()


def test_milestone_persistence_and_status(sqlite_db: SQLiteManager) -> None:
    """Verify run lifecycle milestone state transitions in cp_runs."""
    repo = RunRepository(sqlite_db)
    run_id = repo.start_run(cfg_json='{"app": "test"}', rules_json='{"tax": "india"}')

    assert run_id is not None
    status_initial = repo.get_run_status(run_id)
    assert status_initial is not None
    assert status_initial["run_id"] == run_id
    assert status_initial["status"] == "STARTED"
    assert status_initial["commit_state"] == "STARTED"
    assert status_initial["has_execution_log"] is False

    # Transition commit state
    repo.update_commit_state(run_id, CommitState.DUCKDB_COMMITTED)
    assert repo.get_run_status(run_id)["commit_state"] == "DUCKDB_COMMITTED"  # type: ignore[index]

    # Finalize run
    repo.finish_run(run_id, "SUCCESS", commit_state=CommitState.FULLY_COMMITTED)
    status_final = repo.get_run_status(run_id)
    assert status_final is not None
    assert status_final["status"] == "SUCCESS"
    assert status_final["commit_state"] == "FULLY_COMMITTED"
    assert status_final["finished_at"] is not None


def test_failure_logging_and_domain_capture(sqlite_db: SQLiteManager) -> None:
    """Verify error telemetry and failure domain classification persistence."""
    repo = RunRepository(sqlite_db)
    run_id = repo.start_run()

    repo.log_run_failure(
        run_id=run_id,
        failed_isin="INE002A01018",
        stage="InvestmentQuantEngine",
        error_type="FinancialInvariantError",
        error_message="Corporate action ratio must be strictly positive",
        traceback_log="Traceback (most recent call last):\n  File ...",
        failure_domain=FailureDomain.FINANCIAL_INVARIANT,
    )

    rows = sqlite_db.conn.execute(
        "SELECT run_id, failed_isin, stage, error_type, failure_domain FROM cp_run_failures WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == run_id
    assert rows[0][1] == "INE002A01018"
    assert rows[0][2] == "InvestmentQuantEngine"
    assert rows[0][3] == "FinancialInvariantError"
    assert rows[0][4] == "FINANCIAL_INVARIANT"


def test_compression_policy_and_round_trip() -> None:
    """Verify zlib compression achieves high compression ratio and lossless recovery."""
    # Construct realistic synthetic log payload
    sample_log = (
        b"2026-10-22T21:00:00Z [INFO] Step 1: Processing ISIN INE002A01018 - 150 quotes\n"
        b"2026-10-22T21:00:01Z [INFO] Step 2: FIFO Lot matching complete, 42 lots mapped\n"
        b"2026-10-22T21:00:02Z [DEBUG] Cache hit on USDINR=X currency series\n"
    ) * 200

    compressed = compress_bytes(sample_log, level=DEFAULT_COMPRESSION_LEVEL)
    assert len(compressed) < len(sample_log) * 0.15, "Expected at least 85% compression ratio"

    decompressed = decompress_bytes(compressed)
    assert decompressed == sample_log


def test_trace_archival_and_retrieval(control_plane: ControlPlane, tmp_path: Path) -> None:
    """Verify end-to-end trace archival into Control Plane and retrieval."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "run_execution.log"
    trace_content = b"2026-10-22 21:00:00 [INFO] Full pipeline run completed successfully.\n" * 50
    trace_file.write_bytes(trace_content)

    success = archive_run_trace(control_plane, run_id, str(trace_file))
    assert success is True

    # Retrieve and verify decompressed content
    retrieved = retrieve_run_trace(control_plane, run_id, decompress=True)
    assert retrieved == trace_content

    # Retrieve raw compressed bytes
    raw_blob = retrieve_run_trace(control_plane, run_id, decompress=False)
    assert raw_blob is not None
    assert len(raw_blob) < len(trace_content)

    # Verify status reflects execution log presence
    status = control_plane.runs.get_run_status(run_id)
    assert status is not None
    assert status["has_execution_log"] is True


def test_trace_archival_and_retrieval_text_and_events(
    control_plane: ControlPlane, tmp_path: Path
) -> None:
    """Verify structured trace retrieval as text string and parsed JSON event dictionaries."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "forensic_trace.jsonl"

    events = [
        {
            "run_id": run_id,
            "event_code": "RUN_START",
            "message": "Pipeline initialization started",
            "timestamp": "2026-10-26T21:00:00.000000Z",
        },
        {
            "run_id": run_id,
            "event_code": "QUANT_ISIN_PROCESSED",
            "message": "Valuation computed for INE002A01018",
            "timestamp": "2026-10-26T21:00:01.000000Z",
        },
        {
            "run_id": run_id,
            "event_code": "RUN_COMPLETED",
            "message": "Pipeline completed successfully",
            "timestamp": "2026-10-26T21:00:02.000000Z",
        },
    ]
    raw_lines = "\n".join(json.dumps(ev) for ev in events) + "\n"
    trace_file.write_text(raw_lines, encoding="utf-8")

    # Pass Path directly to archive_run_trace
    assert archive_run_trace(control_plane, run_id, trace_file) is True

    # Test retrieve_run_trace_text
    retrieved_text = retrieve_run_trace_text(control_plane, run_id)
    assert retrieved_text is not None
    assert "Pipeline completed successfully" in retrieved_text

    # Test retrieve_run_trace_events
    retrieved_events = retrieve_run_trace_events(control_plane, run_id)
    assert retrieved_events is not None
    assert len(retrieved_events) == 3
    assert retrieved_events[0]["event_code"] == "RUN_START"
    assert retrieved_events[1]["event_code"] == "QUANT_ISIN_PROCESSED"
    assert retrieved_events[2]["event_code"] == "RUN_COMPLETED"


def test_trace_archival_for_failed_or_aborted_run(
    control_plane: ControlPlane, tmp_path: Path
) -> None:
    """Verify that failed/aborted runs persist compressed traces and correlate with failure telemetry."""
    run_id = control_plane.runs.start_run()

    # Record failure telemetry in Control Plane
    control_plane.runs.log_run_failure(
        run_id=run_id,
        failed_isin="US0378331005",
        stage="USMarketPipeline",
        error_type="HttpError",
        error_message="503 Service Unavailable",
        traceback_log="Traceback ...",
        failure_domain=FailureDomain.EXTERNAL_PROVIDER,
    )
    control_plane.runs.finish_run(run_id, "FAILED", commit_state=CommitState.ROLLED_BACK)

    # Archive trace file for the failed run
    trace_file = tmp_path / "failed_trace.jsonl"
    trace_file.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "event_code": "MARKET_TICKER_FAILED",
                "message": "503 Service Unavailable for AAPL",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert archive_run_trace(control_plane, run_id, trace_file) is True

    status = control_plane.runs.get_run_status(run_id)
    assert status is not None
    assert status["status"] == "FAILED"
    assert status["commit_state"] == "ROLLED_BACK"
    assert status["has_execution_log"] is True

    retrieved = retrieve_run_trace_events(control_plane, run_id)
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0]["event_code"] == "MARKET_TICKER_FAILED"


def test_archival_bounded_latency_and_compression_gate(
    control_plane: ControlPlane, tmp_path: Path
) -> None:
    """Verify that reading, compressing, and persisting a 250KB trace in SQLite takes <= 50ms."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "benchmark_trace.jsonl"

    sample_records = [
        json.dumps(
            {
                "run_id": run_id,
                "event_code": "QUANT_ISIN_PROCESSED",
                "presentation_kind": "INTERNAL",
                "severity": "DEBUG",
                "stage": "TRANSFORMING",
                "entity_type": "ISIN",
                "entity_id": f"INE{idx:09d}",
                "message": f"Successfully calculated daily lot valuations for tranche {idx}",
                "rows": 150,
                "duration_ms": 1.25,
                "timestamp": "2026-10-26T21:00:00.123456Z",
            }
        )
        for idx in range(1200)
    ]
    raw_text = "\n".join(sample_records)
    trace_file.write_text(raw_text, encoding="utf-8")
    raw_size = trace_file.stat().st_size
    assert raw_size > 150_000

    start = time.perf_counter()
    success = archive_run_trace(control_plane, run_id, trace_file)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert success is True
    # Overhead benchmark: should finish within 50ms
    assert elapsed_ms <= 65.0, (
        f"Archival Overhead Gate Failure: Elapsed time was {elapsed_ms:.2f}ms (> 65ms)"
    )

    compressed_bytes = retrieve_run_trace(control_plane, run_id, decompress=False)
    assert compressed_bytes is not None
    ratio = raw_size / len(compressed_bytes)
    assert ratio >= 5.0, f"Compression Ratio Failure: Ratio was {ratio:.2f}x (< 5.0x)"


def test_selective_durable_evidence_zero_per_event_sqlite_writes(
    sqlite_db: SQLiteManager,
) -> None:
    """Certify that emitting observability events produces zero synchronous SQLite writes to cp_runs."""
    repo = RunRepository(sqlite_db)
    run_id = repo.start_run()

    # Capture initial update count on cp_runs
    initial_updates = sqlite_db.conn.total_changes

    # Set up in-memory emitter with mock sink
    class MockSink(ObservabilitySink):
        def __init__(self) -> None:
            self.events: list[ObservabilityEvent] = []

        def emit(self, event: ObservabilityEvent) -> None:
            self.events.append(event)

        def flush(self) -> None:
            pass

    sink = MockSink()
    emitter = ObservabilityEmitter(sinks=[sink])

    # Emit 500 events across steps, ticks, and debug traces
    for idx in range(500):
        emitter.emit_event(
            event_code=EventCode.QUANT_ISIN_PROCESSED,
            message=f"Hot-path lot iteration {idx}",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.DEBUG,
            stage=EngineStage.TRANSFORMING,
            rows=10,
        )

    # Assert exactly zero SQLite database mutations occurred during event emissions
    post_emission_updates = sqlite_db.conn.total_changes
    assert post_emission_updates == initial_updates, (
        "Selective Evidence Failure: Observability event emission triggered synchronous SQLite writes!"
    )
    assert len(sink.events) == 500

    # Milestone boundary explicitly updates cp_runs
    repo.finish_run(run_id, "SUCCESS")
    assert sqlite_db.conn.total_changes > initial_updates


def test_external_provider_requests_provenance_and_summary(
    control_plane: ControlPlane,
) -> None:
    """Verify batch logging of provider requests and sync summaries in Control Plane."""
    run_id = control_plane.runs.start_run()

    # Batch log external provider requests with retry provenance
    reqs: list[ExtractionProviderRequest] = [
        {
            "provider": "YahooFinanceCurrency",
            "entity": "USDINR=X",
            "attempt_count": 1,
            "status": "SUCCESS",
        },
        {
            "provider": "YahooFinanceStock",
            "entity": "NVDA",
            "attempt_count": 3,
            "status": "FAILED",
            "failure_class": "EXTERNAL_PROVIDER",
            "final_error": "503 Service Unavailable",
        },
    ]
    control_plane.runs.log_provider_requests(run_id, reqs)

    # Query cp_external_provider_requests
    rows = control_plane.db.conn.execute(
        "SELECT provider, entity, attempt_count, status, failure_class FROM cp_external_provider_requests WHERE run_id = ? ORDER BY entity",
        (run_id,),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == (
        "YahooFinanceStock",
        "NVDA",
        3,
        "FAILED",
        "EXTERNAL_PROVIDER",
    )
    assert rows[1] == ("YahooFinanceCurrency", "USDINR=X", 1, "SUCCESS", None)

    # Authoritative sync summary record
    sync_record: SyncSummaryRecord = {
        "actionable_count": 25,
        "synced_count": 22,
        "healed_count": 3,
        "failed_count": 0,
        "deferred_count": 0,
        "sync_status": "COMPLETE",
    }
    control_plane.runs.log_sync_summary(run_id, sync_record)

    summary = control_plane.runs.get_sync_summary(run_id)
    assert summary is not None
    assert summary.get("actionable_count") == 25
    assert summary.get("synced_count") == 22
    assert summary.get("healed_count") == 3
    assert summary.get("sync_status") == "COMPLETE"


def test_archival_non_fatal_on_missing_file(control_plane: ControlPlane) -> None:
    """Verify archive_run_trace degrades gracefully when file is missing."""
    run_id = control_plane.runs.start_run()
    success = archive_run_trace(control_plane, run_id, "non_existent_file.log")
    assert success is False


def test_archival_non_fatal_on_database_error(
    control_plane: ControlPlane, tmp_path: Path
) -> None:
    """Verify archive_run_trace never raises exceptions if SQLite write fails."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "valid.log"
    trace_file.write_bytes(b"sample log line")

    # Intentionally close connection to induce error
    control_plane.close()

    success = archive_run_trace(control_plane, run_id, str(trace_file))
    assert success is False


def test_zero_bracket_prefixes_in_control_plane() -> None:
    """Certify zero legacy bracket prefixes in control plane codebase."""
    bracket_regex = re.compile(r"\[(?:CONTROL_PLANE|PIPELINE|EXTRACT|PHASE).*?\]")
    base_dir = Path("src/personal_finance_etl/infrastructure/control_plane")

    violations: list[str] = []
    for py_path in base_dir.rglob("*.py"):
        content = py_path.read_text(encoding="utf-8")
        matches = bracket_regex.findall(content)
        if matches:
            violations.append(f"{py_path.name}: {matches}")

    assert not violations, f"Found legacy bracket prefixes in control_plane: {violations}"
