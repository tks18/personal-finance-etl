"""Physical publication contracts and registries for warehouse layers.

Owns
----
- Contract lookup by physical table name (get_contract_by_table).
- Contract lookup by canonical dataset identity (get_contract_by_dataset_id, get_bronze_contract_by_dataset_id).
- Structural integrity and identity validation for registered data contracts (validate_registry).
- Re-exporting DataContract models, DatasetId, and registries from warehouse.contracts.

Does not own
-------------
- Concrete contract registry definitions (owned by infrastructure.warehouse.contracts).
- DuckDB table execution and DDL creation (owned by infrastructure.warehouse.connection).
- Layer-specific persistence engines (owned by bronze.py, silver.py, gold.py, meta.py).
- Cryptographic registry fingerprint generation (owned by infrastructure.warehouse.fingerprints).
"""

from __future__ import annotations

from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
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
    "DatasetId",
    "get_bronze_contract_by_dataset_id",
    "get_contract_by_dataset_id",
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


def get_contract_by_dataset_id(dataset_id: DatasetId | str) -> DataContract | None:
    """Find a DataContract matching the given DatasetId.

    Parameters
    ----------
    dataset_id : DatasetId | str
        Authoritative dataset identifier to look up.

    Returns
    -------
    DataContract | None
        Matching DataContract if found, otherwise None.
    """
    val = str(dataset_id)
    for contract in DATA_CONTRACT_REGISTRY:
        if contract.dataset_id.value == val or contract.dataset_id == dataset_id:
            return contract
    return None


def get_bronze_contract_by_dataset_id(
    dataset_id: DatasetId | str,
) -> BronzeDataContract | None:
    """Find a BronzeDataContract matching the given DatasetId.

    Parameters
    ----------
    dataset_id : DatasetId | str
        Authoritative Bronze dataset identifier to look up.

    Returns
    -------
    BronzeDataContract | None
        Matching BronzeDataContract if found, otherwise None.
    """
    val = str(dataset_id)
    for contract in BRONZE_CONTRACT_REGISTRY:
        if contract.dataset_id.value == val or contract.dataset_id == dataset_id:
            return contract
    return None


def _validate_data_contracts() -> None:
    """Validate structure, uniqueness, and required attributes of Silver/Gold contracts.

    Raises
    ------
    ValueError
        If duplicate IDs, duplicate dataset IDs, duplicate physical tables, invalid layers,
        or empty fields are found.
    """
    seen_ids: set[str] = set()
    seen_dataset_ids: set[str] = set()
    seen_tables: set[str] = set()

    for contract in DATA_CONTRACT_REGISTRY:
        if not contract.dataset_id:
            raise ValueError(f"Analytical contract {contract.contract_id} missing DatasetId.")
        ds_val = str(contract.dataset_id)
        if ds_val in seen_dataset_ids:
            raise ValueError(f"Duplicate analytical DatasetId found: {ds_val}")
        seen_dataset_ids.add(ds_val)

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
        If duplicate table mappings, duplicate dataset IDs, invalid prefixes,
        or missing categories are found.
    """
    bronze_tables: set[str] = set()
    bronze_dataset_ids: set[str] = set()

    for b_contract in BRONZE_CONTRACT_REGISTRY:
        if not b_contract.dataset_id:
            raise ValueError(
                f"Bronze contract {b_contract.extraction_attribute} missing DatasetId."
            )
        ds_val = str(b_contract.dataset_id)
        if ds_val in bronze_dataset_ids:
            raise ValueError(f"Duplicate Bronze DatasetId found: {ds_val}")
        bronze_dataset_ids.add(ds_val)

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

        if b_contract.identity_requirement not in (
            IdentityRequirement.REQUIRED,
            IdentityRequirement.NONE,
        ):
            raise ValueError(
                f"Bronze contract '{b_contract.dataset_id}' has invalid or missing identity_requirement: {b_contract.identity_requirement}"
            )
        if not b_contract.grain or not b_contract.grain.strip():
            raise ValueError(
                f"Bronze contract '{b_contract.dataset_id}' missing grain declaration."
            )


def validate_registry() -> None:
    """Validate uniqueness and presence of required metadata across registries.

    Raises
    ------
    ValueError
        If duplicate contract IDs, duplicate dataset IDs, duplicate physical tables,
        invalid layers, or empty fields are found.
    """
    _validate_data_contracts()
    _validate_bronze_contracts()

    # Verify global uniqueness of DatasetId across all warehouse contracts
    all_dataset_ids = [str(c.dataset_id) for c in BRONZE_CONTRACT_REGISTRY] + [
        str(c.dataset_id) for c in DATA_CONTRACT_REGISTRY
    ]
    if len(all_dataset_ids) != len(set(all_dataset_ids)):
        duplicates = {x for x in all_dataset_ids if all_dataset_ids.count(x) > 1}
        raise ValueError(f"Cross-layer duplicate DatasetId found across registries: {duplicates}")
