"""Deterministic canonical serialization and cryptographic fingerprinting for source configurations and bindings.

Owns
----
- SourceConfigFingerprint: Immutable model representing computed configuration fingerprint and digest.
- canonicalize_source_configuration: Produces a deterministic canonical dictionary representation.
- compute_source_config_fingerprint: Computes SHA-256 content digest and bounded fingerprint prefix.
- canonicalize_source_binding: Canonical dictionary for a SourceBindingConfig.
- canonicalize_canonical_route: Canonical dictionary for a CanonicalRouteConfig.
- canonicalize_canonical_production: Canonical dictionary for a CanonicalDatasetProductionConfig.
- canonicalize_compiled_topology: Canonical dictionary for a CompiledSourceBindingTopology.
- compute_source_binding_fingerprint: Computes SHA-256 bounded prefix for a SourceBindingConfig.
- compute_canonical_route_fingerprint: Computes SHA-256 bounded prefix for a CanonicalRouteConfig.
- compute_canonical_production_fingerprint: Computes SHA-256 bounded prefix for a CanonicalDatasetProductionConfig.
- compute_compiled_topology_fingerprint: Computes SHA-256 bounded prefix for a CompiledSourceBindingTopology.

Does not own
------------
- Physical database storage or control plane tables (owned by infrastructure.control_plane).
- Observability event emission (owned by infrastructure.observability).
- Pydantic models defining sources and bindings (owned by config.sources.model and binding_model).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.change_detection import ChangeDetectionPolicy
from personal_finance_etl.config.sources.compiler import CompiledSourceBindingTopology
from personal_finance_etl.config.sources.identity import (
    BronzeIdentityStrategy,
    CompositeIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceFieldDeclaration
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    NormalizationRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    DatasetSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.semantics import (
    PredicateRule,
    SemanticMapRule,
    SemanticRule,
)

__all__ = [
    "SourceConfigFingerprint",
    "canonicalize_canonical_production",
    "canonicalize_canonical_route",
    "canonicalize_compiled_topology",
    "canonicalize_source_binding",
    "canonicalize_source_configuration",
    "compute_canonical_production_fingerprint",
    "compute_canonical_route_fingerprint",
    "compute_compiled_topology_fingerprint",
    "compute_source_binding_fingerprint",
    "compute_source_config_fingerprint",
]


@dataclass(frozen=True, slots=True)
class SourceConfigFingerprint:
    """Immutable representation of canonical source configuration fingerprint and payload.

    Parameters
    ----------
    fingerprint : str
        Bounded prefix identifier (e.g. 'src_cfg_a1b2c3d4e5f60718').
    content_hash : str
        Full 64-character SHA-256 hexadecimal content digest for deduplication.
    schema_version : str
        Authoritative schema version of the fingerprinted configuration.
    canonical_payload : str
        Deterministic canonical JSON payload string.
    """

    fingerprint: str
    content_hash: str
    schema_version: str
    canonical_payload: str


# -----------------------------------------------------------------------------
# Reusable Canonical Serialization Primitives
# -----------------------------------------------------------------------------


def _canonicalize_selector(sel: DatasetSelector) -> dict[str, object]:
    """Serialize a DatasetSelector into a deterministic dictionary."""
    sel_dict: dict[str, object] = {"provider_type": sel.provider_type.value}
    if isinstance(sel, CsvSelector):
        sel_dict["delimiter"] = sel.delimiter
        sel_dict["encoding"] = sel.encoding
        sel_dict["file_pattern"] = sel.file_pattern
        sel_dict["has_header"] = sel.has_header
    elif isinstance(sel, ExcelSelector):
        sel_dict["candidate_sheets"] = (
            sorted(sel.candidate_sheets) if sel.candidate_sheets else None
        )
        sel_dict["file_pattern"] = sel.file_pattern
        sel_dict["header_anchor"] = sel.header_anchor
        sel_dict["header_row"] = sel.header_row
        sel_dict["sheet_name"] = sel.sheet_name
        sel_dict["stop_on_blank"] = sel.stop_on_blank
    elif isinstance(sel, SqliteSelector):
        sel_dict["table_name"] = sel.table_name
    else:
        sel_dict["feed_name"] = sel.feed_name
    return sel_dict


def _canonicalize_identity(ident: BronzeIdentityStrategy | None) -> dict[str, object] | None:
    """Serialize a BronzeIdentityStrategy into a deterministic dictionary."""
    if ident is None:
        return None
    ident_dict: dict[str, object] = {"strategy_type": ident.strategy_type}
    if isinstance(ident, SourceFieldIdentity):
        ident_dict["field"] = ident.field
    elif isinstance(ident, CompositeIdentity):
        ident_dict["fields"] = list(ident.fields)
    else:
        ident_dict["fields"] = list(ident.fields)
        ident_dict["namespace"] = ident.namespace
        ident_dict["version"] = ident.version
    return ident_dict


def _canonicalize_mapping(mappings: Sequence[ColumnMapping]) -> list[dict[str, object]]:
    """Serialize ColumnMapping instances into an order-insensitive list of dicts."""
    return [
        {"canonical_field": m.canonical_field, "source_field": m.source_field}
        for m in sorted(mappings, key=lambda m: m.source_field)
    ]


def _canonicalize_normalization(rules: Sequence[NormalizationRule]) -> list[dict[str, object]]:
    """Serialize NormalizationRule instances preserving sequential application order."""
    norm_rules_data: list[dict[str, object]] = []
    for norm in rules:
        rule_dict: dict[str, object] = {
            "field": norm.field,
            "rule": norm.rule,
        }
        if isinstance(norm, CastRule):
            rule_dict["target_type"] = norm.target_type
        elif isinstance(norm, ParseDateRule):
            rule_dict["format"] = norm.format
            rule_dict["strict"] = norm.strict
        elif isinstance(norm, TrimRule):
            rule_dict["mode"] = norm.mode
        elif isinstance(norm, NormalizeCaseRule):
            rule_dict["case"] = norm.case
        elif isinstance(norm, (ConstantRule, DefaultRule)):
            rule_dict["value"] = norm.value
        elif isinstance(norm, NormalizeNullRule):
            rule_dict["null_values"] = sorted(norm.null_values)
        else:
            rule_dict["default"] = norm.default
            rule_dict["mapping"] = {k: norm.mapping[k] for k in sorted(norm.mapping)}
        norm_rules_data.append(rule_dict)
    return norm_rules_data


def _canonicalize_predicates(rules: Sequence[PredicateRule]) -> list[dict[str, object]]:
    """Serialize PredicateRule instances preserving sequential application order."""
    pred_data: list[dict[str, object]] = []
    for p in rules:
        p_dict: dict[str, object] = {
            "field": p.field,
            "operator": p.operator.value,
            "rule": p.rule,
        }
        if p.value is not None:
            if isinstance(p.value, (list, tuple)):
                p_dict["value"] = sorted(str(v) for v in p.value)
            else:
                p_dict["value"] = p.value
        pred_data.append(p_dict)
    return pred_data


def _canonicalize_semantics(rules: Sequence[SemanticRule]) -> list[dict[str, object]]:
    """Serialize SemanticRule instances preserving sequential application order."""
    sem_data: list[dict[str, object]] = []
    for s in rules:
        s_dict: dict[str, object] = {
            "field": s.field,
            "rule": s.rule,
        }
        if isinstance(s, SemanticMapRule):
            s_dict["default"] = s.default
            s_dict["mapping"] = {k: s.mapping[k] for k in sorted(s.mapping)}
            s_dict["on_unmapped"] = s.on_unmapped
        else:
            s_dict["value"] = s.value
        sem_data.append(s_dict)
    return sem_data


def _canonicalize_change_detection(
    cd: ChangeDetectionPolicy | None,
) -> dict[str, object] | None:
    """Serialize ChangeDetectionPolicy into a deterministic dictionary."""
    if cd is None:
        return None
    return {
        "drift_strategy": cd.drift_strategy.value,
        "fingerprint_strategy": cd.fingerprint_strategy.value,
        "rename_strategy": cd.rename_strategy.value,
        "sync_strategy": cd.sync_strategy.value,
    }


def _canonicalize_fields(
    fields: Sequence[SourceFieldDeclaration],
) -> list[dict[str, object]]:
    """Serialize SourceFieldDeclaration instances into an order-insensitive list of dicts."""
    return [
        {
            "data_type": f.data_type,
            "description": f.description,
            "name": f.name,
            "nullable": f.nullable,
            "unique": f.unique,
        }
        for f in sorted(fields, key=lambda f: f.name)
    ]


def _hash_canonical_payload(payload_dict: dict[str, object], prefix: str) -> str:
    """Hash a canonical dictionary into a bounded deterministic prefix."""
    canonical_json = json.dumps(
        payload_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    content_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"{prefix}_{content_hash[:16]}"


# -----------------------------------------------------------------------------
# Configuration Canonicalization & Fingerprinting
# -----------------------------------------------------------------------------


def canonicalize_source_configuration(config: SourceConfiguration) -> dict[str, object]:
    """Produce a deterministic, canonical dictionary representation of SourceConfiguration.

    Parameters
    ----------
    config : SourceConfiguration
        Validated source configuration instance.

    Returns
    -------
    dict[str, object]
        Deterministic canonical dictionary ready for JSON serialization.
    """
    sources_data = [
        {
            "description": s.description,
            "enabled": s.enabled,
            "location": s.location,
            "provider_type": s.provider_type.value,
            "source_id": str(s.source_id),
        }
        for s in sorted(config.sources, key=lambda x: str(x.source_id))
    ]

    datasets_data: list[dict[str, object]] = []
    for ds in sorted(config.datasets, key=lambda x: x.dataset_id.value):
        datasets_data.append(
            {
                "change_detection": _canonicalize_change_detection(ds.change_detection),
                "dataset_id": ds.dataset_id.value,
                "description": ds.description,
                "enabled": ds.enabled,
                "identity": _canonicalize_identity(ds.identity),
                "mapping": _canonicalize_mapping(ds.mapping),
                "normalization": _canonicalize_normalization(ds.normalization),
                "selector": _canonicalize_selector(ds.selector),
                "source_id": str(ds.source_id),
            }
        )

    return {
        "datasets": datasets_data,
        "schema_version": config.schema_version,
        "sources": sources_data,
    }


def compute_source_config_fingerprint(config: SourceConfiguration) -> SourceConfigFingerprint:
    """Compute deterministic cryptographic SHA-256 fingerprint for a SourceConfiguration.

    Parameters
    ----------
    config : SourceConfiguration
        Validated source configuration instance.

    Returns
    -------
    SourceConfigFingerprint
        Computed immutable fingerprint, content digest, and canonical JSON payload.
    """
    payload_dict = canonicalize_source_configuration(config)
    canonical_json = json.dumps(
        payload_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    content_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    fingerprint = f"src_cfg_{content_hash[:16]}"
    return SourceConfigFingerprint(
        fingerprint=fingerprint,
        content_hash=content_hash,
        schema_version=config.schema_version,
        canonical_payload=canonical_json,
    )


# -----------------------------------------------------------------------------
# Additive Source Binding & Topology Fingerprinting
# -----------------------------------------------------------------------------


def canonicalize_canonical_route(route: CanonicalRouteConfig) -> dict[str, object]:
    """Produce a deterministic, canonical dictionary representation of a CanonicalRouteConfig.

    Parameters
    ----------
    route : CanonicalRouteConfig
        Declarative canonical route configuration.

    Returns
    -------
    dict[str, object]
        Deterministic canonical dictionary.
    """
    return {
        "description": route.description,
        "enabled": route.enabled,
        "identity": _canonicalize_identity(route.identity),
        "mapping": _canonicalize_mapping(route.mapping),
        "normalization": _canonicalize_normalization(route.normalization),
        "predicates": _canonicalize_predicates(route.predicates),
        "route_id": str(route.route_id),
        "semantics": _canonicalize_semantics(route.semantics),
        "target_dataset_id": route.target_dataset_id.value,
    }


def compute_canonical_route_fingerprint(route: CanonicalRouteConfig) -> str:
    """Compute deterministic cryptographic fingerprint for a CanonicalRouteConfig.

    Parameters
    ----------
    route : CanonicalRouteConfig
        Canonical route instance.

    Returns
    -------
    str
        Bounded fingerprint prefix formatted as 'can_rt_<hash16>'.
    """
    return _hash_canonical_payload(canonicalize_canonical_route(route), "can_rt")


def canonicalize_source_binding(binding: SourceBindingConfig) -> dict[str, object]:
    """Produce a deterministic, canonical dictionary representation of a SourceBindingConfig.

    Parameters
    ----------
    binding : SourceBindingConfig
        Declarative source binding configuration.

    Returns
    -------
    dict[str, object]
        Deterministic canonical dictionary.
    """
    return {
        "binding_id": str(binding.binding_id),
        "change_detection": _canonicalize_change_detection(binding.change_detection),
        "description": binding.description,
        "enabled": binding.enabled,
        "fields": _canonicalize_fields(binding.fields),
        "routes": [
            canonicalize_canonical_route(r)
            for r in sorted(binding.routes, key=lambda x: str(x.route_id))
        ],
        "selector": _canonicalize_selector(binding.selector),
        "source_id": str(binding.source_id),
    }


def compute_source_binding_fingerprint(binding: SourceBindingConfig) -> str:
    """Compute deterministic cryptographic fingerprint for a SourceBindingConfig.

    Parameters
    ----------
    binding : SourceBindingConfig
        Source binding instance.

    Returns
    -------
    str
        Bounded fingerprint prefix formatted as 'src_bnd_<hash16>'.
    """
    return _hash_canonical_payload(canonicalize_source_binding(binding), "src_bnd")


def canonicalize_canonical_production(
    prod: CanonicalDatasetProductionConfig,
) -> dict[str, object]:
    """Produce a deterministic, canonical dictionary representation of production rules.

    Parameters
    ----------
    prod : CanonicalDatasetProductionConfig
        Declarative dataset production configuration.

    Returns
    -------
    dict[str, object]
        Deterministic canonical dictionary.
    """
    return {
        "assembly_mode": prod.assembly_mode.value,
        "dataset_id": prod.dataset_id.value,
        "enabled": prod.enabled,
        "producer_kind": prod.producer_kind.value,
        "provider_type": prod.provider_type.value if prod.provider_type else None,
        "recipe_name": prod.recipe_name,
        "source_routes": [
            {"binding_id": str(r.binding_id), "route_id": str(r.route_id)}
            for r in sorted(prod.source_routes, key=lambda x: (str(x.binding_id), str(x.route_id)))
        ],
    }


def compute_canonical_production_fingerprint(
    prod: CanonicalDatasetProductionConfig,
) -> str:
    """Compute deterministic cryptographic fingerprint for a CanonicalDatasetProductionConfig.

    Parameters
    ----------
    prod : CanonicalDatasetProductionConfig
        Dataset production rule instance.

    Returns
    -------
    str
        Bounded fingerprint prefix formatted as 'can_prd_<hash16>'.
    """
    return _hash_canonical_payload(canonicalize_canonical_production(prod), "can_prd")


def canonicalize_compiled_topology(
    topology: CompiledSourceBindingTopology,
) -> dict[str, object]:
    """Produce a deterministic canonical dictionary of the entire compiled binding topology.

    Parameters
    ----------
    topology : CompiledSourceBindingTopology
        Compiled source binding topology.

    Returns
    -------
    dict[str, object]
        Deterministic dictionary with sorted bindings and productions.
    """
    return {
        "bindings": [
            canonicalize_source_binding(b)
            for b in sorted(topology.bindings, key=lambda x: str(x.binding_id))
        ],
        "productions": [
            canonicalize_canonical_production(p)
            for p in sorted(topology.productions, key=lambda x: x.dataset_id.value)
        ],
    }


def compute_compiled_topology_fingerprint(
    topology: CompiledSourceBindingTopology,
) -> str:
    """Compute deterministic cryptographic fingerprint for a CompiledSourceBindingTopology.

    Parameters
    ----------
    topology : CompiledSourceBindingTopology
        Compiled source binding topology.

    Returns
    -------
    str
        Bounded fingerprint prefix formatted as 'top_cfg_<hash16>'.
    """
    return _hash_canonical_payload(canonicalize_compiled_topology(topology), "top_cfg")
