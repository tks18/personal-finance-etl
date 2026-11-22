"""Terminal CLI application for Personal Finance ETL with Rich progress and operator services.

Owns
----
- Terminal interactive bootloader and banner.
- Interactive configuration selection prompts.
- Subcommand orchestration: run, status, doctor, info, snapshot, restore.
- Operator inspection rendering with Rich tables and panels.
- Live progress bars and formatted log event sinks.

Does not own
-------------
- Graphical user interface widgets (owned by presentation.desktop).
- Background worker execution or process lifecycle (owned by application.pipeline).
- Database backup/restore operations (owned by infrastructure.recovery).
- Operator read models or check evaluations (owned by application.operator).
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
from rich.table import Table

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.operator import OperatorService
from personal_finance_etl.contracts.observability import (
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
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
██████╗ ███████╗███████╗████████╗██╗     
██╔══██╗██╔════╝██╔════╝╚══██╔══╝██║     
██████╔╝█████╗  █████╗     ██║   ██║     
██╔═══╝ ██╔══╝  ██╔══╝     ██║   ██║     
██║     ██║     ███████╗   ██║   ███████╗
╚═╝     ╚═╝     ╚══════╝   ╚═╝   ╚══════╝
[/bold cyan]
[bold bright_black]PFETL · LOCAL-FIRST FINANCIAL SYSTEMS PLATFORM v{__version__}[/bold bright_black]
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
        time.sleep(0.06)
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
    """Execute interactive or headless SQLite database backup snapshot and exit."""
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
    """Execute interactive or headless database restoration from a chosen snapshot."""
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


def _handle_status(args: argparse.Namespace) -> None:
    """Render read-only system status and latest execution health."""
    config_path: str | None = getattr(args, "config", None)
    op = OperatorService(config_path=config_path)
    status = op.get_status()

    console.print(f"\n[bold cyan]PFETL v{__version__} · System Status[/bold cyan]\n")

    # Lock status
    lock_color = "red" if status.is_locked else "green"
    lock_text = "LOCKED (Active process running)" if status.is_locked else "IDLE (Free)"
    console.print(
        Panel(
            f"State: [{lock_color}]{lock_text}[/{lock_color}]\nPath:  {status.lock_path}",
            title="[bold]Pipeline Lock[/bold]",
            border_style=lock_color,
        )
    )

    # Execution health
    exec_table = Table(title="Latest Pipeline Run", show_header=True, header_style="bold magenta")
    exec_table.add_column("Property", style="bold")
    exec_table.add_column("Value", style="cyan")
    exec_table.add_row("Run ID", status.latest_run_id or "No runs recorded")
    exec_table.add_row("Status", status.latest_run_status or "N/A")
    exec_table.add_row("Started At", status.latest_run_started_at or "N/A")
    exec_table.add_row("Finished At", status.latest_run_finished_at or "N/A")
    exec_table.add_row("Stale Runs", str(status.stale_runs_count))
    exec_table.add_row("Recovery Required", str(status.recovery_required_count))
    console.print(exec_table)

    # Sync summary if present
    if status.latest_sync_summary:
        sync_table = Table(
            title="Latest Evidence Sync Summary", show_header=True, header_style="bold magenta"
        )
        sync_table.add_column("Metric", style="bold")
        sync_table.add_column("Count / Status", style="green")
        for k, v in status.latest_sync_summary.items():
            sync_table.add_row(k.capitalize(), str(v))
        console.print(sync_table)

    # Database file health
    db_table = Table(title="Storage Stores", show_header=True, header_style="bold magenta")
    db_table.add_column("Store", style="bold")
    db_table.add_column("Exists", style="cyan")
    db_table.add_column("Size", style="yellow")
    duck_sz = (
        f"{status.duckdb_size_bytes / (1024 * 1024):.2f} MB"
        if status.duckdb_size_bytes is not None
        else "N/A"
    )
    sqlite_sz = (
        f"{status.sqlite_size_bytes / (1024 * 1024):.2f} MB"
        if status.sqlite_size_bytes is not None
        else "N/A"
    )
    db_table.add_row("DuckDB Lakehouse", "Yes" if status.duckdb_exists else "No", duck_sz)
    db_table.add_row("SQLite Control Plane", "Yes" if status.sqlite_exists else "No", sqlite_sz)
    console.print(db_table)
    console.print()
    sys.exit(0)


def _handle_doctor(args: argparse.Namespace) -> None:
    """Execute actionable system health checks."""
    config_path: str | None = getattr(args, "config", None)
    rules_path: str | None = getattr(args, "rules", None)
    op = OperatorService(config_path=config_path, rules_path=rules_path)
    report = op.run_doctor()

    console.print(f"\n[bold cyan]PFETL v{__version__} · System Doctor Diagnostics[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="bold", width=26)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Details", style="white")
    table.add_column("Action / Remediation", style="yellow")

    for c in report.checks:
        if c.status == "PASS":
            status_style = "[bold green]PASS[/bold green]"
        elif c.status == "WARN":
            status_style = "[bold yellow]WARN[/bold yellow]"
        else:
            status_style = "[bold red]FAIL[/bold red]"
        table.add_row(c.name, status_style, c.message, c.remediation or "—")

    console.print(table)

    summary_color = (
        "green"
        if report.overall_status == "PASS"
        else ("yellow" if report.overall_status == "WARN" else "red")
    )
    console.print(
        f"\n[bold {summary_color}]Overall Diagnostic Result: {report.overall_status}[/bold {summary_color}] "
        f"({report.passed_count} passed, {report.warn_count} warnings, {report.failed_count} failures)\n"
    )

    sys.exit(0 if report.overall_status != "FAIL" else 1)


def _handle_info(args: argparse.Namespace) -> None:
    """Display runtime environment, resolved paths, and warehouse inventory."""
    config_path: str | None = getattr(args, "config", None)
    op = OperatorService(config_path=config_path)
    info = op.get_info()

    console.print(f"\n[bold cyan]PFETL v{__version__} · System Information[/bold cyan]\n")

    env_table = Table(title="Environment & Runtime", show_header=True, header_style="bold magenta")
    env_table.add_column("Attribute", style="bold")
    env_table.add_column("Value", style="cyan")
    env_table.add_row("PFETL Version", info.version)
    env_table.add_row("Python Version", info.python_version)
    env_table.add_row("Platform", info.platform)
    env_table.add_row("Executable", info.executable)
    console.print(env_table)

    paths_table = Table(
        title="Configured Storage & Paths", show_header=True, header_style="bold magenta"
    )
    paths_table.add_column("Config Item", style="bold")
    paths_table.add_column("Path", style="cyan")
    paths_table.add_row("Config TOML", info.config_path or "Not configured")
    paths_table.add_row("Rules TOML", info.rules_path or "Not configured")
    paths_table.add_row("DuckDB Lakehouse", info.database_path or "Not configured")
    paths_table.add_row("SQLite Raw Store", info.raw_store_path or "Not configured")
    paths_table.add_row("Statements Root", info.statements_root or "Not configured")
    paths_table.add_row("Household DB", info.household_db_path or "Not configured")
    console.print(paths_table)

    ware_table = Table(
        title="Warehouse Data Contracts", show_header=True, header_style="bold magenta"
    )
    ware_table.add_column("Layer", style="bold")
    ware_table.add_column("Contract Count", style="green")
    ware_table.add_row("Bronze Layer", str(info.bronze_tables_count))
    ware_table.add_row("Silver Layer", f"{info.silver_tables_count} (24 tables canonical topology)")
    ware_table.add_row("Gold Layer", f"{info.gold_tables_count} (22 tables canonical topology)")
    ware_table.add_row("Schemas", ", ".join(info.warehouse_schemas))
    console.print(ware_table)
    console.print()
    sys.exit(0)


def _run_etl_progress(engine: PersonalFinanceEngine, config_path: str, rules_path: str) -> None:
    """Run pipeline with rich progress bar visualization and terminal event rendering."""
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
    """Display interactive post-execution menu prompting user for next workflow iteration."""
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
    """Execute a single interactive or automated CLI pipeline run cycle."""
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
    """CLI execution entrypoint evaluating parsed arguments and controlling runtime loop."""
    command = getattr(args, "command", "run")

    if command == "status":
        _handle_status(args)
    elif command == "doctor":
        _handle_doctor(args)
    elif command == "info":
        _handle_info(args)
    elif command == "snapshot":
        engine = PersonalFinanceEngine()
        config_path = getattr(args, "config", None)
        _handle_snapshot(engine, config_path)
    elif command == "restore":
        engine = PersonalFinanceEngine()
        config_path = getattr(args, "config", None)
        restore_target = getattr(args, "target", None)
        if not restore_target:
            console.print("[bold red]Error: restore requires target archive path.[/bold red]")
            sys.exit(1)
        _handle_restore(engine, config_path, restore_target)
    elif command in ("run", "cli"):
        cron_mode: bool = bool(getattr(args, "cron", False))
        if not cron_mode:
            print_bootloader()
        engine = PersonalFinanceEngine()
        config_path = getattr(args, "config", None)
        rules_path = getattr(args, "rules", None)
        auto_mode: bool = bool(getattr(args, "auto", False)) or cron_mode
        while True:
            config_path, rules_path = _run_cli_pipeline_iteration(
                engine, config_path, rules_path, auto_mode=auto_mode, cron_mode=cron_mode
            )
            auto_mode = False
    else:
        console.print(f"[bold red]Unknown command: '{command}'[/bold red]")
        sys.exit(1)
