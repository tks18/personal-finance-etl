"""Architecture boundary and immutability guards for canonical satisfiability planning.

Owns
----
- Verification of zero storage/network imports in canonical planning contracts.
- Verification of pure non-I/O execution in CanonicalSatisfiabilityPlanner.
- Verification of frozen slotted immutability for all production planning descriptors.
"""

from __future__ import annotations

import ast
from dataclasses import is_dataclass
from pathlib import Path

from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalProducerCandidate,
    CanonicalProductionPlan,
)


def test_canonical_plans_contract_purity() -> None:
    """Verify contracts/canonical_plans.py contains zero I/O, Polars, Pandera, DuckDB, or SQLite imports."""
    contract_file = Path("src/personal_finance_etl/contracts/canonical_plans.py")
    tree = ast.parse(contract_file.read_text(encoding="utf-8"))

    prohibited_modules = {
        "polars",
        "pandera",
        "duckdb",
        "sqlite3",
        "requests",
        "httpx",
        "urllib",
        "socket",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg not in prohibited_modules, (
                    f"Forbidden import '{alias.name}' detected in {contract_file}."
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg not in prohibited_modules, (
                    f"Forbidden import '{node.module}' detected in {contract_file}."
                )


def test_satisfiability_planner_non_io_purity() -> None:
    """Verify application/pipeline/satisfiability.py does not import networking or persistent database drivers."""
    service_file = Path("src/personal_finance_etl/application/pipeline/satisfiability.py")
    tree = ast.parse(service_file.read_text(encoding="utf-8"))

    prohibited_modules = {
        "duckdb",
        "sqlite3",
        "requests",
        "httpx",
        "urllib",
        "socket",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                assert root_pkg not in prohibited_modules, (
                    f"Forbidden I/O import '{alias.name}' detected in {service_file}."
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg not in prohibited_modules, (
                    f"Forbidden I/O import '{node.module}' detected in {service_file}."
                )


def test_production_plan_descriptors_are_frozen_and_slotted() -> None:
    """Verify all planning descriptors are frozen slotted dataclasses preventing accidental mutation."""
    descriptors = [
        CanonicalProducerCandidate,
        CanonicalDatasetPlan,
        CanonicalProductionPlan,
    ]

    for desc in descriptors:
        assert is_dataclass(desc), f"{desc.__name__} must be a dataclass."
        # Dataclass params: frozen check
        params = getattr(desc, "__dataclass_params__", None)
        assert params is not None and params.frozen is True, f"{desc.__name__} must be frozen."
        # Slots check
        assert hasattr(desc, "__slots__"), f"{desc.__name__} must define __slots__."
