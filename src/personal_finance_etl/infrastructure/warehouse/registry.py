"""Physical publication contracts and registries for warehouse layers.

Owns
----
- Contract lookup by physical table name (get_contract_by_table).
- Structural integrity validation for registered data contracts (validate_registry).
- Re-exporting DataContract models and registries from warehouse.contracts.

Does not own
-------------
- Concrete contract registry definitions (owned by infrastructure.warehouse.contracts).
- DuckDB table execution and DDL creation (owned by infrastructure.warehouse.connection).
- Layer-specific persistence engines (owned by bronze.py, silver.py, gold.py, meta.py).
- Cryptographic registry fingerprint generation (owned by infrastructure.warehouse.fingerprints).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    BronzeDataContract,
    DataContract,
)

__all__ = [
    "BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
    "BronzeDataContract",
    "DataContract",
    "get_contract_by_table",
    "validate_registry",
]


def get_contract_by_table(physical_table: str) -> DataContract | None:
    """Find a DataContract matching the given physical table name (case-insensitive).

    Parameters
    ----------
    physical_table : str
        Physical table name to look up.

    Returns
    -------
    DataContract | None
        Matching DataContract if found, otherwise None.
    """
    for contract in DATA_CONTRACT_REGISTRY:
        if contract.physical_table.lower() == physical_table.lower():
            return contract
    return None


def _validate_data_contracts() -> None:
    """Validate structure, uniqueness, and required attributes of Silver/Gold contracts.

    Raises
    ------
    ValueError
        If duplicate IDs, duplicate physical tables, invalid layers, or empty fields are found.
    """
    seen_ids: set[str] = set()
    seen_tables: set[str] = set()

    for contract in DATA_CONTRACT_REGISTRY:
        if not contract.contract_id:
            raise ValueError("Contract ID cannot be empty.")
        if contract.contract_id in seen_ids:
            raise ValueError(f"Duplicate contract_id found: {contract.contract_id}")
        seen_ids.add(contract.contract_id)

        table_lower = contract.physical_table.lower()
        if table_lower in seen_tables:
            raise ValueError(
                f"Duplicate Silver/Gold physical table mapping: {contract.physical_table}"
            )
        seen_tables.add(table_lower)

        if contract.layer not in ("silver", "gold"):
            raise ValueError(
                f"Invalid layer '{contract.layer}' for contract {contract.contract_id}"
            )

        if not contract.physical_table or not contract.grain or not contract.producer:
            raise ValueError(
                f"Contract {contract.contract_id} is missing required metadata attributes."
            )


def _validate_bronze_contracts() -> None:
    """Validate structure, uniqueness, and prefixing of Bronze contracts.

    Raises
    ------
    ValueError
        If duplicate table mappings, invalid prefixes, or missing categories are found.
    """
    bronze_tables: set[str] = set()
    for b_contract in BRONZE_CONTRACT_REGISTRY:
        if not b_contract.extraction_attribute:
            raise ValueError("Bronze extraction_attribute cannot be empty.")
        if not b_contract.sync_category:
            raise ValueError(f"Bronze sync_category empty for {b_contract.extraction_attribute}")
        if not b_contract.physical_table:
            raise ValueError(f"Bronze physical_table empty for {b_contract.extraction_attribute}")
        if not b_contract.physical_table.startswith("bronze."):
            raise ValueError(f"Bronze table must start with 'bronze.': {b_contract.physical_table}")

        if b_contract.physical_table in bronze_tables:
            raise ValueError(f"Duplicate Bronze table mapping: {b_contract.physical_table}")
        bronze_tables.add(b_contract.physical_table)


def validate_registry() -> None:
    """Validate uniqueness and presence of required metadata across registries.

    Raises
    ------
    ValueError
        If duplicate IDs, duplicate physical tables, invalid layers, or empty fields are found.
    """
    _validate_data_contracts()
    _validate_bronze_contracts()
