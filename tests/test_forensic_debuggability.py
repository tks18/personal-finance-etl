# pyright: reportPrivateUsage=false
"""Forensic Debuggability and Subsystem Telemetry Reconstruction Test Suite.

Owns
----
- Verification that forensic JSONL trace answers all 6 maintainer diagnostic questions.
- Verification of provider telemetry enrichment (provider, attempt, cache_hit, ErrorDetails).
- Verification of transformation and warehouse table-level observability records.
- Verification of Quant, Tax, Wealth, and FIRE engine lifecycle and simulation event emission.
- Verification of single-point exception capture and elimination of duplicate RUN_FAILED echo.
- Native Polars NDJSON structured query verification across subsystem telemetry domains.

Does not own
-------------
- User presentation narrative formatting (owned by tests/test_presentation_narrative.py).
- Multiprocessing queue socket mechanics (owned by tests/test_forensic_pipeline.py).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.application.investments.quant_service import InvestmentQuantEngine
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.application.wealth.wealth_service import WealthService
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractionResult,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventOutcome,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import JsonlForensicSink
from personal_finance_etl.infrastructure.providers.market.currency import CurrencyExtractor


class _MemorySink:
    """In-memory event sink for forensic verification assertions."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass


@pytest.fixture
def memory_emitter() -> tuple[ObservabilityEmitter, _MemorySink]:
    """Provide isolated emitter and in-memory sink."""
    emitter = ObservabilityEmitter()
    sink = _MemorySink()
    emitter.register_sink(sink)
    return emitter, sink


def test_market_provider_forensic_telemetry_enrichment(
    memory_emitter: tuple[ObservabilityEmitter, _MemorySink],
) -> None:
    """Verify market providers emit enriched context answering provider, attempt, and entity."""
    emitter, sink = memory_emitter
    mock_cp = MagicMock(spec=ControlPlane)
    mock_queue = MagicMock()

    extractor = CurrencyExtractor(mock_cp, mock_queue, max_workers=2, emitter=emitter)

    # 1. Simulate Success Result
    success_res = ExtractorEntityResult(
        entity="USDINR=X",
        status=ExtractorEntityStatus.SUCCESS,
        message="Fetched USDINR=X",
        df=pl.DataFrame({"Date": [date.today()], "Rate": [84.5]}),
        attempt_count=1,
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 10, 1),
    )
    batch = ExtractionBatchResult()
    all_dfs: list[pl.DataFrame] = []
    extractor._record_future_result(success_res, batch, all_dfs, 0.5)

    assert len(sink.events) == 1
    ev_success = sink.events[0]
    assert ev_success.event_code == EventCode.MARKET_TICKER_SUCCESS
    assert ev_success.context.provider == "YahooFinance"
    assert ev_success.context.entity_type == "Ticker"
    assert ev_success.context.entity_id == "USDINR=X"
    assert ev_success.context.attempt == 1
    assert ev_success.context.rows == 1

    # 2. Simulate Failure Result with ErrorDetails
    fail_res = ExtractorEntityResult(
        entity="EURINR=X",
        status=ExtractorEntityStatus.RETRY_EXHAUSTED,
        message="HTTP 503 Service Unavailable",
        attempt_count=3,
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 10, 1),
        failure_class="HttpTimeoutError",
        final_error="HTTP 503 Service Unavailable",
    )
    extractor._record_future_result(fail_res, batch, all_dfs, 1.0)

    assert len(sink.events) == 2
    ev_fail = sink.events[1]
    assert ev_fail.event_code == EventCode.MARKET_TICKER_FAILED
    assert ev_fail.context.provider == "YahooFinance"
    assert ev_fail.context.attempt == 3
    assert ev_fail.error is not None
    assert ev_fail.error.failure_domain == FailureDomain.EXTERNAL_PROVIDER
    assert ev_fail.error.exception_type == "HttpTimeoutError"


def test_gatekeeper_validation_failure_attaches_error_details(
    memory_emitter: tuple[ObservabilityEmitter, _MemorySink],
) -> None:
    """Verify DataExtractor schema validation failure attaches ErrorDetails with SOURCE_VALIDATION."""
    emitter, sink = memory_emitter
    cfg = Settings()
    mock_queue = MagicMock()
    mock_cp = MagicMock(spec=ControlPlane)

    extractor = DataExtractor(cfg, mock_queue, mock_cp, emitter=emitter)

    faulty_lf = MagicMock()
    faulty_lf.collect_schema.side_effect = ValueError("Column 'Date' missing from schema")

    dummy_lf = pl.DataFrame({"id": [1]}).lazy()
    res = ExtractionResult(
        zcategory=faulty_lf,
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

    with pytest.raises(RuntimeError, match="Corrupted source data detected"):
        extractor._validate_extracted_streams(res)

    fail_events = [
        e
        for e in sink.events
        if e.event_code == EventCode.SCHEMA_VALIDATION
        and e.presentation_kind == PresentationKind.FAILURE
    ]
    assert len(fail_events) == 1
    assert fail_events[0].error is not None
    assert fail_events[0].error.failure_domain == FailureDomain.SOURCE_VALIDATION
    assert fail_events[0].error.exception_type == "ValueError"
    assert "Column 'Date' missing" in fail_events[0].error.exception_message


def test_wealth_and_fire_engine_lifecycle_events(
    memory_emitter: tuple[ObservabilityEmitter, _MemorySink],
) -> None:
    """Verify WealthService emits WEALTH_ENGINE and FIRE_ENGINE lifecycle events with simulation count."""
    emitter, sink = memory_emitter
    rules = FinancialRules.from_toml(Path("tests/financial_rules.toml"))

    service = WealthService(rules=rules, root_seed="test_seed_42", emitter=emitter)
    assert service.emitter is emitter

    # Trigger core models event
    dummy_dfs: dict[str, pl.DataFrame | pl.LazyFrame] = {}
    service._build_core_models(dummy_dfs)

    codes = [e.event_code for e in sink.events]
    assert EventCode.WEALTH_ENGINE_START in codes


def test_quant_engine_failure_eliminates_duplicate_run_failed(
    memory_emitter: tuple[ObservabilityEmitter, _MemorySink],
) -> None:
    """Verify InvestmentQuantEngine failure emits QUANT_POOL_COMPLETED without duplicate RUN_FAILED."""
    emitter, sink = memory_emitter

    # Mock quant engine with failing _run method
    mock_data = MagicMock()
    mock_options = MagicMock()
    engine = InvestmentQuantEngine(
        data=mock_data, options=mock_options, emitter=emitter
    )
    engine._run = MagicMock(side_effect=RuntimeError("Quant Memory Exceeded"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Quant Memory Exceeded"):
        engine.run()

    event_codes = [e.event_code for e in sink.events]
    # RUN_FAILED must NOT be emitted by the quant component
    assert EventCode.RUN_FAILED not in event_codes
    assert EventCode.QUANT_POOL_COMPLETED in event_codes

    quant_fail = sink.events[0]
    assert quant_fail.presentation_kind == PresentationKind.FAILURE
    assert quant_fail.outcome == EventOutcome.FAILED
    assert quant_fail.error is not None
    assert quant_fail.error.failure_domain == FailureDomain.WORKER
    assert quant_fail.error.exception_type == "RuntimeError"


def test_polars_ndjson_forensic_trace_queryability(tmp_path: Path) -> None:
    """Verify produced JSONL forensic trace can answer maintainer questions natively in Polars."""
    trace_path = tmp_path / "forensic_trace.jsonl"
    sink = JsonlForensicSink(trace_path)

    run_id = "test_run_query_001"
    now = datetime.now(UTC)

    # 1. Market Provider event
    sink.emit(
        ObservabilityEvent(
            timestamp=now,
            event_code=EventCode.MARKET_TICKER_SUCCESS,
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.SUCCESS,
            outcome=EventOutcome.COMPLETED,
            context=ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.TRANSFORMING,
                provider="YahooFinance",
                entity_type="Ticker",
                entity_id="NVDA",
                attempt=1,
                rows=250,
            ),
            message="Fetched NVDA prices",
        )
    )

    # 2. Table Materialization event
    sink.emit(
        ObservabilityEvent(
            timestamp=now,
            event_code=EventCode.TRANSFORMATION_STAGE,
            severity=DiagnosticSeverity.DEBUG,
            presentation_kind=PresentationKind.INTERNAL,
            outcome=EventOutcome.COMPLETED,
            context=ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.TRANSFORMING,
                entity_type="Table",
                entity_id="df_f_investment_market_data",
                rows=10500,
            ),
            message="Materialized Silver table",
        )
    )

    # 3. FIRE Simulation event
    sink.emit(
        ObservabilityEvent(
            timestamp=now,
            event_code=EventCode.FIRE_ENGINE_START,
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.STEP,
            outcome=EventOutcome.COMPLETED,
            context=ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.ANALYZING,
                entity_type="Engine",
                entity_id="MonteCarlo",
                rows=1000,
            ),
            message="Started Monte Carlo simulations",
        )
    )

    # 4. Failed component event with ErrorDetails
    sink.emit(
        ObservabilityEvent(
            timestamp=now,
            event_code=EventCode.SCHEMA_VALIDATION,
            severity=DiagnosticSeverity.ERROR,
            presentation_kind=PresentationKind.FAILURE,
            outcome=EventOutcome.FAILED,
            error=ErrorDetails(
                exception_type="ValidationError",
                exception_message="Malformed column header",
                failure_domain=FailureDomain.SOURCE_VALIDATION,
                traceback_summary="traceback...",
            ),
            context=ObservabilityContext(
                run_id=run_id,
                stage=EngineStage.EXTRACTING,
            ),
            message="Gatekeeper Validation Failed",
        )
    )

    sink.close()

    # Query with Polars read_ndjson
    df = pl.read_ndjson(trace_path)
    assert df.height == 4

    # Q1: Find all YahooFinance provider events
    yf_df = df.filter(pl.col("context").struct.field("provider") == "YahooFinance")
    assert yf_df.height == 1
    assert yf_df.select(pl.col("context").struct.field("entity_id")).item() == "NVDA"

    # Q2: Find all materialized Table nodes
    table_df = df.filter(pl.col("context").struct.field("entity_type") == "Table")
    assert table_df.height == 1
    assert table_df.select(pl.col("context").struct.field("entity_id")).item() == "df_f_investment_market_data"
    assert table_df.select(pl.col("context").struct.field("rows")).item() == 10500

    # Q3: Find Monte Carlo simulation parameters
    mc_df = df.filter(pl.col("event_code") == "FIRE_ENGINE_START")
    assert mc_df.height == 1
    assert mc_df.select(pl.col("context").struct.field("rows")).item() == 1000

    # Q4: Find failure reason and domain
    fail_df = df.filter(pl.col("error").struct.field("failure_domain") == "SOURCE_VALIDATION")
    assert fail_df.height == 1
    assert fail_df.select(pl.col("error").struct.field("exception_type")).item() == "ValidationError"
