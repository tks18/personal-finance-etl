import subprocess
import sys

from scripts.create_pr import main as create_pr_main
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
    """Run full tier quality gate audit (Ruff, Mypy, Pyright, Pylint, Pytest) and export reports."""
    from scripts.quality_gate import run_quality_gate

    sys.exit(run_quality_gate(tier="full", export="all"))


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


def commit_interactive():
    """Run interactive file-by-file conventional commit wizard."""
    from scripts.auto_commit import main as auto_commit_main

    passed_args = sys.argv[1:]
    if "-i" not in passed_args and "--interactive" not in passed_args:
        passed_args.insert(0, "--interactive")
    sys.argv = [sys.argv[0]] + passed_args
    sys.exit(auto_commit_main())


def commit_overrides():
    """Execute automated conventional commits using .commit_overrides.json directly."""
    from scripts.auto_commit import main as auto_commit_main

    passed_args = sys.argv[1:]
    sys.argv = [sys.argv[0], "--map", ".commit_overrides.json", "--run"] + passed_args
    sys.exit(auto_commit_main())


def commit_overrides_preview():
    """Preview automated conventional commits using .commit_overrides.json without committing."""
    from scripts.auto_commit import main as auto_commit_main

    passed_args = sys.argv[1:]
    sys.argv = [sys.argv[0], "--map", ".commit_overrides.json", "--dry-run"] + passed_args
    sys.exit(auto_commit_main())


def commit_overrides_only():
    """Execute commits ONLY for files explicitly listed in .commit_overrides.json."""
    from scripts.auto_commit import main as auto_commit_main

    passed_args = sys.argv[1:]
    sys.argv = [sys.argv[0], "--map", ".commit_overrides.json", "--only-mapped", "--run"] + passed_args
    sys.exit(auto_commit_main())


def pr_preview():
    """Preview GitHub Pull Request title, changelog body, and quality gate audit table."""
    passed_args = sys.argv[1:]
    if "--preview" not in passed_args and "--dry-run" not in passed_args:
        passed_args.insert(0, "--preview")
    sys.exit(create_pr_main(passed_args))


def pr_create():
    """Create or update GitHub Pull Request from dev into master with quality gate audit."""
    passed_args = sys.argv[1:]
    if "--run" not in passed_args:
        passed_args.insert(0, "--run")
    sys.exit(create_pr_main(passed_args))


def release_pipeline():
    """Execute end-to-end post-tag release pipeline: git push -> create PR -> draft release."""
    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]═════ Starting Automated Post-Release Pipeline ═════[/bold cyan]\n")

    # Step 1: Git Push with follow-tags (triggers pre-push hook running audit-full and saving audit_report.json)
    console.print("[bold yellow]Step 1: Pushing commits and release tags to origin dev...[/bold yellow]")
    push_proc = subprocess.run(["git", "push", "--follow-tags", "origin", "dev"], check=False)
    if push_proc.returncode != 0:
        console.print("[bold red]Pipeline aborted: git push failed.[/bold red]")
        sys.exit(push_proc.returncode)

    # Step 2: Create/update PR from dev into master with Quality Gate certification attached
    console.print("\n[bold yellow]Step 2: Creating/updating Pull Request into master with Quality Gate certification...[/bold yellow]")
    pr_code = create_pr_main(["--run", "--head", "dev", "--base", "master"])
    if pr_code != 0:
        console.print("[bold red]Pipeline warning: PR creation had errors.[/bold red]")

    # Step 3: Create GitHub Draft Release for latest version
    console.print("\n[bold yellow]Step 3: Creating GitHub Draft Release for latest version...[/bold yellow]")
    from scripts.create_releases import run_release_cli

    rel_code = run_release_cli(["--latest", "--run", "--draft"])
    if rel_code != 0:
        console.print("[bold red]Pipeline warning: Draft release creation had errors.[/bold red]")

    console.print("\n[bold green]═════ Automated Post-Release Pipeline Completed ═════[/bold green]\n")
    sys.exit(0)



