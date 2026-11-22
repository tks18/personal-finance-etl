# pylint: skip-file
# flake8: noqa
"""Automated Git Commit Tool adhering to Commitlint and Conventional Commits.

Owns
----
- Grouped atomic commits based on semantic Message-to-Paths mappings (.commit_overrides.json).
- Automatic generation of Conventional Commit messages within 72 character limit.
- Upfront Quality Gate execution (Fast Tier: Ruff + Mypy) with atomic --no-verify bypass.
- Atomic handling of file renames, deletions, additions, and modifications.
- Interactive group/file Commitlint wizard (--interactive / -i).
- Rich terminal presentation with failure diagnostics (capturing stdout + stderr).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import sys
from typing import cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

console = Console()

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        reconfig_err(encoding="utf-8", errors="replace")

COMMIT_TYPES: list[tuple[str, str]] = [
    ("feat", "A new feature or capability"),
    ("fix", "A bug fix"),
    ("refactor", "Code change that neither fixes a bug nor adds a feature"),
    ("docs", "Documentation or docstrings only"),
    ("test", "Adding missing tests or correcting existing tests"),
    ("ci", "Changes to CI configs, git hooks, scripts, linters"),
    ("chore", "Miscellaneous tasks, config updates, dependencies"),
    ("style", "Changes that do not affect code meaning (formatting)"),
    ("perf", "A code change that improves performance"),
]


@dataclass
class ChangedFile:
    """Represents an uncommitted file change in the repository."""

    status: str
    filepath: str
    orig_path: str | None = None

    @property
    def display_path(self) -> str:
        """Formatted path for user presentation and logs."""
        if self.orig_path:
            return f"{self.orig_path} -> {self.filepath}"
        return self.filepath


@dataclass
class CommitGroup:
    """Represents a cohesive group of files committed atomically together."""

    message: str
    files: list[ChangedFile] = field(default_factory=lambda: cast(list[ChangedFile], []))

    @property
    def display_summary(self) -> str:
        """Formatted summary of files in this commit group."""
        if not self.files:
            return "(no files)"
        if len(self.files) == 1:
            return self.files[0].display_path
        paths = [f.filepath.replace("\\", "/") for f in self.files]
        sample = ", ".join(Path(p).name for p in paths[:3])
        suffix = f", ... (+{len(paths) - 3} more)" if len(paths) > 3 else ""
        return f"{len(self.files)} files ({sample}{suffix})"


def load_custom_overrides(cli_map_path: str | None = None) -> dict[str, list[str]]:
    """Load Message-to-Paths commit override mappings from external JSON file.

    Parameters
    ----------
    cli_map_path : str | None, optional
        Explicit CLI path to the mapping file, by default None.

    Returns
    -------
    dict[str, list[str]]
        Dictionary mapping commit messages to lists of normalized filepaths.
    """
    candidates: list[Path] = []
    if cli_map_path:
        candidates.append(Path(cli_map_path))
    candidates.append(Path(".commit_overrides.json"))
    candidates.append(Path(".commit_map.json"))

    for p in candidates:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                raw_data: object = json.loads(content)
                if isinstance(raw_data, dict):
                    raw_dict = cast(dict[object, object], raw_data)
                    result: dict[str, list[str]] = {}
                    for k, v in raw_dict.items():
                        msg_or_path = str(k).strip()
                        if isinstance(v, list):
                            # Canonical Message-to-Paths: {"feat(scope): msg": ["file1", "file2"]}
                            raw_list = cast(list[object], v)
                            norm_files = [str(item).replace("\\", "/").strip() for item in raw_list]
                            result[msg_or_path] = norm_files
                        elif isinstance(v, str):
                            # Backward-compatibility Path-to-Message: {"file1": "feat(scope): msg"}
                            msg = str(v).strip()
                            path = msg_or_path.replace("\\", "/").strip()
                            result.setdefault(msg, []).append(path)
                    return result
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse {p}: {e}[/yellow]")
    return {}


def _format_header(type_scope: str, desc: str) -> str:
    """Format and guarantee commit header is strictly within 72 characters."""
    prefix = f"{type_scope}: "
    max_desc_len = 72 - len(prefix)
    if len(desc) > max_desc_len:
        desc = desc[:max_desc_len].rstrip()
    return f"{prefix}{desc}"


def _infer_scope(filepath: str) -> str:
    """Infer a conventional commit scope based on directory path."""
    norm = filepath.replace("\\", "/")
    if norm.startswith("src/personal_finance_etl/"):
        rel = norm.replace("src/personal_finance_etl/", "")
        parts = rel.split("/")
        if len(parts) >= 2 and parts[0] in {"domain", "application", "infrastructure", "presentation"}:
            return parts[1].rstrip("_")
        return parts[0].rstrip("_")
    if norm.startswith("tests/"):
        stem = Path(norm).stem.replace("test_", "").rstrip("_")
        return stem[:15].rstrip("_")
    if norm.startswith("scripts/"):
        return Path(norm).stem[:15].rstrip("_")
    if norm.startswith(".githooks/"):
        return "hooks"
    if norm.startswith(".github/"):
        return "ci"
    if norm.startswith(".planning/"):
        return "planning"
    if norm.endswith(".md"):
        return Path(norm).stem[:15].rstrip("_")
    return Path(norm).stem[:15].rstrip("_")


def _infer_commit_message(file_item: ChangedFile) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = file_item.filepath.replace("\\", "/")

    # Deletions checked first across all files
    if file_item.status == "D":
        if norm.endswith("__init__.py"):
            pkg_parts = norm.split("/")
            pkg_name = pkg_parts[-2] if len(pkg_parts) >= 2 else "root"
            return _format_header(f"refactor({pkg_name[:15].rstrip('_')})", "remove package facade")
        stem = Path(norm).stem
        scope = _infer_scope(norm)
        return _format_header(f"refactor({scope})", f"remove deprecated {stem}")

    # Renames with directory relocation detection
    if file_item.status == "R" and file_item.orig_path:
        norm_orig = file_item.orig_path.replace("\\", "/")
        stem = Path(norm).stem
        orig_stem = Path(norm_orig).stem
        scope = _infer_scope(norm)
        if orig_stem == stem:
            # File kept same name but moved folders
            dest_parts = norm.split("/")
            dest_layer = dest_parts[2] if len(dest_parts) >= 3 else "infrastructure"
            return _format_header(f"refactor({scope})", f"relocate {stem} to {dest_layer}")
        return _format_header(f"refactor({scope})", f"rename {orig_stem} to {stem}")

    # Package __init__.py declaration
    if norm.endswith("__init__.py"):
        pkg_parts = norm.split("/")
        pkg_name = pkg_parts[-2] if len(pkg_parts) >= 2 else "root"
        return _format_header(f"refactor({pkg_name[:15].rstrip('_')})", "update package exports")

    # Tests
    if norm.startswith("tests/"):
        scope = _infer_scope(norm)
        return _format_header(f"test({scope})", "update test suite")

    # Scripts
    if norm.startswith("scripts/"):
        stem = Path(norm).stem[:15].rstrip("_")
        action = "add" if file_item.status in ("?", "??", "A") else "update"
        return _format_header(f"ci({stem})", f"{action} script")

    # CI & Tooling configurations
    if norm.startswith(".github/"):
        return _format_header("ci(github)", "update workflow configuration")
    if norm.startswith(".githooks/"):
        stem = Path(norm).stem.rstrip("_")
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
        tool_name = Path(norm).stem.lstrip(".").split(".")[0].rstrip("_")
        return _format_header(f"ci({tool_name})", "update tool configuration")
    if norm in {"pyproject.toml", "package.json", "uv.lock"}:
        tool_name = Path(norm).stem.rstrip("_")
        return _format_header(f"chore({tool_name})", "update project configuration")

    # Source code packages
    if norm.startswith("src/personal_finance_etl/"):
        scope = _infer_scope(norm)
        stem = Path(norm).stem
        action = "add" if file_item.status in ("?", "??", "A") else "update"
        return _format_header(f"refactor({scope})", f"{action} {stem}")

    # Documentation & Planning
    if norm.startswith(".planning/"):
        return _format_header("docs(planning)", "update refactoring plan and progress")
    if norm.endswith(".md"):
        stem = Path(norm).stem[:15].rstrip("_")
        return _format_header(f"docs({stem})", "update documentation")

    # Generic fallback
    stem = Path(norm).stem.rstrip("_")
    action = "add" if file_item.status in ("?", "??", "A") else "update"
    return _format_header("chore", f"{action} {stem}")


def get_changed_files() -> list[ChangedFile]:
    """Return list of ChangedFile objects for all uncommitted files.

    Stages working tree changes temporarily to allow git to detect renames,
    extracts the status lines, and immediately unstages them so the index
    remains completely clean for isolated, atomic commits.
    """
    # 1. Temporarily stage everything to trigger git's rename heuristics
    subprocess.run(["git", "add", "-A"], capture_output=True, check=False)

    # 2. Query status with find-renames enabled
    proc = subprocess.run(
        ["git", "status", "-s", "-uall", "--find-renames"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    # 3. Immediately unstage everything so the index is 100% clean
    subprocess.run(["git", "restore", "--staged", "."], capture_output=True, check=False)

    results: list[ChangedFile] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        status_part = line[:2].strip()
        file_part = line[2:].strip().strip('"')

        if " -> " in file_part:
            orig, target = file_part.split(" -> ", 1)
            results.append(
                ChangedFile(
                    status="R",
                    filepath=target.strip().strip('"'),
                    orig_path=orig.strip().strip('"'),
                )
            )
        else:
            results.append(
                ChangedFile(
                    status=status_part,
                    filepath=file_part,
                )
            )
    return results


def build_commit_groups(
    files: list[ChangedFile],
    overrides: dict[str, list[str]],
    only_mapped: bool = False,
) -> list[CommitGroup]:
    """Group uncommitted files into atomic CommitGroup objects.

    Parameters
    ----------
    files : list[ChangedFile]
        List of uncommitted files reported by git status.
    overrides : dict[str, list[str]]
        Canonical Message-to-Paths dictionary loaded from overrides JSON.
    only_mapped : bool, optional
        Whether to exclude unmapped files, by default False.

    Returns
    -------
    list[CommitGroup]
        Ordered list of CommitGroup objects ready for atomic execution.
    """
    # Index files by POSIX normalized paths
    file_by_path: dict[str, ChangedFile] = {}
    for f in files:
        norm_target = f.filepath.replace("\\", "/")
        file_by_path[norm_target] = f
        if f.orig_path:
            norm_orig = f.orig_path.replace("\\", "/")
            file_by_path[norm_orig] = f

    groups: list[CommitGroup] = []
    accounted_filepaths: set[str] = set()

    # 1. Populate groups explicitly defined in Message-to-Paths overrides
    for msg, path_list in overrides.items():
        group_files: list[ChangedFile] = []
        for p in path_list:
            norm_p = p.replace("\\", "/")
            if norm_p in file_by_path:
                f_obj = file_by_path[norm_p]
                if f_obj.filepath not in accounted_filepaths:
                    group_files.append(f_obj)
                    accounted_filepaths.add(f_obj.filepath)

        if group_files:
            groups.append(CommitGroup(message=msg, files=group_files))

    # 2. For remaining files, infer messages and aggregate by message
    inferred_groups: dict[str, list[ChangedFile]] = {}
    for f in files:
        if f.filepath not in accounted_filepaths:
            if only_mapped:
                continue
            inf_msg = _infer_commit_message(f)
            inferred_groups.setdefault(inf_msg, []).append(f)

    for inf_msg, inf_files in inferred_groups.items():
        groups.append(CommitGroup(message=inf_msg, files=inf_files))

    return groups


def _show_group_diff(group: CommitGroup) -> None:
    """Display diff summary for all files in a commit group."""
    paths_to_diff: list[str] = []
    for f in group.files:
        if f.status == "R" and f.orig_path:
            paths_to_diff.append(f.orig_path.replace("\\", "/"))
        paths_to_diff.append(f.filepath.replace("\\", "/"))

    proc = subprocess.run(
        ["git", "diff", "HEAD", "--"] + paths_to_diff,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    diff_text = proc.stdout
    if not diff_text.strip():
        diff_text = "(No diff detected or binary content)"

    syntax = Syntax(diff_text[:4000], "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"Group Diff: {group.message}", border_style="cyan"))


def prompt_interactive_group(
    group: CommitGroup,
    index: int,
    total: int,
) -> str | None:
    """Interactive wizard to approve, customize, or skip a commit group."""
    while True:
        file_lines = "\n".join(f"  • [{f.status}] {f.display_path}" for f in group.files[:8])
        if len(group.files) > 8:
            file_lines += f"\n  • ... (+{len(group.files) - 8} more files)"

        console.print(
            Panel(
                f"[bold cyan]Commit Group [{index}/{total}]:[/bold cyan]\n"
                f"[dim]Files ({len(group.files)}):[/dim]\n{file_lines}\n\n"
                f"[dim]Proposed Message:[/dim] [bold green]{group.message}[/bold green] [dim]({len(group.message)}/72 chars)[/dim]",
                title="[bold yellow]Commitlint Group Wizard[/bold yellow]",
                border_style="yellow",
            )
        )

        console.print("[bold]Choices:[/bold]")
        console.print("  [bold cyan]1[/bold cyan] -> Accept proposed message")
        console.print("  [bold cyan]2[/bold cyan] -> Enter custom commit message")
        console.print("  [bold cyan]3[/bold cyan] -> View group diff")
        console.print("  [bold cyan]4[/bold cyan] -> Skip this group")
        console.print("  [bold red]q[/bold red] -> Quit / Abort\n")

        choice = Prompt.ask("[bold]Select option[/bold]", choices=["1", "2", "3", "4", "q"], default="1")

        if choice == "1":
            return group.message

        if choice == "2":
            while True:
                custom_msg = Prompt.ask("Enter full commit message").strip()
                if not custom_msg:
                    console.print("[red]Commit message cannot be empty.[/red]")
                    continue
                if len(custom_msg) > 72:
                    console.print(f"[red]Message exceeds 72 characters ({len(custom_msg)} chars).[/red]")
                    continue
                return custom_msg

        if choice == "3":
            _show_group_diff(group)
            continue

        if choice == "4":
            console.print(f"[dim]Skipped group '{group.message}'[/dim]")
            return None

        if choice.lower() == "q":
            console.print("[red]Aborted by user.[/red]")
            return "__ABORT__"


def run_git_commit_group(
    group: CommitGroup,
    dry_run: bool = False,
    no_verify: bool = False,
) -> bool:
    """Stage all files in a group and create a single atomic git commit.

    Parameters
    ----------
    group : CommitGroup
        The group of files and commit message to execute.
    dry_run : bool, optional
        Whether to preview without executing git commands, by default False.
    no_verify : bool, optional
        Whether to pass --no-verify to git commit, by default False.

    Returns
    -------
    bool
        True if the commit succeeded or was previewed cleanly, False on failure.
    """
    if len(group.message) > 72:
        console.print(
            f"[bold red]ERROR:[/bold red] Commit message exceeds 72 characters ({len(group.message)} chars): '{group.message}'"
        )
        return False

    # Gather all POSIX forward-slash paths to stage
    paths_to_stage: list[str] = []
    for f in group.files:
        if f.status == "R" and f.orig_path:
            paths_to_stage.append(f.orig_path.replace("\\", "/"))
        paths_to_stage.append(f.filepath.replace("\\", "/"))

    if dry_run:
        verify_flag = " --no-verify" if no_verify else ""
        console.print(f"[dim][DRY-RUN][/dim] git add -A -- {' '.join(paths_to_stage[:3])}{' ...' if len(paths_to_stage) > 3 else ''}")
        console.print(f'[dim][DRY-RUN][/dim] git commit -m "{group.message}"{verify_flag} [dim]({len(group.files)} files)[/dim]')
        return True

    # 1. Clean the staging index to ensure pure isolation
    subprocess.run(["git", "restore", "--staged", "."], capture_output=True, check=False)

    # 2. Stage all files in this group
    add_proc = subprocess.run(
        ["git", "add", "-A", "--"] + paths_to_stage,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if add_proc.returncode != 0:
        err = (add_proc.stdout.strip() + "\n" + add_proc.stderr.strip()).strip()
        console.print(Panel(err, title="[bold red]git add FAILED[/bold red]", border_style="red"))
        return False

    # 3. Verify that changes are staged
    staged_proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not staged_proc.stdout.strip():
        console.print(f"[yellow]Skipping group '{group.message}': no staged changes detected.[/yellow]")
        return True

    # 4. Execute atomic commit
    cmd = ["git", "commit", "-m", group.message]
    if no_verify:
        cmd.append("--no-verify")

    commit_proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if commit_proc.returncode != 0:
        combined_err = (commit_proc.stdout.strip() + "\n" + commit_proc.stderr.strip()).strip()
        console.print(
            Panel(
                combined_err,
                title=f"[bold red]FAILED commit: {group.message}[/bold red]",
                border_style="red",
            )
        )
        subprocess.run(["git", "restore", "--staged", "."], capture_output=True, check=False)
        return False

    console.print(f'[bold green][OK][/bold green] Committed ({len(group.files)} files): "[cyan]{group.message}[/cyan]"')
    return True


def run_upfront_quality_gate() -> bool:
    """Execute fast quality gate check (Ruff + Mypy) once upfront before committing.

    Returns
    -------
    bool
        True if all checks pass cleanly, False otherwise.
    """
    console.print("\n[bold cyan]Running Upfront Quality Gate Verification (Ruff + Mypy)...[/bold cyan]")
    proc = subprocess.run(
        ["uv", "run", "poe", "audit-fast"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        combined = (proc.stdout.strip() + "\n" + proc.stderr.strip()).strip()
        console.print(
            Panel(
                combined,
                title="[bold red]Upfront Quality Gate Failed — Commits Aborted[/bold red]",
                border_style="red",
            )
        )
        return False
    console.print("[bold green]✓ Upfront Quality Gate Passed Cleanly![/bold green]\n")
    return True


def main() -> int:
    """CLI Entry point for automated grouped Conventional Commits."""
    parser = argparse.ArgumentParser(
        description="Commit changes in atomic groups following Commitlint standards."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview commits without executing git commands."
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Interactive group-by-group Commitlint wizard."
    )
    parser.add_argument(
        "--run", action="store_true", help="Execute the commits immediately without prompting."
    )
    parser.add_argument(
        "--map", "--overrides", dest="map_path", type=str, default=None,
        help="Path to external gitignored JSON file containing Message-to-Paths overrides."
    )
    parser.add_argument(
        "--only-mapped", "--only-overrides", dest="only_mapped", action="store_true",
        help="Only commit files that are explicitly defined in the custom overrides map."
    )
    parser.add_argument(
        "-n", "--no-verify", dest="no_verify", action="store_true",
        help="Bypass git pre-commit and commit-msg hooks."
    )
    parser.add_argument(
        "--skip-audit", dest="skip_audit", action="store_true",
        help="Skip upfront quality gate verification."
    )
    args = parser.parse_args()

    # Load Message-to-Paths overrides
    custom_overrides = load_custom_overrides(args.map_path)

    # Determine execution mode:
    if args.dry_run:
        is_dry_run = True
    elif args.interactive:
        is_dry_run = False
    else:
        is_dry_run = not args.run

    # Query uncommitted files
    files = get_changed_files()
    if not files:
        console.print("[green]Working tree is completely clean. Nothing to commit.[/green]")
        return 0

    # Build atomic commit groups
    groups = build_commit_groups(files, custom_overrides, only_mapped=args.only_mapped)
    if not groups:
        console.print("[yellow]No changed files match the requested commit criteria.[/yellow]")
        return 0

    mode_label = (
        "INTERACTIVE COMMIT WIZARD"
        if args.interactive
        else ("DRY-RUN PREVIEW" if is_dry_run else "EXECUTING GROUPED COMMITS")
    )
    total_files_in_groups = sum(len(g.files) for g in groups)
    console.print(
        f"\n--- [bold cyan]{mode_label}[/bold cyan] ({len(groups)} groups, {total_files_in_groups} files) ---\n"
    )

    # Preview summary table
    table = Table(title="Planned Commit Groups", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Files", justify="right", style="cyan", width=6)
    table.add_column("Commit Message", style="bold green")
    table.add_column("Scope Summary", style="white")

    for i, g in enumerate(groups, 1):
        table.add_row(str(i), str(len(g.files)), g.message, g.display_summary)
    console.print(table)
    console.print("")

    if is_dry_run:
        console.print("[dim]To execute these grouped commits, run: uv run python scripts/auto_commit.py --run[/dim]")
        console.print("[dim]Or run interactively with:            uv run python scripts/auto_commit.py -i[/dim]")
        return 0

    # Upfront Quality Gate Verification
    bypass_hooks = args.no_verify
    if not args.skip_audit and not args.no_verify:
        if not run_upfront_quality_gate():
            return 1
        bypass_hooks = True  # Verified upfront; safe to fast-bypass per-group hooks

    success_count = 0
    fail_count = 0
    skipped_count = 0

    try:
        for idx, group in enumerate(groups, 1):
            if args.interactive:
                chosen_msg = prompt_interactive_group(group, idx, len(groups))
                if chosen_msg == "__ABORT__":
                    console.print("\n[yellow]Interactive commit session stopped by user.[/yellow]")
                    break
                if chosen_msg is None:
                    skipped_count += 1
                    continue
                group.message = chosen_msg

            ok = run_git_commit_group(group, dry_run=False, no_verify=bypass_hooks)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                break  # Stop immediately on failure to keep repository in known state
    finally:
        # Guarantee no staged leftovers remain in git index
        subprocess.run(["git", "restore", "--staged", "."], capture_output=True, check=False)

    console.print(
        f"\n[bold]Summary:[/bold] {success_count} groups committed, {fail_count} failed, {skipped_count} skipped."
    )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
