"""Bronze dataset row identity planning, compilation, and execution.

Owns
----
- IdentityPlan: Immutable compilation plan for Bronze row identity derivation.
- compile_identity_plan: Compiles Bronze contracts and source strategies into verified plans.
- execute_identity_plan: Evaluates identity plans across DataFrames or records with duplicate collision diagnostics.
- IdentityCollisionError, IdentityCollisionDiagnostic: Rich diagnostic error for duplicate row keys.
- MissingIdentityStrategyError, MissingIdentityFieldError, IdentityNotPermittedError: Typed compilation errors.

Does not own
-------------
- Source identity strategy Pydantic models (owned by config.sources.identity).
- BronzeDataContract definitions (owned by infrastructure.warehouse.contracts).
- Canonical cryptographic hashing kernel (owned by domain.common.identity).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.config.sources.identity import (
    BronzeIdentityStrategy,
    CompositeIdentity,
    DerivedDeterministicIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.domain.common.identity import (
    canonicalize_value,
    generate_deterministic_id,
)
from personal_finance_etl.infrastructure.warehouse.contracts import BronzeDataContract

__all__ = [
    "IdentityCollisionDiagnostic",
    "IdentityCollisionError",
    "IdentityNotPermittedError",
    "IdentityPlan",
    "MissingIdentityFieldError",
    "MissingIdentityStrategyError",
    "compile_identity_plan",
    "execute_identity_plan",
]


class IdentityPlanningError(ValueError):
    """Base exception for identity plan compilation failures."""


class MissingIdentityStrategyError(IdentityPlanningError):
    """Raised when a Bronze dataset requires row identity but no strategy is configured."""


class MissingIdentityFieldError(IdentityPlanningError):
    """Raised when an identity strategy references fields absent from source/canonical schema."""


class IdentityNotPermittedError(IdentityPlanningError):
    """Raised when an identity strategy is configured for a dataset that forbids Bronze identity."""


@dataclass(frozen=True, slots=True)
class IdentityCollisionDiagnostic:
    """Diagnostic details describing duplicate identity collisions.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier where collision occurred.
    duplicate_count : int
        Total number of duplicate row records identified.
    sample_duplicates : list[tuple[str, int]]
        Bounded sample of collision values paired with their repetition frequency.
    strategy_fields : tuple[str, ...]
        Source/canonical fields used to construct the identity.
    message : str
        Human-readable summary of the collision error.
    """

    dataset_id: DatasetId
    duplicate_count: int
    sample_duplicates: list[tuple[str, int]]
    strategy_fields: tuple[str, ...]
    message: str


class IdentityCollisionError(ValueError):
    """Raised when duplicate generated or source identities are detected for a unique dataset.

    Parameters
    ----------
    diagnostic : IdentityCollisionDiagnostic
        Diagnostic context detailing the duplicate keys, count, and strategy.
    """

    def __init__(self, diagnostic: IdentityCollisionDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


@dataclass(frozen=True, slots=True)
class IdentityPlan:
    """Immutable compiled execution plan for Bronze dataset row identity.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    requirement : IdentityRequirement
        Contractual requirement (REQUIRED or NONE).
    strategy : BronzeIdentityStrategy | None
        Target identity strategy to execute, or None if no identity is required.
    grain : str
        Contractual physical/business row grain description.
    target_fields : tuple[str, ...]
        Ordered sequence of source/canonical fields required to generate the identity.
    namespace : str
        Authoritative deterministic namespace prefix.
    """

    dataset_id: DatasetId
    requirement: IdentityRequirement
    strategy: BronzeIdentityStrategy | None
    grain: str
    target_fields: tuple[str, ...]
    namespace: str


def compile_identity_plan(
    contract: BronzeDataContract,
    available_fields: Sequence[str] | set[str],
    strategy: BronzeIdentityStrategy | None = None,
    *,
    allow_optional_identity: bool = False,
) -> IdentityPlan:
    """Compile an immutable IdentityPlan from a Bronze contract and user strategy.

    Parameters
    ----------
    contract : BronzeDataContract
        Authoritative warehouse Bronze data contract.
    available_fields : Sequence[str] | set[str]
        Collection of field/column names available in the source evidence schema.
    strategy : BronzeIdentityStrategy | None, default None
        User-configured identity strategy from source dataset configuration.
    allow_optional_identity : bool, default False
        Explicit override to permit identity strategy on datasets with IdentityRequirement.NONE.

    Returns
    -------
    IdentityPlan
        Compiled, validated immutable identity plan.

    Raises
    ------
    MissingIdentityStrategyError
        If contract.identity_requirement is REQUIRED but strategy is None.
    IdentityNotPermittedError
        If contract.identity_requirement is NONE but strategy is provided without allow_optional_identity.
    MissingIdentityFieldError
        If strategy references any field not present in available_fields.
    """
    avail_set = set(available_fields)

    if contract.identity_requirement == IdentityRequirement.REQUIRED:
        if strategy is None:
            raise MissingIdentityStrategyError(
                f"Bronze dataset '{contract.dataset_id}' has IdentityRequirement.REQUIRED, "
                "but no BronzeIdentityStrategy was provided."
            )

        target_fields: tuple[str, ...]
        match strategy:
            case SourceFieldIdentity(field=f):
                target_fields = (f,)
            case CompositeIdentity(fields=fl):
                target_fields = tuple(fl)
            case DerivedDeterministicIdentity(fields=fl):
                target_fields = tuple(fl)

        missing_fields = [f for f in target_fields if f not in avail_set]
        if missing_fields:
            raise MissingIdentityFieldError(
                f"Identity strategy for Bronze dataset '{contract.dataset_id}' references "
                f"field(s) {missing_fields} not found in available schema fields: "
                f"{sorted(avail_set)}"
            )

        if isinstance(strategy, DerivedDeterministicIdentity) and strategy.namespace:
            namespace = strategy.namespace
        else:
            namespace = f"BRONZE_{contract.dataset_id.name}"

        return IdentityPlan(
            dataset_id=contract.dataset_id,
            requirement=contract.identity_requirement,
            strategy=strategy,
            grain=contract.grain,
            target_fields=target_fields,
            namespace=namespace,
        )

    # contract.identity_requirement == IdentityRequirement.NONE
    if strategy is not None and not allow_optional_identity:
        raise IdentityNotPermittedError(
            f"Bronze dataset '{contract.dataset_id}' has IdentityRequirement.NONE and does not "
            "permit row identity generation. Pass allow_optional_identity=True if this dataset "
            "intentionally preserves source identifiers."
        )

    if strategy is not None and allow_optional_identity:
        match strategy:
            case SourceFieldIdentity(field=f):
                target_fields = (f,)
            case CompositeIdentity(fields=fl):
                target_fields = tuple(fl)
            case DerivedDeterministicIdentity(fields=fl):
                target_fields = tuple(fl)

        missing_fields = [f for f in target_fields if f not in avail_set]
        if missing_fields:
            raise MissingIdentityFieldError(
                f"Optional identity strategy for Bronze dataset '{contract.dataset_id}' references "
                f"field(s) {missing_fields} not found in available schema fields: "
                f"{sorted(avail_set)}"
            )

        namespace = (
            strategy.namespace
            if isinstance(strategy, DerivedDeterministicIdentity) and strategy.namespace
            else f"BRONZE_{contract.dataset_id.name}"
        )
        return IdentityPlan(
            dataset_id=contract.dataset_id,
            requirement=contract.identity_requirement,
            strategy=strategy,
            grain=contract.grain,
            target_fields=target_fields,
            namespace=namespace,
        )

    return IdentityPlan(
        dataset_id=contract.dataset_id,
        requirement=contract.identity_requirement,
        strategy=None,
        grain=contract.grain,
        target_fields=(),
        namespace="",
    )


def _check_and_raise_collisions(
    ids: Sequence[str],
    dataset_id: DatasetId,
    target_fields: tuple[str, ...],
) -> None:
    """Verify that generated identity keys are unique, raising IdentityCollisionError on duplicate keys."""
    counts = Counter(ids)
    duplicates = [(k, c) for k, c in counts.items() if c > 1]
    if duplicates:
        total_dup_rows = sum(c for _, c in duplicates)
        sample = sorted(duplicates, key=lambda x: x[1], reverse=True)[:5]
        msg = (
            f"Duplicate identity keys detected for Bronze dataset '{dataset_id}' "
            f"across fields {target_fields}: {total_dup_rows} total rows collide. "
            f"Sample collisions: {sample}"
        )
        diagnostic = IdentityCollisionDiagnostic(
            dataset_id=dataset_id,
            duplicate_count=total_dup_rows,
            sample_duplicates=sample,
            strategy_fields=target_fields,
            message=msg,
        )
        raise IdentityCollisionError(diagnostic)


def execute_identity_plan(
    plan: IdentityPlan,
    data: pl.DataFrame | Sequence[Mapping[str, object]],
    *,
    id_column: str = "__identity_id__",
) -> pl.DataFrame | list[str]:
    """Execute an IdentityPlan over a Polars DataFrame or sequence of record mappings.

    Parameters
    ----------
    plan : IdentityPlan
        Compiled immutable identity plan.
    data : pl.DataFrame | Sequence[Mapping[str, object]]
        Source tabular evidence data (Polars DataFrame or list of record dicts).
    id_column : str, default "__identity_id__"
        Target identity column name to append when data is a Polars DataFrame.

    Returns
    -------
    pl.DataFrame | list[str]
        Polars DataFrame with attached identity column if input was a DataFrame;
        list of generated identity strings if input was a sequence of dicts.

    Raises
    ------
    KeyError
        If target identity fields are missing from data.
    IdentityCollisionError
        If duplicate identity values are generated for a dataset requiring unique identity.
    """
    if plan.strategy is None:
        if isinstance(data, pl.DataFrame):
            return data
        return []

    # Handle sequence of record dicts
    if not isinstance(data, pl.DataFrame):
        records = list(data)
        ids: list[str] = []
        match plan.strategy:
            case SourceFieldIdentity(field=field_name):
                for row in records:
                    val = row.get(field_name)
                    ids.append(canonicalize_value(val))
            case CompositeIdentity(fields=field_names):
                for row in records:
                    parts = [canonicalize_value(row.get(f)) for f in field_names]
                    ids.append(":".join(parts))
            case DerivedDeterministicIdentity(fields=field_names):
                for row in records:
                    row_fields = {f: row.get(f) for f in field_names}
                    ids.append(generate_deterministic_id(plan.namespace, row_fields))

        _check_and_raise_collisions(ids, plan.dataset_id, plan.target_fields)
        return ids

    # Handle Polars DataFrame
    df = data
    missing_cols = [f for f in plan.target_fields if f not in df.columns]
    if missing_cols:
        raise KeyError(
            f"DataFrame missing required identity fields for '{plan.dataset_id}': {missing_cols}"
        )

    match plan.strategy:
        case SourceFieldIdentity(field=field_name):
            generated_ids = [canonicalize_value(v) for v in df[field_name].to_list()]
        case CompositeIdentity(fields=field_names):
            rows_data = df.select(field_names).to_dicts()
            generated_ids = [
                ":".join(canonicalize_value(row[f]) for f in field_names) for row in rows_data
            ]
        case DerivedDeterministicIdentity(fields=field_names):
            rows_data = df.select(field_names).to_dicts()
            generated_ids = [
                generate_deterministic_id(plan.namespace, {f: row[f] for f in field_names})
                for row in rows_data
            ]

    _check_and_raise_collisions(generated_ids, plan.dataset_id, plan.target_fields)
    return df.with_columns(pl.Series(name=id_column, values=generated_ids, dtype=pl.Utf8))
