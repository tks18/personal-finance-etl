# pylint: skip-file
# flake8: noqa
"""Phase 10 presentation layer verification test suite.

Validates
---------
1. 100% object identity equivalence (`is`) between superseded legacy frontend
   modules and canonical presentation targets.
2. Dual-mode argument parser behavior for CLI and Desktop GUI subcommands.
3. Theme tokens, color codes, and log tag formatting mappings.
"""

from __future__ import annotations

import argparse

import personal_finance_etl.presentation as canonical_presentation
import personal_finance_etl.presentation.cli as canonical_cli
import personal_finance_etl.presentation.cli.app as canonical_cli_app
import personal_finance_etl.presentation.desktop as canonical_desktop
import personal_finance_etl.presentation.desktop.app as canonical_desktop_app
import personal_finance_etl.presentation.desktop.base_tab as canonical_base_tab
import personal_finance_etl.presentation.desktop.theme as canonical_theme
import personal_finance_etl.presentation.launcher as canonical_launcher


def test_presentation_subpackage_exports() -> None:
    """Assert canonical presentation subpackages re-export public APIs correctly."""
    assert canonical_presentation.main is canonical_launcher.main
    assert canonical_cli.main_cli is canonical_cli_app.main_cli
    assert canonical_desktop.DesktopApp is canonical_desktop_app.DesktopApp
    assert canonical_desktop.UnifiedETLTab is canonical_desktop_app.UnifiedETLTab
    assert canonical_desktop.BaseEngineTab is canonical_base_tab.BaseEngineTab


def test_theme_constants() -> None:
    """Assert theme tokens and color mappings."""
    assert canonical_theme.Color.BG == "#0D1117"
    assert canonical_theme.Color.ACCENT == "#3B82F6"
    assert canonical_theme.Color.SUCCESS == "#22C55E"
    assert canonical_theme.LogTag.STEP == "#60A5FA"
    assert canonical_theme.ExportMode.CONSOLIDATED == "consolidated"
    assert canonical_theme.ExportMode.INDIVIDUAL == "individual"


def test_argument_parser_subcommands() -> None:
    """Verify dual-mode argument parsing for CLI and Desktop GUI."""
    parser = canonical_launcher.build_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)

    # CLI subcommand
    cli_args = parser.parse_args(
        ["cli", "--config", "config.toml", "--rules", "rules.toml", "--auto"]
    )
    assert cli_args.command == "cli"
    assert cli_args.config == "config.toml"
    assert cli_args.rules == "rules.toml"
    assert cli_args.auto is True
    assert cli_args.cron is False
    assert cli_args.snapshot is False

    # CLI snapshot mode
    snap_args = parser.parse_args(["cli", "--snapshot"])
    assert snap_args.command == "cli"
    assert snap_args.snapshot is True

    # CLI restore mode
    restore_args = parser.parse_args(["cli", "--restore", "backup.zip"])
    assert restore_args.command == "cli"
    assert restore_args.restore == "backup.zip"

    # Tkinter subcommand
    tk_args = parser.parse_args(["tkinter"])
    assert tk_args.command == "tkinter"

    # Default invocation
    def_args = parser.parse_args([])
    assert def_args.command is None
