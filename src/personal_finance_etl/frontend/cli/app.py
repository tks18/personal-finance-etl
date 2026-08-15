import argparse
import sys
import threading
import importlib.metadata
import time

try:
    __version__ = importlib.metadata.version("personal-finance-etl")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

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

from personal_finance_etl.backend.api.engine import PersonalFinanceEngine
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
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
[bold bright_black]INSTITUTIONAL QUANTITATIVE MASTER ENGINE v{__version__}[/bold bright_black]
"""


def print_bootloader() -> None:
    console.print(LOGO)
    steps = [
        "Initializing core quantum modules...",
        "Bypassing mainframe security protocols...",
        "Loading deep-learning heuristic matrices...",
        "Engaging Numba JIT hyper-compilers...",
        "Synchronizing DuckDB lakehouse state...",
        "[bold green]SYSTEM ONLINE. AWAITING COMMANDS.[/bold green]",
    ]
    for step in steps:
        time.sleep(0.15)
        console.print(f"[dim]>[/dim] {step}")
    console.print()


def get_file_interactive(prompt_text: str, recents: list[str]) -> str:
    if not recents:
        return Prompt.ask(f"[bold cyan]Enter path for {prompt_text}[/bold cyan]")

    console.print(f"\n[bold yellow]--- Recent {prompt_text} ---[/bold yellow]")
    for i, path in enumerate(recents, 1):
        console.print(f"[{i}] [cyan]{path}[/cyan]")
    console.print(f"[{len(recents) + 1}] [magenta]Enter a new path manually...[/magenta]")

    while True:
        choice = Prompt.ask(
            f"[bold cyan]Select {prompt_text} (1-{len(recents) + 1})[/bold cyan]", default="1"
        )
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(recents):
                return recents[choice_idx]
            elif choice_idx == len(recents):
                return Prompt.ask(f"[bold cyan]Enter new path for {prompt_text}[/bold cyan]")
            else:
                console.print("[red]Invalid selection.[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")


def main_cli(args: argparse.Namespace) -> None:
    print_bootloader()

    engine = PersonalFinanceEngine()

    config_path = args.config
    rules_path = args.rules

    if args.snapshot:
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

    if not Confirm.ask("[bold red]Are you ready to IGNITE the pipeline?[/bold red]"):
        console.print("[yellow]Operation aborted by user.[/yellow]")
        sys.exit(0)

    console.print("\n[bold green]🚀 IGNITING ETL PIPELINE...[/bold green]\n")

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

        def on_status(status: EngineStatus) -> None:
            if status.msg:
                if status.level == LogLevel.SUCCESS:
                    progress.console.print(f"[bold green]✓[/bold green] {status.msg}")
                elif status.level == LogLevel.ERROR:
                    progress.console.print(f"[bold red]✗ ERROR:[/bold red] {status.msg}")
                elif status.level == LogLevel.WARNING:
                    progress.console.print(f"[bold yellow]![/bold yellow] {status.msg}")
                elif status.level == LogLevel.STEP:
                    progress.console.print(f"[bold cyan]>>[/bold cyan] {status.msg}")
                else:
                    progress.console.print(f"[dim]•[/dim] {status.msg}")

            if status.progress is not None:
                # Update bar (backend sends 0.0 to 1.0)
                progress.update(main_task, completed=status.progress * 100.0)

            if (
                status.msg in ("Process completed cleanly.", "Process exited abnormally.")
                or "Critical Pipeline Failure" in status.msg
            ):
                completion_event.set()

        engine.run_pipeline_async(config_path, rules_path, on_status)

        try:
            completion_event.wait()
            # Force progress to 100% on clean completion
            progress.update(main_task, completed=100.0)
        except KeyboardInterrupt:
            progress.console.print("\n[bold red]Pipeline forcefully terminated by user.[/bold red]")
            sys.exit(1)

    console.print("\n[bold green]=== SYSTEM HALTED. OPERATION COMPLETE. ===[/bold green]\n")
