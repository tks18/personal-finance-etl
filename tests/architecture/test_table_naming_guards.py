"""Architectural AST and contract guards enforcing unified table naming conventions.

Owns
----
- Verifying zero legacy prefixes (pb_, r_, d_, f_) across all warehouse contracts.
- Verifying 100% adherence to physical_table == f"{layer}.{dataset_id.value}".
- AST scanning src/personal_finance_etl for forbidden legacy physical table name literals.
- Verifying semantic inventory and column disposition catalogs use unified table names.

Does not own
-------------
- Runtime table data insertion or schema creation (owned by infrastructure.warehouse).
- General layer import boundary enforcement (owned by test_boundaries.py).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from personal_finance_etl.contracts.semantic_inventory import (
    GOLD_CONTRACT_DEPENDENCIES,
    SILVER_CONTRACT_SEMANTICS,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    PRE_BRONZE_CONTRACT_REGISTRY,
)

FORBIDDEN_PREFIX_PATTERN = re.compile(r"^(pb_|r_|d_|f_)[A-Za-z0-9_]+")
LEGACY_TABLE_LITERALS = frozenset(
    {
        "pb_household_assets",
        "pb_household_zcategory",
        "pb_household_inoutcome",
        "pb_investment_stock_orders",
        "pb_investment_mf_orders",
        "pb_market_mf_holdings",
        "r_SQLite_ZCategory",
        "r_SQLite_AssetGroup",
        "r_SQLite_Assets",
        "r_SQLite_Currency",
        "r_SQLite_InOutcome",
        "r_Stock_Market_Data",
        "r_MF_Market_Data",
        "r_Stock_Transactions",
        "r_MF_Transactions",
        "r_US_Stock_Transactions",
        "r_MF_ISIN_Mapping",
        "r_Benchmark_Mapping",
        "r_Opening_Balances",
        "r_Benchmark_Master",
        "r_Macro_Parameters",
        "r_Currency_Mapping",
        "r_Currency_FX_Data",
        "r_Benchmark_Data",
        "r_US_Stock_Prices",
        "r_Column_Master",
        "d_Calendar",
        "d_Investment_Master",
        "f_Expense_Transactions",
        "f_Investment_Analytics_Lot",
        "Tax_Year_Summary",
        "Wealth_Asset_Breakdown",
        "Wealth_FIRE_Analytics",
        "Core_Monthly_Fact",
    }
)


def test_pre_bronze_contracts_unified_naming() -> None:
    """Verify all Pre-Bronze contracts follow physical_table == pre_bronze.{dataset_id.value}."""
    for contract in PRE_BRONZE_CONTRACT_REGISTRY:
        expected = f"pre_bronze.{contract.dataset_id.value}"
        assert contract.physical_table == expected, (
            f"Pre-Bronze contract {contract.dataset_id.value} physical_table "
            f"'{contract.physical_table}' must equal '{expected}'."
        )
        bare_table = contract.physical_table.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare_table), (
            f"Pre-Bronze table '{contract.physical_table}' contains forbidden legacy prefix."
        )


def test_bronze_contracts_unified_naming() -> None:
    """Verify all Bronze contracts follow physical_table == bronze.{dataset_id.value}."""
    assert len(BRONZE_CONTRACT_REGISTRY) == 20
    for contract in BRONZE_CONTRACT_REGISTRY:
        expected = f"bronze.{contract.dataset_id.value}"
        assert contract.physical_table == expected, (
            f"Bronze contract {contract.dataset_id.value} physical_table "
            f"'{contract.physical_table}' must equal '{expected}'."
        )
        bare_table = contract.physical_table.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare_table), (
            f"Bronze table '{contract.physical_table}' contains forbidden legacy prefix."
        )


def test_silver_and_gold_contracts_unified_naming() -> None:
    """Verify all Silver and Gold contracts follow physical_table == {layer}.{dataset_id.value}."""
    silver_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"]
    gold_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]

    assert len(silver_contracts) == 24
    assert len(gold_contracts) == 22

    for contract in DATA_CONTRACT_REGISTRY:
        expected = f"{contract.layer}.{contract.dataset_id.value}"
        assert contract.physical_table == expected, (
            f"Contract {contract.dataset_id.value} physical_table "
            f"'{contract.physical_table}' must equal '{expected}'."
        )
        bare_table = contract.physical_table.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare_table), (
            f"Table '{contract.physical_table}' contains forbidden legacy prefix."
        )


def test_silver_column_dispositions_json_unified_naming() -> None:
    """Verify silver_column_dispositions.json references only unified physical table names."""
    json_path = (
        Path(__file__).parents[2]
        / "src"
        / "personal_finance_etl"
        / "contracts"
        / "silver_column_dispositions.json"
    )
    assert json_path.exists(), f"Missing {json_path}"
    data = json.loads(json_path.read_text(encoding="utf-8"))

    tables = {entry["physical_table"] for entry in data}
    for tbl in tables:
        assert tbl.startswith("silver."), f"Table '{tbl}' must start with 'silver.'"
        bare_table = tbl.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare_table), (
            f"Disposition table '{tbl}' contains forbidden legacy prefix."
        )


def test_semantic_inventory_unified_naming() -> None:
    """Verify semantic_inventory.py references only unified physical table names."""
    for entry in SILVER_CONTRACT_SEMANTICS.values():
        assert entry.physical_table.startswith("silver."), (
            f"Silver semantic entry '{entry.physical_table}' must start with 'silver.'"
        )
        bare = entry.physical_table.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare), (
            f"Silver entry '{entry.physical_table}' contains forbidden legacy prefix."
        )

    for gold_entry in GOLD_CONTRACT_DEPENDENCIES.values():
        assert gold_entry.physical_table.startswith("gold."), (
            f"Gold dependency entry '{gold_entry.physical_table}' must start with 'gold.'"
        )
        bare_gold = gold_entry.physical_table.split(".", maxsplit=1)[-1]
        assert not FORBIDDEN_PREFIX_PATTERN.match(bare_gold), (
            f"Gold entry '{gold_entry.physical_table}' contains forbidden legacy prefix."
        )


def test_ast_zero_legacy_table_literals_in_source_tree() -> None:
    """AST guard: verify zero occurrences of legacy table name literals in production source code."""
    src_dir = Path(__file__).parents[2] / "src" / "personal_finance_etl"
    violations: list[str] = []

    for py_file in src_dir.rglob("*.py"):
        # Skip the backward migration script or test fixtures if any
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                for legacy in LEGACY_TABLE_LITERALS:
                    if f".{legacy}" in val or val == legacy:
                        violations.append(
                            f"{py_file.relative_to(src_dir)}:line {node.lineno}: found '{val}'"
                        )

    assert not violations, (
        f"Found {len(violations)} forbidden legacy table literal references in source tree:\n"
        + "\n".join(violations[:20])
    )
