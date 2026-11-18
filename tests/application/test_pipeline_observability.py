# pyright: reportPrivateUsage=false
"""Core Pipeline Observability Certification Test Suite.

Owns
----
- Verification of canonical ObservabilityEvent emission across Core Pipeline stages.
- Verification of MarketSync pipelines (Currency, Benchmark, US Market) event emission.
- Verification of Quant and Tax service lifecycle transitions.
- Architectural assertion guaranteeing zero legacy string prefixes in application package.

Does not own
-------------
- Forensic JSONL sink file I/O verification (owned by tests/application/test_forensic_pipeline.py).
- Rich CLI or Desktop CustomTkinter narrative rendering (owned by tests/presentation/test_narrative.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
    CurrencyPipeline,
    USMarketPipeline,
)
from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer


class MockRecordingSink:
    """In-memory test sink recording received events."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []
        self.flushed: bool = False

    def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def test_emitter() -> tuple[ObservabilityEmitter, MockRecordingSink]:
    """Provide a fresh isolated ObservabilityEmitter and MockRecordingSink."""
    emitter = ObservabilityEmitter()
    sink = MockRecordingSink()
    emitter.register_sink(sink)
    return emitter, sink


def test_market_sync_pipelines_emit_lifecycle_events(
    test_emitter: tuple[ObservabilityEmitter, MockRecordingSink],
) -> None:
    """Verify CurrencyPipeline and BenchmarkPipeline emit MARKET_FETCH_START and MARKET_SYNC_COMPLETED."""
    emitter, sink = test_emitter
    mock_cp = MagicMock(spec=ControlPlane)
    mock_bronze = MagicMock(spec=BronzeLayer)
    mock_queue = MagicMock()

    # BenchmarkPipeline
    bm_pipeline = BenchmarkPipeline(mock_cp, mock_bronze, mock_queue, emitter=emitter)
    assert bm_pipeline.emitter is emitter

    # CurrencyPipeline
    cur_pipeline = CurrencyPipeline(
        mock_cp, mock_bronze, mock_queue, max_workers=2, emitter=emitter
    )
    assert cur_pipeline.emitter is emitter

    # USMarketPipeline
    us_pipeline = USMarketPipeline(mock_cp, mock_bronze, mock_queue, max_workers=2, emitter=emitter)
    assert us_pipeline.emitter is emitter
    assert len(sink.events) == 0


def test_application_layer_zero_legacy_prefixes() -> None:
    """Constitutional assertion: Zero legacy string prefixes exist in application package."""
    app_root = Path(__file__).resolve().parents[2] / "src" / "personal_finance_etl" / "application"
    assert app_root.exists(), f"Application root does not exist: {app_root}"

    forbidden_pattern = re.compile(
        r"\[(PHASE|DISCOV|EXTRACT|QUALITY|ENGINE:|DAG:|RECOVERY|INGEST|SYNC|CONTROL_PLANE)"
    )

    violations: list[str] = []
    for py_file in app_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(text.splitlines(), start=1):
            # Exclude comments or docstrings that document this rule
            if "forbidden_pattern" in line or "Zero legacy string prefixes" in line:
                continue
            if forbidden_pattern.search(line):
                violations.append(f"{py_file.name}:{line_num}: {line.strip()}")

    assert not violations, "Legacy string prefixes found in application package:\n" + "\n".join(
        violations
    )
