# pylint: skip-file
# flake8: noqa
"""Phase 12 Architectural Certification & Constitutional Audit Test Suite.

Owns
----
- Constitutional compliance verification of the entire clean architecture refactor.
- Strict unidirectional layer dependency matrix enforcement (AST-based).
- Verification of zero surviving legacy package imports or remnants.
- Verification of zero `if TYPE_CHECKING:` conditional imports.
- Verification of zero deferred or inline imports inside function/method bodies.
- Verification that all `# type: ignore` directives specify explicit error codes.
- Verification of NumPy-style `Owns` and `Does not own` ownership docstrings across all packages.
- Verification of canonical public facades and CLI/GUI entry points.
- Verification of financial rules composed models.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "personal_finance_etl"
TESTS_ROOT = REPO_ROOT / "tests"

# Constitutional Allowed Dependency Matrix
# Dict mapping each layer to forbidden import prefixes
CONSTITUTIONAL_FORBIDDEN_MATRIX: dict[str, list[str]] = {
    "contracts": [
        "personal_finance_etl.domain",
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.bootstrap",
        "duckdb",
        "sqlite3",
    ],
    "domain": [
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.bootstrap",
        "duckdb",
        "sqlite3",
    ],
    "infrastructure": [
        "personal_finance_etl.application",
        "personal_finance_etl.presentation",
        "personal_finance_etl.bootstrap",
    ],
    "config": [
        "personal_finance_etl.application",
        "personal_finance_etl.presentation",
        "personal_finance_etl.bootstrap",
        "personal_finance_etl.infrastructure.warehouse",
        "personal_finance_etl.infrastructure.control_plane",
    ],
    "presentation": [
        "personal_finance_etl.domain.investments.lots.fifo",
        "personal_finance_etl.infrastructure.warehouse.connection",
        "personal_finance_etl.infrastructure.control_plane.connection",
    ],
}


def test_strict_layer_dependency_matrix() -> None:
    """Enforce strict unidirectional dependency arrows across the 7 Clean Architecture layers."""
    violations: list[str] = []

    for layer, forbidden_prefixes in CONSTITUTIONAL_FORBIDDEN_MATRIX.items():
        layer_dir = SRC_ROOT / layer
        if not layer_dir.is_dir():
            continue

        for py_file in layer_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception as exc:
                violations.append(f"Cannot parse {py_file}: {exc}")
                continue

            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]

                lineno = getattr(node, "lineno", 0)
                for mod in modules:
                    for forbidden in forbidden_prefixes:
                        if mod == forbidden or mod.startswith(forbidden + "."):
                            violations.append(
                                f"{py_file.relative_to(SRC_ROOT)}:{lineno} imports '{mod}' "
                                f"(forbidden in '{layer}': prohibited prefix '{forbidden}')"
                            )

    assert not violations, "Constitutional layer dependency violations found:\n" + "\n".join(
        violations
    )


def test_zero_legacy_remnants() -> None:
    """Assert zero imports from personal_finance_etl.backend or personal_finance_etl.frontend."""
    violations: list[str] = []
    this_file = Path(__file__).resolve()

    for folder in (SRC_ROOT, TESTS_ROOT):
        for py_file in folder.rglob("*.py"):
            if py_file.resolve() == this_file:
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]

                lineno = getattr(node, "lineno", 0)
                for name in names:
                    if name.startswith("personal_finance_etl.backend") or name.startswith(
                        "personal_finance_etl.frontend"
                    ):
                        violations.append(f"{py_file.name}:{lineno} imports {name}")

    assert not violations, "Found surviving legacy imports:\n" + "\n".join(violations)


def test_zero_type_checking_blocks() -> None:
    """Assert zero if TYPE_CHECKING: conditional blocks exist in the entire repository."""
    violations: list[str] = []
    this_file = Path(__file__).resolve()

    for folder in (SRC_ROOT, TESTS_ROOT):
        for py_file in folder.rglob("*.py"):
            if py_file.resolve() == this_file:
                continue
            content = py_file.read_text(encoding="utf-8")
            if "TYPE_CHECKING" in content:
                violations.append(f"{py_file.name} contains TYPE_CHECKING")

    assert not violations, "Found TYPE_CHECKING blocks:\n" + "\n".join(violations)


def test_zero_inline_or_deferred_imports() -> None:
    """Assert zero import statements inside function, method, or class bodies in src/."""
    violations: list[str] = []

    for py_file in SRC_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        violations.append(f"{py_file.relative_to(SRC_ROOT)}:{child.lineno}")

    assert not violations, "Found inline/deferred imports inside functions:\n" + "\n".join(
        violations
    )


def test_type_ignores_have_explicit_codes() -> None:
    """Assert all type: ignore comments in src/ have explicit bracketed error codes."""
    violations: list[str] = []

    for py_file in SRC_ROOT.rglob("*.py"):
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            # Match bare type: ignore without [code]
            if "# type: ignore" in stripped:
                after_ignore = stripped.split("# type: ignore", 1)[1].strip()
                if not after_ignore.startswith("["):
                    violations.append(f"{py_file.relative_to(SRC_ROOT)}:{lineno}: '{stripped}'")

    assert not violations, "Found bare # type: ignore without specific error codes:\n" + "\n".join(
        violations
    )


def test_numpy_package_ownership_docstrings() -> None:
    """Verify that every __init__.py in src/personal_finance_etl has Owns and Does not own docstrings."""
    missing: list[str] = []

    for init_file in SRC_ROOT.rglob("__init__.py"):
        content = init_file.read_text(encoding="utf-8")
        if "Owns" not in content or "Does not own" not in content:
            missing.append(str(init_file.relative_to(SRC_ROOT)))

    assert not missing, "Missing NumPy-style 'Owns' / 'Does not own' docstrings in:\n" + "\n".join(
        missing
    )


def test_canonical_facade_and_container() -> None:
    """Verify canonical PersonalFinanceEngine facade and ServiceContainer wiring."""
    from personal_finance_etl import DesktopApp, PersonalFinanceEngine, main_cli, run_app
    from personal_finance_etl.bootstrap.container import ServiceContainer

    assert callable(PersonalFinanceEngine)
    assert callable(DesktopApp)
    assert callable(main_cli)
    assert callable(run_app)

    container = ServiceContainer(default_config_path="", default_rules_path="")
    assert container is not None
    assert container.get_preferences_manager() is not None


def test_financial_rules_model_completeness() -> None:
    """Verify composed FinancialRules model loads and validates test rules cleanly."""
    from personal_finance_etl.config.financial_rules import FinancialRules

    rules_path = REPO_ROOT / "tests" / "financial_rules.toml"
    assert rules_path.exists(), "Test financial_rules.toml missing"

    rules = FinancialRules.from_toml(str(rules_path))
    assert rules.DEFAULT_CURRENCY_ID == "INR_INR"
    assert rules.income is not None
    assert rules.expense is not None
    assert rules.budget is not None
    assert rules.assets is not None
    assert rules.investments is not None
    assert rules.assumptions is not None
    assert rules.assumptions.tax is not None
    assert rules.assumptions.fire is not None
    assert rules.portfolio_management is not None


def test_entry_points_resolution() -> None:
    """Verify shan-fin and shan-fin-gui console script entry points are importable callables."""
    launcher_mod = importlib.import_module("personal_finance_etl.presentation.launcher")
    desktop_mod = importlib.import_module("personal_finance_etl.presentation.desktop.app")

    assert hasattr(launcher_mod, "main") and callable(launcher_mod.main)
    assert hasattr(desktop_mod, "main") and callable(desktop_mod.main)
