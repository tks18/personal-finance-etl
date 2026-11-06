"""Cross-boundary validation contracts and protocols.

Owns
----
- Pipeline validation stage enumeration (ValidationStage).
- Bounded failure value tokens and check failure descriptors (ValidationExample, ValidationCheckFailure).
- Context metadata for dataset and stage admission (ValidationContext).
- Comprehensive validation result summary (ValidationResult).
- Structured validation exception (ValidationError).
- Abstract DataFrameValidator protocol.

Does not own
-------------
- Pandera schema definitions or backend execution (owned by infrastructure.validation).
- Source configuration parsing (owned by config.sources).
- Financial business logic (owned by domain).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import polars as pl

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId


class ValidationStage(StrEnum):
    """Pipeline stages where tabular validation gates operate."""

    PRE_BRONZE = "PRE_BRONZE"
    CANONICAL_BRONZE = "CANONICAL_BRONZE"


@dataclass(frozen=True, slots=True)
class ValidationExample:
    """A single bounded failure instance.

    Parameters
    ----------
    index : int | None, default=None
        Row index where violation occurred, if applicable.
    value : str, default=""
        Bounded stringified token representing the invalid value.
    """

    index: int | None = None
    value: str = ""


@dataclass(frozen=True, slots=True)
class ValidationCheckFailure:
    """Structured details for a single failed check or schema rule.

    Parameters
    ----------
    column : str | None
        Column name where the failure occurred, or None if frame-level.
    check : str
        Identifier or name of the failed check (e.g., 'not_nullable', 'dtype').
    error_message : str
        Human-readable description of the violation.
    failure_count : int
        Total number of rows or occurrences violating this check.
    examples : tuple[ValidationExample, ...]
        Bounded sample of violation examples (at most 5).
    """

    column: str | None
    check: str
    error_message: str
    failure_count: int
    examples: tuple[ValidationExample, ...]


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Execution context for tabular validation gates.

    Parameters
    ----------
    stage : ValidationStage
        Pipeline stage at which validation is applied.
    dataset_id : DatasetId
        Authoritative dataset identifier being validated.
    source_id : SourceId | None, default=None
        Source provider identifier if validating source-shaped evidence.
    contract_id : str, default=""
        Authoritative contract identifier or schema name.
    contract_version : str, default="1.0.0"
        Semantic version of the validating contract.
    run_id : str | None, default=None
        Active execution run identifier for distributed trace correlation.
    """

    stage: ValidationStage
    dataset_id: DatasetId
    source_id: SourceId | None = None
    contract_id: str = ""
    contract_version: str = "1.0.0"
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Summary outcome of a tabular frame validation run.

    Parameters
    ----------
    is_valid : bool
        True if all checks passed with zero violations.
    stage : ValidationStage
        Validation stage applied.
    dataset_id : DatasetId
        Dataset identifier.
    source_id : SourceId | None
        Source identifier if applicable.
    contract_id : str
        Contract identifier.
    contract_version : str
        Contract semantic version.
    affected_row_count : int
        Total count of rows containing one or more violations.
    failures : tuple[ValidationCheckFailure, ...]
        List of bounded check failure summaries.
    remediation : str | None, default=None
        Actionable remediation guidance for the user or operator.
    duration_ms : float, default=0.0
        Execution duration of the validation evaluation in milliseconds.
    """

    is_valid: bool
    stage: ValidationStage
    dataset_id: DatasetId
    source_id: SourceId | None
    contract_id: str
    contract_version: str
    affected_row_count: int
    failures: tuple[ValidationCheckFailure, ...]
    remediation: str | None = None
    duration_ms: float = 0.0


class ValidationError(RuntimeError):
    """Raised when tabular data fails authoritative validation contracts.

    Parameters
    ----------
    result : ValidationResult
        Structured validation outcome details.
    message : str | None, default=None
        Optional custom error message; if omitted, derives a detailed report from result.
    """

    def __init__(self, result: ValidationResult, message: str | None = None) -> None:
        self.result = result
        if message is None:
            summary_lines = [
                f"Validation failed for dataset '{result.dataset_id.value}' at stage '{result.stage.value}' "
                f"(contract '{result.contract_id}', affected rows: {result.affected_row_count}):"
            ]
            for failure in result.failures:
                col_desc = f"column '{failure.column}'" if failure.column else "frame-level check"
                summary_lines.append(
                    f"  - [{failure.check}] on {col_desc}: {failure.error_message} "
                    f"({failure.failure_count} occurrences)"
                )
                for ex in failure.examples:
                    idx_desc = f" at row {ex.index}" if ex.index is not None else ""
                    summary_lines.append(f"      sample: '{ex.value}'{idx_desc}")
            if result.remediation:
                summary_lines.append(f"Remediation: {result.remediation}")
            message = "\n".join(summary_lines)
        super().__init__(message)


class DataFrameValidator(Protocol):
    """Cross-boundary contract for validating tabular frames against schemas."""

    def validate(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        schema: object,
        context: ValidationContext,
        *,
        raise_on_error: bool = True,
    ) -> ValidationResult:
        """Validate a Polars DataFrame or LazyFrame against an authoritative schema.

        Parameters
        ----------
        frame : pl.DataFrame | pl.LazyFrame
            Input Polars data frame or lazy frame.
        schema : object
            Authoritative validation schema (e.g., Pandera DataFrameSchema).
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
        ValidationError
            If validation checks fail and raise_on_error is True.
        """
        ...
