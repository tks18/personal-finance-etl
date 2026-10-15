"""Phase 10 presentation layer verification test suite.

Validates
---------
1. 100% object identity equivalence (`is`) between superseded legacy frontend
   modules and canonical presentation targets.
2. Dual-mode argument parser behavior for CLI and Desktop GUI subcommands.
3. Theme tokens, color codes, and log tag formatting mappings.
4. Documentation manifest catalog parsing and HTML renderer compilation.
"""

from __future__ import annotations

import argparse

import personal_finance_etl.backend.utils.theme as legacy_theme
import personal_finance_etl.frontend as legacy_frontend
import personal_finance_etl.frontend.cli.app as legacy_cli_app
import personal_finance_etl.frontend.commons.docs.guides_window as legacy_guides_window
import personal_finance_etl.frontend.commons.docs.manifest as legacy_manifest
import personal_finance_etl.frontend.commons.docs.renderer as legacy_renderer
import personal_finance_etl.frontend.desktop.app as legacy_desktop_app
import personal_finance_etl.frontend.desktop.base_tab as legacy_base_tab
import personal_finance_etl.frontend.launcher as legacy_launcher
import personal_finance_etl.presentation as canonical_presentation
import personal_finance_etl.presentation.cli as canonical_cli
import personal_finance_etl.presentation.cli.app as canonical_cli_app
import personal_finance_etl.presentation.desktop as canonical_desktop
import personal_finance_etl.presentation.desktop.app as canonical_desktop_app
import personal_finance_etl.presentation.desktop.base_tab as canonical_base_tab
import personal_finance_etl.presentation.desktop.theme as canonical_theme
import personal_finance_etl.presentation.docs as canonical_docs
import personal_finance_etl.presentation.docs.guides_window as canonical_guides_window
import personal_finance_etl.presentation.docs.manifest as canonical_manifest
import personal_finance_etl.presentation.docs.renderer as canonical_renderer
import personal_finance_etl.presentation.launcher as canonical_launcher


def test_presentation_launcher_identity() -> None:
    """Assert 100% object identity between legacy frontend launcher and canonical presentation launcher."""
    assert legacy_launcher.main is canonical_launcher.main
    assert legacy_launcher.build_argument_parser is canonical_launcher.build_argument_parser
    assert legacy_frontend.run_app is canonical_launcher.main
    assert canonical_presentation.main is canonical_launcher.main


def test_presentation_cli_identity() -> None:
    """Assert 100% object identity between legacy CLI and canonical presentation CLI."""
    assert legacy_cli_app.main_cli is canonical_cli_app.main_cli
    assert legacy_cli_app.print_bootloader is canonical_cli_app.print_bootloader
    assert legacy_cli_app.get_file_interactive is canonical_cli_app.get_file_interactive
    assert legacy_cli_app.LOGO is canonical_cli_app.LOGO
    assert legacy_frontend.main_cli is canonical_cli_app.main_cli
    assert canonical_cli.main_cli is canonical_cli_app.main_cli


def test_presentation_desktop_identity() -> None:
    """Assert 100% object identity between legacy desktop GUI and canonical presentation desktop."""
    assert legacy_desktop_app.DesktopApp is canonical_desktop_app.DesktopApp
    assert legacy_desktop_app.UnifiedETLTab is canonical_desktop_app.UnifiedETLTab
    assert legacy_desktop_app.main is canonical_desktop_app.main
    assert legacy_base_tab.BaseEngineTab is canonical_base_tab.BaseEngineTab
    assert legacy_frontend.DesktopApp is canonical_desktop_app.DesktopApp
    assert canonical_desktop.DesktopApp is canonical_desktop_app.DesktopApp
    assert canonical_desktop.UnifiedETLTab is canonical_desktop_app.UnifiedETLTab
    assert canonical_desktop.BaseEngineTab is canonical_base_tab.BaseEngineTab


def test_presentation_docs_identity() -> None:
    """Assert 100% object identity between legacy docs and canonical presentation docs."""
    assert legacy_manifest.DocEntry is canonical_manifest.DocEntry
    assert legacy_manifest.DocsCatalog is canonical_manifest.DocsCatalog
    assert legacy_renderer.DocsRenderer is canonical_renderer.DocsRenderer
    assert legacy_guides_window.show_guides_window is canonical_guides_window.show_guides_window
    assert canonical_docs.DocEntry is canonical_manifest.DocEntry
    assert canonical_docs.DocsCatalog is canonical_manifest.DocsCatalog
    assert canonical_docs.DocsRenderer is canonical_renderer.DocsRenderer
    assert canonical_docs.show_guides_window is canonical_guides_window.show_guides_window


def test_theme_constants_and_identity() -> None:
    """Assert theme tokens, color mappings, and backward-compatible identity."""
    assert legacy_theme.Color is canonical_theme.Color
    assert legacy_theme.LogTag is canonical_theme.LogTag
    assert legacy_theme.LOG_TAG_COLORS == canonical_theme.LOG_TAG_COLORS
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
    assert cli_args.docs is False

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


def test_docs_catalog_and_renderer() -> None:
    """Verify documentation catalog discovery and HTML compilation."""
    from personal_finance_etl.infrastructure.filesystem.paths import resource_path

    docs_dir = resource_path("docs")
    catalog = canonical_manifest.DocsCatalog(docs_dir)
    assert isinstance(catalog, canonical_manifest.DocsCatalog)

    entries = catalog.get_all_docs()
    assert len(entries) > 0
    first = entries[0]
    assert isinstance(first, canonical_manifest.DocEntry)
    assert first.title
    assert first.path

    renderer = canonical_renderer.DocsRenderer(catalog)
    html_content = renderer.build_html_app()
    assert isinstance(html_content, str)
    assert "<!DOCTYPE html>" in html_content
    assert "mermaid" in html_content
    assert first.title in html_content
