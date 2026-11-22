"""Authoritative additive physical evidence source binding configuration models.

Owns
----
- CanonicalRouteConfig: Declarative row-local route from a binding to a canonical target.
- SourceBindingConfig: Declarative physical tabular evidence stream binding.
- CanonicalDatasetProductionConfig: Declarative canonical dataset assembly and production rule.

Does not own
------------
- SourceId, SourceBindingId, CanonicalRouteId, and ProviderType contract definitions (owned by contracts.sources).
- DatasetId canonical enum registry (owned by contracts.datasets).
- Legacy SourceDatasetConfig (owned by config.sources.model).
- Physical provider extraction mechanics (owned by infrastructure.providers).
"""

from __future__ import annotations

from typing import Self, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from personal_finance_etl.config.sources.change_detection import ChangeDetectionPolicy
from personal_finance_etl.config.sources.identity import BronzeIdentityStrategy
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceFieldDeclaration
from personal_finance_etl.config.sources.normalization import NormalizationRule
from personal_finance_etl.config.sources.selectors import DatasetSelector
from personal_finance_etl.config.sources.semantics import PredicateRule, SemanticRule
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
    SourceId,
    validate_canonical_route_id,
    validate_source_binding_id,
    validate_source_id,
)

__all__ = [
    "CanonicalDatasetProductionConfig",
    "CanonicalRouteConfig",
    "SourceBindingConfig",
]


def _empty_column_mappings() -> list[ColumnMapping]:
    """Create an empty list of ColumnMapping instances."""
    return []


def _empty_normalization_rules() -> list[NormalizationRule]:
    """Create an empty list of NormalizationRule instances."""
    return []


def _empty_predicate_rules() -> list[PredicateRule]:
    """Create an empty list of PredicateRule instances."""
    return []


def _empty_semantic_rules() -> list[SemanticRule]:
    """Create an empty list of SemanticRule instances."""
    return []


def _empty_fields() -> list[SourceFieldDeclaration]:
    """Create an empty list of SourceFieldDeclaration instances."""
    return []


def _empty_routes() -> list[CanonicalRouteConfig]:
    """Create an empty list of CanonicalRouteConfig instances."""
    return []


def _empty_source_routes() -> list[CanonicalRouteRef]:
    """Create an empty list of CanonicalRouteRef instances."""
    return []


class CanonicalRouteConfig(BaseModel):
    """Declarative row-local route from a source binding to a canonical target.

    Parameters
    ----------
    route_id : CanonicalRouteId
        Stable logical identity for this route within its parent binding.
    target_dataset_id : DatasetId
        Canonical PFETL dataset targeted by this route.
    description : str | None, default None
        Optional human-readable description of this route.
    enabled : bool, default True
        Operational toggle to enable or disable this route.
    mapping : list[ColumnMapping], default empty list
        Declarative column translation rules from source names to canonical names.
    normalization : list[NormalizationRule], default empty list
        Ordered list of bounded normalization transformations to apply.
    predicates : list[PredicateRule], default empty list
        Ordered list of bounded row-local include/exclude filter predicates.
    semantics : list[SemanticRule], default empty list
        Ordered list of bounded categorical semantic mappings and constant assignments.
    identity : BronzeIdentityStrategy | None, default None
        Optional explicit row identity strategy override.
    """

    route_id: CanonicalRouteId
    target_dataset_id: DatasetId
    description: str | None = None
    enabled: bool = True
    mapping: list[ColumnMapping] = Field(default_factory=_empty_column_mappings)
    normalization: list[NormalizationRule] = Field(default_factory=_empty_normalization_rules)
    predicates: list[PredicateRule] = Field(default_factory=_empty_predicate_rules)
    semantics: list[SemanticRule] = Field(default_factory=_empty_semantic_rules)
    identity: BronzeIdentityStrategy | None = None

    @field_validator("route_id", mode="before")
    @classmethod
    def _validate_route_id(cls, v: object) -> CanonicalRouteId:
        """Validate route_id format.

        Parameters
        ----------
        v : object
            Input route identifier candidate.

        Returns
        -------
        CanonicalRouteId
            Validated CanonicalRouteId.
        """
        return validate_canonical_route_id(v)


class SourceBindingConfig(BaseModel):
    """Declarative physical tabular evidence stream binding.

    Parameters
    ----------
    binding_id : SourceBindingId
        Stable logical identity for this tabular stream binding.
    source_id : SourceId
        Logical identity of the physical evidence source containing this stream.
    selector : DatasetSelector
        Provider-specific typed selector (CsvSelector, ExcelSelector, SqliteSelector).
    enabled : bool, default True
        Operational toggle to enable or disable ingestion of this binding.
    description : str | None, default None
        Optional human-readable documentation for this binding.
    change_detection : ChangeDetectionPolicy | None, default None
        Optional explicit change-detection and synchronization policy override.
    fields : list[SourceFieldDeclaration], default empty list
        Declarative schema specification of expected source tabular fields.
    routes : list[CanonicalRouteConfig], default empty list
        Declarative canonical routes projecting this binding into canonical datasets.
    """

    binding_id: SourceBindingId
    source_id: SourceId
    selector: DatasetSelector
    enabled: bool = True
    description: str | None = None
    change_detection: ChangeDetectionPolicy | None = None
    fields: list[SourceFieldDeclaration] = Field(default_factory=_empty_fields)
    routes: list[CanonicalRouteConfig] = Field(default_factory=_empty_routes)

    @field_validator("binding_id", mode="before")
    @classmethod
    def _validate_binding_id(cls, v: object) -> SourceBindingId:
        """Validate binding_id format.

        Parameters
        ----------
        v : object
            Input binding identifier candidate.

        Returns
        -------
        SourceBindingId
            Validated SourceBindingId.
        """
        return validate_source_binding_id(v)

    @field_validator("source_id", mode="before")
    @classmethod
    def _validate_source_id(cls, v: object) -> SourceId:
        """Validate source_id format.

        Parameters
        ----------
        v : object
            Input source identifier candidate.

        Returns
        -------
        SourceId
            Validated SourceId.
        """
        return validate_source_id(v)

    @model_validator(mode="after")
    def _validate_unique_route_ids(self) -> Self:
        """Ensure all routes within this binding declare distinct route_ids.

        Returns
        -------
        Self
            The validated instance.

        Raises
        ------
        ValueError
            If duplicate route_ids exist within the routes list.
        """
        seen: set[str] = set()
        for r in self.routes:
            rid = str(r.route_id)
            if rid in seen:
                raise ValueError(
                    f"Duplicate route_id '{rid}' found in binding '{self.binding_id}'."
                )
            seen.add(rid)
        return self


def _coerce_route_ref(v: object) -> CanonicalRouteRef:
    """Coerce various representations into a CanonicalRouteRef instance."""
    if isinstance(v, CanonicalRouteRef):
        return v
    if isinstance(v, str):
        return CanonicalRouteRef.from_string(v)
    if isinstance(v, dict):
        raw_dict = cast(dict[object, object], v)
        b_id = raw_dict.get("binding_id")
        r_id = raw_dict.get("route_id")
        if b_id is not None and r_id is not None:
            return CanonicalRouteRef(
                binding_id=validate_source_binding_id(b_id),
                route_id=validate_canonical_route_id(r_id),
            )
        raise ValueError("Dictionary route reference requires 'binding_id' and 'route_id'")
    raise TypeError(f"Cannot coerce {v.__class__.__name__} to CanonicalRouteRef")


class CanonicalDatasetProductionConfig(BaseModel):
    """Declarative canonical dataset assembly and production rule.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical PFETL dataset produced.
    producer_kind : CanonicalProducerKind, default SOURCE
        Producer mechanism (SOURCE, PROVIDER, DERIVED).
    assembly_mode : SourceAssemblyMode, default DIRECT
        Source fragment assembly mode (DIRECT, UNION).
    source_routes : list[CanonicalRouteRef], default empty list
        List of source routes consumed to produce this canonical dataset.
    provider_type : ProviderType | None, default None
        Physical provider type when producer_kind is PROVIDER.
    recipe_name : str | None, default None
        Registered derivation recipe name when producer_kind is DERIVED.
    enabled : bool, default True
        Operational toggle for this canonical dataset production.
    description : str | None, default None
        Optional human-readable documentation.
    """

    dataset_id: DatasetId
    producer_kind: CanonicalProducerKind = CanonicalProducerKind.SOURCE
    assembly_mode: SourceAssemblyMode = SourceAssemblyMode.DIRECT
    source_routes: list[CanonicalRouteRef] = Field(default_factory=_empty_source_routes)
    provider_type: ProviderType | None = None
    recipe_name: str | None = None
    enabled: bool = True
    description: str | None = None

    @field_validator("source_routes", mode="before")
    @classmethod
    def _coerce_source_routes(cls, v: object) -> list[CanonicalRouteRef]:
        """Coerce raw strings or dicts into CanonicalRouteRef objects.

        Parameters
        ----------
        v : object
            Input candidates for source_routes.

        Returns
        -------
        list[CanonicalRouteRef]
            Coerced list of CanonicalRouteRef instances.
        """
        if not isinstance(v, list | tuple):
            return []
        raw_items = cast(list[object] | tuple[object, ...], v)
        return [_coerce_route_ref(item) for item in raw_items]

    @model_validator(mode="after")
    def _validate_producer_invariants(self) -> Self:
        """Validate producer configuration invariants based on producer_kind.

        Returns
        -------
        Self
            The validated instance.

        Raises
        ------
        ValueError
            If assembly mode, provider type, or recipe rules are violated.
        """
        if self.producer_kind == CanonicalProducerKind.SOURCE:
            if self.assembly_mode == SourceAssemblyMode.DIRECT and len(self.source_routes) > 1:
                raise ValueError(
                    f"DIRECT assembly mode for dataset '{self.dataset_id}' cannot have "
                    f"more than one source route (found {len(self.source_routes)})."
                )
        elif self.producer_kind == CanonicalProducerKind.PROVIDER:
            if self.provider_type is None:
                raise ValueError(
                    f"Canonical dataset '{self.dataset_id}' with producer_kind PROVIDER "
                    "must specify provider_type."
                )
        elif self.producer_kind == CanonicalProducerKind.DERIVED:
            if not self.recipe_name or not self.recipe_name.strip():
                raise ValueError(
                    f"Canonical dataset '{self.dataset_id}' with producer_kind DERIVED "
                    "must specify a non-empty recipe_name."
                )
        return self
