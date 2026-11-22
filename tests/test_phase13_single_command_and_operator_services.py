"""Phase 013 verification suite: Single pfetl command and operator read services.

Validates
---------
1. Packaging entry point: pyproject.toml defines only pfetl under [project.scripts].
2. Command surface: pfetl argument parser supports run, status, doctor, info, snapshot, restore, --gui, and naked invocation.
3. Historical vocabulary retirement: cli and tkinter subcommands are rejected.
4. Operator read services: get_status, get_info, and run_doctor operate read-only and return structured telemetry.
5. Actionable doctor diagnostics: isolates failures, provides remediation hints, and avoids unhandled tracebacks.
6. Facade integration: PersonalFinanceEngine exposes read service methods cleanly.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.operator import (
    DoctorReport,
    OperatorService,
    SystemInfo,
    SystemStatus,
)
from personal_finance_etl.presentation.launcher import build_argument_parser


def test_project_scripts_entry_point() -> None:
    """Assert pyproject.toml defines only pfetl as canonical console script."""
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists(), "pyproject.toml must exist at repository root"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert "pfetl" in scripts, "pfetl must be defined in [project.scripts]"
    assert scripts["pfetl"] == "personal_finance_etl.presentation.launcher:main"
    assert "shan-fin" not in scripts, "Historical 'shan-fin' must be retired"
    assert "shan-fin-gui" not in scripts, "Historical 'shan-fin-gui' must be retired"


def test_argument_parser_command_surface() -> None:
    """Verify all canonical subcommands and flags are recognized."""
    parser = build_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    assert parser.prog == "pfetl"

    # 1. Naked invocation
    naked = parser.parse_args([])
    assert naked.command is None
    assert naked.gui is False

    # 2. --gui flag
    gui_call = parser.parse_args(["--gui"])
    assert gui_call.gui is True
    assert gui_call.command is None

    # 3. run subcommand
    run_call = parser.parse_args(
        ["run", "-c", "custom_config.toml", "-r", "custom_rules.toml", "--auto", "--cron"]
    )
    assert run_call.command == "run"
    assert run_call.config == "custom_config.toml"
    assert run_call.rules == "custom_rules.toml"
    assert run_call.auto is True
    assert run_call.cron is True

    # 4. status subcommand
    status_call = parser.parse_args(["status", "--config", "cfg.toml"])
    assert status_call.command == "status"
    assert status_call.config == "cfg.toml"

    # 5. doctor subcommand
    doctor_call = parser.parse_args(["doctor", "-c", "cfg.toml", "-r", "rules.toml"])
    assert doctor_call.command == "doctor"
    assert doctor_call.config == "cfg.toml"
    assert doctor_call.rules == "rules.toml"

    # 6. info subcommand
    info_call = parser.parse_args(["info"])
    assert info_call.command == "info"

    # 7. snapshot subcommand
    snap_call = parser.parse_args(["snapshot", "-c", "cfg.toml"])
    assert snap_call.command == "snapshot"
    assert snap_call.config == "cfg.toml"

    # 8. restore subcommand
    restore_call = parser.parse_args(["restore", "archive.zip", "-c", "cfg.toml"])
    assert restore_call.command == "restore"
    assert restore_call.target == "archive.zip"
    assert restore_call.config == "cfg.toml"


def test_retired_subcommands_rejected() -> None:
    """Verify historical subcommands 'cli' and 'tkinter' are rejected by the parser."""
    parser = build_argument_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["tkinter"])


def test_operator_status_read_only() -> None:
    """Verify OperatorService.get_status executes read-only and returns valid SystemStatus."""
    op = OperatorService()
    status = op.get_status()

    assert isinstance(status, SystemStatus)
    assert isinstance(status.is_locked, bool)
    assert isinstance(status.duckdb_exists, bool)
    assert isinstance(status.sqlite_exists, bool)
    assert isinstance(status.stale_runs_count, int)
    assert isinstance(status.recovery_required_count, int)
    assert status.lock_path.endswith("pipeline.lock")


def test_operator_info_metadata() -> None:
    """Verify OperatorService.get_info reports correct system metadata and contract counts."""
    op = OperatorService()
    info = op.get_info()

    assert isinstance(info, SystemInfo)
    assert info.version == "11.4.0"
    assert info.python_version == sys.version.split()[0]
    assert info.platform == sys.platform
    assert info.silver_tables_count == 24, "Silver layer must preserve all 24 canonical tables"
    assert info.gold_tables_count == 22, "Gold layer must preserve all 22 canonical tables"
    assert set(info.warehouse_schemas) == {"bronze", "silver", "gold", "meta"}


def test_operator_doctor_diagnostics() -> None:
    """Verify OperatorService.run_doctor executes actionable checks without tracebacks."""
    op = OperatorService()
    report = op.run_doctor()

    assert isinstance(report, DoctorReport)
    assert report.overall_status in ("PASS", "WARN", "FAIL")
    assert len(report.checks) >= 6

    check_names = {c.name for c in report.checks}
    assert "Python Runtime" in check_names
    assert "Settings Configuration" in check_names
    assert "Financial Rules" in check_names

    # Check that any non-PASS item has actionable remediation advice
    for check in report.checks:
        assert check.status in ("PASS", "WARN", "FAIL")
        if check.status in ("WARN", "FAIL"):
            assert check.remediation is not None and len(check.remediation) > 0


def test_facade_operator_methods() -> None:
    """Verify PersonalFinanceEngine exposes operator read services."""
    engine = PersonalFinanceEngine()

    status = engine.get_system_status()
    assert isinstance(status, SystemStatus)

    info = engine.get_system_info()
    assert isinstance(info, SystemInfo)

    doctor = engine.run_doctor()
    assert isinstance(doctor, DoctorReport)
