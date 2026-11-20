#!/usr/bin/env python3
# pylint: skip-file
# flake8: noqa
"""Dynamic Release Orchestrator supporting arbitrary semantic versions and pre-release tracks.

Owns
----
- Dynamic version calculation (major, minor, patch, rc, alpha, beta).
- Interactive and CLI-driven invocations of standard-version without hardcoded versions.
- Safe execution of standard-version cross-platform on Windows and Linux.
- Optional seamless handover to the post-tag release pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        reconfig_err(encoding="utf-8", errors="replace")


def get_project_root() -> Path:
    """Find repository root by inspecting parents for pyproject.toml or package.json."""
    current = Path(__file__).resolve().parent
    for p in [current, *current.parents]:
        if (p / "pyproject.toml").exists() or (p / "package.json").exists():
            return p
    return current.parent


def get_current_version(repo_dir: Path) -> str:
    """Read current version from package.json."""
    pkg_file = repo_dir / "package.json"
    if not pkg_file.exists():
        return "0.0.0"
    try:
        data: dict[str, Any] = json.loads(pkg_file.read_text(encoding="utf-8"))
        version_val = data.get("version", "0.0.0")
        return str(version_val)
    except Exception:
        return "0.0.0"


def calculate_next_versions(current: str) -> dict[str, str]:
    """Calculate prospective next version targets for display in UI/CLI."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z]+)\.(\d+))?", current)
    if not match:
        return {}

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    pre_tag = match.group(4)
    pre_num = int(match.group(5)) if match.group(5) is not None else None

    results: dict[str, str] = {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
        "major_rc": f"{major + 1}.0.0-rc.1",
        "minor_rc": f"{major}.{minor + 1}.0-rc.1",
        "patch_rc": f"{major}.{minor}.{patch + 1}-rc.1",
        "major_alpha": f"{major + 1}.0.0-alpha.1",
        "minor_alpha": f"{major}.{minor + 1}.0-alpha.1",
        "patch_alpha": f"{major}.{minor}.{patch + 1}-alpha.1",
        "major_beta": f"{major + 1}.0.0-beta.1",
        "minor_beta": f"{major}.{minor + 1}.0-beta.1",
        "patch_beta": f"{major}.{minor}.{patch + 1}-beta.1",
    }

    if pre_tag and pre_num is not None:
        results["current_pre_inc"] = f"{major}.{minor}.{patch}-{pre_tag}.{pre_num + 1}"
        results["promote_stable"] = f"{major}.{minor}.{patch}"

    return results


def run_standard_version(
    repo_dir: Path,
    release_as: str | None = None,
    prerelease: str | None = None,
    dry_run: bool = False,
) -> int:
    """Execute standard-version with specified parameters."""
    cmd = ["standard-version", "--commit-all"]

    if release_as:
        cmd.extend(["--release-as", release_as])

    if prerelease:
        cmd.extend(["--prerelease", prerelease])

    if dry_run:
        cmd.append("--dry-run")

    console.print(f"[dim]Running command: {' '.join(cmd)}[/dim]\n")
    proc = subprocess.run(cmd, cwd=repo_dir, shell=True, check=False)
    return proc.returncode


def interactive_wizard(repo_dir: Path) -> tuple[str | None, str | None, bool, bool]:
    """Interactive wizard allowing developer to select any version release strategy."""
    current_ver = get_current_version(repo_dir)
    projections = calculate_next_versions(current_ver)

    console.print(
        Panel(
            f"[bold cyan]Current Repository Version:[/bold cyan] [bold green]{current_ver}[/bold green]\n"
            f"[dim]Select a release track or specify an explicit version.[/dim]",
            title="[bold yellow]Personal Finance ETL — Dynamic Release Wizard[/bold yellow]",
            border_style="yellow",
        )
    )

    options: list[tuple[str, str | None, str | None]] = []

    # If currently in a pre-release
    if "current_pre_inc" in projections:
        options.append((f"Increment Pre-Release -> {projections['current_pre_inc']}", None, "rc"))
        options.append(
            (
                f"Promote Pre-Release to Final Stable -> {projections['promote_stable']}",
                "patch",
                None,
            )
        )

    options.extend(
        [
            (
                f"Next Major Release Candidate (RC) -> {projections.get('major_rc', 'Next Major RC')}",
                "major",
                "rc",
            ),
            (
                f"Next Minor Release Candidate (RC) -> {projections.get('minor_rc', 'Next Minor RC')}",
                "minor",
                "rc",
            ),
            (
                f"Next Patch Release Candidate (RC) -> {projections.get('patch_rc', 'Next Patch RC')}",
                "patch",
                "rc",
            ),
            (
                f"Next Major Alpha -> {projections.get('major', 'Next Major')}-alpha.0",
                "major",
                "alpha",
            ),
            (
                f"Next Major Beta  -> {projections.get('major', 'Next Major')}-beta.0",
                "major",
                "beta",
            ),
            (f"Production Major -> {projections.get('major', 'Next Major')}", "major", None),
            (f"Production Minor -> {projections.get('minor', 'Next Minor')}", "minor", None),
            (f"Production Patch -> {projections.get('patch', 'Next Patch')}", "patch", None),
            ("Custom / Explicit Version (enter manually)", "CUSTOM", None),
        ]
    )

    for idx, (label, _, _) in enumerate(options, 1):
        console.print(f"  [bold cyan]{idx}[/bold cyan]) {label}")

    choice_str = Prompt.ask(
        "\nChoose an option", choices=[str(i) for i in range(1, len(options) + 1)], default="1"
    )
    selected_idx = int(choice_str) - 1
    _, chosen_release_as, chosen_prerelease = options[selected_idx]

    if chosen_release_as == "CUSTOM":
        custom_ver = Prompt.ask("Enter custom version (e.g. 10.0.0-rc.1, 10.1.0, 11.0.0-beta.2)")
        chosen_release_as = custom_ver.strip()
        chosen_prerelease = None
    elif chosen_release_as in ("major", "minor", "patch") and chosen_prerelease:
        key = f"{chosen_release_as}_{chosen_prerelease}"
        if key in projections:
            chosen_release_as = projections[key]
            chosen_prerelease = None

    run_pipeline = Confirm.ask(
        "Execute automated post-release pipeline (push -> PR -> draft release)?", default=True
    )
    is_dry_run = Confirm.ask("Run in dry-run preview mode first?", default=False)

    return chosen_release_as, chosen_prerelease, run_pipeline, is_dry_run


def main(cli_args: list[str] | None = None) -> int:
    """CLI Entrypoint for dynamic release bump."""
    parser = argparse.ArgumentParser(
        prog="poe release:bump",
        description="Dynamic semantic version and pre-release manager.",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Target next major version.",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help="Target next minor version.",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Target next patch version.",
    )
    parser.add_argument(
        "--rc",
        action="store_true",
        help="Create/bump Release Candidate (rc).",
    )
    parser.add_argument(
        "--alpha",
        action="store_true",
        help="Create/bump Alpha pre-release.",
    )
    parser.add_argument(
        "--beta",
        action="store_true",
        help="Create/bump Beta pre-release.",
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="Promote pre-release to final production release.",
    )
    parser.add_argument(
        "--pre",
        type=str,
        default=None,
        metavar="TAG",
        help="Arbitrary pre-release tag name (e.g., --pre preview).",
    )
    parser.add_argument(
        "--as",
        dest="as_version",
        type=str,
        default=None,
        metavar="VERSION",
        help="Explicit version to release as (e.g., --as 10.0.0-rc.1).",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Launch interactive release selection wizard.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview standard-version bump without writing files or creating tags.",
    )
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Execute post-tag release pipeline (push -> PR -> draft release) upon success.",
    )

    args = parser.parse_args(cli_args)
    root_dir = get_project_root()

    # If no flags passed, or --interactive requested, launch interactive wizard
    has_flags = any(
        [
            args.major,
            args.minor,
            args.patch,
            args.rc,
            args.alpha,
            args.beta,
            args.final,
            args.pre,
            args.as_version,
        ]
    )
    if not has_flags or args.interactive:
        release_as, prerelease, run_pipeline, dry_run = interactive_wizard(root_dir)
    else:
        current_ver = get_current_version(root_dir)
        projections = calculate_next_versions(current_ver)

        release_as = args.as_version
        if args.final:
            release_as = projections.get("promote_stable", "major")
            prerelease = None
        elif not release_as:
            if args.major:
                release_as = "major"
            elif args.minor:
                release_as = "minor"
            elif args.patch:
                release_as = "patch"

        prerelease = args.pre
        if not args.final and not prerelease:
            if args.rc:
                prerelease = "rc"
            elif args.alpha:
                prerelease = "alpha"
            elif args.beta:
                prerelease = "beta"

        run_pipeline = args.pipeline
        dry_run = args.dry_run

        # If transitioning from stable to a new pre-release track, start index at 1 (rc.1 / alpha.1 / beta.1)
        if release_as in ("major", "minor", "patch") and prerelease:
            key = f"{release_as}_{prerelease}"
            if key in projections:
                release_as = projections[key]
                prerelease = None

    ret = run_standard_version(
        repo_dir=root_dir,
        release_as=release_as,
        prerelease=prerelease,
        dry_run=dry_run,
    )

    if ret != 0:
        console.print("[bold red]✘ standard-version encountered an error.[/bold red]")
        return ret

    if dry_run:
        console.print(
            "[yellow]Dry-run complete. Re-run without --dry-run to commit and tag.[/yellow]"
        )
        return 0

    if run_pipeline:
        console.print("\n[bold cyan]Handing off to automated post-release pipeline...[/bold cyan]")
        pipe_proc = subprocess.run(
            ["uv", "run", "poe", "release:pipeline"], cwd=root_dir, check=False
        )
        return pipe_proc.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
