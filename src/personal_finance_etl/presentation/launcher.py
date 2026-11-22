"""Single pfetl product entrypoint routing between Terminal commands and Desktop GUI.

Owns
----
- Canonical command-line argument parser for pfetl.
- Subcommands: run, status, doctor, info, snapshot, restore.
- Naked invocation routing directly to desktop GUI (DesktopApp).
- Process initialization with multiprocessing freeze support.

Does not own
-------------
- Concrete terminal progress bars or interactive rendering (owned by presentation.cli).
- Pipeline execution workflows (owned by application.pipeline).
- Operator query services (owned by application.operator).
"""

from __future__ import annotations

import argparse
import importlib.metadata
import multiprocessing

from personal_finance_etl.presentation.cli.app import main_cli
from personal_finance_etl.presentation.desktop.app import DesktopApp

__all__ = ["build_argument_parser", "main"]

try:
    __version__ = importlib.metadata.version("personal-finance-etl")
except Exception:
    __version__ = "unknown"


def build_argument_parser() -> argparse.ArgumentParser:
    """Build canonical command-line argument parser for pfetl."""
    parser = argparse.ArgumentParser(
        prog="pfetl",
        description="PFETL · Local-First Personal Financial Systems Platform",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pfetl v{__version__}",
        help="Show application version and exit",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Explicitly launch the desktop operations console GUI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Operator command to execute")

    # 1. run subcommand
    run_parser = subparsers.add_parser("run", help="Execute the quantitative ETL pipeline")
    run_parser.add_argument("-c", "--config", type=str, help="Path to config.toml", default=None)
    run_parser.add_argument("-r", "--rules", type=str, help="Path to rules.toml", default=None)
    run_parser.add_argument(
        "--auto",
        action="store_true",
        help="Bypass confirmation prompts and automatically start the pipeline",
    )
    run_parser.add_argument(
        "--cron",
        action="store_true",
        help="Run completely unattended and exit immediately after completion (implies --auto)",
    )

    # 2. status subcommand
    status_parser = subparsers.add_parser(
        "status", help="Show system status, locks, and latest run execution health"
    )
    status_parser.add_argument("-c", "--config", type=str, help="Path to config.toml", default=None)

    # 3. doctor subcommand
    doctor_parser = subparsers.add_parser("doctor", help="Run actionable diagnostic health checks")
    doctor_parser.add_argument("-c", "--config", type=str, help="Path to config.toml", default=None)
    doctor_parser.add_argument("-r", "--rules", type=str, help="Path to rules.toml", default=None)

    # 4. info subcommand
    info_parser = subparsers.add_parser(
        "info", help="Display system metadata, runtime environment, and warehouse inventory"
    )
    info_parser.add_argument("-c", "--config", type=str, help="Path to config.toml", default=None)

    # 5. snapshot subcommand
    snap_parser = subparsers.add_parser(
        "snapshot", help="Create a coordinated backup snapshot of the DuckDB and SQLite databases"
    )
    snap_parser.add_argument("-c", "--config", type=str, help="Path to config.toml", default=None)

    # 6. restore subcommand
    restore_parser = subparsers.add_parser(
        "restore", help="Restore DuckDB and SQLite databases from a backup snapshot archive"
    )
    restore_parser.add_argument(
        "target", type=str, help="Path or filename of backup snapshot zip archive"
    )
    restore_parser.add_argument(
        "-c", "--config", type=str, help="Path to config.toml", default=None
    )

    return parser


def main() -> None:
    """Canonical entrypoint function for pfetl executable."""
    multiprocessing.freeze_support()

    parser = build_argument_parser()
    args = parser.parse_args()

    # If naked invocation (no subcommand) or explicit --gui requested, launch DesktopApp
    if args.command is None or getattr(args, "gui", False):
        app = DesktopApp()
        # Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: CustomTkinter untyped mainloop dispatch
        app.mainloop()  # pyright: ignore[reportUnknownMemberType]
    else:
        main_cli(args)


if __name__ == "__main__":
    main()
