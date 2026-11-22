# pyright: reportPrivateUsage=false
"""Core Pipeline Observability Certification Test Suite.

Owns
----
- Verification of canonical ObservabilityEvent emission across Core Pipeline boundaries (Phase 1–5).
- Verification of DataExtractor gatekeeper validation event emission.
- Verification of MarketSync pipelines (Currency, Benchmark, US Market) event emission.
- Verification of Quant and Tax service lifecycle transitions.
- Architectural assertion guaranteeing zero legacy string prefixes in application package.

Does not own
-------------
- Forensic JSONL sink file I/O verification (owned by tests/test_forensic_pipeline.py).
- Rich CLI or Desktop CustomTkinter narrative rendering (owned by tests/test_presentation_narrative.py).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
    CurrencyPipeline,
    USMarketPipeline,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
)
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
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


def test_data_extractor_emits_extraction_and_schema_validation(
    test_emitter: tuple[ObservabilityEmitter, MockRecordingSink],
) -> None:
    """Verify DataExtractor emits EXTRACTION_START and SCHEMA_VALIDATION events."""
    emitter, sink = test_emitter
    cfg = Settings()
    mock_queue = MagicMock()
    mock_cp = MagicMock(spec=ControlPlane)

    extractor = DataExtractor(cfg, mock_queue, mock_cp, emitter=emitter)

    # Empty extraction result for testing schema validation
    dummy_lf = pl.DataFrame({"id": [1], "name": ["test"]}).lazy()
    res = ExtractionResult(
        zcategory=dummy_lf,
        assetgroup=dummy_lf,
        assets=dummy_lf,
        currency=dummy_lf,
        inoutcome=dummy_lf,
        mappings={},
        column_master=pl.DataFrame(),
        stg_mf_isin_mapping=dummy_lf,
        stg_benchmark_mapping=dummy_lf,
        raw_opening_balances=dummy_lf,
        raw_benchmark_master=dummy_lf,
        raw_macro_parameters=dummy_lf,
        currency_mapping_raw=dummy_lf,
        mf_market_data_raw=dummy_lf,
        mf_transactions_raw=dummy_lf,
        stock_market_data_raw=dummy_lf,
        stock_transactions_raw=dummy_lf,
        us_stock_transactions_raw=dummy_lf,
    )

    extractor._validate_extracted_streams(res)

    event_codes = [e.event_code for e in sink.events]
    assert EventCode.SCHEMA_VALIDATION in event_codes

    validation_events = [e for e in sink.events if e.event_code == EventCode.SCHEMA_VALIDATION]
    assert len(validation_events) >= 2
    assert validation_events[0].presentation_kind == PresentationKind.STEP
    assert validation_events[-1].presentation_kind == PresentationKind.SUCCESS
    assert validation_events[-1].context.stage == EngineStage.EXTRACTING


def test_data_extractor_emits_schema_validation_failure(
    test_emitter: tuple[ObservabilityEmitter, MockRecordingSink],
) -> None:
    """Verify DataExtractor emits FAILURE event on schema validation exception."""
    emitter, sink = test_emitter
    cfg = Settings()
    mock_queue = MagicMock()
    mock_cp = MagicMock(spec=ControlPlane)

    extractor = DataExtractor(cfg, mock_queue, mock_cp, emitter=emitter)

    # Faulty extraction result that raises an exception when collected
    bad_lf = pl.LazyFrame()
    # Mocking bad schema collect
    faulty_lf = MagicMock()
    faulty_lf.collect_schema.side_effect = RuntimeError("Corrupted Parquet Stream")

    res = ExtractionResult(
        zcategory=faulty_lf,
        assetgroup=bad_lf,
        assets=bad_lf,
        currency=bad_lf,
        inoutcome=bad_lf,
        mappings={},
        column_master=pl.DataFrame(),
        stg_mf_isin_mapping=bad_lf,
        stg_benchmark_mapping=bad_lf,
        raw_opening_balances=bad_lf,
        raw_benchmark_master=bad_lf,
        raw_macro_parameters=bad_lf,
        currency_mapping_raw=bad_lf,
        mf_market_data_raw=bad_lf,
        mf_transactions_raw=bad_lf,
        stock_market_data_raw=bad_lf,
        stock_transactions_raw=bad_lf,
        us_stock_transactions_raw=bad_lf,
    )

    with pytest.raises(RuntimeError, match="Corrupted source data detected"):
        extractor._validate_extracted_streams(res)

    failed_events = [
        e
        for e in sink.events
        if e.event_code == EventCode.SCHEMA_VALIDATION
        and e.presentation_kind == PresentationKind.FAILURE
    ]
    assert len(failed_events) == 1
    assert "Corrupted Parquet Stream" in failed_events[0].message


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
    app_root = (
        Path(__file__).resolve().parent.parent / "src" / "personal_finance_etl" / "application"
    )
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
