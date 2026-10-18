#!/usr/bin/env python3
# pylint: skip-file
# flake8: noqa
"""Unified Quality Gate & Diagnostics Orchestration Engine.

Repository: personal-finance-etl
Architecture: Two-Tier Automated Quality Verification
- Tier 1 (Fast, ~2s): Ruff Check, Ruff Format Check, Mypy (Staged Pre-Commit)
- Tier 2 (Full, ~40s): Ruff, Format, Mypy, Pyright, Pylint, Pytest (Pre-Push & CI)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if sys.platform == "win32":
    reconfig_out = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig_out):
        reconfig_out(encoding="utf-8", errors="replace")
    reconfig_err = getattr(sys.stderr, "reconfigure", None)
    if callable(reconfig_err):
        reconfig_err(encoding="utf-8", errors="replace")

console = Console()

ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class DiagnosticIssue:
    """Normalized diagnostic issue from any static analysis engine."""

    engine: str
    file: str
    line: int
    column: int
    code: str
    severity: str
    message: str


def _empty_issues() -> list[DiagnosticIssue]:
    """Return a typed empty issue list for dataclass default factory."""
    return []


@dataclass
class EngineResult:
    """Result summary of a single diagnostic engine run."""

    name: str
    tier: str
    command: list[str]
    duration_seconds: float
    exit_code: int
    passed: bool
    issues: list[DiagnosticIssue] = field(default_factory=_empty_issues)
    raw_output: str = ""


# -----------------------------------------------------------------------------
# Output Parsers for Normalizing Diagnostic Issues
# -----------------------------------------------------------------------------


def _parse_ruff_output(output: str) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    # Match: path/file.py:line:col: CODE Message
    pattern = re.compile(r"^([^:]+):(\d+):(\d+):\s+([A-Z0-9]+)\s+(.*)$", re.MULTILINE)
    for match in pattern.finditer(output):
        fpath, line, col, code, msg = match.groups()
        issues.append(
            DiagnosticIssue(
                engine="Ruff",
                file=fpath.strip(),
                line=int(line),
                column=int(col),
                code=code.strip(),
                severity="Error" if code.startswith(("E", "F")) else "Warning",
                message=msg.strip(),
            )
        )
    return issues


def _parse_mypy_output(output: str) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    # Match: path/file.py:line: error: Message  [code]
    pattern = re.compile(
        r"^([^:]+):(\d+):\s+(error|warning|note):\s+(.*?)(?:\s+\[([a-z-]+)\])?$", re.MULTILINE
    )
    for match in pattern.finditer(output):
        fpath, line, sev, msg, code = match.groups()
        issues.append(
            DiagnosticIssue(
                engine="Mypy",
                file=fpath.strip(),
                line=int(line),
                column=0,
                code=(code or sev).strip(),
                severity=sev.capitalize(),
                message=msg.strip(),
            )
        )
    return issues


def _parse_pyright_output(output: str) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    # Match: path/file.py:line:col - error: Message (code)
    pattern = re.compile(
        r"^\s*([^:\n]+):(\d+):(\d+)\s+-\s+(error|warning|info):\s+(.*?)(?:\s+\(([a-zA-Z0-9]+)\))?$",
        re.MULTILINE,
    )
    for match in pattern.finditer(output):
        fpath, line, col, sev, msg, code = match.groups()
        issues.append(
            DiagnosticIssue(
                engine="Pyright",
                file=fpath.strip(),
                line=int(line),
                column=int(col),
                code=(code or sev).strip(),
                severity=sev.capitalize(),
                message=msg.strip(),
            )
        )
    return issues


def _parse_pylint_output(output: str) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    # Match: path/file.py:line:col: C0123: Message (symbol)
    pattern = re.compile(
        r"^([^:]+):(\d+):(\d+):\s+([CRWEF]\d+):\s+(.*?)(?:\s+\(([a-z-]+)\))?$", re.MULTILINE
    )
    for match in pattern.finditer(output):
        fpath, line, col, code, msg, symbol = match.groups()
        sev_map = {"E": "Error", "F": "Fatal", "W": "Warning", "R": "Refactor", "C": "Convention"}
        sev = sev_map.get(code[0], "Warning")
        issues.append(
            DiagnosticIssue(
                engine="Pylint",
                file=fpath.strip(),
                line=int(line),
                column=int(col),
                code=symbol or code,
                severity=sev,
                message=msg.strip(),
            )
        )
    return issues


def _parse_generic_failures(output: str, engine_name: str = "Generic") -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    for line in output.splitlines():
        if "FAILED " in line or "error:" in line.lower():
            issues.append(
                DiagnosticIssue(
                    engine=engine_name,
                    file="general",
                    line=0,
                    column=0,
                    code="FAIL",
                    severity="Error",
                    message=line.strip(),
                )
            )
    return issues


# -----------------------------------------------------------------------------
# Engine Execution Runner
# -----------------------------------------------------------------------------


def _run_engine(
    name: str,
    tier: str,
    command: list[str],
    parser_fn: Any,
) -> EngineResult:
    """Execute a single diagnostic engine command and capture metrics."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    duration = time.perf_counter() - t0
    raw = (proc.stdout + "\n" + proc.stderr).strip()

    passed = proc.returncode == 0
    issues: list[DiagnosticIssue] = []
    if not passed:
        issues = parser_fn(raw) if parser_fn else _parse_generic_failures(raw, engine_name=name)

    return EngineResult(
        name=name,
        tier=tier,
        command=command,
        duration_seconds=duration,
        exit_code=proc.returncode,
        passed=passed,
        issues=issues,
        raw_output=raw,
    )


# -----------------------------------------------------------------------------
# Orchestrator
# -----------------------------------------------------------------------------


def run_quality_gate(
    tier: str = "full",
    export: str = "cli",
    output_path: str | None = None,
    auto_fix: bool = False,
    quiet: bool = False,
) -> int:
    """Run all configured quality engines based on tier and report results."""
    console.print(
        Panel(
            f"[bold cyan]Local-First Quality Gate & Diagnostics[/bold cyan]\n"
            f"[dim]Repository:[/dim] personal-finance-etl | [dim]Tier:[/dim] [bold]{tier.upper()}[/bold] | "
            f"[dim]Export:[/dim] [bold]{export.upper()}[/bold]",
            border_style="cyan",
        )
    )

    if auto_fix:
        console.print("[yellow]>> Running auto-fix (Ruff lint & format)...[/yellow]")
        subprocess.run(["uv", "run", "ruff", "check", "--fix", "."], cwd=ROOT_DIR, check=False)
        subprocess.run(["uv", "run", "ruff", "format", "src/"], cwd=ROOT_DIR, check=False)

    # Engine Catalog
    # Tier 1 (Fast): Ruff Check, Ruff Format, Mypy
    # Tier 2 (Full): Fast + Pyright, Pylint, Pytest
    engine_specs: list[tuple[str, str, list[str], Any]] = [
        ("Ruff Check", "Fast", ["uv", "run", "ruff", "check", "."], _parse_ruff_output),
        (
            "Ruff Format",
            "Fast",
            ["uv", "run", "ruff", "format", "--check", "src/"],
            _parse_generic_failures,
        ),
        ("Mypy Typecheck", "Fast", ["uv", "run", "mypy"], _parse_mypy_output),
    ]

    if tier == "full":
        engine_specs.extend(
            [
                (
                    "Pyright Typecheck",
                    "Full",
                    ["uv", "run", "pyright"],
                    _parse_pyright_output,
                ),
                (
                    "Pylint Deep Analysis",
                    "Full",
                    ["uv", "run", "pylint", "src"],
                    _parse_pylint_output,
                ),
                (
                    "Pytest Suite",
                    "Full",
                    ["uv", "run", "pytest", "tests/", "-q"],
                    _parse_generic_failures,
                ),
            ]
        )

    results: list[EngineResult] = []
    total_start = time.perf_counter()

    for name, eng_tier, cmd, parser_fn in engine_specs:
        if not quiet:
            console.print(f"[dim]Running {name}...[/dim]", end="\r")
        res = _run_engine(name, eng_tier, cmd, parser_fn)
        results.append(res)
        status_label = (
            "[bold green]✓ PASS[/bold green]" if res.passed else "[bold red]✗ FAIL[/bold red]"
        )
        if not quiet:
            console.print(f"  {status_label} {name:<22} ({res.duration_seconds:.2f}s)")

    total_duration = time.perf_counter() - total_start
    all_passed = all(r.passed for r in results)

    # 1. Render CLI Table
    table = Table(title="\nQuality Gate Audit Summary", header_style="bold magenta")
    table.add_column("Engine", style="bold")
    table.add_column("Tier", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Issues", justify="right")
    table.add_column("Status", justify="center")

    total_issues = 0
    all_issues_list: list[DiagnosticIssue] = []

    for r in results:
        total_issues += len(r.issues)
        all_issues_list.extend(r.issues)
        status_str = "[bold green]PASS[/bold green]" if r.passed else "[bold red]FAIL[/bold red]"
        issues_str = "[green]0[/green]" if len(r.issues) == 0 else f"[red]{len(r.issues)}[/red]"
        table.add_row(r.name, r.tier, f"{r.duration_seconds:.2f}s", issues_str, status_str)

    console.print(table)

    # 2. Render Failure Diagnostics if any
    if not all_passed:
        console.print("\n[bold red]── Diagnostics / Failures Detected ──[/bold red]")
        for r in results:
            if not r.passed:
                console.print(f"\n[bold yellow]Engine:[/bold yellow] [bold red]{r.name}[/bold red]")
                if r.issues:
                    for iss in r.issues[:15]:  # Show top 15 issues per engine
                        console.print(
                            f"  [cyan]{iss.file}:{iss.line}[/cyan] [bold]{iss.code}[/bold] ({iss.severity}): {iss.message}"
                        )
                    if len(r.issues) > 15:
                        console.print(f"  [dim]... and {len(r.issues) - 15} more issues[/dim]")
                else:
                    # Generic output fallback
                    lines = r.raw_output.splitlines()[-10:]
                    console.print("  " + "\n  ".join(lines))

    # 3. Handle CSV / JSON Exports
    outputs_dir = ROOT_DIR / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().isoformat()

    if export in ("csv", "all"):
        csv_file = (
            Path(output_path)
            if output_path and export == "csv"
            else outputs_dir / "audit_report.csv"
        )
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Timestamp",
                    "Engine",
                    "Tier",
                    "File",
                    "Line",
                    "Column",
                    "Code",
                    "Severity",
                    "Message",
                ]
            )
            if all_issues_list:
                for iss in all_issues_list:
                    writer.writerow(
                        [
                            timestamp_str,
                            iss.engine,
                            tier,
                            iss.file,
                            iss.line,
                            iss.column,
                            iss.code,
                            iss.severity,
                            iss.message,
                        ]
                    )
            else:
                writer.writerow(
                    [
                        timestamp_str,
                        "ALL_ENGINES",
                        tier,
                        "None",
                        0,
                        0,
                        "CLEAN",
                        "Info",
                        "All checks passed cleanly",
                    ]
                )
        console.print(
            f"\n[bold green]✓ Structured CSV audit report written to:[/bold green] {csv_file}"
        )

    if export in ("json", "all"):
        json_file = (
            Path(output_path)
            if output_path and export == "json"
            else outputs_dir / "audit_report.json"
        )
        payload = {
            "timestamp": timestamp_str,
            "tier": tier,
            "all_passed": all_passed,
            "total_duration_seconds": round(total_duration, 2),
            "total_issues": total_issues,
            "engines": [
                {
                    "name": r.name,
                    "tier": r.tier,
                    "passed": r.passed,
                    "duration_seconds": round(r.duration_seconds, 2),
                    "exit_code": r.exit_code,
                    "issue_count": len(r.issues),
                    "issues": [asdict(iss) for iss in r.issues],
                }
                for r in results
            ],
        }
        with open(json_file, mode="w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        console.print(
            f"[bold green]✓ Structured JSON audit report written to:[/bold green] {json_file}"
        )

    # Summary Footer
    summary_color = "bold green" if all_passed else "bold red"
    status_text = "ALL QUALITY ENGINES PASSED" if all_passed else "QUALITY GATE FAILED"
    console.print(
        f"\n[{summary_color}]══ {status_text} (Total: {total_duration:.2f}s) ══[/{summary_color}]\n"
    )

    return 0 if all_passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified Quality Gate & Multi-Engine Diagnostics Orchestration."
    )
    parser.add_argument(
        "--tier",
        choices=["fast", "full"],
        default="full",
        help="Quality verification tier ('fast' for pre-commit, 'full' for pre-push and CI).",
    )
    parser.add_argument(
        "--export",
        choices=["cli", "csv", "json", "all"],
        default="cli",
        help="Output format: cli table, structured csv, structured json, or all.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Optional destination path for exported report file.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically apply safe formatting and lint fixes before running checks.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress intermediate execution progress logs.",
    )
    args = parser.parse_args()

    return run_quality_gate(
        tier=args.tier,
        export=args.export,
        output_path=args.output_path,
        auto_fix=args.fix,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
