"""Validation boundary and Pandera adapter infrastructure tests.

Owns
----
- Verification of DataFrameValidator protocol implementation and error translation.
- Assertion of bounded failure extraction under large violation payloads.
- Materialization benchmarking between Polars DataFrame and LazyFrame validation.
- Verification of zero Pandera exception leakage across boundary.
- Verification of semantic observability event emission.
- Verification of legacy Gatekeeper coexistence.

Does not own
-------------
- Specific production business rules or financial logic (owned by domain).
- Medallion warehouse storage and table schemas (owned by infrastructure.warehouse).
"""

import time
from typing import Protocol

import pandera.polars as pa
import polars as pl
import pytest
from pandera.api.polars.types import PolarsData

from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.contracts.validation import (
    ValidationContext,
    ValidationError,
    ValidationResult,
    ValidationStage,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)


class _EventSink(ObservabilitySink, Protocol):
    """Protocol for memory event sinks providing list of captured events."""

    events: list[ObservabilityEvent]


def _is_positive(data: PolarsData) -> pl.LazyFrame:
    """Verify that non-null values in numeric column are positive."""
    return data.lazyframe.select(pl.col(data.key).is_null() | (pl.col(data.key) > 0))


def _sample_schema() -> pa.DataFrameSchema:
    """Create a sample Pandera schema for testing validation gates."""
    return pa.DataFrameSchema(
        {
            "id": pa.Column(pl.Int64, nullable=False, unique=True),
            "amount": pa.Column(pl.Float64, nullable=True, checks=pa.Check(_is_positive)),
            "category": pa.Column(pl.String, nullable=False),
        }
    )


def test_valid_dataframe_and_lazyframe_pass(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that both DataFrame and LazyFrame pass validation without violations."""
    schema = _sample_schema()
    df = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "amount": [10.5, 20.0, None],
            "category": ["Food", "Transport", "Bills"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=SourceId("bank_csv"),
        contract_id="contract_test_valid",
    )

    # 1. Test eager DataFrame
    res_df = isolated_dataframe_validator.validate(df, schema, context)
    assert isinstance(res_df, ValidationResult)
    assert res_df.is_valid is True
    assert res_df.affected_row_count == 0
    assert len(res_df.failures) == 0
    assert res_df.duration_ms > 0.0

    # 2. Test LazyFrame
    res_lf = isolated_dataframe_validator.validate(df.lazy(), schema, context)
    assert isinstance(res_lf, ValidationResult)
    assert res_lf.is_valid is True
    assert res_lf.affected_row_count == 0
    assert len(res_lf.failures) == 0


def test_invalid_type_produces_structured_failure(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that schema data type mismatches raise structured ValidationError."""
    schema = _sample_schema()
    # Pass string for 'id' column which expects pl.Int64
    df_invalid = pl.DataFrame(
        {
            "id": ["one", "two", "three"],
            "amount": [10.0, 20.0, 30.0],
            "category": ["A", "B", "C"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_type_check",
    )

    with pytest.raises(ValidationError) as exc_info:
        isolated_dataframe_validator.validate(df_invalid, schema, context)

    err = exc_info.value
    assert err.result.is_valid is False
    assert err.result.stage == ValidationStage.PRE_BRONZE
    assert err.result.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert len(err.result.failures) > 0
    assert any(f.column == "id" for f in err.result.failures)
    assert "contract_type_check" in str(err)


def test_nullability_violation_produces_structured_failure(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that null values in non-nullable columns produce clear failure tokens."""
    schema = _sample_schema()
    df_invalid = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "amount": [10.0, 20.0, 30.0],
            "category": ["Food", None, "Bills"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.CANONICAL_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_null_check",
    )

    with pytest.raises(ValidationError) as exc_info:
        isolated_dataframe_validator.validate(df_invalid, schema, context)

    result = exc_info.value.result
    assert result.is_valid is False
    assert result.stage == ValidationStage.CANONICAL_BRONZE
    assert result.affected_row_count == 1

    null_failure = next((f for f in result.failures if f.check == "not_nullable"), None)
    assert null_failure is not None
    assert null_failure.column == "category"
    assert null_failure.failure_count == 1
    assert len(null_failure.examples) == 1
    assert null_failure.examples[0].index == 1
    assert "Populate missing/null values" in (result.remediation or "")


def test_uniqueness_violation_produces_structured_failure(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that duplicate rows in a unique primary key column produce uniqueness errors."""
    schema = _sample_schema()
    df_invalid = pl.DataFrame(
        {
            "id": [1, 1, 3],
            "amount": [10.0, 20.0, 30.0],
            "category": ["Food", "Travel", "Bills"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_uniq_check",
    )

    with pytest.raises(ValidationError) as exc_info:
        isolated_dataframe_validator.validate(df_invalid, schema, context)

    result = exc_info.value.result
    assert result.is_valid is False
    dup_failure = next(
        (f for f in result.failures if f.check in ("field_uniqueness", "series_are_unique")), None
    )
    assert dup_failure is not None
    assert dup_failure.column == "id"
    assert "Deduplicate records" in (result.remediation or "")


def test_large_failure_set_bounded_and_sanitized(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that large failure sets (e.g. 50,000 invalid rows) bound examples to max_examples."""
    schema = pa.DataFrameSchema(
        {
            "code": pa.Column(pl.String, nullable=False),
        }
    )
    # 50,000 null rows
    n_rows = 50_000
    df_large = pl.DataFrame({"code": [None] * n_rows})
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_large_fail",
    )

    with pytest.raises(ValidationError) as exc_info:
        isolated_dataframe_validator.validate(df_large, schema, context)

    result = exc_info.value.result
    assert result.is_valid is False
    assert result.affected_row_count == n_rows

    failure = result.failures[0]
    assert failure.column == "code"
    assert failure.failure_count == n_rows
    # Must be bounded to max_examples (default 5)
    assert len(failure.examples) <= 5

    # String representation must be compact (under 2,000 characters), not 50,000 lines
    err_str = str(exc_info.value)
    assert len(err_str) < 2000


def test_lazyframe_vs_dataframe_materialization_benchmark(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Benchmark materialization behavior and timing for DataFrame vs LazyFrame validation."""
    schema = _sample_schema()
    n_rows = 20_000
    df = pl.DataFrame(
        {
            "id": list(range(n_rows)),
            "amount": [float(i + 1) for i in range(n_rows)],
            "category": ["Category_" + str(i % 5) for i in range(n_rows)],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_benchmark",
    )

    t0 = time.perf_counter()
    res_df = isolated_dataframe_validator.validate(df, schema, context)
    df_duration = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    res_lf = isolated_dataframe_validator.validate(df.lazy(), schema, context)
    lf_duration = (time.perf_counter() - t1) * 1000.0

    assert res_df.is_valid is True
    assert res_lf.is_valid is True
    # Validation durations are measured and populated
    assert res_df.duration_ms > 0.0
    assert res_lf.duration_ms > 0.0
    # Both complete under 1,000ms for 20k rows
    assert df_duration < 1000.0
    assert lf_duration < 1000.0


def test_zero_pandera_exceptions_leak(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that no internal Pandera exceptions leak past the validation boundary."""
    schema = _sample_schema()
    df_invalid = pl.DataFrame(
        {
            "id": [1, 2],
            "amount": [-10.0, -20.0],  # Violates check > 0
            "category": ["A", "B"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_leak_test",
    )

    try:
        isolated_dataframe_validator.validate(df_invalid, schema, context)
        pytest.fail("Expected ValidationError to be raised")
    except Exception as exc:  # noqa: BLE001
        # Must be ValidationError, strictly not pa.errors.SchemaErrors
        assert isinstance(exc, ValidationError)
        assert not isinstance(exc, pa.errors.SchemaErrors)
        assert not isinstance(exc, pa.errors.SchemaError)


def test_semantic_observability_events_emitted(
    isolated_dataframe_validator: PanderaDataFrameValidator,
    test_emitter: tuple[ObservabilityEmitter, _EventSink],
) -> None:
    """Verify that semantic VALIDATION_START, SUCCESS, and FAILED events are emitted."""
    _, sink = test_emitter
    schema = _sample_schema()
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_obs_test",
    )

    # 1. Success run
    df_valid = pl.DataFrame(
        {
            "id": [10],
            "amount": [5.0],
            "category": ["Books"],
        }
    )
    isolated_dataframe_validator.validate(df_valid, schema, context)

    event_codes = [e.event_code for e in sink.events]
    assert EventCode.VALIDATION_START in event_codes
    assert EventCode.VALIDATION_SUCCESS in event_codes

    success_event = next(e for e in sink.events if e.event_code == EventCode.VALIDATION_SUCCESS)
    assert success_event.presentation_kind == PresentationKind.SUCCESS
    assert success_event.severity == DiagnosticSeverity.INFO

    # 2. Failure run
    sink.events.clear()
    df_invalid = pl.DataFrame(
        {
            "id": [10],
            "amount": [5.0],
            "category": [None],  # Null violation
        }
    )
    with pytest.raises(ValidationError):
        isolated_dataframe_validator.validate(df_invalid, schema, context)

    failure_codes = [e.event_code for e in sink.events]
    assert EventCode.VALIDATION_START in failure_codes
    assert EventCode.VALIDATION_FAILED in failure_codes

    fail_event = next(e for e in sink.events if e.event_code == EventCode.VALIDATION_FAILED)
    assert fail_event.presentation_kind == PresentationKind.FAILURE
    assert fail_event.severity == DiagnosticSeverity.ERROR
    assert fail_event.error is not None
    assert fail_event.error.exception_type == "ValidationError"


def test_raise_on_error_false_returns_result(
    isolated_dataframe_validator: PanderaDataFrameValidator,
) -> None:
    """Verify that raise_on_error=False returns a ValidationResult without raising."""
    schema = _sample_schema()
    df_invalid = pl.DataFrame(
        {
            "id": [1, 2],
            "amount": [10.0, 20.0],
            "category": [None, "Valid"],
        }
    )
    context = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        contract_id="contract_non_raising",
    )

    res = isolated_dataframe_validator.validate(df_invalid, schema, context, raise_on_error=False)
    assert isinstance(res, ValidationResult)
    assert res.is_valid is False
    assert res.affected_row_count == 1
    assert len(res.failures) == 1


def test_legacy_gatekeeper_coexistence(
    isolated_settings: Settings,
    status_queue: EventQueue,
    isolated_control_plane: ControlPlane,
    test_emitter: tuple[ObservabilityEmitter, _EventSink],
) -> None:
    """Verify that the existing legacy Gatekeeper validation executes without interference."""
    emitter, _ = test_emitter
    extractor = DataExtractor(
        isolated_settings,
        status_queue,
        isolated_control_plane,
        emitter=emitter,
    )

    empty_lf = pl.LazyFrame({"col_a": pl.Series([], dtype=pl.String)})
    res = ExtractionResult(
        zcategory=empty_lf,
        assetgroup=empty_lf,
        assets=empty_lf,
        currency=empty_lf,
        inoutcome=empty_lf,
        mappings={},
        column_master=pl.DataFrame({"col": ["val"]}),
        stg_mf_isin_mapping=empty_lf,
        stg_benchmark_mapping=empty_lf,
        raw_opening_balances=empty_lf,
        raw_benchmark_master=empty_lf,
        raw_macro_parameters=empty_lf,
        currency_mapping_raw=empty_lf,
        mf_market_data_raw=empty_lf,
        mf_transactions_raw=empty_lf,
        stock_market_data_raw=empty_lf,
        stock_transactions_raw=empty_lf,
        us_stock_transactions_raw=empty_lf,
    )

    # Legacy validation method must execute without error
    extractor._validate_extracted_streams(res)  # pyright: ignore[reportPrivateUsage]
