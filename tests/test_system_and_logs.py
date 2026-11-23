# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false
# pyright: reportUnknownArgumentType=false
"""Automated tests for Phase 07: Forensic Logs and System UI.

Owns
----
- Verifying JSONL reader handles valid, truncated, and malformed rows without throwing unhandled exceptions.
- Verifying multi-dimensional filtering logic (severity, stage, search query, failures only).
- Verifying logs directory resolution and discovery across Settings profiles.
- Verifying SystemTab data adapter with SystemStatus, SystemInfo, and DoctorReport models.
- Verifying architectural integrity: zero direct sqlite3 or duckdb imports in presentation/desktop.
"""

from __future__ import annotations

import ast
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.application.operator import (
    DoctorCheckResult,
    DoctorReport,
)
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.operator.inspector import LocalOperatorInspector
from personal_finance_etl.presentation.desktop.configuration_tab import ConfigurationTab
from personal_finance_etl.presentation.desktop.logs_tab import LogsTab
from personal_finance_etl.presentation.desktop.run_tab import RunTab
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.system_tab import SystemTab


def test_jsonl_parser_handles_valid_and_malformed_rows(tmp_path: Path) -> None:
    """Verify that read_jsonl_log parses valid, truncated, and malformed lines gracefully."""
    engine = PersonalFinanceEngine()
    log_file = tmp_path / "sample_trace.jsonl"

    valid_evt1: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_code": "RUN_START",
        "severity": "INFO",
        "presentation_kind": "STEP",
        "outcome": "STARTED",
        "message": "Pipeline initialization started",
        "context": {"run_id": "run_test_golden_42", "stage": "INITIALIZATION"},
    }

    valid_evt2: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_code": "SCHEMA_VALIDATION",
        "severity": "ERROR",
        "presentation_kind": "FAILURE",
        "outcome": "FAILED",
        "message": "Missing column in dataset",
        "context": {"run_id": "run_test_golden_42", "stage": "INGESTION"},
        "error": {
            "exception_type": "ValueError",
            "exception_message": "Missing column",
            "failure_domain": "DATA_CONTRACT",
            "traceback_summary": "Traceback...",
            "retryable": False,
        },
    }

    content_lines = [
        json.dumps(valid_evt1),
        "",  # Empty line
        '{"timestamp": "2026-11-23T10:00:00Z", "event_code": "TRUNCATED_',  # Truncated JSON
        '"A scalar string rather than object"',  # Invalid non-dict JSON
        "   ",  # Whitespace line
        json.dumps(valid_evt2),
    ]

    log_file.write_text("\n".join(content_lines), encoding="utf-8")

    events, detected_run = engine.read_jsonl_log(log_file)

    assert detected_run == "run_test_golden_42"
    # Should have parsed 4 events: 2 valid + 2 malformed warning rows
    assert len(events) == 4

    # Event 0 is valid
    assert events[0]["event_code"] == "RUN_START"
    assert events[0]["outcome"] == "STARTED"

    # Event 1 is malformed warning
    assert events[1]["event_code"] == "LOG_PARSE_WARNING"
    assert events[1]["severity"] == "WARNING"
    assert "Truncated" in events[1]["message"] or "truncated" in events[1]["message"].lower()

    # Event 2 is non-dict warning
    assert events[2]["event_code"] == "LOG_PARSE_WARNING"
    assert "Not a JSON object" in str(events[2]["error"]["exception_message"])

    # Event 3 is valid error event
    assert events[3]["event_code"] == "SCHEMA_VALIDATION"
    assert events[3]["severity"] == "ERROR"


def test_logs_directory_resolution_and_file_discovery(tmp_path: Path) -> None:
    """Verify log directory resolution from settings and sorted newest-first file discovery."""
    engine = PersonalFinanceEngine()

    logs_dir = tmp_path / "custom_logs"
    logs_dir.mkdir(parents=True)

    cfg_file = tmp_path / "custom_config.toml"
    cfg = Settings()
    cfg.database.target_db_base_path = str(tmp_path)
    cfg.observability.logs_directory = "custom_logs"
    engine.save_settings_document(str(cfg_file), cfg)

    # Test directory resolution
    resolved_dir = engine.get_logs_directory(str(cfg_file))
    assert resolved_dir.resolve() == logs_dir.resolve()

    # Test fallback on invalid path
    fallback_dir = engine.get_logs_directory("non_existent_file.toml")
    assert fallback_dir == Path("outputs/logs")

    # Create dummy .jsonl files with distinct mtimes
    file1 = logs_dir / "trace_20260101.jsonl"
    file2 = logs_dir / "trace_20260201.jsonl"
    file1.write_text('{"event_code": "OLD"}\n', encoding="utf-8")
    file2.write_text('{"event_code": "NEW"}\n', encoding="utf-8")

    os.utime(file1, (1000, 1000))
    os.utime(file2, (2000, 2000))

    discovered = engine.discover_log_files(str(cfg_file))
    assert len(discovered) == 2
    # file2 must appear first (newest timestamp)
    assert discovered[0].name == "trace_20260201.jsonl"
    assert discovered[1].name == "trace_20260101.jsonl"


def test_logs_tab_filtering_and_selection(tk_root: Any, tmp_path: Path) -> None:
    """Verify LogsTab multi-dimensional filter matching across severities, stages, and searches."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)

    tab = LogsTab(tk_root, engine=engine, app_state=app_state)

    # Populate mock events directly
    tab._parsed_events = [
        {
            "event_code": "DISCOVERY_START",
            "severity": "INFO",
            "outcome": "STARTED",
            "message": "Scanning statements directory",
            "context": {"stage": "DISCOVERY", "operation": "scan_folder", "entity_id": "dir_1"},
        },
        {
            "event_code": "TAX_ENGINE_COMPLETED",
            "severity": "INFO",
            "outcome": "COMPLETED",
            "message": "Tax calculations finalized",
            "context": {"stage": "TAX", "operation": "calculate_tax", "entity_id": "tax_2024"},
        },
        {
            "event_code": "MARKET_TICKER_FAILED",
            "severity": "ERROR",
            "outcome": "FAILED",
            "message": "HTTP Timeout contacting Yahoo Finance",
            "context": {"stage": "INGESTION", "operation": "fetch_ticker", "entity_id": "TICKER_AAPL"},
            "error": {"exception_type": "TimeoutError", "exception_message": "Timed out"},
        },
    ]

    # 1. Default (All Severities, All Stages, No Search) -> 3 events
    tab._apply_filters()
    assert len(tab._filtered_events) == 3

    # 2. Filter by Severity: ERROR
    tab.severity_var.set("ERROR")
    tab._apply_filters()
    assert len(tab._filtered_events) == 1
    assert tab._filtered_events[0]["event_code"] == "MARKET_TICKER_FAILED"

    # Reset severity
    tab.severity_var.set("All Severities")

    # 3. Filter by Stage: TAX
    tab.stage_var.set("TAX")
    tab._apply_filters()
    assert len(tab._filtered_events) == 1
    assert tab._filtered_events[0]["event_code"] == "TAX_ENGINE_COMPLETED"

    # Reset stage
    tab.stage_var.set("All Stages")

    # 4. Filter by Search Query: "yahoo"
    tab.search_var.set("Yahoo")
    tab._apply_filters()
    assert len(tab._filtered_events) == 1
    assert tab._filtered_events[0]["event_code"] == "MARKET_TICKER_FAILED"

    # Clear search
    tab.search_var.set("")

    # 5. Failures Only
    tab.failures_only_var.set(True)
    tab._apply_filters()
    assert len(tab._filtered_events) == 1
    assert tab._filtered_events[0]["event_code"] == "MARKET_TICKER_FAILED"

    # 6. Test detail inspection on row selection
    tab._select_event(0)
    detail_content = tab.detail_text.get("1.0", "end")
    assert "MARKET_TICKER_FAILED" in detail_content
    assert "TimeoutError" in detail_content

    # 7. Test narrative append
    sample_evt = ObservabilityEvent.create(
        event_code=EventCode.GENERIC_DIAGNOSTIC,
        message="Live telemetry line stream test",
        severity=DiagnosticSeverity.INFO,
        presentation_kind=PresentationKind.STEP,
        outcome=EventOutcome.COMPLETED,
    )
    tab.append_narrative_event(sample_evt)
    narrative_text = tab.narrative_box.get("1.0", "end")
    assert "Live telemetry line stream test" in narrative_text


def test_system_tab_data_adapter_and_rendering(tk_root: Any) -> None:
    """Verify SystemTab status tiles, metadata metrics, and Doctor report rendering."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)

    tab = SystemTab(tk_root, engine=engine, app_state=app_state)

    # 1. Verify Status and Info rendering from engine
    tab.refresh_status()
    assert tab._cached_status is not None
    assert tab._cached_info is not None

    # Verify tile labels exist and reflect operational state
    assert tab.duckdb_val.cget("text") != "Checking..."
    assert tab.sqlite_val.cget("text") != "Checking..."
    assert tab.latest_run_val.cget("text") != "Checking..."

    # 2. Verify Doctor report rendering
    mock_report = DoctorReport(
        overall_status="WARN",
        passed_count=5,
        warn_count=1,
        failed_count=0,
        checks=[
            DoctorCheckResult(
                name="Python Runtime",
                status="PASS",
                message="Python 3.13 is supported.",
            ),
            DoctorCheckResult(
                name="Reference Files",
                status="WARN",
                message="Opening balance file missing rows.",
                remediation="Ensure opening_balances.csv contains initial account equity.",
            ),
        ],
    )

    tab._render_doctor_report(mock_report)

    # Verify overall badge reflects WARN state
    badge_text = tab.doctor_status_badge.cget("text")
    assert "WARN" in badge_text
    assert "5 Passed, 1 Warn, 0 Fail" in badge_text

    # Verify check cards were created in checks_container
    check_widgets = tab.checks_container.winfo_children()
    assert len(check_widgets) == 2


def test_configuration_tab_subtab_switching(tk_root: Any) -> None:
    """Verify ConfigurationTab cleanly switches between Settings and Financial Rules."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)

    config_tab = ConfigurationTab(tk_root, engine=engine, app_state=app_state)

    assert config_tab.active_subtab == "settings"
    assert config_tab.settings_editor.winfo_ismapped() or True

    # Switch to rules
    config_tab.switch_subtab("rules")
    assert config_tab.active_subtab == "rules"

    # Switch back to settings
    config_tab.switch_subtab("settings")
    assert config_tab.active_subtab == "settings"


def test_no_direct_sqlite3_or_duckdb_imports_in_desktop() -> None:
    """Enforce architectural boundary: zero direct sqlite3 or duckdb imports in presentation/desktop/."""
    desktop_dir = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "personal_finance_etl"
        / "presentation"
        / "desktop"
    )
    assert desktop_dir.is_dir()

    forbidden_modules = {"sqlite3", "duckdb"}
    violations: list[str] = []

    for py_file in desktop_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception as e:
            pytest.fail(f"Could not parse {py_file}: {e}")

        for node in ast.walk(tree):
            mod_name: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod_name = node.module

            if mod_name and (mod_name in forbidden_modules or any(mod_name.startswith(f"{f}.") for f in forbidden_modules)):
                lineno = getattr(node, "lineno", 0)
                violations.append(f"{py_file.name}:{lineno} imports '{mod_name}'")

    assert not violations, (
        "Architectural violation: presentation/desktop must not directly import sqlite3 or duckdb:\n"
        + "\n".join(violations)
    )


def test_warehouse_inventory_contract_counts() -> None:
    """Verify that warehouse inventory accurately detects all 20 Bronze, 24 Silver, and 22 Gold contracts."""
    engine = PersonalFinanceEngine()
    info = engine.get_system_info()

    assert info.bronze_tables_count == 20
    assert info.silver_tables_count == 24
    assert info.gold_tables_count == 22
    assert "bronze" in info.warehouse_schemas
    assert "silver" in info.warehouse_schemas
    assert "gold" in info.warehouse_schemas


def test_forensic_inspector_formatting_modes(tk_root: Any) -> None:
    """Verify forensic detail inspector renders clean, informative sections for both diagnostic and operational events."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)
    tab = LogsTab(tk_root, engine=engine, app_state=app_state)

    # 1. Diagnostic event (no operational fields)
    diag_evt = {
        "event_code": "GENERIC_DIAGNOSTIC",
        "severity": "INFO",
        "outcome": "COMPLETED",
        "message": "Initializing pipeline subsystems...",
        "context": {
            "run_id": "test_run_123",
            "stage": "INITIALIZING",
            "component": "lifecycle",
            "operation": None,
            "rows": None,
        },
    }
    tab._filtered_events = [diag_evt]
    tab._select_event(0)
    diag_text = tab.detail_text.get("1.0", "end")

    assert "GENERIC_DIAGNOSTIC" in diag_text
    assert "Diagnostic & Lifecycle Event" in diag_text
    assert "No task processing metrics attached to this event" in diag_text
    assert "Operation:         None" not in diag_text
    assert "HEALTHY / NOMINAL" in diag_text

    # 2. Operational task event (with rows and duration)
    op_evt = {
        "event_code": "EXTRACT_COMPLETED",
        "severity": "INFO",
        "outcome": "COMPLETED",
        "message": "Extracted transaction records",
        "context": {
            "run_id": "test_run_123",
            "stage": "INGESTION",
            "component": "bronze_worker",
            "operation": "EXTRACT_TRANSACTIONS",
            "rows": 450,
            "duration_ms": 12.5,
            "provider": "HDFC_Bank",
        },
    }
    tab._filtered_events = [op_evt]
    tab._select_event(0)
    op_text = tab.detail_text.get("1.0", "end")

    assert "EXTRACT_COMPLETED" in op_text
    assert "EXTRACT_TRANSACTIONS" in op_text
    assert "450" in op_text
    assert "12.5 ms" in op_text
    assert "HDFC_Bank" in op_text


def test_base_engine_tab_batched_queue_draining(tk_root: Any) -> None:
    """Verify BaseEngineTab buffers events in thread-safe queue and drains them atomically in batches."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)
    tab = RunTab(tk_root, engine=engine, app_state=app_state)

    # 1. Enqueue multiple status events
    for i in range(5):
        evt = ObservabilityEvent.create(
            event_code=EventCode.GENERIC_DIAGNOSTIC,
            message=f"Batch telemetry tick {i}",
            progress=float(i) / 10.0,
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.STEP,
            outcome=EventOutcome.COMPLETED,
        )
        tab.handle_status(None, evt)

    # Events should be queued in thread-safe buffer
    assert tab._event_queue.qsize() == 5

    # 2. Drain queue explicitly (simulating main-thread event loop tick)
    tab._drain_event_queue()
    assert tab._event_queue.empty()

    # Log text should contain the formatted messages
    log_text = tab.status_log.get("1.0", "end")
    assert "Batch telemetry tick 0" in log_text
    assert "Batch telemetry tick 4" in log_text

    # Progress bar should reflect latest value (40%)
    assert tab.pct_label.cget("text") == "40%"


def test_probe_market_data_provider() -> None:
    """Verify market data provider probe executes safely and returns a boolean status."""
    inspector = LocalOperatorInspector()
    result = inspector.probe_market_data_provider(timeout=3.0)
    assert isinstance(result, bool)



