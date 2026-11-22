"""Authoritative canonical production runtime for assembling, validating, and publishing Bronze datasets.

Owns
----
- CanonicalProductionEngine: Core application engine turning CanonicalFragments into a validated canonical dataset.
- Orchestrates SOURCE (DIRECT, UNION), PROVIDER, and DERIVED canonical production paths.
- Enforces target contract schema alignment (required vs optional columns).
- Evaluates post-assembly canonical row identity with proper multi-source scoping.
- Enforces strict duplicate/grain rules: fails deterministically on conflicting duplicates; rejects ordering-dependent dedupe.
- Executes Gate 2 (Pandera canonical schema validation) on the finalized assembled dataset candidate.

Does not own
-------------
- Low-level source byte extraction or SQLite/Excel/CSV parsing (owned by infrastructure.providers).
- Physical DuckDB database write execution or connection lifecycle (owned by infrastructure.warehouse).
- Silver domain transformations or financial calculations (owned by domain.*).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

import polars as pl

from personal_finance_etl.application.ingestion.canonical_recipes import (
    CanonicalRecipeRegistry,
    get_global_recipe_registry,
)
from personal_finance_etl.application.ingestion.identity import (
    compile_identity_plan,
    execute_identity_plan,
)
from personal_finance_etl.application.ingestion.route_executor import (
    MaterializedCanonicalFragment,
)
from personal_finance_etl.config.sources.identity import (
    BronzeIdentityStrategy,
    SourceFieldIdentity,
)
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.canonical_recipes import (
    CanonicalProductionError,
    CanonicalProductionResult,
    ConflictingDuplicateIdentityError,
    IdenticalEvidenceCollisionError,
    IncompatibleFragmentSchemaError,
    MissingRequiredColumnError,
    UndeclaredUnionRouteError,
)
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.contracts.validation import (
    DataFrameValidator,
    ValidationContext,
    ValidationStage,
)
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    get_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
)

__all__ = [
    "CanonicalProductionEngine",
]


class CanonicalProductionEngine:
    """Authoritative execution engine for assembling and validating canonical Bronze datasets.

    Parameters
    ----------
    validator : DataFrameValidator | None, default None
        Authoritative validator instance executing Gate-2 schema checks.
    recipe_registry : CanonicalRecipeRegistry | None, default None
        Registry for resolving and executing registered derivation recipes.
    """

    def __init__(
        self,
        validator: DataFrameValidator | None = None,
        recipe_registry: CanonicalRecipeRegistry | None = None,
    ) -> None:
        self.validator = validator or PanderaDataFrameValidator()
        self.recipe_registry = recipe_registry or get_global_recipe_registry()

    def _collect_candidate_frames(
        self,
        plan: CanonicalDatasetPlan,
        fragments: Sequence[MaterializedCanonicalFragment],
        provider_data: pl.DataFrame | None,
        dependent_datasets: Mapping[DatasetId, pl.DataFrame] | None,
    ) -> list[pl.DataFrame]:
        """Collect source, provider, or derived frames according to plan."""
        target_ds = plan.dataset_id
        candidate_frames: list[pl.DataFrame] = []

        if plan.producer_kind == CanonicalProducerKind.SOURCE:
            if plan.assembly_mode == SourceAssemblyMode.DIRECT:
                if len(fragments) == 0:
                    raise CanonicalProductionError(
                        f"DIRECT production for dataset '{target_ds.value}' received 0 fragments; exactly 1 required.",
                        dataset_id=target_ds,
                    )
                if len(fragments) > 1:
                    raise CanonicalProductionError(
                        f"DIRECT production for dataset '{target_ds.value}' received {len(fragments)} fragments; "
                        "exactly 1 permitted. Use explicit UNION for multi-fragment assembly.",
                        dataset_id=target_ds,
                    )
                candidate_frames.append(fragments[0].frame)
            elif plan.assembly_mode == SourceAssemblyMode.UNION:
                if len(fragments) == 0:
                    candidate_frames.append(pl.DataFrame())
                else:
                    if plan.route_refs:
                        declared_route_ids = {r.route_id for r in plan.route_refs}
                        undeclared = [
                            f.fragment.route_id
                            for f in fragments
                            if f.fragment.route_id not in declared_route_ids
                        ]
                        if undeclared:
                            raise UndeclaredUnionRouteError(
                                message=(
                                    f"UNION production for dataset '{target_ds.value}' encountered undeclared "
                                    f"route fragments: {sorted(set(str(u) for u in undeclared))}. "
                                    f"Declared routes: {sorted(str(r) for r in declared_route_ids)}."
                                ),
                                dataset_id=target_ds,
                                undeclared_routes=tuple(sorted(set(str(u) for u in undeclared))),
                            )

                    sorted_fragments = sorted(
                        fragments,
                        key=lambda f: (
                            str(f.fragment.binding_id),
                            str(f.fragment.route_id),
                            f.fragment.fragment_id,
                        ),
                    )
                    for f in sorted_fragments:
                        candidate_frames.append(f.frame)

        elif plan.producer_kind == CanonicalProducerKind.PROVIDER:
            if provider_data is None:
                raise CanonicalProductionError(
                    f"PROVIDER production for dataset '{target_ds.value}' requires provider_data.",
                    dataset_id=target_ds,
                )
            candidate_frames.append(provider_data)

        elif plan.producer_kind == CanonicalProducerKind.DERIVED:
            if not plan.recipe_name:
                raise CanonicalProductionError(
                    f"DERIVED production for dataset '{target_ds.value}' requires a non-empty recipe_name.",
                    dataset_id=target_ds,
                )
            derived_df = self.recipe_registry.execute_recipe(
                plan.recipe_name,
                dependent_datasets or {},
            )
            candidate_frames.append(derived_df)

        return candidate_frames

    def _align_candidate_frames(
        self,
        candidate_frames: list[pl.DataFrame],
        target_ds: DatasetId,
        canonical_schema: object,
    ) -> list[pl.DataFrame]:
        """Align fragment schemas against target canonical contract."""
        aligned_frames: list[pl.DataFrame] = []
        schema_cols: dict[str, object] = getattr(canonical_schema, "columns", {})
        required_cols = {
            name
            for name, col in schema_cols.items()
            if not getattr(col, "nullable", True) and name not in ("UID", "__identity_id__")
        }

        for frame in candidate_frames:
            if frame.height == 0 and len(frame.columns) == 0:
                continue

            missing = [c for c in required_cols if c not in frame.columns]
            if missing:
                raise MissingRequiredColumnError(
                    message=(
                        f"Fragment for dataset '{target_ds.value}' lacks required canonical "
                        f"column(s): {sorted(missing)}. Available: {sorted(frame.columns)}."
                    ),
                    dataset_id=target_ds,
                    missing_columns=tuple(sorted(missing)),
                )

            pad_exprs: list[pl.Expr] = []
            for name, col in schema_cols.items():
                col_dtype = getattr(col, "dtype", pl.String)
                target_dtype = getattr(col_dtype, "type", col_dtype) or pl.String
                if name not in frame.columns:
                    pad_exprs.append(pl.lit(None).cast(target_dtype).alias(name))
                else:
                    frame_dtype = frame[name].dtype
                    if (
                        getattr(target_dtype, "is_numeric", lambda: False)()
                        and not frame_dtype.is_numeric()
                    ):
                        if frame[name].null_count() != frame.height:
                            raise IncompatibleFragmentSchemaError(
                                message=(
                                    f"Incompatible type for column '{name}' in dataset '{target_ds.value}': "
                                    f"expected numeric type, got {frame_dtype}."
                                ),
                                dataset_id=target_ds,
                                field_name=name,
                                expected_type=str(target_dtype),
                                actual_type=str(frame_dtype),
                            )

            aligned = frame.with_columns(pad_exprs) if pad_exprs else frame
            allowed = set(schema_cols.keys()) | {"artifact_id", "__artifact_id__"}
            projected = [c for c in aligned.columns if c in allowed]
            aligned_frames.append(aligned.select(projected))

        return aligned_frames

    def _apply_post_assembly_identity(
        self,
        assembled_df: pl.DataFrame,
        resolved_contract: BronzeDataContract | None,
        identity_strategy: BronzeIdentityStrategy | None,
    ) -> tuple[pl.DataFrame, str, bool]:
        """Apply post-assembly canonical row identity."""
        applied_identity = False
        id_col = "UID"
        if resolved_contract is not None:
            if "(" in resolved_contract.grain and ")" in resolved_contract.grain:
                grain_candidate = resolved_contract.grain.split("(")[1].split(")")[0].strip()
                if "," not in grain_candidate and grain_candidate in assembled_df.columns:
                    id_col = grain_candidate

            requires_id = resolved_contract.identity_requirement == IdentityRequirement.REQUIRED
            if isinstance(
                identity_strategy, SourceFieldIdentity
            ) and identity_strategy.field not in (
                "Z_PK",
                "UID",
                "ZUID",
            ):
                id_col = identity_strategy.field

            if identity_strategy is not None:
                ident_plan = compile_identity_plan(
                    contract=resolved_contract,
                    available_fields=set(assembled_df.columns),
                    strategy=identity_strategy,
                    allow_optional_identity=True,
                )
                if ident_plan.strategy is not None and assembled_df.height > 0:
                    ident_res = execute_identity_plan(ident_plan, assembled_df, id_column=id_col)
                    assert isinstance(ident_res, pl.DataFrame)
                    assembled_df = ident_res
                    applied_identity = True
            elif id_col in assembled_df.columns:
                applied_identity = True
            elif requires_id and assembled_df.height > 0:
                compile_identity_plan(
                    contract=resolved_contract,
                    available_fields=set(assembled_df.columns),
                    strategy=None,
                    allow_optional_identity=False,
                )

        return assembled_df, id_col, applied_identity

    def _enforce_duplicates_and_grain(
        self,
        assembled_df: pl.DataFrame,
        target_ds: DatasetId,
        id_col: str,
        allow_identical_collapse: bool,
    ) -> pl.DataFrame:
        """Enforce duplicate and grain policies on assembled candidate."""
        if id_col in assembled_df.columns and assembled_df.height > 0:
            id_counts = assembled_df[id_col].value_counts()
            dup_keys = id_counts.filter(pl.col("count") > 1)[id_col].to_list()

            if dup_keys:
                payload_cols = [
                    c
                    for c in assembled_df.columns
                    if c not in (id_col, "artifact_id", "__artifact_id__")
                ]

                conflicts: list[dict[str, object]] = []
                for k in dup_keys:
                    k_str = str(k)
                    group_df = assembled_df.filter(pl.col(id_col) == k)
                    unique_payloads = group_df.select(payload_cols).n_unique()
                    if unique_payloads > 1:
                        conflicts.append(
                            {
                                "key": k_str,
                                "distinct_payload_variants": unique_payloads,
                                "total_rows": group_df.height,
                            }
                        )

                if conflicts:
                    raise ConflictingDuplicateIdentityError(
                        message=(
                            f"Conflicting duplicate identities detected for dataset '{target_ds.value}' "
                            f"on key column '{id_col}': {len(conflicts)} key(s) contain conflicting payload rows. "
                            f"Sample conflicts: {conflicts[:5]}."
                        ),
                        dataset_id=target_ds,
                        duplicate_count=len(conflicts),
                        sample_conflicts=tuple(conflicts[:5]),
                    )

                if allow_identical_collapse:
                    collapse_subset = [id_col] + payload_cols
                    assembled_df = assembled_df.unique(subset=collapse_subset)
                else:
                    sample_keys = tuple(str(k) for k in dup_keys[:5])
                    raise IdenticalEvidenceCollisionError(
                        message=(
                            f"Identical duplicate identities detected for dataset '{target_ds.value}' "
                            f"on key column '{id_col}': {len(dup_keys)} key(s) repeat identical payload evidence. "
                            f"Sample keys: {sample_keys}. Identical collapse is not enabled."
                        ),
                        dataset_id=target_ds,
                        duplicate_count=len(dup_keys),
                        sample_keys=sample_keys,
                    )

        return assembled_df

    def produce(
        self,
        plan: CanonicalDatasetPlan,
        fragments: Sequence[MaterializedCanonicalFragment] = (),
        *,
        provider_data: pl.DataFrame | None = None,
        dependent_datasets: Mapping[DatasetId, pl.DataFrame] | None = None,
        contract: BronzeDataContract | None = None,
        identity_strategy: BronzeIdentityStrategy | None = None,
        run_id: str | None = None,
        allow_identical_collapse: bool = False,
    ) -> tuple[pl.DataFrame, CanonicalProductionResult]:
        """Produce, assemble, identify, and validate a canonical Bronze dataset candidate.

        Parameters
        ----------
        plan : CanonicalDatasetPlan
            Authoritative compilation plan for the target canonical dataset.
        fragments : Sequence[MaterializedCanonicalFragment], default ()
            Materialized source fragments routed to this dataset.
        provider_data : pl.DataFrame | None, default None
            Normalized tabular evidence supplied by a market or external provider.
        dependent_datasets : Mapping[DatasetId, pl.DataFrame] | None, default None
            Active canonical datasets available as dependencies for DERIVED recipes.
        contract : BronzeDataContract | None, default None
            Authoritative Bronze warehouse contract. If None, resolved via dataset_id.
        identity_strategy : BronzeIdentityStrategy | None, default None
            Configured Bronze row identity strategy.
        run_id : str | None, default None
            Active pipeline execution run identifier.
        allow_identical_collapse : bool, default False
            Whether duplicate rows with identical payload evidence may be collapsed.

        Returns
        -------
        tuple[pl.DataFrame, CanonicalProductionResult]
            Validated canonical Polars DataFrame and production result descriptor.

        Raises
        ------
        CanonicalProductionError
            If assembly mode cardinality rules are violated.
        UndeclaredUnionRouteError
            If UNION assembly encounters fragments from undeclared routes.
        MissingRequiredColumnError
            If any fragment lacks a required canonical target column.
        IncompatibleFragmentSchemaError
            If any fragment column type conflicts with the target schema.
        ConflictingDuplicateIdentityError
            If duplicate identity keys contain conflicting payload values.
        IdenticalEvidenceCollisionError
            If duplicate identity keys have identical evidence but collapse is disallowed.
        """
        target_ds = plan.dataset_id
        resolved_contract = contract or get_bronze_contract_by_dataset_id(target_ds)
        canonical_schema = get_canonical_bronze_schema(target_ds)

        # 1. Fragment Collection & Assembly Mode Validation
        candidate_frames = self._collect_candidate_frames(
            plan, fragments, provider_data, dependent_datasets
        )

        # 2. Target Contract Schema Alignment
        aligned_frames = self._align_candidate_frames(candidate_frames, target_ds, canonical_schema)

        # 3. Vectorized Assembly
        if not aligned_frames:
            assembled_df = pl.DataFrame()
        elif len(aligned_frames) == 1:
            assembled_df = aligned_frames[0]
        else:
            assembled_df = pl.concat(aligned_frames, how="vertical_relaxed")

        # 4. Post-Assembly Canonical Row Identity
        assembled_df, id_col, applied_identity = self._apply_post_assembly_identity(
            assembled_df, resolved_contract, identity_strategy
        )

        # 5. Strict Duplicate & Grain Enforcement
        assembled_df = self._enforce_duplicates_and_grain(
            assembled_df, target_ds, id_col, allow_identical_collapse
        )

        # 6. Gate 2 Validation (CANONICAL_BRONZE)
        validation_passed = False
        if assembled_df.height > 0:
            canonical_ctx = ValidationContext(
                stage=ValidationStage.CANONICAL_BRONZE,
                dataset_id=target_ds,
                source_id=None,
                contract_id=resolved_contract.physical_table
                if resolved_contract
                else target_ds.value,
                run_id=run_id,
            )
            self.validator.validate(
                assembled_df, canonical_schema, canonical_ctx, raise_on_error=True
            )
            validation_passed = True
        else:
            validation_passed = True

        # 7. Compute Schema Fingerprint and Result Descriptor
        schema_repr = {
            c: str(dtype)
            for c, dtype in zip(assembled_df.columns, assembled_df.dtypes, strict=False)
        }
        schema_fingerprint = hashlib.sha256(
            json.dumps(schema_repr, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        result = CanonicalProductionResult(
            dataset_id=target_ds,
            producer_kind=plan.producer_kind,
            row_count=assembled_df.height,
            fragment_count=len(fragments),
            applied_identity=applied_identity,
            schema_fingerprint=schema_fingerprint,
            validation_passed=validation_passed,
        )

        return assembled_df, result
