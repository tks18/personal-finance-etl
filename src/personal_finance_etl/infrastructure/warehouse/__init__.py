"""DuckDB warehouse persistence, layer managers, and schema registries.

Owns
----
- DuckDB connection management, extensions, and PRAGMA configurations.
- DataContract registries for Pre-Bronze, Bronze, Silver, Gold, and Meta layers.
- Concrete persistence implementations for Pre-Bronze, Bronze, Silver, Gold, and Meta tables.

Does not own
-------------
- Control Plane operational metadata (owned by infrastructure.control_plane).
- Business formulas or financial transformations (owned by domain.*).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_CONTRACT_REGISTRY,
    PRE_BRONZE_DATASET_ID,
    PRE_BRONZE_PROVENANCE_COLUMNS,
    PRE_BRONZE_SOURCE_ID,
    PreBronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import (
    PreBronzeLayer,
    get_pre_bronze_table_name,
    sanitize_physical_identifier,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    BronzeDataContract,
    DataContract,
    get_contract_by_table,
    get_pre_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_table,
    validate_registry,
)

__all__ = [
    "BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
    "PRE_BRONZE_ARTIFACT_ID",
    "PRE_BRONZE_CONTRACT_REGISTRY",
    "PRE_BRONZE_DATASET_ID",
    "PRE_BRONZE_PROVENANCE_COLUMNS",
    "PRE_BRONZE_SOURCE_ID",
    "BronzeDataContract",
    "DataContract",
    "DuckDBManager",
    "PreBronzeDataContract",
    "PreBronzeLayer",
    "generate_contract_registry_fingerprint",
    "get_contract_by_table",
    "get_pre_bronze_contract_by_dataset_id",
    "get_pre_bronze_contract_by_table",
    "get_pre_bronze_table_name",
    "sanitize_physical_identifier",
    "validate_registry",
]
