"""Authoritative contracts and descriptors for canonical derivation recipes and production outcomes.

Owns
----
- CanonicalRecipeDescriptor: Slotted metadata descriptor for registered canonical derivation recipes.
- CanonicalProductionResult: Immutable descriptor for the outcome of canonical production for a dataset.
- CanonicalProductionError: Root exception hierarchy for canonical production and assembly failures.
- MissingRequiredColumnError: Raised when an assembled fragment lacks a required canonical target column.
- IncompatibleFragmentSchemaError: Raised when a fragment's column types conflict with the target contract.
- UndeclaredUnionRouteError: Raised when UNION assembly encounters unexpected or undeclared route fragments.
- ConflictingDuplicateIdentityError: Raised when duplicate identity keys have conflicting canonical payload values.
- IdenticalEvidenceCollisionError: Raised when duplicate identity keys have identical evidence but contract forbids collapse.
- UnresolvedRecipeError: Raised when a requested derivation recipe is not registered.
- CanonicalIntegrityError: Raised when cross-dataset referential integrity fails before Silver execution.

Does not own
-------------
- Polars DataFrame manipulation or vectorized execution (owned by application.ingestion.canonical_production).
- Pandera schema validation execution (owned by infrastructure.validation).
- DuckDB transaction or physical table persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_finance_etl.contracts.canonical_plans import CanonicalProducerKind
from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "CanonicalIntegrityError",
    "CanonicalProductionError",
    "CanonicalProductionResult",
    "CanonicalRecipeDescriptor",
    "ConflictingDuplicateIdentityError",
    "IdenticalEvidenceCollisionError",
    "IncompatibleFragmentSchemaError",
    "MissingRequiredColumnError",
    "UndeclaredUnionRouteError",
    "UnresolvedRecipeError",
]


class CanonicalProductionError(Exception):
    """Base exception for all canonical production, assembly, and integrity errors.

    Parameters
    ----------
    message : str
        Human-readable description of the production failure.
    dataset_id : DatasetId | str | None, default None
        Target canonical dataset identifier associated with the failure, if known.
    """

    def __init__(self, message: str, dataset_id: DatasetId | str | None = None) -> None:
        self.dataset_id = str(dataset_id) if dataset_id is not None else None
        prefix = f"[{self.dataset_id}] " if self.dataset_id else ""
        super().__init__(f"{prefix}{message}")


class MissingRequiredColumnError(CanonicalProductionError):
    """Raised when an incoming fragment lacks one or more required canonical target columns.

    Parameters
    ----------
    message : str
        Detailed description of the missing required columns.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    missing_columns : tuple[str, ...]
        Names of required columns missing from the fragment.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        missing_columns: tuple[str, ...],
    ) -> None:
        self.missing_columns = missing_columns
        super().__init__(message, dataset_id=dataset_id)


class IncompatibleFragmentSchemaError(CanonicalProductionError):
    """Raised when an incoming fragment contains column types incompatible with the target contract.

    Parameters
    ----------
    message : str
        Detailed description of the schema incompatibility.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    field_name : str
        Name of the incompatible column.
    expected_type : str
        Expected canonical data type description.
    actual_type : str
        Actual data type observed in the fragment.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        field_name: str,
        expected_type: str,
        actual_type: str,
    ) -> None:
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(message, dataset_id=dataset_id)


class UndeclaredUnionRouteError(CanonicalProductionError):
    """Raised when UNION assembly encounters route fragments not explicitly configured for the dataset.

    Parameters
    ----------
    message : str
        Detailed description of the unexpected routes.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    undeclared_routes : tuple[str, ...]
        Identifiers of routes encountered but not declared in production plan.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        undeclared_routes: tuple[str, ...],
    ) -> None:
        self.undeclared_routes = undeclared_routes
        super().__init__(message, dataset_id=dataset_id)


class ConflictingDuplicateIdentityError(CanonicalProductionError):
    """Raised when duplicate canonical identity keys are detected with conflicting payload values.

    Parameters
    ----------
    message : str
        Detailed description of the duplicate collision conflict.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    duplicate_count : int
        Total number of conflicting duplicate rows detected.
    sample_conflicts : tuple[dict[str, object], ...]
        Bounded sample of conflicting row representations.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        duplicate_count: int,
        sample_conflicts: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.duplicate_count = duplicate_count
        self.sample_conflicts = sample_conflicts
        super().__init__(message, dataset_id=dataset_id)


class IdenticalEvidenceCollisionError(CanonicalProductionError):
    """Raised when duplicate identity keys have identical evidence but contract forbids collapse.

    Parameters
    ----------
    message : str
        Detailed description of the identical collision.
    dataset_id : DatasetId | str
        Target canonical dataset identifier.
    duplicate_count : int
        Total number of identical duplicate rows detected.
    sample_keys : tuple[str, ...]
        Bounded sample of collided identity keys.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        duplicate_count: int,
        sample_keys: tuple[str, ...] = (),
    ) -> None:
        self.duplicate_count = duplicate_count
        self.sample_keys = sample_keys
        super().__init__(message, dataset_id=dataset_id)


class UnresolvedRecipeError(CanonicalProductionError):
    """Raised when a requested canonical derivation recipe is not registered.

    Parameters
    ----------
    message : str
        Detailed description of the missing recipe.
    recipe_name : str
        Name of the requested derivation recipe.
    dataset_id : DatasetId | str | None, default None
        Target canonical dataset identifier, if known.
    """

    def __init__(
        self,
        message: str,
        recipe_name: str,
        dataset_id: DatasetId | str | None = None,
    ) -> None:
        self.recipe_name = recipe_name
        super().__init__(message, dataset_id=dataset_id)


class CanonicalIntegrityError(CanonicalProductionError):
    """Raised when cross-dataset referential integrity fails across active canonical datasets.

    Parameters
    ----------
    message : str
        Detailed description of the referential integrity violation.
    dataset_id : DatasetId | str
        Source dataset containing broken foreign references.
    foreign_key : str
        Foreign key column name.
    target_dataset_id : DatasetId | str
        Referenced target dataset identifier.
    orphan_count : int
        Total count of orphan reference values detected.
    sample_orphans : tuple[str, ...]
        Bounded sample of orphan reference keys.
    """

    def __init__(
        self,
        message: str,
        dataset_id: DatasetId | str,
        foreign_key: str,
        target_dataset_id: DatasetId | str,
        orphan_count: int,
        sample_orphans: tuple[str, ...] = (),
    ) -> None:
        self.foreign_key = foreign_key
        self.target_dataset_id = str(target_dataset_id)
        self.orphan_count = orphan_count
        self.sample_orphans = sample_orphans
        super().__init__(message, dataset_id=dataset_id)


@dataclass(frozen=True, slots=True)
class CanonicalRecipeDescriptor:
    """Immutable slotted metadata descriptor for a registered canonical derivation recipe.

    Parameters
    ----------
    recipe_id : str
        Unique identifier of the derivation recipe.
    version : str
        Semantic version string of the recipe implementation.
    target_dataset_id : DatasetId
        Canonical dataset produced by this recipe.
    dependencies : tuple[DatasetId, ...]
        Ordered tuple of canonical DatasetIds required as inputs to this recipe.
    description : str
        Human-readable summary of the derivation logic.
    """

    recipe_id: str
    version: str
    target_dataset_id: DatasetId
    dependencies: tuple[DatasetId, ...]
    description: str


@dataclass(frozen=True, slots=True)
class CanonicalProductionResult:
    """Immutable outcome descriptor for canonical production of a single canonical dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier produced.
    producer_kind : CanonicalProducerKind
        Producer mechanism executed (SOURCE, PROVIDER, DERIVED).
    row_count : int
        Number of valid canonical rows produced.
    fragment_count : int
        Number of contributing source fragments assembled.
    applied_identity : bool
        Whether canonical row identity was evaluated or applied.
    schema_fingerprint : str | None, default None
        Optional cryptographic fingerprint of the final assembled schema.
    validation_passed : bool, default True
        Whether Gate-2 validation succeeded for this dataset candidate.
    """

    dataset_id: DatasetId
    producer_kind: CanonicalProducerKind
    row_count: int
    fragment_count: int
    applied_identity: bool
    schema_fingerprint: str | None = None
    validation_passed: bool = True
