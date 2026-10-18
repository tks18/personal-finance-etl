import subprocess
import sys

from scripts.create_releases import run_release_cli


def dev():
    """Run the app with hot-reloading."""
    print("Starting development server...")
    sys.exit(subprocess.call(["tkreload", "main.py"]))


def build():
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    sys.exit(subprocess.call(["pyinstaller", "--clean", "-y", "main.spec"]))

def release_preview():
    """Preview release notes for the latest version in CHANGELOG.md."""
    sys.exit(run_release_cli(["--preview"]))


def release_preview_all():
    """Preview full release notes for all versions in CHANGELOG.md."""
    sys.exit(run_release_cli(["--preview-all"]))


def release_dry_run():
    """List matching Git tags and changelog entries in dry-run mode."""
    sys.exit(run_release_cli([]))


def release_latest():
    """Publish the latest changelog version as a GitHub release."""
    sys.exit(run_release_cli(["--latest", "--run"]))


def release_latest_draft():
    """Publish the latest changelog version as a draft on GitHub."""
    sys.exit(run_release_cli(["--latest", "--run", "--draft"]))


def release_all():
    """Publish all unreleased historical tags interactively to GitHub."""
    sys.exit(run_release_cli(["--run", "--interactive"]))


def release_all_draft():
    """Publish all unreleased historical tags as drafts to GitHub."""
    sys.exit(run_release_cli(["--run", "--draft"]))


def audit():
    """Run quality gate audit (defaults to full tier, passing any CLI flags through)."""
    from scripts.quality_gate import main as quality_gate_main

    sys.exit(quality_gate_main())


def audit_fast():
    """Run fast tier quality gate audit (Ruff + Mypy, < 3s)."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="fast", export="cli"))


def audit_fast_fix():
    """Run fast tier quality gate audit with auto-fix enabled."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="fast", export="cli", auto_fix=True))


def audit_full():
    """Run full tier quality gate audit (Ruff, Mypy, Pyright, Pylint, Pytest)."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="full", export="cli"))


def audit_csv():
    """Run full tier quality gate audit and export structured CSV report."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="full", export="csv"))


def audit_json():
    """Run full tier quality gate audit and export structured JSON report."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="full", export="json"))


def install_hooks():
    """Install and configure Git pre-commit and pre-push hooks."""
    from scripts.install_hooks import install_hooks as run_install_hooks

    sys.exit(run_install_hooks())


def commit():
    """Run automated conventional commit tool, forwarding any CLI flags."""
    from scripts.auto_commit import main as auto_commit_main

    sys.exit(auto_commit_main())


def commit_preview():
    """Preview automated conventional commits without executing git commands."""
    from scripts.auto_commit import main as auto_commit_main

    sys.argv = [sys.argv[0], "--dry-run"]
    sys.exit(auto_commit_main())


def commit_run():
    """Execute automated conventional commits file-by-file."""
    from scripts.auto_commit import main as auto_commit_main

    sys.argv = [sys.argv[0], "--run"]
    sys.exit(auto_commit_main())



