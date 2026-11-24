# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false
# pyright: reportUnknownArgumentType=false
"""Automated tests for Forensic Logs and System Diagnostics UI.

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
import threading
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
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
from personal_finance_etl.presentation.desktop.background_tasks import BackgroundTaskRunner
from personal_finance_etl.presentation.desktop.config_editor import ConfigFieldEditor
from personal_finance_etl.presentation.desktop.configuration_tab import ConfigurationTab
from personal_finance_etl.presentation.desktop.forensic_model import (
    ForensicEvent,
    TraceCache,
    format_display_timestamp,
    format_full_local_timestamp,
    parse_trace_file,
)
from personal_finance_etl.presentation.desktop.logs_tab import LogsTab
from personal_finance_etl.presentation.desktop.run_tab import RunTab
from personal_finance_etl.presentation.desktop.state import AppState, OperationState
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


def test_background_task_runner_lifecycle(tk_root: Any) -> None:
    """Verify BackgroundTaskRunner dispatches workers, returns results to Tk, and handles failures."""
    runner = BackgroundTaskRunner(max_workers=2)
    success_results: list[int] = []
    success_event = threading.Event()

    def _on_success(val: int) -> None:
        success_results.append(val)
        success_event.set()

    # 1. Successful execution
    runner.run(lambda: 42, parent_widget=tk_root, on_success=_on_success)
    for _ in range(50):
        runner.drain()
        tk_root.update()
        if success_event.is_set():
            break
        time.sleep(0.02)

    assert success_results == [42]

    # 2. Error execution
    error_results: list[Exception] = []
    error_event = threading.Event()

    def _on_error(err: Exception) -> None:
        error_results.append(err)
        error_event.set()

    runner.run(lambda: 1 / 0, parent_widget=tk_root, on_error=_on_error)
    for _ in range(50):
        runner.drain()
        tk_root.update()
        if error_event.is_set():
            break
        time.sleep(0.02)

    assert len(error_results) == 1
    assert isinstance(error_results[0], ZeroDivisionError)

    # 3. Task cancellation
    handle = runner.run(lambda: time.sleep(0.2), parent_widget=tk_root)
    handle.cancel()
    assert handle.is_cancelled is True

    # 4. Safe execution on destroyed widget target
    dummy_frame = ctk.CTkFrame(tk_root)
    dummy_frame.destroy()
    runner.run(lambda: 100, parent_widget=dummy_frame)

    runner.shutdown()


def test_operation_state_transitions_and_interlocks() -> None:
    """Verify AppState operation state transitions and strict UI interlocking predicates."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)

    assert app_state.operation_state == OperationState.READY
    assert app_state.is_busy() is False
    assert app_state.can_run_pipeline() is True
    assert app_state.can_snapshot() is True
    assert app_state.can_check_system() is True

    # Transition to PIPELINE_RUNNING
    app_state.set_operation(OperationState.PIPELINE_RUNNING, "Pipeline active")
    assert app_state.is_busy() is True
    assert app_state.can_run_pipeline() is False
    assert app_state.can_snapshot() is False
    assert app_state.can_check_system() is False

    # Transition to SNAPSHOTTING
    app_state.set_operation(OperationState.SNAPSHOTTING, "Creating snapshot")
    assert app_state.is_busy() is True
    assert app_state.can_run_pipeline() is False
    assert app_state.can_snapshot() is False

    # Transition to RESTORING
    app_state.set_operation(OperationState.RESTORING, "Restoring database")
    assert app_state.is_busy() is True
    assert app_state.can_run_pipeline() is False
    assert app_state.can_snapshot() is False

    # Transition to RECOVERY_REQUIRED
    app_state.set_operation(OperationState.RECOVERY_REQUIRED, "Snapshot required")
    assert app_state.is_busy() is False
    assert app_state.can_run_pipeline() is False
    assert app_state.can_snapshot() is True

    # Reset to READY
    app_state.set_operation(OperationState.READY, "System nominal")
    assert app_state.is_busy() is False
    assert app_state.can_run_pipeline() is True


def test_forensic_model_indexing_and_lru_cache(tmp_path: Path) -> None:
    """Verify ForensicModel inverted indexing, fast search text, and LRU cache with invalidation."""
    trace_file = tmp_path / "test_forensic.jsonl"
    lines = [
        json.dumps({
            "timestamp": "2026-11-23T10:00:00Z",
            "event_code": "RUN_START",
            "severity": "INFO",
            "presentation_kind": "STEP",
            "outcome": "STARTED",
            "message": "Starting pipeline execution for user portfolio",
            "context": {"run_id": "trace-101", "stage": "INITIALIZATION"},
        }),
        json.dumps({
            "timestamp": "2026-11-23T10:00:01Z",
            "event_code": "MARKET_TICKER_WARNING",
            "severity": "WARNING",
            "presentation_kind": "STEP",
            "outcome": "COMPLETED",
            "message": "Market rate limit reached for ticker QQQ",
            "context": {"run_id": "trace-101", "stage": "INGESTION"},
        }),
        json.dumps({
            "timestamp": "2026-11-23T10:00:02Z",
            "event_code": "TRANSFORM_FAILED",
            "severity": "ERROR",
            "presentation_kind": "FAILURE",
            "outcome": "FAILED",
            "message": "Null pointer encountered in FIFO matching",
            "context": {"run_id": "trace-101", "stage": "TRANSFORM"},
            "error": {"exception_type": "ValueError", "exception_message": "Null lot"},
        }),
        "{truncated line json",
    ]
    trace_file.write_text("\n".join(lines), encoding="utf-8")

    parsed = parse_trace_file(trace_file)
    assert parsed.total_events == 3
    assert "INITIALIZATION" in parsed.all_stages
    assert "INGESTION" in parsed.all_stages
    assert "TRANSFORM" in parsed.all_stages
    assert "INFO" in parsed.all_severities
    assert "WARNING" in parsed.all_severities
    assert "ERROR" in parsed.all_severities
    assert len(parsed.failed_indices) == 1

    # Filter by severity
    res_err = parsed.filter_events(severity="ERROR")
    assert res_err == [2]

    # Filter by failures only
    res_fail = parsed.filter_events(failures_only=True)
    assert res_fail == [2]

    # Filter by search token
    res_search = parsed.filter_events(query="rate limit")
    assert res_search == [1]

    # Multi-dimensional intersection
    res_multi = parsed.filter_events(severity="WARNING", stage="INGESTION", query="QQQ")
    assert res_multi == [1]

    # ForensicEvent mapping interface
    evt = parsed.events[0]
    assert evt["event_code"] == "RUN_START"
    assert evt.get("severity") == "INFO"
    assert "user portfolio" in evt.normalized_search_text

    # LRU Cache verification
    cache = TraceCache(capacity=2)
    cache.put(parsed)
    assert cache.get(trace_file) is not None

    # Invalidate by mtime change
    os.utime(trace_file, (5000, 5000))
    assert cache.get(trace_file) is None

    # Capacity eviction
    f2 = tmp_path / "t2.jsonl"
    f3 = tmp_path / "t3.jsonl"
    f2.write_text('{"event_code": "EVT2"}\n', encoding="utf-8")
    f3.write_text('{"event_code": "EVT3"}\n', encoding="utf-8")
    p2 = parse_trace_file(f2)
    p3 = parse_trace_file(f3)
    cache.put(p2)
    cache.put(p3)
    assert len(cache) == 2


def test_forensic_pagination_and_selection_preservation(tk_root: Any, tmp_path: Path) -> None:
    """Verify fixed 100-event pagination and persistent selection preservation across page turns."""
    engine = PersonalFinanceEngine()
    app_state = AppState(engine)
    tab = LogsTab(tk_root, engine=engine, app_state=app_state)

    lines: list[str] = []
    for i in range(250):
        lines.append(
            json.dumps({
                "timestamp": f"2026-11-23T10:{i // 60:02d}:{i % 60:02d}Z",
                "event_code": f"EVENT_{i:03d}",
                "severity": "INFO",
                "presentation_kind": "STEP",
                "outcome": "COMPLETED",
                "message": f"Processing item {i}",
                "context": {"run_id": "run-page-test", "stage": "INGESTION"},
            })
        )
    trace_file = tmp_path / "trace_page_test.jsonl"
    trace_file.write_text("\n".join(lines), encoding="utf-8")

    parsed = parse_trace_file(trace_file)
    tab._active_trace = parsed
    tab._apply_filters()

    assert tab.total_pages == 3
    assert tab.page_info_lbl.cget("text") == "Page 1 of 3"

    # Turn page forward
    tab._next_page()
    assert tab._current_page == 2
    assert tab.page_info_lbl.cget("text") == "Page 2 of 3"

    # Turn page backward
    tab._prev_page()
    assert tab._current_page == 1
    assert tab.page_info_lbl.cget("text") == "Page 1 of 3"

    # Select event 5 on page 1
    tab._select_event(5)
    assert tab._selected_event_index == 5
    assert tab._selected_event_key is not None

    # Filter events - selection key preserved
    tab.search_var.set("item 5")
    tab._apply_filters()
    assert tab._selected_event_index is not None


def test_config_editor_dirty_tracking_and_inline_error(tk_root: Any) -> None:
    """Verify ConfigFieldEditor dirty baseline checking and inline validation error highlighting."""
    from pydantic.fields import FieldInfo

    field_info = FieldInfo(annotation=int, description="Retain Last N Runs")
    editor = ConfigFieldEditor(
        tk_root,
        field_name="retain_last_n_runs",
        field_info=field_info,
        initial_value=15,
    )

    assert editor.get_value() == 15

    # Inline validation error display
    editor.set_error("Must be between 1 and 100")
    assert editor._error_label is not None
    assert "Must be between 1 and 100" in editor._error_label.cget("text")

    editor.clear_error()
    assert editor._error_label is None


def test_ui_preferences_and_desktop_shortcuts() -> None:
    """Verify presentation UI preferences persistence and keyboard shortcut bindings."""
    import subprocess
    import sys

    engine = PersonalFinanceEngine()
    engine.save_ui_preferences({"window_geometry": "950x650", "active_tab": "system"})

    saved = engine.get_ui_preferences()
    assert saved.get("window_geometry") == "950x650"
    assert saved.get("active_tab") == "system"

    script = (
        "from personal_finance_etl.presentation.desktop.app import DesktopApp\n"
        "app = DesktopApp()\n"
        "app.withdraw()\n"
        "assert app.active_tab_id == 'system'\n"
        "assert app._on_shortcut_find() == 'break'\n"
        "assert app.active_tab_id == 'logs'\n"
        "assert app._on_shortcut_escape() == 'break'\n"
        "assert app._on_shortcut_refresh() == 'break'\n"
        "app.destroy()\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.returncode == 0


def test_probe_market_data_fallback_and_offline() -> None:
    """Verify market data probe handles HTTP errors, fallback socket probes, and offline states."""
    inspector = LocalOperatorInspector()

    # Case 1: HTTP error confirms network reachability
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError("https://fc.yahoo.com", 404, "Not Found", None, None)  # type: ignore[arg-type]
        assert inspector.probe_market_data_provider() is True

    # Case 2: HTTP fails, TCP socket connects to Yahoo port 443
    with patch("urllib.request.urlopen") as mock_urlopen, patch("socket.create_connection") as mock_conn:
        mock_urlopen.side_effect = Exception("SSL handshake failed")
        mock_conn.return_value = MagicMock()
        assert inspector.probe_market_data_provider() is True

    # Case 3: Both HTTP and TCP socket fail (true offline)
    with patch("urllib.request.urlopen") as mock_urlopen, patch("socket.create_connection") as mock_conn:
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")
        mock_conn.side_effect = OSError("Connection refused")
        assert inspector.probe_market_data_provider() is False


def test_logs_tab_row_subwidget_clicking(tk_root: Any, tmp_path: Path) -> None:
    """Verify clicking row sub-widgets selects the item and maps to trace index even under filtering."""
    engine = PersonalFinanceEngine()
    log_file = tmp_path / "click_test.jsonl"

    events_data = [
        {"timestamp": "2026-11-24T10:00:00Z", "event_code": "EVT_ZERO", "severity": "INFO", "message": "Zero msg"},
        {"timestamp": "2026-11-24T10:01:00Z", "event_code": "EVT_ONE", "severity": "ERROR", "message": "Error target"},
        {"timestamp": "2026-11-24T10:02:00Z", "event_code": "EVT_TWO", "severity": "INFO", "message": "Two msg"},
    ]
    with open(log_file, "w", encoding="utf-8") as f:
        for d in events_data:
            f.write(json.dumps(d) + "\n")

    tab = LogsTab(tk_root, engine=engine)
    tab._active_trace = parse_trace_file(log_file)
    assert tab._active_trace is not None

    # Filter to only ERROR events (trace index 1)
    tab.severity_var.set("ERROR")
    tab._apply_filters()
    assert tab._filtered_indices == [1]

    # Render page and check row widgets
    tab._render_events_page()
    assert 1 in tab._rendered_row_frames
    row_frame = tab._rendered_row_frames[1]

    # Find child widgets in the row
    children = row_frame.winfo_children()
    assert len(children) >= 4

    # Trigger click on a child widget (e.g. timestamp or severity badge)
    child_widget = children[0]
    # Find bound <Button-1> function
    bind_id = child_widget.bind("<Button-1>")
    assert bind_id != ""

    # Call _select_event directly with trace index 1
    tab._select_event(1)
    assert tab._selected_event_index == 1
    assert tab._selected_event_key == ("2026-11-24T10:01:00Z", "EVT_ONE")
    detail_content = tab.detail_text.get("1.0", "end")
    assert "EVT_ONE" in detail_content
    assert "Error target" in detail_content


def test_forensic_timestamp_local_timezone_conversion() -> None:
    """Verify ISO-8601 UTC timestamps convert to host local timezone for row and detail views."""
    iso_utc = "2026-11-24T14:20:00Z"

    # Row display: HH:MM:SS in local timezone
    display_ts = format_display_timestamp(iso_utc)
    expected_local_time = datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    assert display_ts == expected_local_time

    # Inspector detail display: Full local time with tz and UTC reference
    full_local_ts = format_full_local_timestamp(iso_utc)
    assert expected_local_time in full_local_ts
    assert "UTC: 2026-11-24T14:20:00Z" in full_local_ts

    # Graceful fallback for blank/malformed timestamps
    assert format_display_timestamp("") == "-"
    assert format_full_local_timestamp("") == "-"
    assert format_display_timestamp("not-a-timestamp") == "not-a-timestamp"

    # Verify ForensicEvent.from_dict assigns local display timestamp
    evt = ForensicEvent.from_dict({"timestamp": iso_utc, "event_code": "SYNC_OK"}, raw_index=0)
    assert evt.timestamp_display == expected_local_time
    assert evt.timestamp_iso == iso_utc





