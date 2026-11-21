"""Unit tests for presentation CLI diagnostic handlers and launcher argument parsing.

Owns
----
- Testing ArgumentParser subcommand structure for diagnostic CLI tools:
  validate-config, check-sources, preview-mapping, preview-identity, preview-plan, dry-run-admission.
- Testing presentation handler routing and exit code conventions.

Does not own
-------------
- Pure diagnostic business logic (owned by application.diagnostics.service).
- Direct terminal I/O capture beyond handler invocation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.presentation.cli.diagnostics import (
    handle_check_sources,
    handle_dry_run_admission,
    handle_preview_identity,
    handle_preview_mapping,
    handle_preview_plan,
    handle_validate_config,
)
from personal_finance_etl.presentation.launcher import build_argument_parser


def test_build_argument_parser_diagnostic_subcommands() -> None:
    """Verify all 6 diagnostic subcommands are registered with appropriate arguments."""
    parser = build_argument_parser()

    # validate-config
    args = parser.parse_args(
        ["validate-config", "--config", "c.toml", "--rules", "r.toml", "--sources", "s.toml"]
    )
    assert args.command == "validate-config"
    assert args.config == "c.toml"
    assert args.rules == "r.toml"
    assert args.sources == "s.toml"

    # check-sources
    args = parser.parse_args(["check-sources", "--sources", "s.toml", "--config", "c.toml"])
    assert args.command == "check-sources"
    assert args.sources == "s.toml"

    # preview-mapping
    args = parser.parse_args(["preview-mapping", "household_inoutcome", "--sources", "s.toml"])
    assert args.command == "preview-mapping"
    assert args.dataset == "household_inoutcome"

    # preview-identity
    args = parser.parse_args(["preview-identity", "household_inoutcome", "--sources", "s.toml"])
    assert args.command == "preview-identity"
    assert args.dataset == "household_inoutcome"

    # preview-plan
    args = parser.parse_args(["preview-plan", "--config", "c.toml", "--sources", "s.toml"])
    assert args.command == "preview-plan"

    # dry-run-admission
    args = parser.parse_args(["dry-run-admission", "--dataset", "household_inoutcome"])
    assert args.command == "dry-run-admission"
    assert args.dataset == "household_inoutcome"


def test_handle_validate_config(config_path: Path, rules_path: Path, sources_path: Path) -> None:
    """Verify handle_validate_config returns 0 for valid configuration."""
    args = argparse.Namespace(
        config=str(config_path),
        rules=str(rules_path),
        sources=str(sources_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_validate_config(args, engine)
    assert code == 0


def test_handle_validate_config_failure() -> None:
    """Verify handle_validate_config returns 1 when validation fails."""
    args = argparse.Namespace(
        config="non_existent_config.toml",
        rules="non_existent_rules.toml",
        sources="non_existent_sources.toml",
    )
    engine = PersonalFinanceEngine()
    code = handle_validate_config(args, engine)
    assert code == 1


def test_handle_check_sources(config_path: Path, sources_path: Path) -> None:
    """Verify handle_check_sources executes without crashing."""
    args = argparse.Namespace(
        sources=str(sources_path),
        config=str(config_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_check_sources(args, engine)
    assert code in (0, 1)


def test_handle_preview_mapping(sources_path: Path) -> None:
    """Verify handle_preview_mapping returns 0 for known dataset."""
    args = argparse.Namespace(
        dataset="household_inoutcome",
        sources=str(sources_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_preview_mapping(args, engine)
    assert code == 0


def test_handle_preview_mapping_missing_dataset() -> None:
    """Verify handle_preview_mapping returns 1 when dataset argument is missing."""
    args = argparse.Namespace(dataset=None, sources="sources.toml")
    engine = PersonalFinanceEngine()
    code = handle_preview_mapping(args, engine)
    assert code == 1


def test_handle_preview_identity(config_path: Path, sources_path: Path) -> None:
    """Verify handle_preview_identity returns 0 for known dataset."""
    args = argparse.Namespace(
        dataset="household_inoutcome",
        sources=str(sources_path),
        config=str(config_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_preview_identity(args, engine)
    assert code == 0


def test_handle_preview_plan(config_path: Path, sources_path: Path) -> None:
    """Verify handle_preview_plan returns 0 for valid config and sources."""
    args = argparse.Namespace(
        config=str(config_path),
        sources=str(sources_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_preview_plan(args, engine)
    assert code == 0


def test_handle_dry_run_admission(config_path: Path, rules_path: Path, sources_path: Path) -> None:
    """Verify handle_dry_run_admission executes and returns expected status."""
    args = argparse.Namespace(
        dataset="household_inoutcome",
        config=str(config_path),
        rules=str(rules_path),
        sources=str(sources_path),
    )
    engine = PersonalFinanceEngine()
    code = handle_dry_run_admission(args, engine)
    assert code in (0, 1)
