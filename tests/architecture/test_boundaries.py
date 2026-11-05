"""Architectural boundary enforcement tests.

Owns
----
- Verification of the dependency graph according to the Target Dependency Model
  (02-target-dependency-model.md) and the Engineering Constitution (Section 5).
- Prevents architectural regressions and forbidden import arrows.
"""

import ast
import re
from pathlib import Path

import pytest

from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "personal_finance_etl"

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
    "config": [
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.domain",
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


def test_package_structure_exists() -> None:
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
        "config/sources",
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


def test_numpy_docstrings_in_target_packages() -> None:
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


def test_dependency_boundaries() -> None:
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


def test_legacy_packages_demolished() -> None:
    """Assert that legacy backend and frontend packages no longer exist under SRC_ROOT."""
    assert not (SRC_ROOT / "backend").exists(), "Legacy 'backend' directory still exists in src"
    assert not (SRC_ROOT / "frontend").exists(), "Legacy 'frontend' directory still exists in src"


def test_no_source_category_in_financial_logic() -> None:
    """Constitutional guard: No application or domain logic may branch on __file_category__.

    Guarantees that financial logic relies exclusively on canonical classification
    (CURRENCY_ID, COUNTRY, GEO, INSTRUMENT_CLASS, etc.) rather than source file taxonomy.
    """
    financial_layers = ["application", "domain"]
    violations: list[str] = []

    class ComparisonChecker(ast.NodeVisitor):
        def __init__(self, filepath: Path) -> None:
            self.filepath = filepath

        def visit_Compare(self, node: ast.Compare) -> None:
            # Check equality/relational value comparisons against __file_category__
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                if isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                    operands = [node.left, comparator]
                    for operand in operands:
                        if (
                            isinstance(operand, ast.Constant)
                            and operand.value == "__file_category__"
                        ):
                            violations.append(
                                f"{self.filepath}:{node.lineno}: Value comparison on '__file_category__'"
                            )
                        if isinstance(operand, ast.Call):
                            for arg in operand.args:
                                if (
                                    isinstance(arg, ast.Constant)
                                    and arg.value == "__file_category__"
                                ):
                                    violations.append(
                                        f"{self.filepath}:{node.lineno}: Expression compares pl.col('__file_category__')"
                                    )
                        if isinstance(operand, ast.Subscript):
                            if (
                                isinstance(operand.slice, ast.Constant)
                                and operand.slice.value == "__file_category__"
                            ):
                                violations.append(
                                    f"{self.filepath}:{node.lineno}: Subscript comparison on '__file_category__'"
                                )
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("is_in", "is_between"):
                if isinstance(node.func.value, ast.Call):
                    for arg in node.func.value.args:
                        if isinstance(arg, ast.Constant) and arg.value == "__file_category__":
                            violations.append(
                                f"{self.filepath}:{node.lineno}: Call '{node.func.attr}' on '__file_category__'"
                            )
            self.generic_visit(node)

    for layer in financial_layers:
        layer_dir = SRC_ROOT / layer
        if not layer_dir.is_dir():
            continue
        for py_file in layer_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            checker = ComparisonChecker(py_file.relative_to(SRC_ROOT))
            checker.visit(tree)

    assert not violations, (
        "Forbidden source-category financial logic found in application/domain:\n"
        + "\n".join(violations)
    )


def test_silver_ddl_has_no_legacy_path_columns() -> None:
    """Verify that physical Silver DDL declares zero legacy file/folder path columns."""
    assert "__file_name__" not in SILVER_DDL
    assert "__folder_path__" not in SILVER_DDL


def test_silver_ddl_has_no_provider_specific_columns() -> None:
    """Verify that physical Silver DDL declares zero external provider-specific ticker columns."""
    assert "yF_Ticker" not in SILVER_DDL
    assert "YAHOO_TICKER" not in SILVER_DDL


def test_domain_has_no_provider_ticker_references() -> None:
    """Verify that pure financial domain layer contains zero vendor ticker references."""
    domain_path = Path("src/personal_finance_etl/domain")
    forbidden_terms = {"yF_Ticker", "YAHOO_TICKER"}
    violations: list[str] = []

    for py_file in domain_path.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in content:
                violations.append(f"{py_file}: contains forbidden vendor symbol '{term}'")

    assert not violations, (
        "Forbidden provider ticker references found in pure domain layer:\n" + "\n".join(violations)
    )


def test_silver_ddl_has_no_legacy_source_residue_or_file_category() -> None:
    """Verify that physical Silver DDL declares zero legacy residue or source taxonomy columns."""
    forbidden_residue = [
        "__file_category__",
        "ORDER_SEQUENCE",
        "S_NO",
        "PAID",
        "MARK",
        "CARDDIVIDMONTH",
        "DEVICE_ID",
        "USE_TIME",
        "ADDED_TIME",
        "INSERT_TYPE",
        "IS_SHOW",
        "ZTXDATESTR",
        "ZASSETUID",
        "ZCURRENCYUID",
        "ZAMOUNTACCOUNT",
        "ZUTIME",
    ]
    for term in forbidden_residue:
        pattern = rf"^\s*{re.escape(term)}\s+"
        match = re.search(pattern, SILVER_DDL, re.MULTILINE)
        assert match is None, f"Forbidden legacy residue column '{term}' declared in Silver DDL"


def test_capabilities_contract_purity() -> None:
    """Verify that capability contracts module imports only pure contracts and standard library."""
    capabilities_file = SRC_ROOT / "contracts" / "capabilities.py"
    assert capabilities_file.is_file(), "contracts/capabilities.py must exist"

    imported = _extract_imported_modules(capabilities_file)
    for lineno, mod in imported:
        if mod.startswith("personal_finance_etl."):
            assert mod.startswith("personal_finance_etl.contracts"), (
                f"Line {lineno}: capability contracts must only import from contracts layer, got '{mod}'"
            )


def test_domain_has_no_capability_plan_inspection() -> None:
    """Verify that pure domain layer never inspects execution plans or capability flags."""
    domain_dir = SRC_ROOT / "domain"
    forbidden_symbols = {"ExecutionPlan", "CapabilityId", "CapabilityPlanner"}
    violations: list[str] = []

    for py_file in domain_dir.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(sym in alias.name for sym in forbidden_symbols):
                        violations.append(
                            f"{py_file.relative_to(SRC_ROOT)}:{node.lineno}: imports '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    sym in node.module for sym in ("capabilities", "execution_plan", "planner")
                ):
                    violations.append(
                        f"{py_file.relative_to(SRC_ROOT)}:{node.lineno}: imports from '{node.module}'"
                    )
                for alias in node.names:
                    if alias.name in forbidden_symbols:
                        violations.append(
                            f"{py_file.relative_to(SRC_ROOT)}:{node.lineno}: imports '{alias.name}'"
                        )

    assert not violations, (
        "Pure domain layer must never inspect execution plans or capability flags:\n"
        + "\n".join(violations)
    )
