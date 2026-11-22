"""DuckDB warehouse persistence, layer managers, and schema registries.

Owns
----
- DuckDB connection management, extensions, and PRAGMA configurations.
- DataContract registries for Bronze, Silver, Gold, and Meta layers.
- Concrete persistence implementations for Bronze, Silver, Gold, and Meta tables.

Does not own
-------------
- Control Plane operational metadata (owned by infrastructure.control_plane).
- Business formulas or financial transformations (owned by domain.*).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    BronzeDataContract,
    DataContract,
    get_contract_by_table,
    validate_registry,
)

__all__ = [
    "BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
    "BronzeDataContract",
    "DataContract",
    "DuckDBManager",
    "generate_contract_registry_fingerprint",
    "get_contract_by_table",
    "validate_registry",
]
