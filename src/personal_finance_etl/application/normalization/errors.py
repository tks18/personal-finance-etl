"""Authoritative typed exception hierarchy for the mapping and normalization engine.

Owns
----
- NormalizationError: Root exception carrying DatasetId and SourceId forensic context.
- MappingCompilationError: Base exception for errors during normalization plan compilation.
- MissingSourceFieldError: Raised when a required source column is missing from source data.
- InvalidCanonicalTargetError: Raised when a mapping targets an unknown canonical Bronze field.
- DuplicateMappingError: Raised when duplicate source or canonical fields appear in mappings.
- NormalizationExecutionError: Raised when a vectorized normalization operation fails at runtime.

Does not own
-------------
- Pipeline lifecycle coordinator exceptions (owned by application.pipeline.lifecycle).
- Gatekeeper validation exceptions (owned by application.ingestion.coordinator).
"""

from __future__ import annotations

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId

__all__ = [
    "DuplicateMappingError",
    "InvalidCanonicalTargetError",
    "MappingCompilationError",
    "MissingSourceFieldError",
    "NormalizationError",
    "NormalizationExecutionError",
]


class NormalizationError(Exception):
    """Base exception for all normalization and mapping compilation/execution failures.

    Parameters
    ----------
    message : str
        Human-readable explanation of the error.
    dataset_id : DatasetId | str
        Canonical dataset identifier being planned or executed.
    source_id : SourceId | str | None, default None
        Physical evidence source identifier associated with the dataset, if known.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        source_id: SourceId | str | None = None,
    ) -> None:
        self.dataset_id = str(dataset_id)
        self.source_id = str(source_id) if source_id is not None else None
        super().__init__(f"[{self.dataset_id}] {message}")


class MappingCompilationError(NormalizationError):
    """Base exception for errors during normalization plan compilation."""


class MissingSourceFieldError(MappingCompilationError):
    """Raised when a mapped or normalized source field is missing from the incoming schema.

    Parameters
    ----------
    message : str
        Detailed description of the missing column.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    missing_field : str
        Name of the missing column in the source schema.
    available_fields : tuple[str, ...]
        List or tuple of available columns found in the source schema.
    source_id : SourceId | str | None, default None
        Physical source identifier if known.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        missing_field: str,
        available_fields: tuple[str, ...],
        source_id: SourceId | str | None = None,
    ) -> None:
        self.missing_field = missing_field
        self.available_fields = available_fields
        super().__init__(message, dataset_id, source_id)


class InvalidCanonicalTargetError(MappingCompilationError):
    """Raised when a column mapping targets an unknown canonical Bronze field.

    Parameters
    ----------
    message : str
        Detailed description of the invalid mapping target.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    target_field : str
        Invalid target field name specified in configuration.
    permitted_fields : frozenset[str]
        Set of valid canonical Bronze column names for this dataset.
    source_id : SourceId | str | None, default None
        Physical source identifier if known.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        target_field: str,
        permitted_fields: frozenset[str],
        source_id: SourceId | str | None = None,
    ) -> None:
        self.target_field = target_field
        self.permitted_fields = permitted_fields
        super().__init__(message, dataset_id, source_id)


class DuplicateMappingError(MappingCompilationError):
    """Raised when duplicate source fields or duplicate canonical targets appear in mappings.

    Parameters
    ----------
    message : str
        Detailed description of the duplicate collision.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    duplicate_field : str
        Column name that appeared more than once.
    is_source_field : bool
        True if the collision occurred on a source field, False if on a canonical target.
    source_id : SourceId | str | None, default None
        Physical source identifier if known.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        duplicate_field: str,
        is_source_field: bool,
        source_id: SourceId | str | None = None,
    ) -> None:
        self.duplicate_field = duplicate_field
        self.is_source_field = is_source_field
        super().__init__(message, dataset_id, source_id)


class NormalizationExecutionError(NormalizationError):
    """Raised when a vectorized normalization operation fails at runtime.

    Parameters
    ----------
    message : str
        Detailed description of the runtime failure.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    operation : str
        Normalization rule name that failed.
    field : str
        Column name upon which the operation failed.
    source_id : SourceId | str | None, default None
        Physical source identifier if known.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        operation: str,
        field: str,
        source_id: SourceId | str | None = None,
    ) -> None:
        self.operation = operation
        self.field = field
        super().__init__(message, dataset_id, source_id)
