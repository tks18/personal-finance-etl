"""Pandera infrastructure validation adapter.

Owns
----
- Implementation of DataFrameValidator protocol via Pandera Polars backend.
- Execution under ValidationDepth.SCHEMA_AND_DATA for thorough LazyFrame check execution.
- Parsing and bounding of Pandera SchemaErrors into typed ValidationResult models.
- Fan-out of semantic validation telemetry events via ObservabilityEmitter.
- Shielding callers from internal Pandera exceptions.

Does not own
-------------
- Validation contracts and error definitions (owned by contracts.validation).
- Source or target dataset schema compilation (owned by config.sources and warehouse contracts).
- Tabular persistence or storage (owned by infrastructure.warehouse).
"""

import time
import traceback

import pandera.polars as pa
import polars as pl
from pandera.config import ValidationDepth, config_context

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventOutcome,
    PresentationKind,
)
from personal_finance_etl.contracts.validation import (
    DataFrameValidator,
    ValidationCheckFailure,
    ValidationContext,
    ValidationError,
    ValidationExample,
    ValidationResult,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_observability_diagnostics,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.infrastructure.validation")


class PanderaDataFrameValidator(DataFrameValidator):
    """Authoritative tabular validator backed by Pandera's Polars engine.

    Parameters
    ----------
    emitter : ObservabilityEmitter | None, default=None
        Active observability emitter for telemetry events.
    max_examples : int, default=5
        Maximum number of violation examples preserved per failed check.
    """

    def __init__(
        self,
        emitter: ObservabilityEmitter | None = None,
        max_examples: int = 5,
    ) -> None:
        self.emitter = emitter
        self.max_examples = max_examples

    def _bound_failures(
        self, failure_cases: pl.DataFrame
    ) -> tuple[tuple[ValidationCheckFailure, ...], int]:
        """Aggregate, group, and bound raw Pandera failure cases.

        Parameters
        ----------
        failure_cases : pl.DataFrame
            Raw failure cases frame from Pandera SchemaErrors.

        Returns
        -------
        tuple[tuple[ValidationCheckFailure, ...], int]
            Pair of (bounded check failure summaries, total affected row count).
        """
        if failure_cases.is_empty():
            return (), 0

        # Calculate affected unique rows if index column exists
        if "index" in failure_cases.columns:
            valid_indices = failure_cases.filter(pl.col("index").is_not_null())["index"]
            affected_rows = (
                len(valid_indices.unique()) if not valid_indices.is_empty() else len(failure_cases)
            )
        else:
            affected_rows = len(failure_cases)

        rows = failure_cases.iter_rows(named=True)
        grouped: dict[tuple[str | None, str], list[dict[str, object]]] = {}

        for row in rows:
            raw_col = row.get("column")
            col_name = str(raw_col) if raw_col is not None else None
            raw_check = row.get("check")
            check_name = str(raw_check) if raw_check is not None else "unknown_check"

            # If missing column, check is 'column_in_dataframe' and failure_case holds the column name
            if check_name == "column_in_dataframe" and col_name is None:
                raw_case = row.get("failure_case")
                col_name = str(raw_case) if raw_case is not None else "unknown"

            key = (col_name, check_name)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)

        failures: list[ValidationCheckFailure] = []
        for (col_name, check_name), items in grouped.items():
            failure_count = len(items)
            examples: list[ValidationExample] = []

            for item in items[: self.max_examples]:
                raw_val = item.get("failure_case")
                val_str = str(raw_val) if raw_val is not None else "null"
                if len(val_str) > 60:
                    val_str = val_str[:57] + "..."

                raw_idx = item.get("index")
                idx: int | None = None
                if isinstance(raw_idx, (int, str)):
                    try:
                        idx = int(raw_idx)
                    except (ValueError, TypeError):
                        idx = None

                examples.append(ValidationExample(index=idx, value=val_str))

            if check_name == "not_nullable":
                err_msg = f"Non-nullable column '{col_name}' contains null values"
            elif check_name == "column_in_dataframe":
                err_msg = f"Missing required column '{col_name}' in tabular data"
            elif check_name in ("field_uniqueness", "series_are_unique"):
                err_msg = (
                    f"Column '{col_name}' contains duplicate values violating uniqueness constraint"
                )
            elif check_name.startswith("dtype"):
                err_msg = f"Column '{col_name}' data type check failed: {check_name}"
            else:
                err_msg = f"Column '{col_name}' failed validation check '{check_name}'"

            failures.append(
                ValidationCheckFailure(
                    column=col_name,
                    check=check_name,
                    error_message=err_msg,
                    failure_count=failure_count,
                    examples=tuple(examples),
                )
            )

        return tuple(failures), affected_rows

    def _derive_remediation(
        self,
        failures: tuple[ValidationCheckFailure, ...],
        context: ValidationContext,
    ) -> str:
        """Construct actionable user remediation guidance from check failures.

        Parameters
        ----------
        failures : tuple[ValidationCheckFailure, ...]
            Aggregated check failure summaries.
        context : ValidationContext
            Validation execution context.

        Returns
        -------
        str
            Actionable guidance sentence.
        """
        missing = [f.column for f in failures if f.check == "column_in_dataframe" and f.column]
        nulls = [f.column for f in failures if f.check == "not_nullable" and f.column]
        dups = [
            f.column
            for f in failures
            if f.check in ("field_uniqueness", "series_are_unique") and f.column
        ]

        remediations: list[str] = []
        if missing:
            remediations.append(
                f"Ensure source file contains required column(s): {', '.join(missing)}"
            )
        if nulls:
            remediations.append(
                f"Populate missing/null values in mandatory column(s): {', '.join(nulls)}"
            )
        if dups:
            remediations.append(f"Deduplicate records on unique key column(s): {', '.join(dups)}")
        if not remediations:
            remediations.append(
                f"Review schema contract '{context.contract_id}' and correct invalid source records"
            )

        return "; ".join(remediations) + "."

    def validate(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        schema: object,
        context: ValidationContext,
        *,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """Validate a Polars DataFrame or LazyFrame against an authoritative Pandera schema.

        Parameters
        ----------
        frame : pl.DataFrame | pl.LazyFrame
            Polars data frame or lazy frame to validate.
        schema : object
            Authoritative Pandera DataFrameSchema specification.
        context : ValidationContext
            Execution context metadata.
        raise_on_error : bool, default=True
            Whether to raise ValidationError on failure or return the ValidationResult.

        Returns
        -------
        ValidationResult
            Structured validation outcome details.

        Raises
        ------
        TypeError
            If schema is not a Pandera DataFrameSchema instance.
        ValidationError
            If validation checks fail and raise_on_error is True.
        """
        if not isinstance(schema, pa.DataFrameSchema):
            raise TypeError(
                f"Expected Pandera DataFrameSchema instance, got {type(schema).__name__}"
            )

        if self.emitter is not None:
            self.emitter.emit_event(
                event_code=EventCode.VALIDATION_START,
                message=(
                    f"Validating dataset '{context.dataset_id.value}' at stage "
                    f"'{context.stage.value}' against contract '{context.contract_id}'..."
                ),
                presentation_kind=PresentationKind.STEP,
                severity=DiagnosticSeverity.INFO,
                outcome=EventOutcome.STARTED,
                stage=EngineStage.EXTRACTING,
                component="validation",
                operation="validate_dataframe",
                entity_type="dataset",
                entity_id=context.dataset_id.value,
            )

        t0 = time.perf_counter()

        try:
            with config_context(validation_depth=ValidationDepth.SCHEMA_AND_DATA):
                if isinstance(frame, pl.DataFrame):
                    schema.validate(frame, lazy=True)
                else:
                    schema.validate(frame, lazy=True)

            duration_ms = (time.perf_counter() - t0) * 1000.0
            row_count = frame.height if isinstance(frame, pl.DataFrame) else None

            diagnostics.debug(
                "Validation passed for dataset '%s' (%s) in %.2fms.",
                context.dataset_id.value,
                context.stage.value,
                duration_ms,
            )

            if self.emitter is not None:
                self.emitter.emit_event(
                    event_code=EventCode.VALIDATION_SUCCESS,
                    message=(
                        f"Validation passed for dataset '{context.dataset_id.value}' "
                        f"({duration_ms:.2f}ms)"
                    ),
                    presentation_kind=PresentationKind.SUCCESS,
                    severity=DiagnosticSeverity.INFO,
                    outcome=EventOutcome.COMPLETED,
                    duration_ms=duration_ms,
                    rows=row_count,
                    stage=EngineStage.EXTRACTING,
                    component="validation",
                    operation="validate_dataframe",
                    entity_type="dataset",
                    entity_id=context.dataset_id.value,
                )

            return ValidationResult(
                is_valid=True,
                stage=context.stage,
                dataset_id=context.dataset_id,
                source_id=context.source_id,
                contract_id=context.contract_id,
                contract_version=context.contract_version,
                affected_row_count=0,
                failures=(),
                remediation=None,
                duration_ms=duration_ms,
            )

        except pa.errors.SchemaErrors as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            raw_cases: object = getattr(exc, "failure_cases", None)
            failure_cases: pl.DataFrame = (
                raw_cases if isinstance(raw_cases, pl.DataFrame) else pl.DataFrame()
            )
            failures, affected_rows = self._bound_failures(failure_cases)
            remediation = self._derive_remediation(failures, context)

            result = ValidationResult(
                is_valid=False,
                stage=context.stage,
                dataset_id=context.dataset_id,
                source_id=context.source_id,
                contract_id=context.contract_id,
                contract_version=context.contract_version,
                affected_row_count=affected_rows,
                failures=failures,
                remediation=remediation,
                duration_ms=duration_ms,
            )

            diagnostics.warning(
                "Validation failed for dataset '%s' (%s) with %d failures across %d rows in %.2fms.",
                context.dataset_id.value,
                context.stage.value,
                len(failures),
                affected_rows,
                duration_ms,
            )

            if self.emitter is not None:
                err_details = ErrorDetails(
                    exception_type="ValidationError",
                    exception_message=(
                        f"Validation failed for '{context.dataset_id.value}': {len(failures)} "
                        f"violation groups across {affected_rows} rows"
                    ),
                    failure_domain=FailureDomain.SOURCE_VALIDATION,
                    traceback_summary=traceback.format_exc(),
                    retryable=False,
                )
                self.emitter.emit_event(
                    event_code=EventCode.VALIDATION_FAILED,
                    message=(
                        f"Validation failed for dataset '{context.dataset_id.value}' at stage "
                        f"'{context.stage.value}': {len(failures)} check failures across "
                        f"{affected_rows} rows"
                    ),
                    presentation_kind=PresentationKind.FAILURE,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    duration_ms=duration_ms,
                    rows=affected_rows,
                    error=err_details,
                    stage=EngineStage.EXTRACTING,
                    component="validation",
                    operation="validate_dataframe",
                    entity_type="dataset",
                    entity_id=context.dataset_id.value,
                )

            if raise_on_error:
                raise ValidationError(result) from exc

            return result

        except pa.errors.SchemaError as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            raw_single_cases: object = getattr(exc, "failure_cases", None)
            if isinstance(raw_single_cases, pl.DataFrame):
                failures, affected_rows = self._bound_failures(raw_single_cases)
            else:
                schema_obj: object = getattr(exc, "schema", None)
                schema_name: object = (
                    getattr(schema_obj, "name", None) if schema_obj is not None else None
                )
                col_name: str | None = str(schema_name) if schema_name is not None else None
                check_obj: object = getattr(exc, "check", None)
                check_name: str = str(check_obj) if check_obj is not None else "schema_error"
                failures = (
                    ValidationCheckFailure(
                        column=col_name,
                        check=check_name,
                        error_message=str(exc),
                        failure_count=1,
                        examples=(),
                    ),
                )
                affected_rows = 1

            remediation = self._derive_remediation(failures, context)
            result = ValidationResult(
                is_valid=False,
                stage=context.stage,
                dataset_id=context.dataset_id,
                source_id=context.source_id,
                contract_id=context.contract_id,
                contract_version=context.contract_version,
                affected_row_count=affected_rows,
                failures=failures,
                remediation=remediation,
                duration_ms=duration_ms,
            )

            diagnostics.warning(
                "Validation failed for dataset '%s' (%s) with single SchemaError: %s",
                context.dataset_id.value,
                context.stage.value,
                exc,
            )

            if self.emitter is not None:
                err_details = ErrorDetails(
                    exception_type="ValidationError",
                    exception_message=f"Validation failed for '{context.dataset_id.value}': {exc}",
                    failure_domain=FailureDomain.SOURCE_VALIDATION,
                    traceback_summary=traceback.format_exc(),
                    retryable=False,
                )
                self.emitter.emit_event(
                    event_code=EventCode.VALIDATION_FAILED,
                    message=(
                        f"Validation failed for dataset '{context.dataset_id.value}' at stage "
                        f"'{context.stage.value}': {exc}"
                    ),
                    presentation_kind=PresentationKind.FAILURE,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    duration_ms=duration_ms,
                    rows=affected_rows,
                    error=err_details,
                    stage=EngineStage.EXTRACTING,
                    component="validation",
                    operation="validate_dataframe",
                    entity_type="dataset",
                    entity_id=context.dataset_id.value,
                )

            if raise_on_error:
                raise ValidationError(result) from exc

            return result
