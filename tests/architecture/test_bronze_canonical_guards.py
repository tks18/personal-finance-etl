"""Architectural guards enforcing strict canonical Bronze invariants for Phase 036.

Owns
----
- Invariant 1: BronzeLayer does not define an _evolve_schema method.
- Invariant 2: Zero occurrences of ALTER TABLE ... ADD COLUMN in warehouse.bronze.
- Invariant 3: Zero occurrences of CREATE TABLE ... AS SELECT in warehouse.bronze.
- Invariant 4: BRONZE_DDL explicitly covers all 20 canonical Bronze tables.
- Invariant 5: All canonical Bronze validation schemas enforce strict=True.

Does not own
-------------
- Functional execution of Bronze writes (owned by tests.infrastructure.test_bronze_strict_canonical).
- Seven-layer boundary AST assertions (owned by tests.architecture.test_boundaries).
"""

from __future__ import annotations

import re
from pathlib import Path

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    CANONICAL_BRONZE_SCHEMAS,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import BRONZE_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.bronze import BRONZE_DDL

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "personal_finance_etl"


def test_bronze_layer_has_no_evolve_schema_method() -> None:
    """Verify BronzeLayer does not define or inherit _evolve_schema."""
    assert not hasattr(BronzeLayer, "_evolve_schema"), (
        "BronzeLayer must not define _evolve_schema; runtime schema evolution is prohibited."
    )


def test_zero_alter_table_add_column_in_bronze() -> None:
    """Verify zero occurrences of ALTER TABLE ... ADD COLUMN in warehouse/bronze.py."""
    bronze_py = SRC_ROOT / "infrastructure" / "warehouse" / "bronze.py"
    content = bronze_py.read_text(encoding="utf-8")
    match = re.search(r"ALTER\s+TABLE\s+.*ADD\s+COLUMN", content, re.IGNORECASE)
    assert match is None, (
        f"Found prohibited ALTER TABLE ADD COLUMN in {bronze_py}: {match.group(0) if match else ''}"
    )


def test_zero_create_table_as_select_in_bronze() -> None:
    """Verify zero occurrences of CREATE TABLE AS SELECT in warehouse/bronze.py."""
    bronze_py = SRC_ROOT / "infrastructure" / "warehouse" / "bronze.py"
    content = bronze_py.read_text(encoding="utf-8")
    match = re.search(r"CREATE\s+TABLE\s+.*AS\s+SELECT", content, re.IGNORECASE)
    assert match is None, (
        f"Found prohibited CREATE TABLE AS SELECT in {bronze_py}: {match.group(0) if match else ''}"
    )


def test_bronze_ddl_covers_all_canonical_tables() -> None:
    """Verify BRONZE_DDL contains explicit CREATE TABLE IF NOT EXISTS for all 20 tables."""
    for contract in BRONZE_CONTRACT_REGISTRY:
        table_name = contract.physical_table
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in BRONZE_DDL, (
            f"Table '{table_name}' for dataset '{contract.dataset_id.value}' missing from BRONZE_DDL."
        )


def test_all_canonical_schemas_enforce_strict_validation() -> None:
    """Verify every registered canonical Bronze schema has strict=True."""
    for ds_id in DatasetId:
        if ds_id in CANONICAL_BRONZE_SCHEMAS:
            schema = CANONICAL_BRONZE_SCHEMAS[ds_id]
            assert schema.strict is True, (
                f"Canonical Bronze schema for dataset '{ds_id.value}' must have strict=True, "
                f"got strict={schema.strict}."
            )


def test_zero_filename_operational_predicates_in_bronze() -> None:
    """Verify zero SQL operational predicates key by __file_name__ in warehouse/bronze.py."""
    bronze_py = SRC_ROOT / "infrastructure" / "warehouse" / "bronze.py"
    content = bronze_py.read_text(encoding="utf-8")
    assert "__file_name__" not in content, (
        f"Found prohibited __file_name__ reference in {bronze_py}. "
        "All Bronze partition and identity operations must use artifact_id."
    )


def test_zero_filename_operational_predicates_in_meta_healing() -> None:
    """Verify zero SQL operational predicates key by __file_name__ in warehouse/meta/healing.py."""
    healing_py = SRC_ROOT / "infrastructure" / "warehouse" / "meta" / "healing.py"
    content = healing_py.read_text(encoding="utf-8")
    assert "__file_name__" not in content, (
        f"Found prohibited __file_name__ reference in {healing_py}. "
        "All Meta healing operations must use artifact_id."
    )


def test_bronze_ddl_contains_zero_filename_columns() -> None:
    """Verify BRONZE_DDL contains zero __file_name__ or __folder_path__ columns."""
    assert "__file_name__" not in BRONZE_DDL, (
        "BRONZE_DDL must not declare operational column __file_name__."
    )
    assert "__folder_path__" not in BRONZE_DDL, (
        "BRONZE_DDL must not declare operational column __folder_path__."
    )


def test_canonical_schemas_contain_zero_filename_columns() -> None:
    """Verify no canonical Bronze schema declares __file_name__ or __folder_path__."""
    for ds_id, schema in CANONICAL_BRONZE_SCHEMAS.items():
        assert "__file_name__" not in schema.columns, (
            f"Canonical schema for '{ds_id.value}' must not declare '__file_name__'."
        )
        assert "__folder_path__" not in schema.columns, (
            f"Canonical schema for '{ds_id.value}' must not declare '__folder_path__'."
        )
