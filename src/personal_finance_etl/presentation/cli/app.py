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

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.observability import (
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.presentation.docs.guides_window import show_guides_window
from personal_finance_etl.presentation.observability import RichNarrativeSink

__all__ = ["LOGO", "EngineStatus", "get_file_interactive", "main_cli", "print_bootloader"]

# Canonical status type export
EngineStatus = ObservabilityEvent

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
            if choice_idx == len(recents):
                return str(Prompt.ask(f"[bold cyan]Enter new path for {prompt_text}[/bold cyan]"))
            console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")


def _handle_snapshot(engine: PersonalFinanceEngine, config_path: str | None) -> None:
    """Execute interactive or headless SQLite database backup snapshot and exit.

    Parameters
    ----------
    engine : PersonalFinanceEngine
        Personal finance engine instance.
    config_path : str | None
        Path to pipeline config file or None for interactive prompt.
    """
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


def _handle_restore(
    engine: PersonalFinanceEngine, config_path: str | None, restore_target: str
) -> None:
    """Execute interactive or headless database restoration from a chosen snapshot.

    Parameters
    ----------
    engine : PersonalFinanceEngine
        Personal finance engine instance.
    config_path : str | None
        Path to pipeline config file or None for interactive prompt.
    restore_target : str
        Snapshot filename or relative/absolute path to restore.
    """
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


def _run_etl_progress(engine: PersonalFinanceEngine, config_path: str, rules_path: str) -> None:
    """Run pipeline with rich progress bar visualization and terminal event rendering.

    Parameters
    ----------
    engine : PersonalFinanceEngine
        Personal finance engine instance.
    config_path : str
        Path to pipeline TOML configuration.
    rules_path : str
        Path to financial rules TOML configuration.
    """
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
        narrative_sink = RichNarrativeSink(
            console=console,
            progress=progress,
            task_id=main_task,
        )

        def on_status(status: ObservabilityEvent) -> None:
            narrative_sink.emit(status)
            if status.event_code in (
                EventCode.SYSTEM_TEARDOWN,
                EventCode.RUN_COMPLETED,
                EventCode.RUN_FAILED,
                EventCode.RUN_ABORTED,
            ) or (
                status.outcome in (EventOutcome.COMPLETED, EventOutcome.FAILED)
                and status.presentation_kind in (PresentationKind.SUCCESS, PresentationKind.FAILURE)
                and (status.progress == 1.0 or status.outcome == EventOutcome.FAILED)
            ):
                completion_event.set()

        engine.run_pipeline_async(config_path, rules_path, on_status)

        try:
            completion_event.wait()
            progress.update(main_task, completed=100.0)
        except KeyboardInterrupt:
            progress.console.print("\n[bold red]Pipeline forcefully terminated by user.[/bold red]")
            sys.exit(1)


def _prompt_next_iteration(config_path: str, rules_path: str) -> tuple[str | None, str | None]:
    """Display interactive post-execution menu prompting user for next workflow iteration.

    Parameters
    ----------
    config_path : str
        Previous configuration file path.
    rules_path : str
        Previous financial rules file path.

    Returns
    -------
    tuple[str | None, str | None]
        Selected configuration path pair or None to prompt anew.
    """
    console.print("\n[bold cyan]--- What would you like to do next? ---[/bold cyan]")
    console.print("[1] Restart pipeline with PREVIOUS configuration")
    console.print("[2] Restart pipeline with NEW configuration")
    console.print("[3] Exit")

    while True:
        choice = str(Prompt.ask("[bold cyan]Select an option (1-3)[/bold cyan]", default="1"))
        if choice == "1":
            return config_path, rules_path
        if choice == "2":
            return None, None
        if choice == "3":
            sys.exit(0)
        console.print("[red]Invalid selection.[/red]")


def _run_cli_pipeline_iteration(
    engine: PersonalFinanceEngine,
    config_path: str | None,
    rules_path: str | None,
    auto_mode: bool,
    cron_mode: bool,
) -> tuple[str | None, str | None]:
    """Execute a single interactive or automated CLI pipeline run cycle.

    Parameters
    ----------
    engine : PersonalFinanceEngine
        The orchestrating engine instance.
    config_path : str | None
        Current pipeline configuration file path, if specified.
    rules_path : str | None
        Current financial rules file path, if specified.
    auto_mode : bool
        Whether to bypass execution confirmation prompt.
    cron_mode : bool
        Whether the CLI is running under an automated cron runner.

    Returns
    -------
    tuple[str | None, str | None]
        Resolved configuration and rules path for the subsequent iteration.
    """
    if not config_path:
        config_path = get_file_interactive("Config TOML", engine.get_recent_configs())

    if config_path:
        engine.add_recent_config(config_path)

    if not rules_path:
        rules_path = get_file_interactive("Financial Rules TOML", engine.get_recent_rules())

    if rules_path:
        engine.add_recent_rules(rules_path)

    console.print()
    console.print(
        Panel(
            f"[bold]Targeting Configuration:[/bold]\nConfig: {config_path}\nRules:  {rules_path}",
            title="[bold magenta]Execution Parameters[/bold magenta]",
            border_style="magenta",
        )
    )

    if not auto_mode and not Confirm.ask("[bold cyan]Execute financial ETL pipeline?[/bold cyan]"):
        console.print("[yellow]Operation aborted by user.[/yellow]")
        sys.exit(0)

    console.print("\n[bold green]🚀 EXECUTING ETL PIPELINE...[/bold green]\n")
    _run_etl_progress(engine, config_path, rules_path)
    console.print("\n[bold green]=== SYSTEM HALTED. OPERATION COMPLETE. ===[/bold green]\n")

    if cron_mode:
        sys.exit(0)

    return _prompt_next_iteration(config_path, rules_path)


def main_cli(args: argparse.Namespace) -> None:
    """CLI execution entrypoint evaluating parsed arguments and controlling runtime loop.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    """
    if getattr(args, "docs", False):
        console.print("[bold cyan]Initializing Documentation Engine...[/bold cyan]")
        show_guides_window()
        sys.exit(0)

    print_bootloader()

    engine = PersonalFinanceEngine()

    config_path: str | None = getattr(args, "config", None)
    rules_path: str | None = getattr(args, "rules", None)
    cron_mode: bool = bool(getattr(args, "cron", False))
    auto_mode: bool = bool(getattr(args, "auto", False)) or cron_mode

    if getattr(args, "snapshot", False):
        _handle_snapshot(engine, config_path)

    restore_target: str | None = getattr(args, "restore", None)
    if restore_target:
        _handle_restore(engine, config_path, restore_target)

    while True:
        config_path, rules_path = _run_cli_pipeline_iteration(
            engine, config_path, rules_path, auto_mode=auto_mode, cron_mode=cron_mode
        )
        auto_mode = False
