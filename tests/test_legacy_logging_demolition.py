"""Legacy Logging Demolition and Live JSONL Production Certification Test Suite.

Owns
----
- Verification of QueueStream raw forwarding without string-based level inference.
- Verification of infer_log_level clean boolean routing.
- Verification of live RunLifecycleCoordinator JSONL forensic sink attachment and lifecycle.
- Verification that generated trace files are queryable natively via Polars (pl.read_ndjson).
- Verification of Control Plane trace archival using the generated JSONL file.
- Static codebase assertions confirming complete elimination of legacy bracket prefixes.

Does not own
-------------
- Presentation narrative formatting (owned by tests/test_presentation_narrative.py).
- Redaction pattern benchmarks (owned by tests/test_redaction_and_retention.py).
"""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl

from personal_finance_etl.application.observability import ObservabilityEmitter
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.application.pipeline.worker import (
    QueueStream,
    WorkerPoolCoordinator,
    infer_log_level,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability.archival import retrieve_run_trace
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


class _MockStatusQueue:
    """Mock queue capturing ObservabilityEvent instances for testing."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def put(
        self,
        status: object,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        del block, timeout
        if isinstance(status, ObservabilityEvent):
            self.events.append(status)


def test_queue_stream_demolition_of_string_inference() -> None:
    """Verify QueueStream routes raw stdout/stderr without string-based guessing."""
    mock_q = _MockStatusQueue()
    stdout_stream = QueueStream(mock_q, is_error=False)

    stdout_stream.write("Processing dataset batch 1...\n")
    stdout_stream.write("Error occurred inside inner calculation\n")
    stdout_stream.write("Warning: memory threshold exceeded\n")
    stdout_stream.write("Complete: [GATE] Verified 18 schemas\n")
    stdout_stream.flush()

    assert len(mock_q.events) == 4
    for event in mock_q.events:
        assert event.severity == DiagnosticSeverity.INFO
        assert event.event_code == EventCode.RAW_STDOUT

    stderr_mock_q = _MockStatusQueue()
    stderr_stream = QueueStream(stderr_mock_q, is_error=True)
    stderr_stream.write("Fatal crash during network socket binding\n")
    stderr_stream.flush()

    assert len(stderr_mock_q.events) == 1
    assert stderr_mock_q.events[0].severity == DiagnosticSeverity.ERROR
    assert stderr_mock_q.events[0].event_code == EventCode.RAW_STDERR


def test_infer_log_level_boolean_routing() -> None:
    """Verify infer_log_level relies strictly on is_error boolean flag."""
    assert infer_log_level("Error: fatal disk corruption", is_error=False) == LogLevel.INFO
    assert infer_log_level("Normal status check", is_error=False) == LogLevel.INFO
    assert infer_log_level("Success!", is_error=True) == LogLevel.ERROR
    assert infer_log_level("", is_error=True) == LogLevel.ERROR


def test_worker_pool_coordinator_queue_item_parsing() -> None:
    """Verify WorkerPoolCoordinator parses queue items into canonical ObservabilityEvent."""
    canonical = ObservabilityEvent.create(
        event_code=EventCode.RAW_STDOUT,
        message="Market ticker sync complete",
        progress=0.5,
    )
    event1 = WorkerPoolCoordinator._parse_queue_item(canonical)  # pyright: ignore[reportPrivateUsage]
    assert event1 is canonical

    event2 = WorkerPoolCoordinator._parse_queue_item("Raw status string")  # pyright: ignore[reportPrivateUsage]
    assert isinstance(event2, ObservabilityEvent)
    assert event2.message == "Raw status string"
    assert event2.severity == DiagnosticSeverity.INFO


def test_lifecycle_coordinator_live_jsonl_production_and_archival(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator attaches live JSONL sink, writes trace, and archives it."""
    cfg = Settings()
    cfg.TARGET_DB_BASE_PATH = str(tmp_path)
    cfg.RAW_DOCUMENT_STORE_NAME = "raw_store.db"
    cfg.LOGS_DIRECTORY = "logs/runs"

    db_path = str(tmp_path / "test_warehouse.duckdb")
    db_mgr = DuckDBManager(db_path)
    mock_q = _MockStatusQueue()
    rules = FinancialRules.from_toml(Path("tests/financial_rules.toml"))
    emitter = ObservabilityEmitter()

    coordinator = RunLifecycleCoordinator(
        cfg=cfg,
        status_queue=mock_q,
        db_manager=db_mgr,
        rules=rules,
        emitter=emitter,
    )

    cp, run_id, _ = coordinator.initialize()
    assert coordinator.forensic_file_path is not None
    assert coordinator.forensic_sink is not None
    assert coordinator.forensic_file_path.name == f"trace_{run_id}.jsonl"

    emitter.emit_event(
        event_code=EventCode.DISCOVERY_START,
        message="Scanned 42 financial statements from disk",
        presentation_kind=PresentationKind.STEP,
        stage=EngineStage.DISCOVERING,
        rows=42,
    )
    emitter.emit_event(
        event_code=EventCode.SCHEMA_VALIDATION,
        message="Schema validation complete with 0 violations",
        presentation_kind=PresentationKind.SUCCESS,
        stage=EngineStage.EXTRACTING,
        rows=18,
    )

    coordinator.commit()
    coordinator.teardown()

    assert coordinator.forensic_sink is None
    assert coordinator.forensic_file_path.exists()
    assert coordinator.forensic_file_path.stat().st_size > 0

    trace_df = pl.read_ndjson(coordinator.forensic_file_path)
    assert trace_df.height >= 2
    assert "event_code" in trace_df.columns
    assert "message" in trace_df.columns

    event_codes = trace_df["event_code"].to_list()
    assert EventCode.DISCOVERY_START.value in event_codes
    assert EventCode.SCHEMA_VALIDATION.value in event_codes

    cp.open()
    archived_bytes = retrieve_run_trace(cp, run_id)
    assert archived_bytes is not None
    assert len(archived_bytes) > 0

    decompressed_text = archived_bytes.decode("utf-8")
    assert "Scanned 42 financial statements from disk" in decompressed_text
    cp.close()


def test_static_absence_of_legacy_bracket_prefixes() -> None:
    """Verify static absence of obsolete bracket prefixes and helper functions across src/."""
    src_dir = Path("src/personal_finance_etl")
    prohibited_prefixes = [
        "[BRONZE",
        "[SCHEMA]",
        "[SYNC:",
        "[INGEST:",
        "[ARTIFACT]",
        "[DATABASE:",
    ]

    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        parsed = ast.parse(content, filename=str(py_file))

        for node in ast.walk(parsed):
            if isinstance(node, ast.FunctionDef) and node.name in (
                "_is_step_log",
                "_is_success_log",
            ):
                raise AssertionError(
                    f"Found obsolete string inspection function {node.name} in {py_file}"
                )

        # Check for legacy logging prefixes in string literals
        for prefix in prohibited_prefixes:
            if prefix in content:
                # Exclude comments or docstrings that mention the transition
                lines = [
                    line
                    for line in content.splitlines()
                    if prefix in line and not line.strip().startswith("#")
                ]
                if lines:
                    raise AssertionError(
                        f"Found prohibited legacy prefix '{prefix}' in {py_file}:\n"
                        + "\n".join(lines[:3])
                    )
