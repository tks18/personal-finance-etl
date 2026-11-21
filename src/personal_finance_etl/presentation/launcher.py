"""Dual-mode launcher entrypoint routing between Terminal CLI, Diagnostics, and Desktop GUI.

Owns
----
- Subparser CLI definitions for "cli", "tkinter", and diagnostic subcommands:
  validate-config, check-sources, preview-mapping, preview-identity, preview-plan, dry-run-admission.
- Process initialization with multiprocessing freeze support.
- Dispatching execution to presentation.cli.app.main_cli, presentation.cli.diagnostics handlers,
  or presentation.desktop.app.DesktopApp.

Does not own
-------------
- Pipeline execution workflows (owned by application.pipeline).
- Direct UI widget logic (owned by presentation.desktop or presentation.cli).
- Diagnostic compilation or execution logic (owned by application.diagnostics.service).
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.presentation.cli.app import main_cli
from personal_finance_etl.presentation.cli.diagnostics import (
    handle_check_sources,
    handle_dry_run_admission,
    handle_preview_identity,
    handle_preview_mapping,
    handle_preview_plan,
    handle_validate_config,
)
from personal_finance_etl.presentation.desktop.app import DesktopApp

__all__ = ["build_argument_parser", "main"]


def build_argument_parser() -> argparse.ArgumentParser:
    """Build canonical command-line argument parser for Personal Finance ETL."""
    parser = argparse.ArgumentParser(
        description="Personal Finance ETL · Financial Systems Engineering"
    )
    subparsers = parser.add_subparsers(dest="command", help="Frontend or diagnostic tool to launch")

    # CLI Subcommand
    cli_parser = subparsers.add_parser("cli", help="Launch the terminal CLI")
    cli_parser.add_argument("--config", type=str, help="Path to config.toml", default=None)
    cli_parser.add_argument("--rules", type=str, help="Path to rules.toml", default=None)
    cli_parser.add_argument("--sources", type=str, help="Path to sources.toml", default=None)
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
        "--skip-preflight",
        action="store_true",
        help="Skip Phase 0 pre-flight health checks (not recommended for interactive runs)",
    )
    cli_parser.add_argument(
        "--docs",
        action="store_true",
        help="Open the documentation and guides window, then exit",
    )

    # Tkinter Subcommand
    subparsers.add_parser("tkinter", help="Launch the Desktop GUI")

    # Diagnostics Subcommands
    val_parser = subparsers.add_parser(
        "validate-config", help="Validate settings, rules, and sources configuration"
    )
    val_parser.add_argument("--config", type=str, help="Path to config.toml", default="config.toml")
    val_parser.add_argument("--rules", type=str, help="Path to rules.toml", default="rules.toml")
    val_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )

    check_parser = subparsers.add_parser(
        "check-sources", help="Check reachability and selectors of physical evidence sources"
    )
    check_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )
    check_parser.add_argument(
        "--config", type=str, help="Path to config.toml", default="config.toml"
    )

    map_parser = subparsers.add_parser(
        "preview-mapping", help="Preview column mapping and normalization rules for a dataset"
    )
    map_parser.add_argument(
        "dataset", type=str, help="Canonical dataset ID (e.g. household_transactions)"
    )
    map_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )

    ident_parser = subparsers.add_parser(
        "preview-identity", help="Preview deterministic row identity generation and test collision"
    )
    ident_parser.add_argument(
        "dataset", type=str, help="Canonical dataset ID (e.g. household_transactions)"
    )
    ident_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )
    ident_parser.add_argument(
        "--config", type=str, help="Path to config.toml", default="config.toml"
    )

    plan_parser = subparsers.add_parser(
        "preview-plan", help="Preview topological execution plan and capability activation"
    )
    plan_parser.add_argument(
        "--config", type=str, help="Path to config.toml", default="config.toml"
    )
    plan_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )

    dry_parser = subparsers.add_parser(
        "dry-run-admission", help="Perform zero-mutation pre-bronze admission and schema validation"
    )
    dry_parser.add_argument(
        "--dataset", type=str, help="Dataset ID or 'all' to dry-run admission", default="all"
    )
    dry_parser.add_argument("--config", type=str, help="Path to config.toml", default="config.toml")
    dry_parser.add_argument("--rules", type=str, help="Path to rules.toml", default="rules.toml")
    dry_parser.add_argument(
        "--sources", type=str, help="Path to sources.toml", default="sources.toml"
    )

    return parser


def main() -> None:
    """Canonical entrypoint function for terminal, diagnostics, and desktop interfaces."""
    multiprocessing.freeze_support()

    parser = build_argument_parser()
    args = parser.parse_args()

    if args.command == "cli":
        main_cli(args)
    elif args.command == "validate-config":
        engine = PersonalFinanceEngine()
        sys.exit(handle_validate_config(args, engine))
    elif args.command == "check-sources":
        engine = PersonalFinanceEngine()
        sys.exit(handle_check_sources(args, engine))
    elif args.command == "preview-mapping":
        engine = PersonalFinanceEngine()
        sys.exit(handle_preview_mapping(args, engine))
    elif args.command == "preview-identity":
        engine = PersonalFinanceEngine()
        sys.exit(handle_preview_identity(args, engine))
    elif args.command == "preview-plan":
        engine = PersonalFinanceEngine()
        sys.exit(handle_preview_plan(args, engine))
    elif args.command == "dry-run-admission":
        engine = PersonalFinanceEngine()
        sys.exit(handle_dry_run_admission(args, engine))
    else:
        # Default to tkinter if no command, or if command == "tkinter"
        app = DesktopApp()
        # Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: CustomTkinter untyped mainloop dispatch
        app.mainloop()  # pyright: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    main()
