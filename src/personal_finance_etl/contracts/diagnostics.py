"""Authoritative cross-boundary diagnostic result contracts and error descriptors.

Owns
----
- DiagnosticSeverity: Diagnostic severity classification.
- DiagnosticIssue: Structured actionable diagnostic issue.
- ConfigValidationResult: Comprehensive multi-configuration validation result.
- SourceReachabilityStatus: Reachability status enumeration.
- DatasetSelectorStatus: Selector validation status for a dataset.
- SourceCheckDetail: Detailed reachability and selector status for an evidence source.
- SourceCheckResult: Complete source and selector reachability result.
- MappingPreviewResult: Source-to-canonical column mapping and normalization preview.
- IdentityPreviewResult: Row identity strategy, target fields, and collision diagnostics.
- PlanPreviewResult: Execution plan topology, active capabilities, and contract inventory.
- DatasetAdmissionDryRunStatus: Single dataset dry-run admission evaluation status.
- AdmissionDryRunResult: Complete admission dry run outcome with zero-mutation guarantee.

Does not own
------------
- Diagnostic compilation or execution (owned by application.diagnostics).
- Presentation terminal rendering (owned by presentation.cli.diagnostics).
- Configuration parsing (owned by config layer).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    ExternalEnrichmentId,
)
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.contracts.observability import DiagnosticSeverity
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.contracts.validation import ValidationCheckFailure

__all__ = [
    "AdmissionDryRunResult",
    "ConfigValidationResult",
    "DatasetAdmissionDryRunStatus",
    "DatasetSelectorStatus",
    "DiagnosticIssue",
    "DiagnosticSeverity",
    "IdentityPreviewResult",
    "MappingPreviewResult",
    "PlanPreviewResult",
    "PreflightCheckFailedError",
    "SourceCheckDetail",
    "SourceCheckResult",
    "SourceReachabilityStatus",
]


@dataclass(frozen=True, slots=True)
class DiagnosticIssue:
    """Structured actionable diagnostic issue or configuration failure.

    Parameters
    ----------
    category : str
        Subsystem category (e.g. 'SETTINGS', 'SOURCES', 'RULES', 'SELECTOR', 'IDENTITY').
    severity : DiagnosticSeverity
        Diagnostic issue severity.
    location : str
        Configuration file path, section, or line identifier.
    message : str
        Human-readable description of the issue.
    remediation : str
        Actionable guidance explaining how to resolve the issue.
    field : str | None, default None
        Specific field or property key associated with the issue, if applicable.
    """

    category: str
    severity: DiagnosticSeverity
    location: str
    message: str
    remediation: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigValidationResult:
    """Comprehensive validation outcome for settings, sources, and financial rules.

    Parameters
    ----------
    is_valid : bool
        True if all configuration files are valid under the active execution plan.
    active_capabilities : tuple[CapabilityId, ...]
        Resolved capabilities active for this configuration.
    active_datasets : tuple[DatasetId, ...]
        Active Bronze datasets required or optional under this configuration.
    issues : tuple[DiagnosticIssue, ...]
        All diagnostic issues, warnings, and errors discovered.
    settings_path : str
        Path to settings TOML file.
    rules_path : str
        Path to financial rules TOML file.
    sources_path : str
        Path to sources TOML file.
    """

    is_valid: bool
    active_capabilities: tuple[CapabilityId, ...]
    active_datasets: tuple[DatasetId, ...]
    issues: tuple[DiagnosticIssue, ...]
    settings_path: str
    rules_path: str
    sources_path: str
    compiled_bindings_count: int = 0

    @property
    def errors(self) -> tuple[DiagnosticIssue, ...]:
        """Filter issues returning only errors."""
        return tuple(i for i in self.issues if i.severity == DiagnosticSeverity.ERROR)

    @property
    def warnings(self) -> tuple[DiagnosticIssue, ...]:
        """Filter issues returning only warnings."""
        return tuple(i for i in self.issues if i.severity == DiagnosticSeverity.WARNING)


class SourceReachabilityStatus(StrEnum):
    """Reachability status for an external evidence source."""

    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    INVALID_SELECTOR = "INVALID_SELECTOR"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DatasetSelectorStatus:
    """Diagnostic validation status for a dataset's selector.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    selector_type : str
        Type of selector (e.g. 'excel_sheet', 'sqlite_table', 'csv_pattern').
    selector_target : str
        Target sheet, table name, or glob pattern specified in configuration.
    is_valid : bool
        True if the target exists and is reachable.
    details : str
        Human-readable status summary or error description.
    available_targets : tuple[str, ...], default ()
        Discovered available targets (e.g. valid sheet or table names) to aid remediation.
    """

    dataset_id: DatasetId
    selector_type: str
    selector_target: str
    is_valid: bool
    details: str
    available_targets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceCheckDetail:
    """Detailed reachability and selector status for a single evidence source.

    Parameters
    ----------
    source_id : SourceId
        Logical identifier of the evidence source.
    provider_type : ProviderType
        Physical extractor provider type.
    location : str
        Configured location string.
    resolved_location : str
        Fully resolved filesystem path or connection URI.
    status : SourceReachabilityStatus
        Physical reachability status.
    message : str
        Human-readable status message.
    dataset_selectors : tuple[DatasetSelectorStatus, ...]
        Selector checks for each dataset bound to this source.
    """

    source_id: SourceId
    provider_type: ProviderType
    location: str
    resolved_location: str
    status: SourceReachabilityStatus
    message: str
    dataset_selectors: tuple[DatasetSelectorStatus, ...]


@dataclass(frozen=True, slots=True)
class SourceCheckResult:
    """Complete source reachability and selector diagnostic outcome.

    Parameters
    ----------
    is_all_reachable : bool
        True if all configured sources and selectors are reachable and valid.
    sources : tuple[SourceCheckDetail, ...]
        Detailed check results for each configured source.
    issues : tuple[DiagnosticIssue, ...]
        Aggregated actionable issues.
    """

    is_all_reachable: bool
    sources: tuple[SourceCheckDetail, ...]
    issues: tuple[DiagnosticIssue, ...]


@dataclass(frozen=True, slots=True)
class MappingPreviewResult:
    """Source-to-canonical mapping and normalization operation preview.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    source_id : SourceId | None
        Bound physical evidence source identifier.
    provider_type : ProviderType | None
        Physical provider type.
    field_mappings : tuple[tuple[str, str], ...]
        Sequence of (source_field, canonical_field) pairs.
    pre_rename_rules : tuple[str, ...]
        Summary strings of normalization operations applied before column renaming.
    post_rename_rules : tuple[str, ...]
        Summary strings of normalization operations applied after column renaming.
    expected_canonical_fields : tuple[str, ...]
        Ordered sequence of canonical fields expected in the final normalized frame.
    provenance_fields : tuple[str, ...]
        Pipeline lineage and audit metadata fields preserved.
    """

    dataset_id: DatasetId
    source_id: SourceId | None
    provider_type: ProviderType | None
    field_mappings: tuple[tuple[str, str], ...]
    pre_rename_rules: tuple[str, ...]
    post_rename_rules: tuple[str, ...]
    expected_canonical_fields: tuple[str, ...]
    provenance_fields: tuple[str, ...]
    source_binding_id: str | None = None
    canonical_route_id: str | None = None
    predicates: tuple[str, ...] = ()
    semantic_rules: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IdentityPreviewResult:
    """Row identity strategy, target fields, and collision diagnostic preview.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    requirement : IdentityRequirement
        Contractual requirement (REQUIRED or NONE).
    strategy_kind : str
        Descriptive strategy name (e.g. 'SourceFieldIdentity', 'DerivedDeterministicIdentity').
    strategy_target_fields : tuple[str, ...]
        Source/canonical fields used to construct the row identity.
    namespace : str
        Deterministic cryptographic hash namespace prefix.
    sample_ids : tuple[str, ...]
        Bounded sample of generated or source identity tokens.
    collision_detected : bool
        True if duplicate identity keys were discovered.
    collision_diagnostic : str | None
        Human-readable collision diagnostic message if duplicate keys were found.
    is_trusted_source_id : bool
        True if the identity directly adopts trusted upstream source identifiers.
    """

    dataset_id: DatasetId
    requirement: IdentityRequirement
    strategy_kind: str
    strategy_target_fields: tuple[str, ...]
    namespace: str
    sample_ids: tuple[str, ...]
    collision_detected: bool
    collision_diagnostic: str | None
    is_trusted_source_id: bool


@dataclass(frozen=True, slots=True)
class PlanPreviewResult:
    """Execution plan topology, active capabilities, and contract inventory preview.

    Parameters
    ----------
    plan_fingerprint : str
        Cryptographic SHA-256 fingerprint identifying the plan configuration.
    requested_capabilities : tuple[CapabilityId, ...]
        Explicitly requested capabilities.
    resolved_capabilities : tuple[CapabilityId, ...]
        Topologically sorted list of all active capabilities including transitive dependencies.
    required_bronze_datasets : tuple[DatasetId, ...]
        Mandatory Bronze evidence datasets.
    optional_bronze_datasets : tuple[DatasetId, ...]
        Optional Bronze datasets.
    active_silver_datasets : tuple[DatasetId, ...]
        Canonical Silver datasets produced.
    active_gold_datasets : tuple[DatasetId, ...]
        Decision-ready Gold analytical datasets produced.
    required_external_enrichments : tuple[ExternalEnrichmentId, ...]
        External market data feeds required.
    ordered_engine_stages : tuple[EngineStage, ...]
        Pipeline execution stages governed by this plan.
    """

    plan_fingerprint: str
    requested_capabilities: tuple[CapabilityId, ...]
    resolved_capabilities: tuple[CapabilityId, ...]
    required_bronze_datasets: tuple[DatasetId, ...]
    optional_bronze_datasets: tuple[DatasetId, ...]
    active_silver_datasets: tuple[DatasetId, ...]
    active_gold_datasets: tuple[DatasetId, ...]
    required_external_enrichments: tuple[ExternalEnrichmentId, ...]
    ordered_engine_stages: tuple[EngineStage, ...]


@dataclass(frozen=True, slots=True)
class DatasetAdmissionDryRunStatus:
    """Admission dry-run evaluation outcome for a single dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    status : Literal["PASSED", "FAILED", "SKIPPED"]
        Admission check status.
    rows_read : int
        Number of raw evidence rows read from source.
    rows_admitted : int
        Number of normalized rows successfully validated against Bronze schema.
    duration_seconds : float
        Elapsed execution time in seconds.
    failures : tuple[ValidationCheckFailure, ...]
        Structured Pandera schema or constraint failures if validation failed.
    error_message : str | None, default None
        Exception message if admission encountered an unhandled error.
    """

    dataset_id: DatasetId
    status: Literal["PASSED", "FAILED", "SKIPPED"]
    rows_read: int
    rows_admitted: int
    duration_seconds: float
    failures: tuple[ValidationCheckFailure, ...] = ()
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class AdmissionDryRunResult:
    """Complete admission dry run outcome with zero warehouse mutation guarantee.

    Parameters
    ----------
    is_success : bool
        True if all evaluated datasets passed extraction, normalization, and validation.
    dataset_results : tuple[DatasetAdmissionDryRunStatus, ...]
        Per-dataset admission evaluation outcomes.
    total_rows_admitted : int
        Total count of rows admitted across all datasets.
    total_duration_seconds : float
        Total dry run duration in seconds.
    zero_warehouse_mutation_guaranteed : bool, default True
        Assertion that production warehouse and SQLite Control Plane were not mutated.
    """

    is_success: bool
    dataset_results: tuple[DatasetAdmissionDryRunStatus, ...]
    total_rows_admitted: int
    total_duration_seconds: float
    zero_warehouse_mutation_guaranteed: bool = True


class PreflightCheckFailedError(RuntimeError):
    """Raised when pre-flight health checks detect blocking configuration or source reachability errors.

    Parameters
    ----------
    message : str
        Human-readable summary of pre-flight validation failures.
    issues : tuple[DiagnosticIssue, ...], default ()
        Structured diagnostic issues detailing the failures.
    """

    def __init__(self, message: str, issues: tuple[DiagnosticIssue, ...] = ()) -> None:
        super().__init__(message)
        self.issues = issues
