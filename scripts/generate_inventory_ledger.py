"""Automated AST Census and Migration Ledger Generator for Logging Infrastructure.

Owns
----
- Complete AST extraction of legacy logging and status callsites across the codebase.
- Canonical classification into EventCode, Audience, DiagnosticSeverity, Context, and Action.
- Generation of the structured migration ledger in `.planning/logging_inventory_ledger.md`.

Does not own
-------------
- Pipeline event emission logic (owned by application.observability).
- Runtime logging handler setup (owned by infrastructure.logging).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Final

ROOT_DIR: Final[Path] = Path(__file__).resolve().parent.parent
SRC_DIR: Final[Path] = ROOT_DIR / "src" / "personal_finance_etl"
PLANNING_DIR: Final[Path] = ROOT_DIR / ".planning"
LEDGER_OUTPUT_PATH: Final[Path] = PLANNING_DIR / "logging_inventory_ledger.md"

PREFIX_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[([A-Z0-9_\-:\*]+)\]")


@dataclass(frozen=True)
class LedgerEntry:
    """Represents a single inventoried logging or status callsite."""

    callsite: str
    component: str
    call_type: str
    raw_code: str
    event_code: str
    audience: str
    severity: str
    context: str
    action: str


def _classify_severity(func_name: str, raw_snippet: str) -> str:
    """Classify legacy call into canonical DiagnosticSeverity."""
    upper = func_name.upper()
    if upper == "EXCEPTION":
        return "ERROR"
    if upper in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return upper
    if "level=LogLevel.ERROR" in raw_snippet or "is_error=True" in raw_snippet:
        return "ERROR"
    if "level=LogLevel.WARNING" in raw_snippet:
        return "WARNING"
    if "level=LogLevel.STEP" in raw_snippet:
        return "STEP"
    if "level=LogLevel.SUCCESS" in raw_snippet:
        return "SUCCESS"
    return "INFO"


def _classify_audience(rel_path: str, severity: str, is_esm: bool) -> str:
    """Classify target audience: USER, FORENSIC, or CONTROL_PLANE."""
    if is_esm:
        return "USER"
    if severity in ("INFO", "STEP", "SUCCESS") and any(
        k in rel_path for k in ("application/pipeline", "application/ingestion", "presentation")
    ):
        return "USER"
    if severity == "ERROR" and any(k in rel_path for k in ("lifecycle", "control_plane")):
        return "USER, CONTROL_PLANE"
    return "FORENSIC"


def _derive_event_code(rel_path: str, raw_snippet: str, prefix: str) -> str:
    """Map legacy log call to a canonical EventCode."""
    if "lifecycle.py" in rel_path:
        if "log_run_start" in raw_snippet or "initializing" in raw_snippet.lower():
            return "LIFECYCLE_RUN_START"
        if "commit" in raw_snippet.lower():
            return "LIFECYCLE_RUN_COMMITTED"
        if "failure" in raw_snippet.lower() or "critical" in raw_snippet.lower():
            return "LIFECYCLE_RUN_FAILED"
        if "teardown" in raw_snippet.lower() or "cleaning" in raw_snippet.lower():
            return "LIFECYCLE_TEARDOWN"

    if prefix:
        clean = prefix.replace(":", "_").replace("*", "ALL")
        return f"PREFIX_{clean}"

    if "quant_service" in rel_path or "quant" in rel_path:
        return "QUANT_DIAGNOSTIC"
    if "isin" in rel_path:
        return "ISIN_WORKER_DIAGNOSTIC"
    if "market_sync" in rel_path or "market" in rel_path:
        return "MARKET_SYNC_DIAGNOSTIC"
    if "coordinator" in rel_path or "extractor" in rel_path:
        return "EXTRACTION_DIAGNOSTIC"
    if "transformer" in rel_path:
        return "TRANSFORM_DIAGNOSTIC"
    if "bronze" in rel_path:
        return "BRONZE_LAKEHOUSE_DIAGNOSTIC"
    if "silver" in rel_path:
        return "SILVER_MART_DIAGNOSTIC"
    if "gold" in rel_path:
        return "GOLD_MART_DIAGNOSTIC"
    if "meta" in rel_path:
        return "META_LAYER_DIAGNOSTIC"
    if "recovery" in rel_path or "restore" in rel_path or "backup" in rel_path:
        return "RECOVERY_DIAGNOSTIC"
    if "control_plane" in rel_path:
        return "CONTROL_PLANE_DIAGNOSTIC"
    if "worker.py" in rel_path:
        return "WORKER_STATUS_CAPTURE"

    return "GENERIC_APPLICATION_DIAGNOSTIC"


def _derive_context(rel_path: str) -> str:
    """Identify relevant contextual fields for the callsite."""
    fields: list[str] = ["run_id", "stage", "component"]
    if "isin" in rel_path:
        fields.extend(["isin", "worker_id", "rows"])
    elif "market" in rel_path:
        fields.extend(["provider", "attempt", "duration_ms"])
    elif "warehouse" in rel_path:
        fields.extend(["table_name", "rows", "duration_ms"])
    elif "lifecycle" in rel_path:
        fields.extend(["commit_state", "failure_domain", "duration_ms"])
    return ", ".join(fields)


def _derive_action(severity: str, prefix: str, is_esm: bool, raw_snippet: str) -> str:
    """Determine modern migration action for the legacy callsite."""
    if is_esm:
        return "MIGRATE_TO_USER_NARRATIVE"
    if prefix:
        return "CONVERT_PREFIX_TO_STRUCTURED_EVENT"
    if severity in ("STEP", "SUCCESS") or ("phase" in raw_snippet.lower()):
        return "MIGRATE_TO_USER_NARRATIVE"
    if any(k in raw_snippet.lower() for k in ("loop", "fifo", "per-row", "iter")):
        return "RESTRICT_TO_TRACE"
    return "MIGRATE_TO_FORENSIC_EVENT"


def scan_codebase() -> list[LedgerEntry]:
    """Scan all Python files under SRC_DIR and produce a typed inventory."""
    entries: list[LedgerEntry] = []

    for py_path in sorted(SRC_DIR.rglob("*.py")):
        rel_path = str(py_path.relative_to(SRC_DIR)).replace("\\", "/")
        lines = py_path.read_text(encoding="utf-8").splitlines()
        try:
            tree = ast.parse("\n".join(lines), filename=str(py_path))
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_logger = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "logger"
            )
            is_esm = (isinstance(func, ast.Name) and func.id == "EngineStatusMessage") or (
                isinstance(func, ast.Attribute) and func.attr == "EngineStatusMessage"
            )

            if not (is_logger or is_esm):
                continue

            lineno = node.lineno
            raw_snippet = lines[lineno - 1].strip() if lineno <= len(lines) else ""
            call_type = "logger" if is_logger else "EngineStatusMessage"
            func_name = (
                func.attr
                if (is_logger and isinstance(func, ast.Attribute))
                else "EngineStatusMessage"
            )

            prefix_match = PREFIX_PATTERN.search(raw_snippet)
            prefix = prefix_match.group(1) if prefix_match else ""

            severity = _classify_severity(func_name, raw_snippet)
            audience = _classify_audience(rel_path, severity, is_esm)
            event_code = _derive_event_code(rel_path, raw_snippet, prefix)
            context = _derive_context(rel_path)
            action = _derive_action(severity, prefix, is_esm, raw_snippet)
            component = rel_path.split("/")[0]

            entries.append(
                LedgerEntry(
                    callsite=f"{rel_path}:{lineno}",
                    component=component,
                    call_type=call_type,
                    raw_code=raw_snippet[:100],
                    event_code=event_code,
                    audience=audience,
                    severity=severity,
                    context=context,
                    action=action,
                )
            )

    # Add QueueStream and Control Plane persistence callsites
    entries.append(
        LedgerEntry(
            callsite="application/pipeline/worker.py:124-125",
            component="application",
            call_type="QueueStream",
            raw_code="sys.stdout = QueueStream(status_queue, is_error=False)",
            event_code="STREAM_STDOUT_CAPTURE",
            audience="FORENSIC",
            severity="DEBUG",
            context="run_id, stage, worker_id",
            action="DEMOLISH_SEVERITY_INFERENCE",
        )
    )
    entries.append(
        LedgerEntry(
            callsite="application/pipeline/lifecycle.py:326",
            component="application",
            call_type="ControlPlanePersistence",
            raw_code="self.cp.runs.save_execution_log(self.run_id, compressed_log)",
            event_code="CONTROL_PLANE_ARCHIVE_LOG",
            audience="CONTROL_PLANE",
            severity="INFO",
            context="run_id, log_size_bytes, compression_ratio",
            action="BENCHMARK_AND_OPTIMIZE_ZLIB_LEVEL",
        )
    )
    entries.append(
        LedgerEntry(
            callsite="application/pipeline/lifecycle.py:308",
            component="application",
            call_type="ControlPlaneTelemetry",
            raw_code="self._persist_failure_telemetry(exc)",
            event_code="CONTROL_PLANE_FAIL_TELEMETRY",
            audience="CONTROL_PLANE, USER",
            severity="ERROR",
            context="run_id, stage, failure_domain, exception_type",
            action="MIGRATE_TO_STRUCTURED_FAILURE_EVENT",
        )
    )

    return entries


def render_ledger_markdown(entries: list[LedgerEntry]) -> str:
    """Render the complete migration ledger into GitHub-flavored Markdown."""
    total_calls = len(entries)
    logger_calls = sum(1 for e in entries if e.call_type == "logger")
    esm_calls = sum(1 for e in entries if e.call_type == "EngineStatusMessage")
    other_calls = total_calls - logger_calls - esm_calls

    by_layer: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_audience: dict[str, int] = {}
    by_action: dict[str, int] = {}

    for e in entries:
        by_layer[e.component] = by_layer.get(e.component, 0) + 1
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        by_audience[e.audience] = by_audience.get(e.audience, 0) + 1
        by_action[e.action] = by_action.get(e.action, 0) + 1

    lines: list[str] = [
        "# Complete Logging & Status Migration Ledger (Phase 0)",
        "",
        "> **Classification Schema:** `callsite → event code → audience → severity → context → action`",
        "",
        "## 1. Executive Summary & Census Statistics",
        "",
        f"- **Total Inventoried Callsites:** {total_calls}",
        f"  - Python `logger` Callsites: {logger_calls}",
        f"  - `EngineStatusMessage` Producers: {esm_calls}",
        f"  - Pipeline Streams / Control Plane Telemetry: {other_calls}",
        "",
        "### Breakdown by Architectural Layer",
        "",
        "| Layer | Callsite Count | % of Total |",
        "|---|---|---|",
    ]
    for layer, count in sorted(by_layer.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| `{layer}` | {count} | {count / total_calls * 100:.1f}% |")

    lines.extend([
        "",
        "### Breakdown by Diagnostic Severity",
        "",
        "| Severity | Count | % of Total |",
        "|---|---|---|",
    ])
    for sev, count in sorted(by_severity.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| `{sev}` | {count} | {count / total_calls * 100:.1f}% |")

    lines.extend([
        "",
        "### Breakdown by Audience Projection",
        "",
        "| Audience | Count | Target Sink |",
        "|---|---|---|",
    ])
    for aud, count in sorted(by_audience.items(), key=lambda x: x[1], reverse=True):
        sink = "CLI / Desktop UI" if "USER" in aud else "JSONL Async Debug Trace"
        if "CONTROL_PLANE" in aud:
            sink += " & Control Plane SQLite"
        lines.append(f"| `{aud}` | {count} | {sink} |")

    lines.extend([
        "",
        "### Breakdown by Migration Action",
        "",
        "| Migration Action | Count | Modernization Phase |",
        "|---|---|---|",
    ])
    for act, count in sorted(by_action.items(), key=lambda x: x[1], reverse=True):
        phase_str = "Phase 4 & 5" if "USER" in act else "Phase 5 & 6"
        if "PREFIX" in act:
            phase_str = "Phase 5 (Prefix Demolition)"
        elif "DEMOLISH" in act:
            phase_str = "Phase 9 (Demolition)"
        elif "BENCHMARK" in act:
            phase_str = "Phase 7 (Control Plane)"
        lines.append(f"| `{act}` | {count} | {phase_str} |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Complete Inventory Ledger",
        "",
        "| Callsite | Event Code | Audience | Severity | Context Fields | Modern Action |",
        "|---|---|---|---|---|---|",
    ])

    for e in entries:
        safe_callsite = f"`{e.callsite}`"
        lines.append(
            f"| {safe_callsite} | `{e.event_code}` | {e.audience} | `{e.severity}` | `{e.context}` | `{e.action}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Execute inventory scan and write migration ledger markdown."""
    entries = scan_codebase()
    markdown = render_ledger_markdown(entries)
    PLANNING_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(f"Successfully generated Migration Ledger with {len(entries)} callsites at {LEDGER_OUTPUT_PATH}")


if __name__ == "__main__":
    main()

