"""Authoritative vectorized Polars execution engine for dataset normalization plans.

Owns
----
- NormalizationExecutor: Vectorized execution engine transforming source frames to canonical frames.

Does not own
-------------
- Plan compilation or target validation (owned by application.normalization.compiler).
- Physical database write or transaction logic (owned by infrastructure.warehouse).
- Extraction from disk or raw stores (owned by infrastructure.providers).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.application.normalization.errors import (
    MissingSourceFieldError,
    NormalizationExecutionError,
)
from personal_finance_etl.application.normalization.models import NormalizationPlan
from personal_finance_etl.config.sources.normalization import (
    CanonicalDtype,
    CastRule,
    ConstantRule,
    DefaultRule,
    MapValuesRule,
    NormalizationRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)

__all__ = ["NormalizationExecutor"]

_DTYPE_MAP: dict[CanonicalDtype, type[pl.DataType]] = {
    "string": pl.String,
    "int64": pl.Int64,
    "float64": pl.Float64,
    "boolean": pl.Boolean,
    "date": pl.Date,
}


def _build_rule_expression(rule: NormalizationRule) -> pl.Expr:
    """Build a pure, vectorized Polars expression for a single normalization rule.

    Parameters
    ----------
    rule : NormalizationRule
        Bounded normalization rule candidate.

    Returns
    -------
    pl.Expr
        Vectorized Polars expression executing the transformation.
    """
    col = pl.col(rule.field)

    if isinstance(rule, TrimRule):
        if rule.mode == "left":
            expr = col.str.strip_chars_start()
        elif rule.mode == "right":
            expr = col.str.strip_chars_end()
        else:
            expr = col.str.strip_chars()
    elif isinstance(rule, NormalizeNullRule):
        expr = pl.when(col.is_in(rule.null_values)).then(None).otherwise(col)
    elif isinstance(rule, ParseDateRule):
        expr = col.str.to_date(format=rule.format, strict=rule.strict)
    elif isinstance(rule, CastRule):
        target_pl_type = _DTYPE_MAP[rule.target_type]
        expr = col.cast(target_pl_type, strict=False)
    elif isinstance(rule, NormalizeCaseRule):
        if rule.case == "lower":
            expr = col.str.to_lowercase()
        elif rule.case == "title":
            expr = col.str.to_titlecase()
        else:
            expr = col.str.to_uppercase()
    elif isinstance(rule, MapValuesRule):
        if rule.default is not None:
            expr = col.replace_strict(rule.mapping, default=rule.default)
        else:
            expr = col.replace(rule.mapping)
    elif isinstance(rule, DefaultRule):
        expr = col.fill_null(rule.value)
    else:
        # ConstantRule
        return pl.lit(rule.value).alias(rule.field)

    return expr.alias(rule.field)


class NormalizationExecutor:
    """Executes compiled NormalizationPlans using high-performance, vectorized Polars expressions."""

    def execute(
        self,
        plan: NormalizationPlan,
        frame: pl.LazyFrame | pl.DataFrame,
    ) -> pl.LazyFrame:
        """Execute the normalization plan on a source-shaped frame into a canonical frame.

        Parameters
        ----------
        plan : NormalizationPlan
            Validated, deterministic execution plan.
        frame : pl.LazyFrame | pl.DataFrame
            Source-shaped input frame.

        Returns
        -------
        pl.LazyFrame
            Transformed canonical LazyFrame.

        Raises
        ------
        MissingSourceFieldError
            If required mapped source columns are missing from the input frame schema.
        NormalizationExecutionError
            If execution fails due to expression evaluation issues.
        """
        lf = frame.lazy() if isinstance(frame, pl.DataFrame) else frame

        # 1. Inspect Schema & Validate Source Column Presence
        available_schema = lf.collect_schema()
        available_names = set(available_schema.names())
        available_tuple = tuple(available_schema.names())

        for src_field in plan.column_mapping:
            if src_field not in available_names:
                raise MissingSourceFieldError(
                    message=(
                        f"Required source field '{src_field}' not found in incoming frame. "
                        f"Available columns: {list(available_tuple)}."
                    ),
                    dataset_id=plan.dataset_id,
                    missing_field=src_field,
                    available_fields=available_tuple,
                    source_id=plan.source_id,
                )

        # 2. Execute Pre-Rename Vectorized Rules
        for rule in plan.pre_rename_rules:
            if rule.field in available_names:
                try:
                    lf = lf.with_columns(_build_rule_expression(rule))
                except Exception as e:
                    raise NormalizationExecutionError(
                        message=f"Pre-rename rule '{rule.rule}' on field '{rule.field}' failed: {e}",
                        dataset_id=plan.dataset_id,
                        operation=rule.rule,
                        field=rule.field,
                        source_id=plan.source_id,
                    ) from e

        # 3. Apply Column Mapping (Renaming)
        if plan.column_mapping:
            try:
                lf = lf.rename(plan.column_mapping)
            except Exception as e:
                raise NormalizationExecutionError(
                    message=f"Column rename failed: {e}",
                    dataset_id=plan.dataset_id,
                    operation="rename",
                    field="mapping",
                    source_id=plan.source_id,
                ) from e

        # 4. Execute Post-Rename Vectorized Rules
        current_schema_names = set(lf.collect_schema().names())
        for rule in plan.post_rename_rules:
            # ConstantRule can add a new column, others operate on existing columns
            if isinstance(rule, ConstantRule) or rule.field in current_schema_names:
                try:
                    lf = lf.with_columns(_build_rule_expression(rule))
                    current_schema_names.add(rule.field)
                except Exception as e:
                    raise NormalizationExecutionError(
                        message=f"Post-rename rule '{rule.rule}' on field '{rule.field}' failed: {e}",
                        dataset_id=plan.dataset_id,
                        operation=rule.rule,
                        field=rule.field,
                        source_id=plan.source_id,
                    ) from e

        # 5. Project Expected Canonical Output Fields + Preserved Lineage Metadata
        # If output fields are defined, select them along with any present provenance fields
        if plan.expected_output_fields:
            projected: list[str] = [
                f for f in plan.expected_output_fields if f in current_schema_names
            ]
            for prov in plan.provenance_fields:
                if prov in current_schema_names and prov not in projected:
                    projected.append(prov)
            lf = lf.select(projected)

        return lf
