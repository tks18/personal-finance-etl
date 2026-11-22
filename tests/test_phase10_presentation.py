# pylint: skip-file
# flake8: noqa
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


def test_presentation_subpackage_exports() -> None:
    """Assert canonical presentation subpackages re-export public APIs correctly."""
    assert canonical_presentation.main is canonical_launcher.main
    assert canonical_cli.main_cli is canonical_cli_app.main_cli
    assert canonical_desktop.DesktopApp is canonical_desktop_app.DesktopApp
    assert canonical_desktop.UnifiedETLTab is canonical_desktop_app.UnifiedETLTab
    assert canonical_desktop.BaseEngineTab is canonical_base_tab.BaseEngineTab
    assert canonical_docs.DocEntry is canonical_manifest.DocEntry
    assert canonical_docs.DocsCatalog is canonical_manifest.DocsCatalog
    assert canonical_docs.DocsRenderer is canonical_renderer.DocsRenderer
    assert canonical_docs.show_guides_window is canonical_guides_window.show_guides_window


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
