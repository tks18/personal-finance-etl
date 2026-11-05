"""Architectural cross-boundary contracts.

Owns
----
- Typed messages and results crossing architectural and process boundaries.
- Pipeline lifecycle state enums (CommitState, FailureDomain).
- Tabular data transport contract (EngineDataTransport).
- Canonical dataset identifiers (DatasetId).
- Source identity and provider contracts (SourceId, ProviderType, validate_source_id).
- Extraction batch and entity outcomes (ExtractionBatchResult, ExtractorEntityResult).
- Snapshot and restore outcome contracts (SnapshotResult, RestoreResult).
- Canonical event transport queue contracts.
- Canonical typed observability and telemetry contracts (ObservabilityEvent, EventCode).
- Authoritative Silver and Gold semantic inventories, column classifications, and dispositions.
- Canonical provenance and artifact metadata contracts (ProvenanceRef, ArtifactMetadata).
- Provider-neutral market vocabulary and symbol mapping contracts (ProviderSymbolMapping, ProviderSymbolRegistry).
- Financial capability graph, descriptors, and resolution (CapabilityId, CapabilityDescriptor, CapabilityGraph).

Does not own
-------------
- Domain-internal calculation records (owned by domain.*).
- Database table DDL or SQL schemas (owned by infrastructure.warehouse.schema).
- UI widget state (owned by presentation).
"""

from personal_finance_etl.contracts.application import (
    EngineDataTransport,
    EngineExecutionResult,
    EngineStage,
)
from personal_finance_etl.contracts.capabilities import (
    CAPABILITY_REGISTRY,
    COMMON_PRODUCED_SILVER_DATASETS,
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityGraphError,
    CapabilityId,
    ContributionDescriptor,
    ContributionScope,
    ExternalEnrichmentId,
    ResolvedCapabilityGraph,
)
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    EXTERNAL_CONFIGURED_DATASETS,
    PROVIDER_GENERATED_DATASETS,
    TRANSITIONAL_DATASETS,
    DatasetId,
    DatasetOrigin,
    IdentityRequirement,
    get_bronze_dataset_origin,
)
from personal_finance_etl.contracts.event_transport import EventQueue, NullEventQueue
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractionCompletenessError,
    ExtractionProviderRequest,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    SyncSummaryRecord,
    classify_failure_domain,
)
from personal_finance_etl.contracts.market import (
    ProviderSymbolMapping,
    ProviderSymbolRegistry,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    ErrorDetailsDict,
    EventCode,
    EventEmitter,
    EventOutcome,
    NullObservabilitySink,
    ObservabilityContext,
    ObservabilityContextDict,
    ObservabilityEvent,
    ObservabilityEventDict,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.contracts.provenance import (
    ArtifactMetadata,
    ProvenanceRef,
)
from personal_finance_etl.contracts.recovery import (
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.contracts.semantic_inventory import (
    ALL_SILVER_COLUMN_DISPOSITIONS,
    GOLD_CONTRACT_DEPENDENCIES,
    SILVER_COLUMN_DISPOSITIONS,
    SILVER_CONTRACT_SEMANTICS,
    ColumnClassification,
    ColumnDisposition,
    GoldContractDependency,
    SilverColumnDisposition,
    SilverContractSemantics,
    get_columns_by_classification,
    get_columns_by_disposition,
    get_gold_contract_dependency,
    get_silver_column_disposition,
    get_silver_contract_semantics,
)
from personal_finance_etl.contracts.sources import (
    ProviderType,
    SourceId,
    validate_source_id,
)

__all__ = [
    "ALL_SILVER_COLUMN_DISPOSITIONS",
    "ArtifactMetadata",
    "BRONZE_DATASET_ORIGIN_MAP",
    "CAPABILITY_REGISTRY",
    "COMMON_PRODUCED_SILVER_DATASETS",
    "CapabilityDescriptor",
    "CapabilityGraph",
    "CapabilityGraphError",
    "CapabilityId",
    "ColumnClassification",
    "ColumnDisposition",
    "CommitState",
    "ContributionDescriptor",
    "ContributionScope",
    "DatasetId",
    "DatasetOrigin",
    "DiagnosticSeverity",
    "EXTERNAL_CONFIGURED_DATASETS",
    "EngineDataTransport",
    "EngineExecutionResult",
    "EngineStage",
    "ErrorDetails",
    "ErrorDetailsDict",
    "EventCode",
    "EventEmitter",
    "EventOutcome",
    "ExternalEnrichmentId",
    "ExtractionBatchResult",
    "ExtractionCompletenessError",
    "ExtractionProviderRequest",
    "ExtractorEntityResult",
    "ExtractorEntityStatus",
    "FailureDomain",
    "GOLD_CONTRACT_DEPENDENCIES",
    "GoldContractDependency",
    "IdentityRequirement",
    "EventQueue",
    "NullEventQueue",
    "NullObservabilitySink",
    "ObservabilityContext",
    "ObservabilityContextDict",
    "ObservabilityEvent",
    "ObservabilityEventDict",
    "ObservabilitySink",
    "PROVIDER_GENERATED_DATASETS",
    "PresentationKind",
    "ProvenanceRef",
    "ProviderSymbolMapping",
    "ProviderSymbolRegistry",
    "ProviderType",
    "ResolvedCapabilityGraph",
    "RestoreOutcome",
    "RestoreResult",
    "SILVER_COLUMN_DISPOSITIONS",
    "SILVER_CONTRACT_SEMANTICS",
    "SilverColumnDisposition",
    "SilverContractSemantics",
    "SnapshotOutcome",
    "SnapshotResult",
    "SourceId",
    "SyncSummaryRecord",
    "TRANSITIONAL_DATASETS",
    "classify_failure_domain",
    "get_bronze_dataset_origin",
    "get_columns_by_classification",
    "get_columns_by_disposition",
    "get_gold_contract_dependency",
    "get_silver_column_disposition",
    "get_silver_contract_semantics",
    "validate_source_id",
]
