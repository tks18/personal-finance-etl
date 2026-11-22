"""Authoritative compiler transforming canonical route configurations into deterministic execution plans.

Owns
----
- CompiledRoutePlan: Immutable execution plan governing route execution.
- RouteCompiler: Non-I/O service compiling CanonicalRouteConfig into CompiledRoutePlan.

Does not own
------------
- Route dataframe execution (owned by application.ingestion.route_executor).
- User route configuration models (owned by config.sources.binding_model).
- Canonical Bronze contract definitions (owned by contracts.canonical_fields).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from personal_finance_etl.application.normalization.errors import (
    DuplicateMappingError,
    InvalidCanonicalTargetError,
    MissingSourceFieldError,
)
from personal_finance_etl.config.sources.binding_model import CanonicalRouteConfig
from personal_finance_etl.config.sources.normalization import (
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
from personal_finance_etl.config.sources.semantics import (
    PredicateRule,
    SemanticConstantRule,
    SemanticMapRule,
    SemanticRule,
)
from personal_finance_etl.contracts.canonical_fields import (
    get_canonical_fields,
    is_valid_canonical_field,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import CanonicalRouteId, SourceBindingId
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_BINDING_ID,
    PRE_BRONZE_DATASET_ID,
    PRE_BRONZE_SOURCE_ID,
)

__all__ = ["CompiledRoutePlan", "RouteCompiler"]

_NORMALIZATION_EXECUTION_ORDER: dict[type[NormalizationRule], int] = {
    TrimRule: 1,
    NormalizeNullRule: 2,
    ParseDateRule: 3,
    CastRule: 4,
    NormalizeCaseRule: 5,
    DefaultRule: 6,
}


@dataclass(frozen=True, slots=True)
class CompiledRoutePlan:
    """Deterministic, immutable execution plan governing canonical route interpretation.

    Parameters
    ----------
    route_id : CanonicalRouteId
        Identity of the route.
    target_dataset_id : DatasetId
        Canonical dataset targeted by this route.
    binding_id : SourceBindingId | None
        Parent source binding identity if known.
    source_renames : dict[str, str]
        Mapping of source column names to canonical or intermediate names.
    normalization_rules : tuple[NormalizationRule, ...]
        Ordered representation normalization rules (trim, null, date, cast, case, default).
    predicates : tuple[PredicateRule, ...]
        Ordered bounded row-local include/exclude filter predicates.
    semantic_rules : tuple[SemanticRule, ...]
        Ordered semantic interpretation rules (MapValues, Constant).
    canonical_columns : tuple[str, ...]
        Permitted canonical column names for the target dataset.
    provenance_columns : tuple[str, ...]
        Operational provenance columns to preserve in fragment.
    """

    route_id: CanonicalRouteId
    target_dataset_id: DatasetId
    binding_id: SourceBindingId | None
    source_renames: dict[str, str]
    normalization_rules: tuple[NormalizationRule, ...]
    predicates: tuple[PredicateRule, ...]
    semantic_rules: tuple[SemanticRule, ...]
    canonical_columns: tuple[str, ...]
    provenance_columns: tuple[str, ...] = (
        PRE_BRONZE_ARTIFACT_ID,
        PRE_BRONZE_SOURCE_ID,
        PRE_BRONZE_BINDING_ID,
        PRE_BRONZE_DATASET_ID,
        "artifact_id",
    )


class RouteCompiler:
    """Non-I/O service compiling declarative CanonicalRouteConfig into a deterministic execution plan."""

    def compile(
        self,
        route_config: CanonicalRouteConfig,
        binding_id: SourceBindingId | None = None,
        available_source_columns: Sequence[str] | None = None,
    ) -> CompiledRoutePlan:
        """Compile a CanonicalRouteConfig into a CompiledRoutePlan.

        Parameters
        ----------
        route_config : CanonicalRouteConfig
            Declarative route configuration.
        binding_id : SourceBindingId | None, optional
            Originating source binding identity.
        available_source_columns : Sequence[str] | None, optional
            Columns present in incoming source frame to validate against.

        Returns
        -------
        CompiledRoutePlan
            Deterministic, validated route execution plan.

        Raises
        ------
        InvalidCanonicalTargetError
            If a mapped target field is not recognized in the canonical target vocabulary.
        DuplicateMappingError
            If duplicate source fields or duplicate canonical targets appear in mapping.
        MissingSourceFieldError
            If available_source_columns is provided and a required source field is missing.
        """
        target_ds = route_config.target_dataset_id
        permitted_fields = get_canonical_fields(target_ds) or frozenset()

        # 1. Validate Target Canonical Vocabulary and Mapping Uniqueness
        seen_source_fields: set[str] = set()
        seen_canonical_fields: set[str] = set()
        source_renames: dict[str, str] = {}

        for m in route_config.mapping:
            if not is_valid_canonical_field(target_ds, m.canonical_field):
                raise InvalidCanonicalTargetError(
                    message=(
                        f"Route '{route_config.route_id}' maps to invalid canonical field "
                        f"'{m.canonical_field}' for dataset '{target_ds.value}'."
                    ),
                    dataset_id=target_ds,
                    target_field=m.canonical_field,
                    permitted_fields=permitted_fields,
                )
            if m.source_field in seen_source_fields:
                raise DuplicateMappingError(
                    message=f"Duplicate mapping for source field '{m.source_field}' in route '{route_config.route_id}'.",
                    dataset_id=target_ds,
                    duplicate_field=m.source_field,
                    is_source_field=True,
                )
            if m.canonical_field in seen_canonical_fields:
                raise DuplicateMappingError(
                    message=f"Duplicate mapping for canonical field '{m.canonical_field}' in route '{route_config.route_id}'.",
                    dataset_id=target_ds,
                    duplicate_field=m.canonical_field,
                    is_source_field=False,
                )
            seen_source_fields.add(m.source_field)
            seen_canonical_fields.add(m.canonical_field)
            source_renames[m.source_field] = m.canonical_field

        # 2. Check Available Source Columns if Provided
        if available_source_columns is not None:
            available_set = set(available_source_columns)
            for m in route_config.mapping:
                if m.source_field not in available_set:
                    raise MissingSourceFieldError(
                        message=(
                            f"Mapped source field '{m.source_field}' not found in incoming source columns. "
                            f"Available: {sorted(available_set)}."
                        ),
                        dataset_id=target_ds,
                        missing_field=m.source_field,
                        available_fields=tuple(sorted(available_set)),
                    )
            for p in route_config.predicates:
                # Predicate field can be source name or already mapped canonical name
                if p.field not in available_set and p.field not in seen_canonical_fields:
                    raise MissingSourceFieldError(
                        message=(
                            f"Predicate field '{p.field}' in route '{route_config.route_id}' "
                            f"not found in incoming source columns or target fields."
                        ),
                        dataset_id=target_ds,
                        missing_field=p.field,
                        available_fields=tuple(sorted(available_set | seen_canonical_fields)),
                    )

        # 3. Partition Normalization vs Semantic Rules (handling legacy compatibility)
        norm_rules: list[NormalizationRule] = []
        sem_rules: list[SemanticRule] = list(route_config.semantics)

        for rule in route_config.normalization:
            if isinstance(rule, ConstantRule):
                # Normalize legacy ConstantRule into SemanticConstantRule
                sem_rules.append(SemanticConstantRule(field=rule.field, value=rule.value))
            elif isinstance(rule, MapValuesRule):
                # Normalize legacy MapValuesRule into SemanticMapRule
                sem_rules.append(
                    SemanticMapRule(
                        field=rule.field,
                        mapping=rule.mapping,
                        on_unmapped="default" if rule.default is not None else "error",
                        default=rule.default,
                    )
                )
            else:
                norm_rules.append(rule)

        # Validate semantic constant targets
        for s in sem_rules:
            if isinstance(s, SemanticConstantRule):
                if not is_valid_canonical_field(target_ds, s.field):
                    raise InvalidCanonicalTargetError(
                        message=(
                            f"Route '{route_config.route_id}' semantic constant injects invalid field "
                            f"'{s.field}' for dataset '{target_ds.value}'."
                        ),
                        dataset_id=target_ds,
                        target_field=s.field,
                        permitted_fields=permitted_fields,
                    )

        # Sort normalization rules by deterministic execution priority
        sorted_norm_rules = sorted(
            norm_rules,
            key=lambda r: _NORMALIZATION_EXECUTION_ORDER.get(type(r), 99),
        )

        # Resolve field names to working names after source renames
        resolved_norm_rules = tuple(
            r.model_copy(update={"field": source_renames.get(r.field, r.field)})
            for r in sorted_norm_rules
        )
        resolved_predicates = tuple(
            p.model_copy(update={"field": source_renames.get(p.field, p.field)})
            for p in route_config.predicates
        )
        resolved_sem_rules = tuple(
            s.model_copy(update={"field": source_renames.get(s.field, s.field)}) for s in sem_rules
        )

        # 4. Resolve Canonical Projection Columns
        canonical_cols = tuple(sorted(permitted_fields))

        return CompiledRoutePlan(
            route_id=route_config.route_id,
            target_dataset_id=target_ds,
            binding_id=binding_id,
            source_renames=source_renames,
            normalization_rules=resolved_norm_rules,
            predicates=resolved_predicates,
            semantic_rules=resolved_sem_rules,
            canonical_columns=canonical_cols,
        )
