# pylint: skip-file
# flake8: noqa
"""Automated Git Commit Tool adhering to Commitlint and Conventional Commits.

Owns
----
- Automatic generation of Conventional Commit messages within 72 character limit.
- Individual file staging and granular committing for refactoring workflows.
- Dynamic external mapping support (.commit_overrides.json / --map).
- Interactive file-by-file Commitlint wizard (--interactive / -i).
- Dry-run preview of commit headers and scopes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
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


def load_custom_overrides(cli_map_path: str | None = None) -> dict[str, str]:
    """Load optional custom commit overrides from external gitignored JSON files."""
    candidates: list[Path] = []
    if cli_map_path:
        candidates.append(Path(cli_map_path))
    candidates.append(Path(".commit_overrides.json"))
    candidates.append(Path(".commit_map.json"))

    for p in candidates:
        if p.is_file():
            try:
                content: str = p.read_text(encoding="utf-8")
                raw_data: object = json.loads(content)
                if isinstance(raw_data, dict):
                    raw_dict = cast(dict[object, object], raw_data)
                    return {str(k).replace("\\", "/"): str(v) for k, v in raw_dict.items()}
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
            return parts[1]
        return parts[0]
    if norm.startswith("tests/"):
        stem = Path(norm).stem.replace("test_", "")
        return stem[:12]
    if norm.startswith("scripts/"):
        return Path(norm).stem[:12]
    if norm.startswith(".githooks/"):
        return "hooks"
    if norm.startswith(".github/"):
        return "ci"
    if norm.startswith(".planning/"):
        return "planning"
    if norm.endswith(".md"):
        return Path(norm).stem[:12]
    return Path(norm).stem[:12]


def _infer_commit_message(filepath: str, status: str, overrides: dict[str, str] | None = None) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = filepath.replace("\\", "/")
    if overrides and norm in overrides:
        return overrides[norm]

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


def _get_file_stat(filepath: str) -> str:
    """Return diff stat summary for a given file."""
    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath
    proc = subprocess.run(
        ["git", "diff", "--numstat", "HEAD", "--", norm_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        parts = proc.stdout.strip().split()
        if len(parts) >= 2:
            return f"+{parts[0]} / -{parts[1]} lines"
    p = Path(filepath)
    if p.is_file():
        try:
            line_count = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            return f"new file ({line_count} lines)"
        except Exception:  # nosec B110
            pass
    return "modified"


def _show_file_diff(filepath: str) -> None:
    """Display a colored syntax diff for a file in the terminal."""
    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath
    proc = subprocess.run(
        ["git", "diff", "HEAD", "--", norm_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    diff_text = proc.stdout
    if not diff_text.strip():
        p = Path(filepath)
        if p.is_file():
            try:
                diff_text = p.read_text(encoding="utf-8", errors="replace")[:2000]
            except Exception:
                diff_text = "(Binary or unreadable file)"
        else:
            diff_text = "(No diff available)"

    syntax = Syntax(diff_text, "diff" if "diff --git" in diff_text else "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"Diff: {norm_path}", border_style="cyan"))


def prompt_interactive_commit(
    filepath: str,
    status: str,
    inferred_msg: str,
    index: int,
    total: int,
) -> str | None:
    """Interactive wizard to select, customize, or skip a commit message for a file."""
    norm_path = filepath.replace("\\", "/")
    stat_summary = _get_file_stat(filepath)
    suggested_scope = _infer_scope(filepath)

    status_name = {
        "M": "[yellow]Modified[/yellow]",
        "A": "[green]Added[/green]",
        "??": "[cyan]Untracked[/cyan]",
        "D": "[red]Deleted[/red]",
        "R": "[magenta]Renamed[/magenta]",
    }.get(status, f"[dim]{status}[/dim]")

    while True:
        console.print(
            Panel(
                f"[bold cyan]File [{index}/{total}]:[/bold cyan] [bold white]{norm_path}[/bold white]\n"
                f"[dim]Status:[/dim]   {status_name} ({stat_summary})\n"
                f"[dim]Inferred:[/dim] [bold green]{inferred_msg}[/bold green] [dim]({len(inferred_msg)}/72 chars)[/dim]",
                title="[bold yellow]Commitlint Interactive Wizard[/bold yellow]",
                border_style="yellow",
            )
        )

        console.print("[bold]Choices:[/bold]")
        console.print("  [bold cyan]1[/bold cyan] -> Accept inferred message")
        console.print("  [bold cyan]2[/bold cyan] -> Select Type & Scope (feat, fix, refactor, docs, test, ci, chore...)")
        console.print("  [bold cyan]3[/bold cyan] -> Enter custom message")
        console.print("  [bold cyan]4[/bold cyan] -> View file diff")
        console.print("  [bold cyan]5[/bold cyan] -> Skip this file")
        console.print("  [bold red]q[/bold red] -> Quit / Abort\n")

        choice = Prompt.ask("[bold]Select option[/bold]", choices=["1", "2", "3", "4", "5", "q"], default="1")

        if choice == "1":
            return inferred_msg

        if choice == "2":
            table = Table(title="Conventional Commit Types", show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=4)
            table.add_column("Type", style="bold cyan", width=10)
            table.add_column("Description", style="white")
            for i, (ctype, cdesc) in enumerate(COMMIT_TYPES, 1):
                table.add_row(str(i), ctype, cdesc)
            console.print(table)

            type_idx_str = Prompt.ask(
                "Select type number",
                choices=[str(i) for i in range(1, len(COMMIT_TYPES) + 1)],
                default="3",
            )
            selected_type = COMMIT_TYPES[int(type_idx_str) - 1][0]

            scope_val = Prompt.ask("Scope", default=suggested_scope).strip()

            prefix = f"{selected_type}({scope_val}): " if scope_val else f"{selected_type}: "
            max_desc_len = 72 - len(prefix)

            while True:
                desc = Prompt.ask(f"Description (max {max_desc_len} chars)").strip()
                if not desc:
                    console.print("[red]Description cannot be empty.[/red]")
                    continue
                full_msg = f"{prefix}{desc}"
                if len(full_msg) > 72:
                    console.print(f"[red]Message too long ({len(full_msg)} chars > 72). Please shorten.[/red]")
                    continue
                console.print(f"\n[bold green]Final commit message:[/bold green] '{full_msg}' ({len(full_msg)}/72 chars)")
                if Confirm.ask("Use this commit message?", default=True):
                    return full_msg

        if choice == "3":
            while True:
                custom_msg = Prompt.ask("Enter full commit message").strip()
                if not custom_msg:
                    console.print("[red]Commit message cannot be empty.[/red]")
                    continue
                if len(custom_msg) > 72:
                    console.print(f"[red]Message exceeds 72 characters ({len(custom_msg)} chars).[/red]")
                    continue
                return custom_msg

        if choice == "4":
            _show_file_diff(filepath)
            continue

        if choice == "5":
            console.print(f"[dim]Skipped {norm_path}[/dim]")
            return None

        if choice.lower() == "q":
            console.print("[red]Aborted by user.[/red]")
            return "__ABORT__"


def run_git_commit(filepath: str, message: str, dry_run: bool = False) -> bool:
    """Stage a single file and create a git commit."""
    if len(message) > 72:
        console.print(f"[bold red]ERROR:[/bold red] Commit message exceeds 72 characters ({len(message)} chars): '{message}'")
        return False

    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath

    if dry_run:
        console.print(f"[dim][DRY-RUN][/dim] git add {norm_path}")
        console.print(f'[dim][DRY-RUN][/dim] git commit -m "{message}" [dim](len: {len(message)})[/dim]')
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
        console.print(f"[bold red]FAILED git add {norm_path}:[/bold red] {add_proc.stderr}")
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
        console.print(f"[bold red]FAILED git commit for {norm_path}:[/bold red] {commit_proc.stderr}")
        return False

    console.print(f'[bold green][OK][/bold green] Committed {norm_path}: "[cyan]{message}[/cyan]"')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit changes file-by-file following Commitlint standards."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview commits without executing git commands."
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Interactive file-by-file Commitlint wizard."
    )
    parser.add_argument(
        "--run", action="store_true", help="Execute the commits immediately without prompting."
    )
    parser.add_argument(
        "--file", type=str, help="Commit only a single specific file."
    )
    parser.add_argument(
        "--map", "--overrides", dest="map_path", type=str, default=None,
        help="Path to external gitignored JSON file containing custom commit message overrides."
    )
    parser.add_argument(
        "--only-mapped", "--only-overrides", dest="only_mapped", action="store_true",
        help="Only commit files that are explicitly defined in the custom overrides map."
    )
    args = parser.parse_args()

    # Load custom external overrides if present
    custom_overrides = load_custom_overrides(args.map_path)

    # Determine execution mode:
    # --dry-run always takes precedence
    if args.dry_run:
        is_dry_run = True
    elif args.interactive:
        is_dry_run = False
    else:
        is_dry_run = not args.run

    if args.file:
        files = [("M", args.file)]
    else:
        files = get_changed_files()

    if args.only_mapped:
        files = [(s, f) for s, f in files if f.replace("\\", "/") in custom_overrides]
        if not files:
            console.print("[yellow]No changed files match the overrides in the mapping file.[/yellow]")
            return 0

    if not files:
        console.print("[green]Working tree is completely clean. Nothing to commit.[/green]")
        return 0

    mode_label = (
        "INTERACTIVE COMMIT WIZARD"
        if args.interactive
        else ("DRY-RUN PREVIEW" if is_dry_run else "EXECUTING COMMITS")
    )
    console.print(f"\n--- [bold cyan]{mode_label}[/bold cyan] ({len(files)} files found) ---\n")

    success_count = 0
    fail_count = 0
    skipped_count = 0

    for idx, (status, filepath) in enumerate(files, 1):
        inferred = _infer_commit_message(filepath, status, custom_overrides)

        if args.interactive:
            chosen_msg = prompt_interactive_commit(filepath, status, inferred, idx, len(files))
            if chosen_msg == "__ABORT__":
                console.print("\n[yellow]Interactive commit session stopped by user.[/yellow]")
                break
            if chosen_msg is None:
                skipped_count += 1
                continue
            message = chosen_msg
        else:
            message = inferred

        ok = run_git_commit(filepath, message, dry_run=is_dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    console.print(
        f"\n[bold]Summary:[/bold] {success_count} succeeded, {fail_count} failed, {skipped_count} skipped."
    )
    if is_dry_run and not args.interactive:
        console.print("[dim]To execute these commits, run: uv run python scripts/auto_commit.py --run[/dim]")
        console.print("[dim]Or run interactively with:     uv run python scripts/auto_commit.py -i[/dim]")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
