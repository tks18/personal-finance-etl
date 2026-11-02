# pyright: reportPrivateUsage=false
"""Provider, Worker Diagnostics, and Hot-Loop Silence Certification.

Owns
----
- Verification of typed ObservabilityEvent emission across Market providers (Benchmark, Currency, US Market).
- Verification of Cache Hit, Success, and Failure event context contracts.
- Verification of hot-loop silence across Quant IsinProcessor and Worker tasks.
- Architectural assertion guaranteeing zero legacy bracket prefixes in providers and workers.

Does not own
-------------
- General core pipeline events (owned by tests/test_core_pipeline_observability.py).
- Forensic JSONL sink file I/O verification (owned by tests/test_forensic_pipeline.py).
"""

from __future__ import annotations

import ast
import queue
import re
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.providers.market.benchmark import BenchmarkExtractor
from personal_finance_etl.infrastructure.providers.market.currency import CurrencyExtractor
from personal_finance_etl.infrastructure.providers.market.us_market import USMarketExtractor


@pytest.fixture
def mock_control_plane() -> MagicMock:
    """Provide a mock ControlPlane facade."""
    return MagicMock(spec=ControlPlane)


def test_benchmark_extractor_emits_structured_events(mock_control_plane: MagicMock) -> None:
    """Verify BenchmarkExtractor emits typed ObservabilityEvent instances."""
    status_q: queue.Queue[object] = queue.Queue()
    extractor = BenchmarkExtractor(cp=mock_control_plane, status_queue=status_q)
    batch = ExtractionBatchResult(
        provider="Yahoo Finance",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    all_new_data: list[pl.DataFrame] = []

    # 1. Cache hit
    cached_res = ExtractorEntityResult(
        entity="^NSEI",
        status=ExtractorEntityStatus.CACHED,
        message="^NSEI fully cached up to 2025-01-10",
        attempt_count=0,
        requested_start=date(2025, 1, 1),
        requested_end=date(2025, 1, 10),
    )
    extractor._record_future_result(cached_res, batch, all_new_data, 0.2)
    ev_cached = status_q.get_nowait()
    assert isinstance(ev_cached, ObservabilityEvent)
    assert ev_cached.event_code == EventCode.MARKET_TICKER_CACHE_HIT
    assert ev_cached.context.cache_hit is True
    assert ev_cached.context.entity_id == "^NSEI"
    assert ev_cached.presentation_kind == PresentationKind.STEP

    # 2. Success with data
    df_data = pl.DataFrame({"Date": [date(2025, 1, 2)], "Close": [24000.0]})
    success_res = ExtractorEntityResult(
        entity="^NDX",
        status=ExtractorEntityStatus.SUCCESS,
        message="API Fetched ^NDX",
        df=df_data,
        attempt_count=1,
        requested_start=date(2025, 1, 1),
        requested_end=date(2025, 1, 10),
    )
    extractor._record_future_result(success_res, batch, all_new_data, 0.5)
    ev_success = status_q.get_nowait()
    assert isinstance(ev_success, ObservabilityEvent)
    assert ev_success.event_code == EventCode.MARKET_TICKER_SUCCESS
    assert ev_success.context.rows == 1
    assert ev_success.outcome == EventOutcome.COMPLETED
    assert ev_success.presentation_kind == PresentationKind.SUCCESS

    # 3. Failure
    failed_res = ExtractorEntityResult(
        entity="^CRSLDX",
        status=ExtractorEntityStatus.FAILED,
        message="HTTP 500 Connection Timeout",
        attempt_count=3,
        requested_start=date(2025, 1, 1),
        requested_end=date(2025, 1, 10),
    )
    extractor._record_future_result(failed_res, batch, all_new_data, 0.9)
    ev_failed = status_q.get_nowait()
    assert isinstance(ev_failed, ObservabilityEvent)
    assert ev_failed.event_code == EventCode.MARKET_TICKER_FAILED
    assert ev_failed.severity == DiagnosticSeverity.ERROR
    assert ev_failed.presentation_kind == PresentationKind.FAILURE


def test_currency_extractor_emits_structured_events(mock_control_plane: MagicMock) -> None:
    """Verify CurrencyExtractor emits typed ObservabilityEvent instances."""
    status_q: queue.Queue[object] = queue.Queue()
    extractor = CurrencyExtractor(cp=mock_control_plane, status_queue=status_q)
    batch = ExtractionBatchResult(
        provider="Yahoo Finance",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    all_new_data: list[pl.DataFrame] = []

    # Cache hit
    cached_res = ExtractorEntityResult(
        entity="USDINR=X",
        status=ExtractorEntityStatus.CACHED,
        message="USDINR=X fully cached up to 2025-01-10",
        attempt_count=0,
        requested_start=date(2025, 1, 1),
        requested_end=date(2025, 1, 10),
    )
    extractor._record_future_result(cached_res, batch, all_new_data, 0.3)
    ev_cached = status_q.get_nowait()
    assert isinstance(ev_cached, ObservabilityEvent)
    assert ev_cached.event_code == EventCode.MARKET_TICKER_CACHE_HIT
    assert ev_cached.context.cache_hit is True
    assert ev_cached.context.entity_id == "USDINR=X"


def test_us_market_extractor_emits_structured_events(mock_control_plane: MagicMock) -> None:
    """Verify USMarketExtractor emits typed ObservabilityEvent instances."""
    status_q: queue.Queue[object] = queue.Queue()
    extractor = USMarketExtractor(cp=mock_control_plane, status_queue=status_q)
    batch = ExtractionBatchResult(
        provider="Yahoo Finance",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    all_new_data: list[pl.DataFrame] = []

    # Cache hit
    cached_res = ExtractorEntityResult(
        entity="NVDA (US67066G1040)",
        status=ExtractorEntityStatus.CACHED,
        message="NVDA fully cached up to 2025-01-10",
        attempt_count=0,
        requested_start=date(2025, 1, 1),
        requested_end=date(2025, 1, 10),
    )
    extractor._record_future_result(cached_res, batch, all_new_data, 0.4)
    ev_cached = status_q.get_nowait()
    assert isinstance(ev_cached, ObservabilityEvent)
    assert ev_cached.event_code == EventCode.MARKET_TICKER_CACHE_HIT
    assert ev_cached.context.cache_hit is True
    assert ev_cached.context.entity_id == "NVDA (US67066G1040)"


def test_isin_processor_hot_loop_silence() -> None:
    """Ensure zero logging calls exist inside per-quote iteration loops of IsinProcessor."""
    processor_path = Path(
        "src/personal_finance_etl/application/investments/isin_service/processor.py"
    )
    tree = ast.parse(processor_path.read_text(encoding="utf-8"))

    # Traverse AST and locate IsinProcessor.process method
    process_func: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "IsinProcessor":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "process":
                    process_func = item
                    break

    assert process_func is not None, "IsinProcessor.process method not found"

    # Walk all loops inside process() and ensure no diagnostic emission occurs.
    forbidden_diagnostic_calls: list[str] = []
    for node in ast.walk(process_func):
        if isinstance(node, (ast.For, ast.While)):
            for loop_child in ast.walk(node):
                if isinstance(loop_child, ast.Call):
                    func = loop_child.func
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                        if func.value.id in {"diagnostics", "emitter"}:
                            forbidden_diagnostic_calls.append(
                                f"Line {loop_child.lineno}: {func.value.id}.{func.attr}"
                            )

    assert not forbidden_diagnostic_calls, (
        "Hot-loop observability violations detected in IsinProcessor.process: "
        f"{forbidden_diagnostic_calls}"
    )


def test_zero_bracket_prefixes_in_providers_and_investments() -> None:
    """Certify zero legacy bracket prefixes in providers and investments."""
    bracket_regex = re.compile(
        r"\[(?:US Market|Benchmark|Currency|EXTRACT|Processor|Worker).*?\]|\[(?:PHASE|DISCOV|QUALITY|ENGINE|DAG)\b"
    )
    scan_dirs = [
        Path("src/personal_finance_etl/infrastructure/providers"),
        Path("src/personal_finance_etl/application/investments"),
    ]

    violations: list[str] = []
    for base_dir in scan_dirs:
        for py_path in base_dir.rglob("*.py"):
            content = py_path.read_text(encoding="utf-8")
            matches = bracket_regex.findall(content)
            if matches:
                violations.append(f"{py_path.name}: {matches}")

    assert not violations, f"Found legacy bracket prefixes in providers/investments: {violations}"
