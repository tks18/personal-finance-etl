"""Authoritative vectorized Polars execution engine for canonical route interpretation.

Owns
----
- UnmappedSemanticValueError: Strongly-typed diagnostic exception for unmapped categorical values.
- MaterializedCanonicalFragment: Materialized tabular fragment paired with CanonicalFragment metadata.
- RouteExecutor: Vectorized Polars engine transforming Pre-Bronze frames into CanonicalFragments.

Does not own
------------
- Route compilation or target schema validation (owned by application.ingestion.route_compiler).
- Physical warehouse table persistence (owned by infrastructure.warehouse).
- Multi-source assembly / UNION (owned by application.pipeline.canonical_production).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.application.ingestion.route_compiler import CompiledRoutePlan
from personal_finance_etl.application.normalization.executor import build_rule_expression
from personal_finance_etl.config.sources.semantics import (
    ExcludeWhen,
    PredicateOperator,
    PredicateRule,
    SemanticMapRule,
)
from personal_finance_etl.contracts.canonical_plans import CanonicalFragment
from personal_finance_etl.contracts.sources import CanonicalRouteId, SourceBindingId

__all__ = [
    "MaterializedCanonicalFragment",
    "RouteExecutor",
    "UnmappedSemanticValueError",
]


class UnmappedSemanticValueError(ValueError):
    """Exception raised when an unrecognized categorical value violates fail-fast semantic mapping.

    Parameters
    ----------
    message : str
        Actionable error diagnostic message.
    binding_id : SourceBindingId | None
        Originating source binding identity.
    route_id : CanonicalRouteId
        Originating canonical route identity.
    field : str
        Target column name where unmapped value appeared.
    offending_values : list[str]
        List of unmapped categorical values encountered in data.
    """

    def __init__(
        self,
        message: str,
        binding_id: SourceBindingId | None,
        route_id: CanonicalRouteId,
        field: str,
        offending_values: list[str],
    ) -> None:
        super().__init__(message)
        self.binding_id = binding_id
        self.route_id = route_id
        self.field = field
        self.offending_values = offending_values


@dataclass(frozen=True, slots=True)
class MaterializedCanonicalFragment:
    """Materialized tabular fragment paired with canonical fragment descriptor metadata.

    Parameters
    ----------
    fragment : CanonicalFragment
        Authoritative immutable fragment descriptor.
    frame : pl.DataFrame
        Materialized canonical tabular data frame.
    """

    fragment: CanonicalFragment
    frame: pl.DataFrame


def _build_predicate_expression(pred: PredicateRule) -> pl.Expr:
    """Build a vectorized Polars boolean predicate expression.

    Parameters
    ----------
    pred : PredicateRule
        Declarative route predicate rule candidate.

    Returns
    -------
    pl.Expr
        Vectorized Polars expression evaluating to Boolean.
    """
    col = pl.col(pred.field)
    op = pred.operator

    expr: pl.Expr
    if op == PredicateOperator.EQUALS:
        expr = col == pl.lit(pred.value)
    elif op == PredicateOperator.NOT_EQUALS:
        expr = col != pl.lit(pred.value)
    elif op == PredicateOperator.IS_IN:
        in_vals = list(pred.value) if isinstance(pred.value, (list, tuple)) else [pred.value]
        expr = col.is_in(in_vals)
    elif op == PredicateOperator.NOT_IN:
        in_vals = list(pred.value) if isinstance(pred.value, (list, tuple)) else [pred.value]
        expr = ~col.is_in(in_vals)
    elif op == PredicateOperator.IS_NULL:
        expr = col.is_null()
    elif op == PredicateOperator.IS_NOT_NULL:
        expr = col.is_not_null()
    elif op == PredicateOperator.IS_EMPTY:
        expr = (col.is_null()) | (col.cast(pl.String).str.strip_chars() == "")
    else:
        # IS_NOT_EMPTY
        expr = (col.is_not_null()) & (col.cast(pl.String).str.strip_chars() != "")

    if isinstance(pred, ExcludeWhen):
        return ~expr
    return expr


class RouteExecutor:
    """Vectorized Polars engine executing compiled canonical route plans."""

    def execute(
        self,
        plan: CompiledRoutePlan,
        frame: pl.DataFrame | pl.LazyFrame,
    ) -> MaterializedCanonicalFragment:
        """Execute a compiled canonical route over an incoming tabular frame.

        Parameters
        ----------
        plan : CompiledRoutePlan
            Compiled deterministic route execution plan.
        frame : pl.DataFrame | pl.LazyFrame
            Pre-Bronze tabular source evidence.

        Returns
        -------
        MaterializedCanonicalFragment
            Materialized tabular frame and CanonicalFragment metadata.

        Raises
        ------
        UnmappedSemanticValueError
            If a categorical value is unmapped and route specifies fail-fast policy.
        """
        mat_df = frame.collect() if isinstance(frame, pl.LazyFrame) else frame

        # Stage 1: Source Projection / Rename
        active_renames = {k: v for k, v in plan.source_renames.items() if k in mat_df.columns}
        res = mat_df.rename(active_renames) if active_renames else mat_df

        # Stage 2: Representation Normalization (trim, null, date, cast, case, default)
        for norm_rule in plan.normalization_rules:
            if norm_rule.field in res.columns:
                expr = build_rule_expression(norm_rule)
                res = res.with_columns(expr)

        # Stage 3: Predicate Filtering (IncludeWhen / ExcludeWhen)
        # Note: Filtering placeholder/deleted rows occurs BEFORE semantic value mapping
        for pred in plan.predicates:
            if pred.field in res.columns:
                pred_expr = _build_predicate_expression(pred)
                res = res.filter(pred_expr)

        # Stage 4: Semantic Interpretation (MapValues, Constant)
        for sem_rule in plan.semantic_rules:
            if isinstance(sem_rule, SemanticMapRule):
                if sem_rule.field in res.columns:
                    col_series = res[sem_rule.field]
                    # Check for unmapped non-null values if fail-fast policy is active
                    if sem_rule.on_unmapped == "error" and res.height > 0:
                        distinct_vals = col_series.drop_nulls().cast(pl.String).unique().to_list()
                        unmapped = [str(v) for v in distinct_vals if str(v) not in sem_rule.mapping]
                        if unmapped:
                            raise UnmappedSemanticValueError(
                                message=(
                                    f"Route '{plan.route_id}' in binding '{plan.binding_id}' failed: "
                                    f"encountered unmapped categorical values {unmapped} in column '{sem_rule.field}'. "
                                    f"Permitted mappings: {sorted(sem_rule.mapping.keys())}."
                                ),
                                binding_id=plan.binding_id,
                                route_id=plan.route_id,
                                field=sem_rule.field,
                                offending_values=unmapped,
                            )

                    # Vectorized mapping
                    if sem_rule.default is not None:
                        res = res.with_columns(
                            pl.col(sem_rule.field)
                            .cast(pl.String)
                            .replace_strict(sem_rule.mapping, default=sem_rule.default)
                        )
                    else:
                        res = res.with_columns(
                            pl.col(sem_rule.field).cast(pl.String).replace(sem_rule.mapping)
                        )
            else:
                # SemanticConstantRule
                res = res.with_columns(pl.lit(sem_rule.value).alias(sem_rule.field))

        # Stage 5: Canonical Target Projection
        # Retain only recognized canonical fields for the target dataset plus operational provenance
        allowed_fields = set(plan.canonical_columns) | set(plan.provenance_columns)
        projected_cols = [c for c in res.columns if c in allowed_fields]
        res = res.select(projected_cols)

        # Stage 6: Materialize CanonicalFragment Descriptor
        binding_part = str(plan.binding_id) if plan.binding_id is not None else "unbound"
        frag_id = f"frag_{binding_part}_{plan.route_id}_{plan.target_dataset_id.value}"

        schema_repr = {c: str(dtype) for c, dtype in zip(res.columns, res.dtypes, strict=False)}
        schema_hash = hashlib.sha256(
            json.dumps(schema_repr, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        fragment = CanonicalFragment(
            fragment_id=frag_id,
            binding_id=plan.binding_id or SourceBindingId(binding_part),
            route_id=plan.route_id,
            target_dataset_id=plan.target_dataset_id,
            row_count=res.height,
            schema_fingerprint=f"sch_{schema_hash}",
        )

        return MaterializedCanonicalFragment(fragment=fragment, frame=res)
