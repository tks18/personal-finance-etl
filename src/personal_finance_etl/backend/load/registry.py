"""Pass-through delegation shim for warehouse data contracts.

Superseded by personal_finance_etl.infrastructure.warehouse.registry.
"""

from __future__ import annotations

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
    "get_contract_by_table",
    "validate_registry",
]
