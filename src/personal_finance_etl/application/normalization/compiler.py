"""Authoritative compiler transforming source dataset configurations into execution plans.

Owns
----
- NormalizationCompiler: Pure non-I/O service compiling SourceDatasetConfig into NormalizationPlan.

Does not own
-------------
- Frame execution (owned by application.normalization.executor).
- User configuration models (owned by config.sources).
- Canonical Bronze contract registry (owned by contracts.canonical_fields).
"""

from __future__ import annotations

from personal_finance_etl.application.normalization.errors import (
    DuplicateMappingError,
    InvalidCanonicalTargetError,
    MissingSourceFieldError,
)
from personal_finance_etl.application.normalization.models import NormalizationPlan
from personal_finance_etl.config.sources.model import SourceDatasetConfig
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
from personal_finance_etl.contracts.canonical_fields import (
    CANONICAL_PROVENANCE_FIELDS,
    get_canonical_fields,
    is_valid_canonical_field,
)

__all__ = ["NormalizationCompiler"]

# Deterministic execution order priority for pre-rename operations
_PRE_RENAME_PRIORITY: dict[type[NormalizationRule], int] = {
    TrimRule: 1,
    NormalizeNullRule: 2,
}

# Deterministic execution order priority for post-rename operations
_POST_RENAME_PRIORITY: dict[type[NormalizationRule], int] = {
    TrimRule: 1,
    NormalizeNullRule: 2,
    ParseDateRule: 3,
    CastRule: 4,
    NormalizeCaseRule: 5,
    MapValuesRule: 6,
    DefaultRule: 7,
    ConstantRule: 8,
}


class NormalizationCompiler:
    """Non-I/O compiler translating declarative dataset mapping configuration into execution plans."""

    def compile(
        self,
        config: SourceDatasetConfig,
        available_source_columns: list[str] | tuple[str, ...] | None = None,
    ) -> NormalizationPlan:
        """Compile a SourceDatasetConfig into a deterministic NormalizationPlan.

        Parameters
        ----------
        config : SourceDatasetConfig
            Declarative dataset binding containing mappings and normalization rules.
        available_source_columns : list[str] | tuple[str, ...] | None, optional
            Optional list of columns present in the incoming source schema to validate against.

        Returns
        -------
        NormalizationPlan
            Validated, deterministic execution plan ready for execution.

        Raises
        ------
        InvalidCanonicalTargetError
            If a mapped target field is not recognized in the canonical Bronze vocabulary.
        DuplicateMappingError
            If duplicate source fields or duplicate canonical targets appear in the mapping.
        MissingSourceFieldError
            If available_source_columns is provided and a required source field is missing.
        """
        dataset_id = config.dataset_id
        source_id = config.source_id

        # 1. Validate Target Canonical Vocabulary
        for m in config.mapping:
            if not is_valid_canonical_field(dataset_id, m.canonical_field):
                permitted = get_canonical_fields(dataset_id) or frozenset()
                raise InvalidCanonicalTargetError(
                    message=(
                        f"Target field '{m.canonical_field}' is not a valid canonical Bronze "
                        f"field for dataset '{dataset_id.value}'."
                    ),
                    dataset_id=dataset_id,
                    target_field=m.canonical_field,
                    permitted_fields=permitted,
                    source_id=source_id,
                )

        # 2. Check for Duplicate Mappings
        seen_sources: set[str] = set()
        seen_targets: set[str] = set()
        for m in config.mapping:
            if m.source_field in seen_sources:
                raise DuplicateMappingError(
                    message=f"Duplicate source field mapping for '{m.source_field}'.",
                    dataset_id=dataset_id,
                    duplicate_field=m.source_field,
                    is_source_field=True,
                    source_id=source_id,
                )
            if m.canonical_field in seen_targets:
                raise DuplicateMappingError(
                    message=f"Duplicate canonical target mapping for '{m.canonical_field}'.",
                    dataset_id=dataset_id,
                    duplicate_field=m.canonical_field,
                    is_source_field=False,
                    source_id=source_id,
                )
            seen_sources.add(m.source_field)
            seen_targets.add(m.canonical_field)

        # 3. Validate against available source columns if supplied
        if available_source_columns is not None:
            available_set = set(available_source_columns)
            available_tuple = tuple(available_source_columns)
            for m in config.mapping:
                if m.source_field not in available_set:
                    raise MissingSourceFieldError(
                        message=(
                            f"Mapped source field '{m.source_field}' not found in incoming source "
                            f"schema. Available columns: {list(available_source_columns)}."
                        ),
                        dataset_id=dataset_id,
                        missing_field=m.source_field,
                        available_fields=available_tuple,
                        source_id=source_id,
                    )

        # 4. Partition and deterministically order normalization rules
        column_mapping = {m.source_field: m.canonical_field for m in config.mapping}
        pre_rules: list[NormalizationRule] = []
        post_rules: list[NormalizationRule] = []

        for rule in config.normalization:
            # If the rule's field is an unmapped source field, it runs pre-rename
            if rule.field in seen_sources and rule.field not in seen_targets:
                pre_rules.append(rule)
            else:
                post_rules.append(rule)

        # Deterministic sorting: priority integer, then field name
        sorted_pre = tuple(
            sorted(
                pre_rules,
                key=lambda r: (_PRE_RENAME_PRIORITY.get(type(r), 99), r.field),
            )
        )
        sorted_post = tuple(
            sorted(
                post_rules,
                key=lambda r: (_POST_RENAME_PRIORITY.get(type(r), 99), r.field),
            )
        )

        # 5. Assemble Expected Output Fields
        expected_fields: list[str] = [m.canonical_field for m in config.mapping]
        # Include any constant rule fields injected post-rename
        for rule in post_rules:
            if isinstance(rule, ConstantRule) and rule.field not in expected_fields:
                expected_fields.append(rule.field)

        return NormalizationPlan(
            dataset_id=dataset_id,
            source_id=source_id,
            column_mapping=column_mapping,
            pre_rename_rules=sorted_pre,
            post_rename_rules=sorted_post,
            expected_output_fields=tuple(expected_fields),
            provenance_fields=tuple(sorted(CANONICAL_PROVENANCE_FIELDS)),
        )
