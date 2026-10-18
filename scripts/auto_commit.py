"""Automated Git Commit Tool adhering to Commitlint and Conventional Commits.

Owns
----
- Automatic generation of Conventional Commit messages within 72-80 character limit.
- Individual file staging and granular committing for refactoring workflows.
- Dry-run preview of commit headers and scopes.
- Reusable across all refactoring phases (Phase 0 through Phase 8).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        reconfig_err(encoding="utf-8", errors="replace")

# Optional explicit overrides for ad-hoc or special files
CUSTOM_COMMIT_MESSAGES: dict[str, str] = {
    "scripts/auto_commit.py": "chore(scripts): prune legacy commit dictionaries",
}


def _format_header(type_scope: str, desc: str) -> str:
    """Format and guarantee commit header is within 72 characters."""
    prefix = f"{type_scope}: "
    max_desc_len = 72 - len(prefix)
    if len(desc) > max_desc_len:
        desc = desc[:max_desc_len].rstrip()
    return f"{prefix}{desc}"


def _infer_commit_message(filepath: str, status: str) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = filepath.replace("\\", "/")
    if norm in CUSTOM_COMMIT_MESSAGES:
        return CUSTOM_COMMIT_MESSAGES[norm]

    # Package __init__.py declaration
    if norm.endswith("__init__.py"):
        pkg_parts = norm.split("/")
        pkg_name = pkg_parts[-2] if len(pkg_parts) >= 2 else "root"
        return _format_header(f"refactor({pkg_name[:15]})", "update package exports")

    # Tests
    if norm.startswith("tests/"):
        stem = Path(norm).stem.replace("test_", "")
        return _format_header(f"test({stem[:15]})", "update test suite")

    # Scripts
    if norm.startswith("scripts/"):
        stem = Path(norm).stem
        return _format_header(f"chore({stem[:15]})", "update development script")

    # CI & Tooling configurations
    if norm.startswith(".github/"):
        return _format_header("ci(github)", "update workflow configuration")
    if norm.startswith(".githooks/"):
        stem = Path(norm).stem
        return _format_header(f"ci({stem[:12]})", "update git hook")
    if norm in {
        "ruff.toml",
        "mypy.ini",
        "pyrightconfig.json",
        "pyrefly.toml",
        "uv.toml",
        ".pylintrc",
        ".flake8",
        ".codacy.yml",
        ".coderabbit.yaml",
        "poe_tasks.toml",
    }:
        tool_name = Path(norm).stem.lstrip(".").split(".")[0]
        return _format_header(f"ci({tool_name})", "update tool configuration")
    if norm in {"pyproject.toml", "package.json", "uv.lock"}:
        tool_name = Path(norm).stem
        return _format_header(f"chore({tool_name})", "update project configuration")

    # Source code packages
    if norm.startswith("src/personal_finance_etl/"):
        rel = norm.replace("src/personal_finance_etl/", "")
        parts = rel.split("/")
        layer = parts[0]
        stem = Path(norm).stem
        action = "add" if "?" in status or "A" in status else "update"
        return _format_header(f"refactor({layer})", f"{action} {stem}")

    # Documentation & Planning
    if norm.startswith(".planning/"):
        return _format_header("docs(planning)", "update refactoring plan and progress")
    if norm.endswith(".md"):
        stem = Path(norm).stem
        return _format_header(f"docs({stem[:15]})", "update documentation")

    # Generic fallback
    stem = Path(norm).stem
    action = "add" if "?" in status or "A" in status else "update"
    return _format_header("chore", f"{action} {stem}")


def get_changed_files() -> list[tuple[str, str]]:
    """Return list of (status, filepath) for all uncommitted files."""
    proc = subprocess.run(
        ["git", "status", "-s", "-uall"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    results: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        status_part = line[:2].strip()
        file_part = line[2:].strip().strip('"')
        results.append((status_part, file_part))
    return results


def run_git_commit(filepath: str, message: str, dry_run: bool = False) -> bool:
    """Stage a single file and create a git commit."""
    # Commitlint enforcement: header must be <= 72 characters, lowercase
    if len(message) > 72:
        print(f"ERROR: Commit message exceeds 72 characters ({len(message)} chars): '{message}'")
        return False

    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath

    if dry_run:
        print(f"[DRY-RUN] git add {norm_path}")
        print(f'[DRY-RUN] git commit -m "{message}" (len: {len(message)})')
        return True

    # 1. git add
    add_proc = subprocess.run(
        ["git", "add", norm_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if add_proc.returncode != 0:
        print(f"FAILED git add {norm_path}: {add_proc.stderr}")
        return False

    # 2. git commit
    commit_proc = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if commit_proc.returncode != 0:
        print(f"FAILED git commit for {norm_path}: {commit_proc.stderr}")
        return False

    print(f'[OK] Committed {norm_path}: "{message}"')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit changes file-by-file following Commitlint standards."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview commits without executing git commands."
    )
    parser.add_argument("--run", action="store_true", help="Execute the commits immediately.")
    parser.add_argument("--file", type=str, help="Commit only a single specific file.")
    args = parser.parse_args()

    # Default to dry-run if neither --run nor --dry-run is passed
    is_dry_run = not args.run

    if args.file:
        files = [("M", args.file)]
    else:
        files = get_changed_files()

    if not files:
        print("Working tree is completely clean. Nothing to commit.")
        return 0

    mode_label = "DRY-RUN PREVIEW" if is_dry_run else "EXECUTING COMMITS"
    print(f"\n--- {mode_label} ({len(files)} files found) ---\n")

    success_count = 0
    fail_count = 0

    for status, filepath in files:
        message = _infer_commit_message(filepath, status)
        ok = run_git_commit(filepath, message, dry_run=is_dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\nDone: {success_count} succeeded, {fail_count} failed.")
    if is_dry_run:
        print("To execute these commits, run: uv run python scripts/auto_commit.py --run")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
