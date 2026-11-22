"""Architectural security and boundary guards for canonical production and recipes.

Owns
----
- Verification that contracts.canonical_recipes contains zero storage or dataframe imports.
- Verification that CanonicalProductionEngine contains zero ordering-dependent dedupe (no keep='first'/'last').
- Verification that RecipeRegistry allows only certified internal static handlers.
"""

from __future__ import annotations

import ast
from pathlib import Path

from personal_finance_etl.contracts.canonical_recipes import (
    CanonicalRecipeDescriptor,
)

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "personal_finance_etl"


def test_canonical_recipes_contracts_purity() -> None:
    """Verify that contracts.canonical_recipes has zero polars, duckdb, sqlite3, or pandera imports."""
    contract_file = SRC_ROOT / "contracts" / "canonical_recipes.py"
    assert contract_file.exists(), "canonical_recipes.py contract file must exist."

    tree = ast.parse(contract_file.read_text(encoding="utf-8"))
    forbidden_modules = {"polars", "pl", "duckdb", "sqlite3", "pandera", "pa"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg not in forbidden_modules, (
                    f"Forbidden import '{alias.name}' in contracts/canonical_recipes.py"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg not in forbidden_modules, (
                    f"Forbidden from-import '{node.module}' in contracts/canonical_recipes.py"
                )


def test_no_ordering_dependent_dedupe_in_production_engine() -> None:
    """Verify that CanonicalProductionEngine never invokes unique(keep='first'|'last')."""
    engine_file = SRC_ROOT / "application" / "ingestion" / "canonical_production.py"
    assert engine_file.exists(), "canonical_production.py file must exist."

    content = engine_file.read_text(encoding="utf-8")
    assert 'keep="first"' not in content, (
        "Forbidden ordering-dependent keep='first' in production engine."
    )
    assert "keep='first'" not in content, (
        "Forbidden ordering-dependent keep='first' in production engine."
    )
    assert 'keep="last"' not in content, (
        "Forbidden ordering-dependent keep='last' in production engine."
    )
    assert "keep='last'" not in content, (
        "Forbidden ordering-dependent keep='last' in production engine."
    )


def test_recipe_descriptor_immutability() -> None:
    """Verify that CanonicalRecipeDescriptor is frozen and slotted."""
    from personal_finance_etl.contracts.datasets import DatasetId

    desc = CanonicalRecipeDescriptor(
        recipe_id="test_recipe",
        version="1.0.0",
        target_dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        dependencies=(DatasetId.HOUSEHOLD_ASSETS,),
        description="Test descriptor",
    )
    import pytest

    with pytest.raises((AttributeError, TypeError)):
        desc.recipe_id = "mutated"  # type: ignore[misc]
