"""Phase 11 Legacy Demolition Certification Test Suite.

Owns
----
- Verification of complete demolition of legacy `backend` and `frontend` packages.
- Verification that importing `personal_finance_etl.backend` or `personal_finance_etl.frontend` raises ModuleNotFoundError.
- Verification of canonical public API re-exports in root `personal_finance_etl/__init__.py`.
- Verification of entry point callables configured in `pyproject.toml`.
- Verification that zero occurrences of legacy module imports exist across `src/` and `tests/`.
- Verification of canonical `TransformationDAG` importability.
- Verification of the 7 canonical Clean Architecture package roots.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "personal_finance_etl"
TESTS_ROOT = REPO_ROOT / "tests"

CANONICAL_PACKAGES = {
    "application",
    "bootstrap",
    "config",
    "contracts",
    "domain",
    "infrastructure",
    "presentation",
}


def test_legacy_directories_permanently_demolished() -> None:
    """Verify that backend and frontend directories do not exist on disk."""
    backend_dir = SRC_ROOT / "backend"
    frontend_dir = SRC_ROOT / "frontend"

    assert not backend_dir.exists(), f"Legacy directory still exists: {backend_dir}"
    assert not frontend_dir.exists(), f"Legacy directory still exists: {frontend_dir}"


def test_canonical_packages_structure() -> None:
    """Verify that only the 7 canonical Clean Architecture packages exist at package root."""
    actual_packages = {
        item.name
        for item in SRC_ROOT.iterdir()
        if item.is_dir() and not item.name.startswith((".", "_"))
    }
    assert actual_packages == CANONICAL_PACKAGES, (
        f"Mismatch in root packages: expected {CANONICAL_PACKAGES}, got {actual_packages}"
    )


def test_legacy_backend_import_raises_module_not_found() -> None:
    """Verify that attempting to import personal_finance_etl.backend raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("personal_finance_etl.backend")
    assert "backend" in str(exc_info.value)


def test_legacy_frontend_import_raises_module_not_found() -> None:
    """Verify that attempting to import personal_finance_etl.frontend raises ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("personal_finance_etl.frontend")
    assert "frontend" in str(exc_info.value)


def test_root_package_canonical_exports() -> None:
    """Verify root personal_finance_etl re-exports canonical Clean Architecture facades."""
    import personal_finance_etl

    assert hasattr(personal_finance_etl, "PersonalFinanceEngine")
    assert hasattr(personal_finance_etl, "DesktopApp")
    assert hasattr(personal_finance_etl, "main_cli")
    assert hasattr(personal_finance_etl, "run_app")
    assert hasattr(personal_finance_etl, "__version__")
    assert hasattr(personal_finance_etl, "__author__")

    from personal_finance_etl.application.facade import PersonalFinanceEngine
    from personal_finance_etl.presentation.cli.app import main_cli
    from personal_finance_etl.presentation.desktop.app import DesktopApp
    from personal_finance_etl.presentation.launcher import main as run_app

    assert personal_finance_etl.PersonalFinanceEngine is PersonalFinanceEngine
    assert personal_finance_etl.DesktopApp is DesktopApp
    assert personal_finance_etl.main_cli is main_cli
    assert personal_finance_etl.run_app is run_app


def test_transformation_dag_canonical_exports() -> None:
    """Verify TransformationDAG is importable from application.pipeline."""
    from personal_finance_etl.application.pipeline import TransformationDAG
    from personal_finance_etl.application.pipeline.transformer import (
        TransformationDAG as CanonicalDAG,
    )

    assert TransformationDAG is CanonicalDAG


def test_pyproject_entry_points_validity() -> None:
    """Verify console script entry points in pyproject.toml resolve to callable functions."""
    launcher_mod = importlib.import_module("personal_finance_etl.presentation.launcher")
    assert hasattr(launcher_mod, "main")
    assert callable(launcher_mod.main)

    desktop_mod = importlib.import_module("personal_finance_etl.presentation.desktop.app")
    assert hasattr(desktop_mod, "main")
    assert callable(desktop_mod.main)


def _check_no_legacy_imports_in_tree(
    tree_root: Path, exclude_file: Path | None = None
) -> list[str]:
    """Inspect AST of all python files in tree and flag any legacy import strings."""
    violations: list[str] = []
    for py_file in tree_root.rglob("*.py"):
        if exclude_file and py_file.resolve() == exclude_file.resolve():
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(
                        "personal_finance_etl.backend"
                    ) or alias.name.startswith("personal_finance_etl.frontend"):
                        violations.append(f"{py_file}:{node.lineno} imports '{alias.name}'")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("personal_finance_etl.backend") or node.module.startswith(
                    "personal_finance_etl.frontend"
                ):
                    violations.append(f"{py_file}:{node.lineno} imports from '{node.module}'")
    return violations


def test_zero_legacy_imports_in_src() -> None:
    """Assert zero imports from personal_finance_etl.backend or personal_finance_etl.frontend in src/."""
    violations = _check_no_legacy_imports_in_tree(SRC_ROOT)
    assert not violations, "Found prohibited legacy imports in src/:\n" + "\n".join(violations)


def test_zero_legacy_imports_in_tests() -> None:
    """Assert zero imports from personal_finance_etl.backend or personal_finance_etl.frontend in tests/."""
    this_file = Path(__file__).resolve()
    violations = _check_no_legacy_imports_in_tree(TESTS_ROOT, exclude_file=this_file)
    assert not violations, "Found prohibited legacy imports in tests/:\n" + "\n".join(violations)
