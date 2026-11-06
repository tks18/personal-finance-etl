"""Evidence ingestion and synchronization coordination.

Owns
----
- Orchestrating evidence acquisition from providers.
- Checking extraction completeness and recording provenance.
- Coordinating Bronze storage persistence and synchronization.
- Transitional compatibility resolution for change detection (resolve_legacy_change_detection_policy).
- Identity plan compilation and deterministic execution for Bronze datasets (compile_identity_plan, execute_identity_plan).
- Pre-Bronze dataset admission coordinating normalization and identity resolution (AdmissionPlan, AdmissionService).

Does not own
-------------
- Concrete file parsers or API client requests (owned by infrastructure.providers).
- Control Plane database transactions (owned by infrastructure.control_plane).
- Semantic canonical transformations (owned by domain.*).
"""

from __future__ import annotations

from personal_finance_etl.application.ingestion.admission import (
    AdmissionPlan,
    AdmissionService,
)
from personal_finance_etl.application.ingestion.asset_strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)
from personal_finance_etl.application.ingestion.coordinator import (
    DataExtractor,
)
from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionDiagnostic,
    IdentityCollisionError,
    IdentityNotPermittedError,
    IdentityPlan,
    MissingIdentityFieldError,
    MissingIdentityStrategyError,
    compile_identity_plan,
    execute_identity_plan,
)
from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
    CurrencyPipeline,
    USMarketPipeline,
)
from personal_finance_etl.application.ingestion.policy_resolver import (
    resolve_legacy_change_detection_policy,
)

__all__ = [
    "AdmissionPlan",
    "AdmissionService",
    "AssetPipeline",
    "BenchmarkPipeline",
    "CurrencyPipeline",
    "DataExtractor",
    "IdentityCollisionDiagnostic",
    "IdentityCollisionError",
    "IdentityNotPermittedError",
    "IdentityPlan",
    "MissingIdentityFieldError",
    "MissingIdentityStrategyError",
    "MutualFundPipeline",
    "StockPipeline",
    "USMarketPipeline",
    "USStockPipeline",
    "compile_identity_plan",
    "execute_identity_plan",
    "resolve_legacy_change_detection_policy",
]
