"""Tests verifying Phase 6 EngineStatusMessage complete eradication and status queue unification.

Owns
----
- Verification that zero EngineStatusMessage references exist anywhere in production src/.
- Verification that EngineStatusMessage is eradicated from contracts.
- Verification of QueueStream emitting canonical ObservabilityEvents for stdout and stderr.
- Verification of WorkerPoolCoordinator parsing queue items into pure ObservabilityEvents.
- Verification of facade and presentation surfaces accepting pure ObservabilityEvents.

Does not own
-------------
- Data transport and DataFrame payload isolation (owned by test_data_transport).
- Forensic JSONL file serialization (owned by test_observability_certification).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import personal_finance_etl.contracts as contracts
import personal_finance_etl.contracts.application as app_contracts
import personal_finance_etl.contracts.observability as obs_contracts
from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.pipeline.worker import (
    QueueStream,
    WorkerPoolCoordinator,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)


class _AstSymbolFinder(ast.NodeVisitor):
    """AST visitor collecting all references to EngineStatusMessage."""

    def __init__(self) -> None:
        self.locations: list[tuple[int, int]] = []

    def visit_Name(self, node: ast.Name) -> None:
        """Inspect name references."""
        if node.id == "EngineStatusMessage":
            self.locations.append((node.lineno, node.col_offset))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Inspect attribute references."""
        if node.attr == "EngineStatusMessage":
            self.locations.append((node.lineno, node.col_offset))
        self.generic_visit(node)


def test_zero_engine_status_message_references_in_production() -> None:
    """Verify zero references to EngineStatusMessage exist across entire src/ codebase."""
    src_root = Path("src/personal_finance_etl")
    violations: list[str] = []

    for py_file in src_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        finder = _AstSymbolFinder()
        finder.visit(tree)

        for lineno, col in finder.locations:
            violations.append(f"{py_file}:{lineno}:{col}")

    assert not violations, (
        f"Found {len(violations)} surviving EngineStatusMessage references in production code:\n"
        + "\n".join(violations)
    )


def test_engine_status_message_eradicated_from_contracts() -> None:
    """Verify EngineStatusMessage is completely eradicated from contracts package."""
    assert not hasattr(contracts, "EngineStatusMessage")
    assert not hasattr(app_contracts, "EngineStatusMessage")
    assert not hasattr(obs_contracts, "EngineStatusMessage")


def test_queue_stream_emits_canonical_observability_events() -> None:
    """Verify QueueStream writes produce canonical ObservabilityEvents with appropriate severities."""

    class _CaptureQueue:
        def __init__(self) -> None:
            self.events: list[ObservabilityEvent] = []

        def put(
            self,
            status: Any,
            /,
            block: bool = True,
            timeout: float | None = None,
        ) -> None:
            del block, timeout
            if isinstance(status, ObservabilityEvent):
                self.events.append(status)

    mock_q = _CaptureQueue()
    stdout_stream = QueueStream(mock_q, is_error=False)
    stdout_stream.write("Ingesting bronze lakehouse entities...\n")
    stdout_stream.flush()

    assert len(mock_q.events) == 1
    event = mock_q.events[0]
    assert isinstance(event, ObservabilityEvent)
    assert event.event_code == EventCode.RAW_STDOUT
    assert event.severity == DiagnosticSeverity.INFO
    assert event.outcome == EventOutcome.COMPLETED
    assert event.presentation_kind == PresentationKind.PROGRESS
    assert event.message == "Ingesting bronze lakehouse entities..."

    mock_err_q = _CaptureQueue()
    stderr_stream = QueueStream(mock_err_q, is_error=True)
    stderr_stream.write("Execution failed during network fetch\n")
    stderr_stream.flush()

    assert len(mock_err_q.events) == 1
    err_event = mock_err_q.events[0]
    assert isinstance(err_event, ObservabilityEvent)
    assert err_event.event_code == EventCode.RAW_STDERR
    assert err_event.severity == DiagnosticSeverity.ERROR
    assert err_event.outcome == EventOutcome.FAILED
    assert err_event.presentation_kind == PresentationKind.PROGRESS
    assert err_event.message == "Execution failed during network fetch"


def test_worker_pool_coordinator_queue_parsing_unification() -> None:
    """Verify WorkerPoolCoordinator._parse_queue_item handles events and objects cleanly."""
    # 1. Existing canonical event passed through unchanged
    canonical = ObservabilityEvent.create(
        event_code=EventCode.RUN_START,
        message="Starting test run",
        progress=0.0,
    )
    res1 = WorkerPoolCoordinator._parse_queue_item(canonical)  # pyright: ignore[reportPrivateUsage]
    assert res1 is canonical

    # 2. Raw string wrapped into canonical ObservabilityEvent
    res2 = WorkerPoolCoordinator._parse_queue_item("Worker thread heartbeat")  # pyright: ignore[reportPrivateUsage]
    assert isinstance(res2, ObservabilityEvent)
    assert res2.message == "Worker thread heartbeat"
    assert res2.severity == DiagnosticSeverity.INFO


def test_facade_on_status_protocol() -> None:
    """Verify PersonalFinanceEngine async execution contract expects pure ObservabilityEvent."""
    sig = inspect.signature(PersonalFinanceEngine.run_pipeline_async)
    on_status_param = sig.parameters.get("on_status")
    assert on_status_param is not None
    type_annot = str(on_status_param.annotation)
    assert "ObservabilityEvent" in type_annot
    assert "EngineStatusMessage" not in type_annot
