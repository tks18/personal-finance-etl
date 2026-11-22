#!/usr/bin/env python3
# pylint: skip-file
# flake8: noqa
"""Installer for Git pre-commit and pre-push quality hooks.

Repository: personal-finance-etl
Two-Tier Quality Architecture:
- pre-commit: Fast Tier (< 2s) - Ruff Lint, Ruff Format, Mypy Strict
- pre-push:   Full Tier (~40-70s) - Ruff, Format, Mypy, Pyright, Pylint, Pytest
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TRACKED_HOOKS_DIR = ROOT_DIR / ".githooks"
GIT_DIR = ROOT_DIR / ".git"
GIT_HOOKS_DIR = GIT_DIR / "hooks"

PRE_COMMIT_SCRIPT = """#!/usr/bin/env sh
# Personal Finance ETL - Pre-Commit Quality Gate (Fast Tier)
# Runs Ruff Check, Ruff Format Check, and Mypy Typecheck (< 2s).
echo "[Quality Gate] Running Pre-Commit Fast Verification (Ruff + Mypy)..."

uv run poe audit-fast
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[Quality Gate] [FAIL] Pre-commit checks failed."
    echo "[Quality Gate] Fix issues or run 'uv run poe audit-fast:fix' to auto-fix formatting."
    exit $EXIT_CODE
fi

echo "[Quality Gate] [PASS] Pre-commit checks passed cleanly."
exit 0
"""

PRE_PUSH_SCRIPT = """#!/usr/bin/env sh
# Personal Finance ETL - Pre-Push Quality Gate (Full Tier)
# Runs Ruff, Format, Mypy, Pyright, Pylint, and Pytest (~40-70s).
echo "[Quality Gate] Running Pre-Push Full Verification Suite..."

uv run poe audit-full
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[Quality Gate] [FAIL] Pre-push verification failed."
    echo "[Quality Gate] Push aborted. Ensure all 6 engines pass before pushing."
    exit $EXIT_CODE
fi

echo "[Quality Gate] [PASS] Full verification suite passed cleanly. Proceeding with push."
exit 0
"""


def _make_executable(target: Path) -> None:
    """Set executable bits on POSIX file systems."""
    try:
        current_mode = os.stat(target).st_mode
        os.chmod(target, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def install_hooks() -> int:
    """Install git pre-commit and pre-push hooks both in .githooks and .git/hooks.

    Configures Git's core.hooksPath to point to the tracked .githooks directory,
    ensuring that hooks persist across clones and commits in version control.
    """
    TRACKED_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Write tracked repo hooks
    tracked_pre_commit = TRACKED_HOOKS_DIR / "pre-commit"
    tracked_pre_push = TRACKED_HOOKS_DIR / "pre-push"

    tracked_pre_commit.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8", newline="\n")
    _make_executable(tracked_pre_commit)
    print(f"[OK] Tracked Git pre-commit hook -> {tracked_pre_commit}")

    tracked_pre_push.write_text(PRE_PUSH_SCRIPT, encoding="utf-8", newline="\n")
    _make_executable(tracked_pre_push)
    print(f"[OK] Tracked Git pre-push hook   -> {tracked_pre_push}")

    # 2. Point git core.hooksPath to .githooks
    if GIT_DIR.exists():
        proc = subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            print("[OK] Configured git core.hooksPath = .githooks")
        else:
            print(f"[WARN] Failed to configure git core.hooksPath: {proc.stderr}")

        # 3. Fallback write directly to .git/hooks if exists
        if GIT_HOOKS_DIR.exists():
            git_pre_commit = GIT_HOOKS_DIR / "pre-commit"
            git_pre_push = GIT_HOOKS_DIR / "pre-push"
            git_pre_commit.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8", newline="\n")
            _make_executable(git_pre_commit)
            git_pre_push.write_text(PRE_PUSH_SCRIPT, encoding="utf-8", newline="\n")
            _make_executable(git_pre_push)
            print("[OK] Fallback hooks copied to .git/hooks/")

    return 0


if __name__ == "__main__":
    sys.exit(install_hooks())
