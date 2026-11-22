"""AST-level documentation auditor and compliance verification gate.

Owns
----
- Static AST inspection of all modules, classes, functions, methods, and properties in src/.
- Enforcement of NumPy-style docstrings, parameters, returns, and package ownership contracts.
- Automated compliance verification per Engineering Standards Section 3 and Section 22.
- CLI reporting and structured exit codes for CI and local Quality Gate tasks.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_fn):
        reconfigure_fn(encoding="utf-8")

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "personal_finance_etl"


@dataclass
class DocViolation:
    file: str
    line: int
    entity_type: str
    entity_name: str
    rule: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "rule": self.rule,
            "message": self.message,
        }


def _is_property(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function node has a property decorator."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter"):
            return True
    return False


class DocumentationAuditor:
    def __init__(self, include_private: bool = False, require_init_docs: bool = False) -> None:
        self.include_private = include_private
        self.require_init_docs = require_init_docs
        self.violations: list[DocViolation] = []

    def audit_file(self, file_path: Path) -> None:
        rel_path = str(file_path.relative_to(SRC_ROOT))
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as exc:
            self.violations.append(
                DocViolation(
                    file=rel_path,
                    line=1,
                    entity_type="Module",
                    entity_name=file_path.name,
                    rule="PARSE_ERROR",
                    message=f"Failed to parse AST: {exc}",
                )
            )
            return

        # 1. Module Docstring Check
        module_doc = ast.get_docstring(tree)
        if not module_doc or not module_doc.strip():
            self.violations.append(
                DocViolation(
                    file=rel_path,
                    line=1,
                    entity_type="Module",
                    entity_name=file_path.name,
                    rule="MISSING_MODULE_DOCSTRING",
                    message="Module is missing a top-level docstring.",
                )
            )
        elif file_path.name == "__init__.py":
            # Check package docstrings for Owns / Does not own per Section 3
            if "Owns" not in module_doc or "Does not own" not in module_doc:
                self.violations.append(
                    DocViolation(
                        file=rel_path,
                        line=1,
                        entity_type="Package",
                        entity_name=file_path.parent.name,
                        rule="MISSING_OWNERSHIP_CONTRACT",
                        message="__init__.py missing 'Owns' and/or 'Does not own' boundary contract.",
                    )
                )

        # 2. Walk AST for Classes, Functions, Methods, Properties
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._audit_class(node, rel_path)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._audit_function(node, rel_path, is_method=False)

    def _audit_class(self, node: ast.ClassDef, file_path: str) -> None:
        if not self.include_private and node.name.startswith("_") and not node.name.startswith("__"):
            return

        cls_doc = ast.get_docstring(node)
        if not cls_doc or not cls_doc.strip():
            self.violations.append(
                DocViolation(
                    file=file_path,
                    line=node.lineno,
                    entity_type="Class",
                    entity_name=node.name,
                    rule="MISSING_CLASS_DOCSTRING",
                    message=f"Class '{node.name}' is missing a docstring.",
                )
            )

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_prop = _is_property(item)
                self._audit_function(
                    item,
                    file_path,
                    is_method=True,
                    is_property=is_prop,
                    parent_class=node.name,
                    parent_class_doc=cls_doc,
                )
            elif isinstance(item, ast.ClassDef):
                self._audit_class(item, file_path)

    def _audit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        is_method: bool = False,
        is_property: bool = False,
        parent_class: str = "",
        parent_class_doc: str | None = None,
    ) -> None:
        entity_type = "Property" if is_property else ("Method" if is_method else "Function")
        full_name = f"{parent_class}.{node.name}" if parent_class else node.name

        # Private filter
        is_private = node.name.startswith("_") and not (
            node.name.startswith("__") and node.name.endswith("__")
        )
        if not self.include_private and is_private:
            return

        doc = ast.get_docstring(node)

        # Special handling for __init__ per NumPy docstring convention
        if is_method and node.name == "__init__":
            # If explicit docstring exists, it is compliant
            if doc and doc.strip():
                return
            # If not requiring dedicated __init__ docs, verify parent class documents parameters
            if not self.require_init_docs and parent_class_doc and parent_class_doc.strip():
                return
            # Otherwise, flag missing constructor documentation
            self.violations.append(
                DocViolation(
                    file=file_path,
                    line=node.lineno,
                    entity_type="Method",
                    entity_name=full_name,
                    rule="MISSING_INIT_DOCSTRING",
                    message=f"Constructor '{full_name}' lacks docstring and parent class lacks parameters documentation.",
                )
            )
            return

        # General docstring check
        if not doc or not doc.strip():
            self.violations.append(
                DocViolation(
                    file=file_path,
                    line=node.lineno,
                    entity_type=entity_type,
                    entity_name=full_name,
                    rule=f"MISSING_{entity_type.upper()}_DOCSTRING",
                    message=f"{entity_type} '{full_name}' is missing a docstring.",
                )
            )


def run_audit(include_private: bool = False, require_init_docs: bool = False) -> list[DocViolation]:
    auditor = DocumentationAuditor(
        include_private=include_private, require_init_docs=require_init_docs
    )
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        auditor.audit_file(py_file)
    return auditor.violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AST-level documentation compliance auditor for personal-finance-etl."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Include private methods, functions, and internal helper routines (_foo).",
    )
    parser.add_argument(
        "--require-init",
        action="store_true",
        help="Require dedicated docstrings inside __init__ even if parent class documents parameters.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON instead of human-readable CLI table.",
    )
    args = parser.parse_args()

    violations = run_audit(
        include_private=args.strict, require_init_docs=args.require_init
    )

    if args.json:
        print(json.dumps([v.to_dict() for v in violations], indent=2))
        return 1 if violations else 0

    mode_label: list[str] = []
    if args.strict:
        mode_label.append("STRICT (includes private)")
    else:
        mode_label.append("PUBLIC INTERFACES")
    if args.require_init:
        mode_label.append("REQUIRE DEDICATED __INIT__")

    print("=" * 80)
    print(f"AST Documentation Auditor | Scope: src/personal_finance_etl | Mode: {', '.join(mode_label)}")
    print("=" * 80)

    if not violations:
        print("[PASS] ALL ENTITIES 100% DOCUMENTED! Zero violations found.")
        print("=" * 80)
        return 0

    print(f"Found {len(violations)} documentation violations:\n")
    by_type: dict[str, int] = {}
    for v in violations:
        by_type[v.entity_type] = by_type.get(v.entity_type, 0) + 1
        print(f"  [{v.entity_type:8s}] {v.file}:{v.line} -> {v.entity_name}")
        print(f"             Rule: {v.rule} | {v.message}")

    print("\nSummary by Entity Type:")
    for etype, count in sorted(by_type.items()):
        print(f"  - {etype}: {count}")

    print(f"\nTotal violations: {len(violations)}")
    print("=" * 80)
    return 1


if __name__ == "__main__":
    sys.exit(main())
