"""Dual-mode launcher entrypoint routing between Terminal CLI and Desktop GUI.

Owns
----
- Subparser CLI definitions for "cli" and "tkinter" commands.
- Process initialization with multiprocessing freeze support.
- Dispatching execution to presentation.cli.app.main_cli or presentation.desktop.app.DesktopApp.

Does not own
-------------
- Pipeline execution workflows (owned by application.pipeline).
- Direct UI widget logic (owned by presentation.desktop or presentation.cli).
"""

from __future__ import annotations

import argparse
import multiprocessing

from personal_finance_etl.presentation.cli.app import main_cli
from personal_finance_etl.presentation.desktop.app import DesktopApp

__all__ = ["build_argument_parser", "main"]


def build_argument_parser() -> argparse.ArgumentParser:
    """Build canonical command-line argument parser for Personal Finance ETL."""
    parser = argparse.ArgumentParser(description="Personal Finance Quant Engine")
    subparsers = parser.add_subparsers(dest="command", help="Frontend to launch")

    # CLI Subcommand
    cli_parser = subparsers.add_parser("cli", help="Launch the terminal CLI")
    cli_parser.add_argument("--config", type=str, help="Path to config.toml", default=None)
    cli_parser.add_argument("--rules", type=str, help="Path to rules.toml", default=None)
    cli_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Snapshot the DuckDB database instead of running ETL",
    )
    cli_parser.add_argument(
        "--restore",
        type=str,
        help="Path to backup zip file to restore (requires --config)",
        default=None,
    )
    cli_parser.add_argument(
        "--auto",
        action="store_true",
        help="Bypass confirmation prompts and automatically start the pipeline",
    )
    cli_parser.add_argument(
        "--cron",
        action="store_true",
        help="Run completely unattended and exit immediately after completion (implies --auto)",
    )
    cli_parser.add_argument(
        "--docs",
        action="store_true",
        help="Open the documentation and guides window, then exit",
    )

    # Tkinter Subcommand
    subparsers.add_parser("tkinter", help="Launch the Desktop GUI")

    return parser


def main() -> None:
    """Canonical entrypoint function for both terminal and desktop interfaces."""
    multiprocessing.freeze_support()

    parser = build_argument_parser()
    args = parser.parse_args()

    if args.command == "cli":
        main_cli(args)
    else:
        # Default to tkinter if no command, or if command == "tkinter"
        app = DesktopApp()
        app.mainloop()  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
