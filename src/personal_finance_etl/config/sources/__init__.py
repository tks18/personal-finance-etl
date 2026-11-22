"""Physical evidence source configuration package.

Owns
----
- CURRENT_SOURCE_CONFIG_SCHEMA_VERSION, SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS: Schema versions.
- CapabilitySelection: Declarative capability selection model.
- SourceConfiguration: Versioned root evidence source configuration model.
- SourceConfig: Declarative validated evidence source configuration model.
- SourceDatasetConfig: Declarative binding of a physical source to a canonical dataset.
- CsvSelector, ExcelSelector, SqliteSelector: Discriminated physical dataset selectors.
- DatasetSelector: Discriminated union of supported dataset selectors.
- ChangeDetectionPolicy: Decoupled change-detection and synchronization policy model.
- FingerprintStrategy, DriftStrategy, RenameStrategy, SyncStrategy: Policy dimension enums.
- resolve_change_detection_policy: Pure resolution function building policy from format and flags.
- SourceFieldIdentity, CompositeIdentity, DerivedDeterministicIdentity: Row identity strategies.
- BronzeIdentityStrategy: Discriminated union of supported Bronze identity strategies.
- SourceConfigFingerprint, canonicalize_source_configuration, compute_source_config_fingerprint: Provenance.
- ColumnMapping, dict_to_mapping_list, mapping_list_to_dict: Source-to-canonical mapping models.
- CanonicalDtype, CastRule, ParseDateRule, TrimRule, NormalizeCaseRule: Bounded normalization rules.
- ConstantRule, DefaultRule, NormalizeNullRule, MapValuesRule, NormalizationRule: Bounded normalization rules.
- TopologyCoverageReport: Diagnostic report summarizing Bronze dataset coverage.
- evaluate_bronze_topology_coverage: Evaluator comparing configured bindings against Bronze contracts.
- validate_source_dataset_bindings: Aggregate validation helper for sources and dataset bindings.
- validate_source_selector_compatibility: Cross-model provider compatibility validator.
- get_shan_baseline_sources, get_shan_baseline_dataset_bindings: Baseline evidence specifications.
- get_shan_baseline_source_configuration: Canonical baseline SourceConfiguration instance.

Does not own
------------
- SourceId, ProviderType, and DatasetId contract definitions (owned by contracts).
- Root settings or runtime operational environment flags (owned by config.settings).
- Physical provider extraction mechanics (owned by infrastructure.providers).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.binding_model import (
    CanonicalDatasetProductionConfig,
    CanonicalRouteConfig,
    SourceBindingConfig,
)
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    DriftStrategy,
    FingerprintStrategy,
    RenameStrategy,
    SyncStrategy,
    resolve_change_detection_policy,
)
from personal_finance_etl.config.sources.compiler import (
    DEFAULT_COMPATIBILITY_ROUTE_ID,
    CompatibilitySourceBindingCompiler,
    CompiledSourceBindingTopology,
    derive_source_binding_id,
)
from personal_finance_etl.config.sources.fingerprint import (
    SourceConfigFingerprint,
    canonicalize_canonical_production,
    canonicalize_canonical_route,
    canonicalize_compiled_topology,
    canonicalize_source_binding,
    canonicalize_source_configuration,
    compute_canonical_production_fingerprint,
    compute_canonical_route_fingerprint,
    compute_compiled_topology_fingerprint,
    compute_source_binding_fingerprint,
    compute_source_config_fingerprint,
)
from personal_finance_etl.config.sources.identity import (
    PROTECTED_FINANCIAL_NAMESPACES,
    BronzeIdentityStrategy,
    CompositeIdentity,
    DerivedDeterministicIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.loader import (
    CURRENT_SOURCE_CONFIG_SCHEMA_VERSION,
    SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS,
    CapabilitySelection,
    SourceConfiguration,
    get_shan_baseline_dataset_bindings,
    get_shan_baseline_source_configuration,
    get_shan_baseline_sources,
)
from personal_finance_etl.config.sources.mapping import (
    ColumnMapping,
    dict_to_mapping_list,
    mapping_list_to_dict,
)
from personal_finance_etl.config.sources.model import (
    SourceConfig,
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
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
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    DatasetSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.semantics import (
    ExcludeWhen,
    IncludeWhen,
    PredicateOperator,
    PredicateRule,
    SemanticConstantRule,
    SemanticMapRule,
    SemanticRule,
)
from personal_finance_etl.config.sources.topology import (
    TopologyCoverageReport,
    evaluate_bronze_topology_coverage,
)
from personal_finance_etl.config.sources.validation import (
    validate_source_bindings,
    validate_source_dataset_bindings,
    validate_source_selector_compatibility,
)

__all__ = [
    "CURRENT_SOURCE_CONFIG_SCHEMA_VERSION",
    "DEFAULT_COMPATIBILITY_ROUTE_ID",
    "SUPPORTED_SOURCE_CONFIG_SCHEMA_VERSIONS",
    "BronzeIdentityStrategy",
    "CanonicalDatasetProductionConfig",
    "CanonicalDtype",
    "CanonicalRouteConfig",
    "CapabilitySelection",
    "CastRule",
    "ChangeDetectionPolicy",
    "ColumnMapping",
    "CompatibilitySourceBindingCompiler",
    "CompiledSourceBindingTopology",
    "CompositeIdentity",
    "ConstantRule",
    "CsvSelector",
    "DatasetSelector",
    "DefaultRule",
    "DerivedDeterministicIdentity",
    "DriftStrategy",
    "ExcelSelector",
    "ExcludeWhen",
    "FingerprintStrategy",
    "IncludeWhen",
    "MapValuesRule",
    "NormalizeCaseRule",
    "NormalizeNullRule",
    "NormalizationRule",
    "PROTECTED_FINANCIAL_NAMESPACES",
    "ParseDateRule",
    "PredicateOperator",
    "PredicateRule",
    "RenameStrategy",
    "SemanticConstantRule",
    "SemanticMapRule",
    "SemanticRule",
    "SourceBindingConfig",
    "SourceConfig",
    "SourceConfigFingerprint",
    "SourceConfiguration",
    "SourceDatasetConfig",
    "SourceFieldDeclaration",
    "SourceFieldIdentity",
    "SqliteSelector",
    "SyncStrategy",
    "TopologyCoverageReport",
    "TrimRule",
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
    "derive_source_binding_id",
    "dict_to_mapping_list",
    "evaluate_bronze_topology_coverage",
    "get_shan_baseline_dataset_bindings",
    "get_shan_baseline_source_configuration",
    "get_shan_baseline_sources",
    "mapping_list_to_dict",
    "resolve_change_detection_policy",
    "validate_source_bindings",
    "validate_source_dataset_bindings",
    "validate_source_selector_compatibility",
]
