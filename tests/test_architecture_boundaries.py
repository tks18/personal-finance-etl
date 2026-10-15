"""Architectural boundary enforcement tests.

Owns
----
- Verification of the dependency graph according to the Target Dependency Model
  (02-target-dependency-model.md) and the Engineering Constitution (Section 5).
- Prevents architectural regressions and forbidden import arrows.
"""

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "personal_finance_etl"

# Forbidden import prefixes per layer according to the Engineering Constitution
FORBIDDEN_IMPORTS = {
    "contracts": [
        "personal_finance_etl.domain",
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.backend",
        "personal_finance_etl.frontend",
    ],
    "domain": [
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.backend.pipeline",
        "personal_finance_etl.backend.api",
        "personal_finance_etl.frontend",
        "duckdb",
        "sqlite3",
    ],
    "presentation": [
        "personal_finance_etl.domain.investments.lots.fifo",
        "personal_finance_etl.infrastructure.warehouse.connection",
        "personal_finance_etl.infrastructure.control_plane.connection",
        "personal_finance_etl.backend.load.database",
        "personal_finance_etl.backend.load.control_plane.connection",
    ],
}


def _extract_imported_modules(py_file: Path) -> list[tuple[int, str]]:
    """Parse AST of a Python file and extract imported module names with line numbers."""
    try:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))
    except Exception as exc:
        pytest.fail(f"Could not parse {py_file}: {exc}")

    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append((node.lineno, node.module))
    return imported


def test_package_structure_exists():
    """Verify that all target architecture packages exist and contain __init__.py."""
    expected_packages = [
        "application",
        "application/pipeline",
        "application/ingestion",
        "application/investments",
        "application/tax",
        "application/wealth",
        "application/recovery",
        "bootstrap",
        "config",
        "config/financial_rules",
        "contracts",
        "domain",
        "domain/common",
        "domain/household",
        "domain/household/transforms",
        "domain/market",
        "domain/investments",
        "domain/investments/transforms",
        "domain/investments/lots",
        "domain/investments/valuation",
        "domain/investments/performance",
        "domain/investments/reconciliation",
        "domain/investments/portfolio",
        "domain/tax",
        "domain/wealth",
        "domain/fire",
        "infrastructure",
        "infrastructure/control_plane",
        "infrastructure/warehouse",
        "infrastructure/warehouse/schema",
        "infrastructure/providers",
        "infrastructure/providers/files",
        "infrastructure/providers/market",
        "infrastructure/recovery",
        "infrastructure/preferences",
        "infrastructure/logging",
        "infrastructure/filesystem",
        "presentation",
        "presentation/cli",
        "presentation/desktop",
        "presentation/docs",
    ]

    for pkg in expected_packages:
        pkg_dir = SRC_ROOT / pkg
        init_file = pkg_dir / "__init__.py"
        assert pkg_dir.is_dir(), f"Target package directory missing: {pkg}"
        assert init_file.is_file(), f"Target package missing __init__.py: {pkg}"


def test_numpy_docstrings_in_target_packages():
    """Verify that all target package __init__.py files have NumPy-style ownership docstrings."""
    target_layers = (
        "application",
        "bootstrap",
        "config",
        "contracts",
        "domain",
        "infrastructure",
        "presentation",
    )
    for init_path in SRC_ROOT.rglob("__init__.py"):
        rel_path = init_path.relative_to(SRC_ROOT)
        if rel_path.parts[0] not in target_layers:
            continue

        content = init_path.read_text(encoding="utf-8")
        assert "Owns" in content, f"Missing 'Owns' section in docstring for {rel_path}"
        assert "Does not own" in content, (
            f"Missing 'Does not own' section in docstring for {rel_path}"
        )


def test_dependency_boundaries():
    """Enforce the strict architectural import boundaries across newly refactored layers."""
    violations: list[str] = []

    for layer, forbidden_prefixes in FORBIDDEN_IMPORTS.items():
        layer_dir = SRC_ROOT / layer
        if not layer_dir.is_dir():
            continue

        for py_file in layer_dir.rglob("*.py"):
            imports = _extract_imported_modules(py_file)
            for lineno, mod in imports:
                for forbidden in forbidden_prefixes:
                    if mod == forbidden or mod.startswith(forbidden + "."):
                        violations.append(
                            f"{py_file.relative_to(SRC_ROOT)}:{lineno} imports '{mod}' "
                            f"(forbidden in '{layer}': prohibited prefix '{forbidden}')"
                        )

    assert not violations, "Architectural boundary violations found:\n" + "\n".join(violations)


def test_legacy_packages_demolished():
    """Assert that legacy backend and frontend packages no longer exist under SRC_ROOT."""
    assert not (SRC_ROOT / "backend").exists(), "Legacy 'backend' directory still exists in src"
    assert not (SRC_ROOT / "frontend").exists(), "Legacy 'frontend' directory still exists in src"
