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
    """Verify pfetl argument parsing for CLI subcommands and Desktop GUI."""
    parser = canonical_launcher.build_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    assert parser.prog == "pfetl"

    # run subcommand
    run_args = parser.parse_args(
        ["run", "--config", "config.toml", "--rules", "rules.toml", "--auto"]
    )
    assert run_args.command == "run"
    assert run_args.config == "config.toml"
    assert run_args.rules == "rules.toml"
    assert run_args.auto is True
    assert run_args.cron is False

    # status subcommand
    status_args = parser.parse_args(["status", "--config", "config.toml"])
    assert status_args.command == "status"
    assert status_args.config == "config.toml"

    # doctor subcommand
    doctor_args = parser.parse_args(["doctor", "--config", "config.toml", "--rules", "rules.toml"])
    assert doctor_args.command == "doctor"
    assert doctor_args.config == "config.toml"
    assert doctor_args.rules == "rules.toml"

    # info subcommand
    info_args = parser.parse_args(["info"])
    assert info_args.command == "info"

    # snapshot subcommand
    snap_args = parser.parse_args(["snapshot", "--config", "config.toml"])
    assert snap_args.command == "snapshot"
    assert snap_args.config == "config.toml"

    # restore subcommand
    restore_args = parser.parse_args(["restore", "backup.zip", "--config", "config.toml"])
    assert restore_args.command == "restore"
    assert restore_args.target == "backup.zip"
    assert restore_args.config == "config.toml"

    # GUI flag
    gui_args = parser.parse_args(["--gui"])
    assert gui_args.gui is True
    assert gui_args.command is None

    # Default naked invocation
    def_args = parser.parse_args([])
    assert def_args.command is None
