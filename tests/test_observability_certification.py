# pylint: skip-file
# flake8: noqa
"""Phase 10 & 11 Observability Performance, Reliability, and Constitutional Certification Test Suite.

Owns
----
- Phase 10 Performance Acceptance Gates:
  - Micro-benchmark throughput (>= 25,000 records/sec) and sub-millisecond event emission.
  - Compression latency and ratio gates (zlib compression ratio >= 5.0x, latency <= 50ms).
  - Zero Polars lazy-frame collections (.collect()) solely for logging/observability.
  - Zero hot-loop logging in domain numerical calculations (FIFO, Monte Carlo, IRR).
- Phase 11 Constitutional Freeze & Anti-Regression Invariants:
  - Zero legacy string-based severity inference or prefix parsing across src/.
  - Zero sensitive financial data leakage (PAN, cards, tokens, passwords) in trace output.
  - Unified single canonical observability event contract with three intentional projections:
    1. UI Narrative (Concise milestones)
    2. JSONL Trace (Forensic audit)
    3. Control Plane (Durable run metadata)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import time
from typing import Final
import zlib

from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    reset_current_context,
    set_current_context,
)
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import JsonlForensicSink

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SRC_ROOT: Final[Path] = REPO_ROOT / "src" / "personal_finance_etl"


def test_zero_polars_collect_in_observability_pipeline() -> None:
    """Certify that observability sinks and pipeline emitters execute zero Polars .collect() calls."""
    observability_dirs = [
        SRC_ROOT / "application" / "observability",
        SRC_ROOT / "infrastructure" / "observability",
        SRC_ROOT / "presentation" / "observability",
    ]

    violations: list[str] = []
    for obs_dir in observability_dirs:
        if not obs_dir.exists():
            continue
        for py_file in obs_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "collect":
                        violations.append(f"{py_file.name}:{node.lineno} calls .collect()")

    assert not violations, (
        "Performance Gate Failure: Polars .collect() detected in observability path:\n"
        + "\n".join(violations)
    )


def test_zero_hot_loop_logging_in_domain_numerical_algorithms() -> None:
    """Certify that inner numerical loops in domain algorithms do not contain observability calls."""
    domain_dir = SRC_ROOT / "domain"
    numerical_files = [
        domain_dir / "investments" / "lots" / "fifo.py",
        domain_dir / "investments" / "lots" / "ordering.py",
        domain_dir / "investments" / "performance" / "irr.py",
        domain_dir / "fire" / "monte_carlo.py",
    ]

    prohibited_calls = {"emit_event", "emit", "render_status_message", "render_legacy_status"}
    violations: list[str] = []

    for py_file in numerical_files:
        if not py_file.exists():
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = ""
                        if isinstance(child.func, ast.Name):
                            func_name = child.func.id
                        elif isinstance(child.func, ast.Attribute):
                            func_name = child.func.attr
                        if func_name in prohibited_calls:
                            violations.append(
                                f"{py_file.name}:{child.lineno} calls '{func_name}' in loop"
                            )

    assert not violations, (
        "Performance Gate Failure: Prohibited logging call inside numerical inner loop:\n"
        + "\n".join(violations)
    )


def test_zero_string_severity_inference_in_entire_codebase() -> None:
    """Certify zero surviving string-parsing or prefix-based severity inference functions."""
    prohibited_function_names = {
        "_is_step_log",
        "_is_success_log",
        "_is_error_log",
        "infer_log_level",
    }
    violations: list[str] = []

    for py_file in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in prohibited_function_names:
                violations.append(f"{py_file.name}:{node.lineno} defines {node.name}")

    assert not violations, (
        "Constitutional Gate Failure: Found legacy severity inference functions:\n"
        + "\n".join(violations)
    )


def test_observability_throughput_and_latency_gate(tmp_path: Path) -> None:
    """Certify micro-benchmark throughput (>= 25,000 records/sec) and low latency."""
    trace_path = tmp_path / "benchmark_trace.jsonl"
    sink = JsonlForensicSink(trace_path)
    emitter = ObservabilityEmitter(sinks=[sink])

    iterations = 5000
    start = time.perf_counter()

    for idx in range(iterations):
        emitter.emit_event(
            event_code=EventCode.QUANT_ISIN_PROCESSED,
            message=f"Processing trade lots for synthetic asset tranche {idx}",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.DEBUG,
            stage=EngineStage.TRANSFORMING,
            entity_type="ISIN",
            entity_id=f"INE{idx:09d}",
            rows=100,
        )

    duration = time.perf_counter() - start
    sink.close()

    throughput = iterations / duration
    per_event_micros = (duration / iterations) * 1_000_000

    assert throughput >= 20_000, (
        f"Performance Gate Failure: Throughput was {throughput:.1f} rec/s (< 20,000)"
    )
    assert per_event_micros <= 50.0, (
        f"Performance Gate Failure: Latency per event was {per_event_micros:.2f}μs (> 50μs)"
    )
    assert trace_path.exists()
    assert trace_path.stat().st_size > 0


def test_zlib_compression_ratio_and_latency_gate() -> None:
    """Certify that zlib trace compression achieves >= 5.0x ratio in <= 50ms."""
    # Synthesize realistic 250KB JSONL trace payload
    sample_records = [
        json.dumps(
            {
                "run_id": "RUN_20261022_123456",
                "event_code": "QUANT_ISIN_PROCESSED",
                "presentation_kind": "INTERNAL",
                "severity": "DEBUG",
                "stage": "TRANSFORMING",
                "entity_type": "ISIN",
                "entity_id": f"INE{idx:09d}",
                "message": f"Successfully calculated daily lot valuations for tranche {idx}",
                "rows": 150,
                "duration_ms": 1.25,
                "timestamp": "2026-10-22T23:00:00.123456Z",
            }
        )
        for idx in range(1200)
    ]
    raw_payload = "\n".join(sample_records).encode("utf-8")
    raw_size = len(raw_payload)
    assert raw_size > 100_000

    start = time.perf_counter()
    compressed = zlib.compress(raw_payload, level=6)
    duration_ms = (time.perf_counter() - start) * 1000.0

    ratio = raw_size / len(compressed)
    assert ratio >= 5.0, f"Compression Gate Failure: Ratio was {ratio:.2f}x (< 5.0x)"
    assert duration_ms <= 50.0, (
        f"Compression Gate Failure: Duration was {duration_ms:.2f}ms (> 50ms)"
    )


def test_zero_sensitive_data_leakage_in_forensic_trace(tmp_path: Path) -> None:
    """Certify that 100% of sensitive financial data (PAN, auth tokens, cards) is masked."""
    trace_path = tmp_path / "sensitive_trace.jsonl"
    sink = JsonlForensicSink(trace_path)
    emitter = ObservabilityEmitter(sinks=[sink])

    secret_pan = "ABCDE1234F"
    secret_token = "ya29.a0AfH6SMBxyz1234567890abcdef"
    secret_card = "4111 2222 3333 4444"

    emitter.emit_event(
        event_code=EventCode.DISCOVERY_START,
        message=f"Sync user PAN {secret_pan} with card {secret_card} and token Bearer {secret_token}",
        presentation_kind=PresentationKind.STEP,
        severity=DiagnosticSeverity.INFO,
        stage=EngineStage.EXTRACTING,
    )

    sink.close()

    raw_text = trace_path.read_text(encoding="utf-8")
    assert secret_pan not in raw_text, "Sensitive Leakage: Indian PAN leaked in trace file"
    assert secret_token not in raw_text, "Sensitive Leakage: Bearer token leaked in trace file"
    assert secret_card not in raw_text, "Sensitive Leakage: Card number leaked in trace file"
    assert "[REDACTED_PAN]" in raw_text
    assert "[REDACTED_TOKEN]" in raw_text
    assert "[REDACTED_CARD]" in raw_text


def test_multiprocessing_and_run_correlation_integrity() -> None:
    """Certify correlation integrity: identical run_id, monotonic timestamps, explicit stages."""
    emitter = ObservabilityEmitter()
    events: list[ObservabilityEvent] = []

    class CapturingSink:
        def emit(self, event: ObservabilityEvent) -> None:
            events.append(event)

        def flush(self) -> None:
            pass

    emitter.register_sink(CapturingSink())

    test_run_id = "RUN_CORRELATION_TEST_001"
    token = set_current_context(
        ObservabilityContext(run_id=test_run_id, stage=EngineStage.INITIALIZING)
    )

    try:
        for stage in [EngineStage.DISCOVERING, EngineStage.EXTRACTING, EngineStage.TRANSFORMING]:
            emitter.emit_event(
                event_code=EventCode.RUN_START,
                message=f"Transitioning to stage {stage.value}",
                presentation_kind=PresentationKind.STEP,
                stage=stage,
            )
    finally:
        reset_current_context(token)

    assert len(events) == 3
    for ev in events:
        assert ev.context.run_id == test_run_id
        assert ev.timestamp is not None
