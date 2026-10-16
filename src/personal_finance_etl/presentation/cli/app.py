"""Terminal CLI application for Personal Finance ETL with Rich progress rendering.

Owns
----
- Terminal interactive bootloader and banner.
- Interactive configuration selection prompts.
- Subcommand orchestration for snapshot, restore, pipeline execution, and docs.
- Rich-based live progress bars and formatted log event sinks.

Does not own
-------------
- Graphical user interface widgets (owned by presentation.desktop).
- Background worker execution or process lifecycle (owned by application.pipeline).
- Database backup/restore operations (owned by infrastructure.recovery).
"""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
import threading
import time
from datetime import datetime

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.presentation.docs.guides_window import show_guides_window

__all__ = ["LOGO", "EngineStatus", "get_file_interactive", "main_cli", "print_bootloader"]

# Backward-compatibility alias
EngineStatus = EngineStatusMessage

try:
    __version__ = importlib.metadata.version("personal-finance-etl")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

if sys.platform == "win32":
    try:
        # Exception TYP-005 [UNTYPED_EXTERNAL_BOUNDARY]: Windows stdout/stderr TextIOWrapper dynamic reconfiguration
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    except Exception:
        pass

console = Console()

LOGO = f"""
[bold cyan]
███████╗██╗  ██╗ █████╗ ███╗   ██╗    ███████╗████████╗██╗     
██╔════╝██║  ██║██╔══██╗████╗  ██║    ██╔════╝╚══██╔══╝██║     
███████╗███████║███████║██╔██╗ ██║    █████╗     ██║   ██║     
╚════██║██╔══██║██╔══██║██║╚██╗██║    ██╔══╝     ██║   ██║     
███████║██║  ██║██║  ██║██║ ╚████║    ███████╗   ██║   ███████╗
╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝    ╚══════╝   ╚═╝   ╚══════╝
[/bold cyan]
[bold bright_black]LOCAL-FIRST FINANCIAL DATA ENGINEERING & QUANTITATIVE PLATFORM v{__version__}[/bold bright_black]
"""


def print_bootloader() -> None:
    """Render terminal ASCII banner and staged initialization sequence."""
    console.print(LOGO)
    steps = [
        "Preserving source evidence & control plane integrity...",
        "Loading canonical schemas and domain contracts...",
        "Initializing FIFO reconstruction & reconciliation engines...",
        "Warming analytical simulation & tax compute kernels...",
        "Synchronizing DuckDB lakehouse state...",
        "[bold green]SYSTEM READY. AWAITING COMMANDS.[/bold green]",
    ]
    for step in steps:
        time.sleep(0.08)
        console.print(f"[dim]>[/dim] {step}")
    console.print()


def get_file_interactive(prompt_text: str, recents: list[str]) -> str:
    """Interactively query user for file path, presenting history options if available."""
    if not recents:
        return str(Prompt.ask(f"[bold cyan]Enter path for {prompt_text}[/bold cyan]"))

    console.print(f"\n[bold yellow]--- Recent {prompt_text} ---[/bold yellow]")
    for i, path in enumerate(recents, 1):
        console.print(f"[{i}] [cyan]{path}[/cyan]")
    console.print(f"[{len(recents) + 1}] [magenta]Enter a new path manually...[/magenta]")

    while True:
        choice = str(
            Prompt.ask(
                f"[bold cyan]Select {prompt_text} (1-{len(recents) + 1})[/bold cyan]",
                default="1",
            )
        )
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(recents):
                return recents[choice_idx]
            elif choice_idx == len(recents):
                return str(Prompt.ask(f"[bold cyan]Enter new path for {prompt_text}[/bold cyan]"))
            else:
                console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")


def main_cli(args: argparse.Namespace) -> None:
    """CLI execution entrypoint evaluating parsed arguments and controlling runtime loop."""
    docs_mode = bool(getattr(args, "docs", False))

    if docs_mode:
        console.print("[bold cyan]Initializing Documentation Engine...[/bold cyan]")
        show_guides_window()
        sys.exit(0)

    print_bootloader()

    engine = PersonalFinanceEngine()

    config_path: str | None = getattr(args, "config", None)
    rules_path: str | None = getattr(args, "rules", None)
    auto_mode: bool = bool(getattr(args, "auto", False))
    cron_mode: bool = bool(getattr(args, "cron", False))
    snapshot_mode: bool = bool(getattr(args, "snapshot", False))
    restore_target: str | None = getattr(args, "restore", None)

    if cron_mode:
        auto_mode = True

    if snapshot_mode:
        if not config_path:
            console.print("\n[bold]Snapshot requires a config file.[/bold]")
            config_path = get_file_interactive("Config TOML", engine.get_recent_configs())

        console.print(
            f"\n[bold green]📸 Snapshotting Database based on config: {config_path}[/bold green]"
        )
        snap = engine.snapshot_database(config_path)
        if snap:
            console.print(
                f"[bold green]✓ Snapshot successfully created at:[/bold green] [cyan]{snap}[/cyan]"
            )
        else:
            console.print(
                "[bold red]✗ Failed to create snapshot or DB does not exist. Run the pipeline first.[/bold red]"
            )
        sys.exit(0)

    if restore_target:
        if not config_path:
            console.print("\n[bold]Restore requires a config file.[/bold]")
            config_path = get_file_interactive("Config TOML", engine.get_recent_configs())

        console.print(
            "\n[bold yellow]⚠️  WARNING: Restoring will overwrite the current database.[/bold yellow]"
        )
        if not Confirm.ask("[bold red]Are you sure you want to proceed?[/bold red]"):
            console.print("[yellow]Restore aborted by user.[/yellow]")
            sys.exit(0)

        console.print(f"\n[bold green]♻️ Restoring Database from: {restore_target}[/bold green]")
        try:
            success = engine.restore_database(config_path, restore_target)
            if success:
                console.print("[bold green]✓ Snapshot successfully restored.[/bold green]")
            else:
                console.print("[bold red]✗ Failed to restore snapshot.[/bold red]")
        except PermissionError as pe:
            console.print(f"[bold red]✗ {pe}[/bold red]")
        except Exception as e:
            console.print(f"[bold red]✗ Unexpected error: {e}[/bold red]")
        sys.exit(0)

    while True:
        if not config_path:
            config_path = get_file_interactive("Config TOML", engine.get_recent_configs())

        if not rules_path:
            rules_path = get_file_interactive("Financial Rules TOML", engine.get_recent_rules())
            engine.add_recent_rules(rules_path)

        console.print()
        console.print(
            Panel(
                f"[bold]Targeting Configuration:[/bold]\nConfig: {config_path}\nRules:  {rules_path}",
                title="[bold magenta]Execution Parameters[/bold magenta]",
                border_style="magenta",
            )
        )

        if not auto_mode:
            if not Confirm.ask("[bold cyan]Execute financial ETL pipeline?[/bold cyan]"):
                console.print("[yellow]Operation aborted by user.[/yellow]")
                sys.exit(0)

        console.print("\n[bold green]🚀 EXECUTING ETL PIPELINE...[/bold green]\n")

        completion_event = threading.Event()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
            expand=True,
        ) as progress:
            main_task = progress.add_task("[cyan]ETL Pipeline Progress", total=100.0)

            def on_status(
                status: EngineStatusMessage,
                progress: Progress = progress,
                main_task: TaskID = main_task,
                completion_event: threading.Event = completion_event,
            ) -> None:
                if status.msg:
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Escape the message so rich doesn't swallow tags like "[stock_pl]"
                    safe_msg = escape(status.msg)

                    if status.level == LogLevel.SUCCESS:
                        progress.console.print(
                            f"[dim][{ts}][/dim] [bold green]✓[/bold green] {safe_msg}"
                        )
                    elif status.level == LogLevel.ERROR:
                        progress.console.print(
                            f"[dim][{ts}][/dim] [bold red]✗ ERROR:[/bold red] {safe_msg}"
                        )
                    elif status.level == LogLevel.WARNING:
                        progress.console.print(
                            f"[dim][{ts}][/dim] [bold yellow]![/bold yellow] {safe_msg}"
                        )
                    elif status.level == LogLevel.STEP:
                        progress.console.print(
                            f"[dim][{ts}][/dim] [bold cyan]>>[/bold cyan] {safe_msg}"
                        )
                    else:
                        progress.console.print(f"[dim][{ts}][/dim] [dim]•[/dim] {safe_msg}")

                if status.progress is not None:
                    # Update progress bar (0.0 to 1.0 -> 0.0 to 100.0)
                    progress.update(main_task, completed=status.progress * 100.0)

                if (
                    status.msg in ("Process completed cleanly.", "Process exited abnormally.")
                    or "Critical Pipeline Failure" in status.msg
                ):
                    completion_event.set()

            engine.run_pipeline_async(config_path, rules_path, on_status)

            try:
                completion_event.wait()
                progress.update(main_task, completed=100.0)
            except KeyboardInterrupt:
                progress.console.print(
                    "\n[bold red]Pipeline forcefully terminated by user.[/bold red]"
                )
                sys.exit(1)

        console.print("\n[bold green]=== SYSTEM HALTED. OPERATION COMPLETE. ===[/bold green]\n")

        if cron_mode:
            sys.exit(0)

        console.print("\n[bold cyan]--- What would you like to do next? ---[/bold cyan]")
        console.print("[1] Restart pipeline with PREVIOUS configuration")
        console.print("[2] Restart pipeline with NEW configuration")
        console.print("[3] Exit")

        while True:
            choice = str(Prompt.ask("[bold cyan]Select an option (1-3)[/bold cyan]", default="1"))
            if choice == "1":
                auto_mode = False
                break
            elif choice == "2":
                config_path = None
                rules_path = None
                auto_mode = False
                break
            elif choice == "3":
                sys.exit(0)
            else:
                console.print("[red]Invalid selection.[/red]")
