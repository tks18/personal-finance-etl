"""Deterministic canonical serialization and cryptographic fingerprinting for SourceConfiguration.

Owns
----
- SourceConfigFingerprint: Immutable model representing computed configuration fingerprint and digest.
- canonicalize_source_configuration: Produces a deterministic canonical dictionary representation.
- compute_source_config_fingerprint: Computes SHA-256 content digest and bounded fingerprint prefix.

Does not own
------------
- Physical database storage or control plane tables (owned by infrastructure.control_plane).
- Observability event emission (owned by infrastructure.observability).
- Pydantic models defining sources and datasets (owned by config.sources.model).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from personal_finance_etl.config.sources.identity import (
    CompositeIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
)

__all__ = [
    "SourceConfigFingerprint",
    "canonicalize_source_configuration",
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


def canonicalize_source_configuration(config: SourceConfiguration) -> dict[str, object]:
    """Produce a deterministic, canonical dictionary representation of SourceConfiguration.

    Sorts unordered collections (sources, datasets, mappings, capabilities) to guarantee
    invariance to input order, while strictly preserving sequential order for semantic
    operations (normalization rules).

    Parameters
    ----------
    config : SourceConfiguration
        Validated source configuration instance.

    Returns
    -------
    dict[str, object]
        Deterministic canonical dictionary ready for JSON serialization.
    """
    capabilities_data: list[str] | None = None
    if config.capabilities.enabled is not None:
        capabilities_data = sorted(c.value for c in config.capabilities.enabled)

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
        sel = ds.selector
        sel_dict: dict[str, object] = {"provider_type": sel.provider_type.value}
        if isinstance(sel, CsvSelector):
            sel_dict["delimiter"] = sel.delimiter
            sel_dict["encoding"] = sel.encoding
            sel_dict["file_pattern"] = sel.file_pattern
            sel_dict["has_header"] = sel.has_header
        elif isinstance(sel, ExcelSelector):
            sel_dict["header_row"] = sel.header_row
            sel_dict["sheet_name"] = sel.sheet_name
        else:
            sel_dict["table_name"] = sel.table_name

        ident = ds.identity
        ident_dict: dict[str, object] | None = None
        if ident is not None:
            ident_dict = {"strategy_type": ident.strategy_type}
            if isinstance(ident, SourceFieldIdentity):
                ident_dict["field"] = ident.field
            elif isinstance(ident, CompositeIdentity):
                ident_dict["fields"] = list(ident.fields)
            else:
                ident_dict["fields"] = list(ident.fields)
                ident_dict["namespace"] = ident.namespace
                ident_dict["version"] = ident.version

        mappings_data = [
            {"canonical_field": m.canonical_field, "source_field": m.source_field}
            for m in sorted(ds.mapping, key=lambda m: m.source_field)
        ]

        norm_rules_data: list[dict[str, object]] = []
        for norm in ds.normalization:
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

        cd = ds.change_detection
        cd_dict: dict[str, object] | None = None
        if cd is not None:
            cd_dict = {
                "drift_strategy": cd.drift_strategy.value,
                "fingerprint_strategy": cd.fingerprint_strategy.value,
                "rename_strategy": cd.rename_strategy.value,
                "sync_strategy": cd.sync_strategy.value,
            }

        datasets_data.append(
            {
                "change_detection": cd_dict,
                "dataset_id": ds.dataset_id.value,
                "description": ds.description,
                "enabled": ds.enabled,
                "identity": ident_dict,
                "mapping": mappings_data,
                "normalization": norm_rules_data,
                "selector": sel_dict,
                "source_id": str(ds.source_id),
            }
        )

    return {
        "capabilities": capabilities_data,
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
