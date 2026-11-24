"""Forensic telemetry and live narrative observability log viewer tab.

Owns
----
- LogsTab: Dual sub-view presentation container (Live Narrative and Forensic JSONL).
- Live narrative terminal with text streaming, copy, and clear controls.
- Forensic JSONL inspector: run/trace selector, multi-dimensional filters
  (severity, stage, search query, failures only), fixed 100-event pagination,
  debounced search, compact row rendering, and structured context/error drill-down pane.

Does not own
-------------
- JSONL file persistence or event emission (owned by infrastructure.observability).
- Database querying or pipeline execution (owned by application.pipeline).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC
from pathlib import Path
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.presentation.desktop.background_tasks import get_background_runner
from personal_finance_etl.presentation.desktop.forensic_model import (
    ForensicEvent,
    ParsedTrace,
    format_full_local_timestamp,
    get_trace_cache,
    parse_trace_file,
)
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import LOG_TAG_COLORS, Color

__all__ = ["LogsTab"]

PAGE_SIZE = 100


def _open_directory(dir_path: Path | str) -> None:
    """Open a directory in the host system file explorer safely."""
    # pylint: disable=consider-using-with
    path_str = str(dir_path)
    if not os.path.exists(path_str):
        return
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", path_str])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path_str])
        else:
            subprocess.Popen(["xdg-open", path_str])
    except Exception:
        pass


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTkFrame base class
class LogsTab(ctk.CTkFrame):  # type: ignore[misc]  # pylint: disable=too-many-instance-attributes
    """Full-featured Observability and Forensic Trace Analysis Tab."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
    ) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state

        self.active_subtab: str = "forensic"
        self.subtab_buttons: dict[str, ctk.CTkButton] = {}

        # Log state
        self._discovered_files: list[Path] = []
        self._parsed_events: list[Any] = []
        self._filtered_events: list[Any] = []
        self._filtered_indices: list[int] = []
        self._active_trace: ParsedTrace | None = None
        self._selected_event_index: int | None = None
        self._selected_event_key: tuple[str, str] | None = None

        # Pagination & Debounce state
        self._current_page: int = 1
        self._load_generation: int = 0
        self._search_debounce_job: str | None = None

        # Row widget tracking for fast selection toggles
        self._rendered_row_frames: dict[int, ctk.CTkFrame] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top sub-navigation
        self.grid_rowconfigure(1, weight=1)  # Sub-tab content area

        self._build_top_bar()
        self._build_subviews()

        # Lazy loading state
        self._loaded: bool = False

    def ensure_loaded(self) -> None:
        """Lazily scan and load log traces on first view."""
        if not self._loaded:
            self._loaded = True
            self.refresh_runs()

    def focus_search(self) -> None:
        """Switch to forensic sub-tab if needed and focus the search entry."""
        if self.active_subtab != "forensic":
            self.switch_subtab("forensic")
        if hasattr(self, "search_entry") and self.search_entry.winfo_exists():
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")

    def clear_search(self) -> None:
        """Clear the free-text search query in forensic logs."""
        if hasattr(self, "search_var"):
            self.search_var.set("")

    def get_filter_preferences(self) -> dict[str, object]:
        """Return current forensic filter presentation preferences."""
        prefs: dict[str, object] = {
            "severity": self.severity_var.get()
            if hasattr(self, "severity_var")
            else "All Severities",
            "stage": self.stage_var.get() if hasattr(self, "stage_var") else "All Stages",
            "failures_only": self.failures_only_var.get()
            if hasattr(self, "failures_only_var")
            else False,
        }
        if self._active_trace is not None and os.path.isfile(self._active_trace.filepath):
            prefs["selected_trace"] = os.path.basename(self._active_trace.filepath)
        return prefs

    def apply_preferences(self, prefs: Mapping[str, object]) -> None:
        """Apply saved presentation filter preferences safely."""
        filters = prefs.get("forensic_filters")
        if isinstance(filters, dict):
            sev = filters.get("severity")
            if isinstance(sev, str) and hasattr(self, "severity_var"):
                self.severity_var.set(sev)
            stage = filters.get("stage")
            if isinstance(stage, str) and hasattr(self, "stage_var"):
                self.stage_var.set(stage)
            failures = filters.get("failures_only")
            if isinstance(failures, bool) and hasattr(self, "failures_only_var"):
                self.failures_only_var.set(failures)
            trace_name = filters.get("selected_trace")
            if isinstance(trace_name, str) and hasattr(self, "runs_combo"):
                for val in self.runs_combo.cget("values"):
                    if trace_name in val:
                        self.runs_combo.set(val)
                        self._on_run_selected(val)
                        break

    # ── 1. Top Sub-Navigation Bar ─────────────────────────────────────────────

    def _build_top_bar(self) -> None:
        """Construct the top sub-navigation bar switching between Narrative and Forensic."""
        top_frame = ctk.CTkFrame(self, fg_color="#0F1420", height=42, corner_radius=0)
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)

        switcher_frame = ctk.CTkFrame(
            top_frame,
            fg_color="#151D2E",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        switcher_frame.pack(side="left", padx=16, pady=6)

        specs = [
            ("narrative", "💬  Live Narrative"),
            ("forensic", "🔬  Forensic JSONL"),
        ]

        for sub_id, label in specs:
            btn = ctk.CTkButton(
                switcher_frame,
                text=label,
                width=150,
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=Color.ACCENT if sub_id == self.active_subtab else "transparent",
                hover_color=Color.ACC_HOV if sub_id == self.active_subtab else "#1E293B",
                text_color="#FFFFFF" if sub_id == self.active_subtab else "#94A3B8",
                corner_radius=5,
                command=lambda sid=sub_id: self.switch_subtab(sid),
            )
            btn.pack(side="left", padx=2, pady=2)
            self.subtab_buttons[sub_id] = btn

    def switch_subtab(self, sub_id: str) -> None:
        """Switch active observability sub-tab view."""
        if sub_id == self.active_subtab:
            return

        self.active_subtab = sub_id

        for sid, btn in self.subtab_buttons.items():
            if sid == sub_id:
                btn.configure(
                    fg_color=Color.ACCENT,
                    hover_color=Color.ACC_HOV,
                    text_color="#FFFFFF",
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color="#1E293B",
                    text_color="#94A3B8",
                )

        if sub_id == "narrative":
            self.forensic_frame.grid_remove()
            self.narrative_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.narrative_frame.grid_remove()
            self.forensic_frame.grid(row=0, column=0, sticky="nsew")

    # ── 2. Subviews Container ─────────────────────────────────────────────────

    def _build_subviews(self) -> None:
        """Instantiate both Narrative and Forensic sub-view frames."""
        self.content_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self._build_narrative_view()
        self._build_forensic_view()

        # Show initially active subtab
        if self.active_subtab == "forensic":
            self.narrative_frame.grid_remove()
            self.forensic_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.forensic_frame.grid_remove()
            self.narrative_frame.grid(row=0, column=0, sticky="nsew")

    # ── 3. Live Narrative Terminal ────────────────────────────────────────────

    def _build_narrative_view(self) -> None:
        """Construct the live narrative streaming terminal view."""
        self.narrative_frame = ctk.CTkFrame(self.content_container, fg_color=Color.BG)
        self.narrative_frame.grid_columnconfigure(0, weight=1)
        self.narrative_frame.grid_rowconfigure(0, weight=0)  # Toolbar
        self.narrative_frame.grid_rowconfigure(1, weight=1)  # Monospace Terminal

        toolbar = ctk.CTkFrame(self.narrative_frame, fg_color="transparent", height=38)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))

        ctk.CTkLabel(
            toolbar,
            text="Real-Time Execution Narrative",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left", pady=6)

        ctk.CTkButton(
            toolbar,
            text="Clear",
            width=70,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._clear_narrative,
        ).pack(side="right", padx=(4, 12), pady=6)

        ctk.CTkButton(
            toolbar,
            text="Copy All",
            width=75,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._copy_narrative,
        ).pack(side="right", padx=4, pady=6)

        self.narrative_box = ctk.CTkTextbox(
            self.narrative_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=Color.LOG_BG,
            text_color="#CBD5E1",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.narrative_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))

        for tag_name, hex_color in LOG_TAG_COLORS.items():
            self.narrative_box.tag_config(tag_name, foreground=hex_color)

    def append_narrative_batch(self, events: list[ObservabilityEvent]) -> None:
        """Stream a batch of ObservabilityEvents into the narrative terminal atomically."""
        lines_to_add: list[tuple[str, str]] = []
        for event in events:
            if event.presentation_kind == PresentationKind.INTERNAL or not event.message.strip():
                continue
            if event.event_code in (
                EventCode.MARKET_TICKER_SUCCESS,
                EventCode.MARKET_TICKER_CACHE_HIT,
                EventCode.QUANT_ISIN_PROCESSED,
            ) and event.presentation_kind in (PresentationKind.STEP, PresentationKind.SUCCESS):
                continue
            dt = event.timestamp
            if dt.tzinfo is not None:
                ts_str = dt.astimezone().strftime("%H:%M:%S")
            else:
                ts_str = dt.replace(tzinfo=UTC).astimezone().strftime("%H:%M:%S")
            kind_str = str(event.presentation_kind).lower()
            tag = kind_str if kind_str in LOG_TAG_COLORS else "info"
            lines_to_add.append((f"[{ts_str}] {event.message}\n", tag))

        if not lines_to_add:
            return

        self.narrative_box.configure(state="normal")
        for line, tag in lines_to_add:
            self.narrative_box.insert("end", line, tag)
        line_count = int(self.narrative_box._textbox.index("end-1c").split(".", maxsplit=1)[0])
        if line_count > 5000:
            self.narrative_box._textbox.delete("1.0", f"{line_count - 4500}.0")
        self.narrative_box.see("end")
        self.narrative_box.configure(state="disabled")

    def append_narrative_event(self, event: ObservabilityEvent) -> None:
        """Stream a single ObservabilityEvent into the narrative terminal."""
        self.append_narrative_batch([event])

    def _clear_narrative(self) -> None:
        """Clear narrative terminal contents."""
        self.narrative_box.configure(state="normal")
        self.narrative_box.delete("1.0", "end")
        self.narrative_box.configure(state="disabled")

    def _copy_narrative(self) -> None:
        """Copy all text from narrative terminal to clipboard."""
        text = self.narrative_box.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)

    # ── 4. Forensic JSONL View ────────────────────────────────────────────────

    def _build_forensic_view(self) -> None:
        """Construct the Forensic JSONL multi-pane trace analysis interface."""
        self.forensic_frame = ctk.CTkFrame(self.content_container, fg_color=Color.BG)
        self.forensic_frame.grid_columnconfigure(0, weight=1)
        self.forensic_frame.grid_rowconfigure(0, weight=0)  # Run Selector
        self.forensic_frame.grid_rowconfigure(1, weight=0)  # Filter Toolbar
        self.forensic_frame.grid_rowconfigure(2, weight=1)  # Two-pane Split

        self._build_run_selector_bar()
        self._build_filter_toolbar()
        self._build_two_pane_content()

    def _build_run_selector_bar(self) -> None:
        """Top selector bar for choosing JSONL log traces."""
        selector_bar = ctk.CTkFrame(
            self.forensic_frame,
            fg_color="#101624",
            height=44,
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        selector_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))

        ctk.CTkLabel(
            selector_bar,
            text="Forensic Trace:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8",
        ).pack(side="left", padx=(14, 8), pady=8)

        self.runs_combo = ctk.CTkComboBox(
            selector_bar,
            width=480,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            values=["No .jsonl log files found"],
            command=self._on_run_selected,
        )
        self.runs_combo.pack(side="left", padx=4, pady=8)

        self.trace_status_lbl = ctk.CTkLabel(
            selector_bar,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38BDF8",
        )
        self.trace_status_lbl.pack(side="left", padx=(8, 4), pady=8)

        ctk.CTkButton(
            selector_bar,
            text="🔄 Refresh",
            width=85,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self.refresh_runs,
        ).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(
            selector_bar,
            text="📂 Open Logs Folder",
            width=135,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._open_logs_folder,
        ).pack(side="right", padx=(8, 14), pady=8)

    def _build_filter_toolbar(self) -> None:
        """Filter bar providing multi-dimensional search and stage/severity slices."""
        filter_bar = ctk.CTkFrame(
            self.forensic_frame,
            fg_color="#0D131F",
            height=40,
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        filter_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Severity Filter
        ctk.CTkLabel(
            filter_bar,
            text="Severity:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B",
        ).pack(side="left", padx=(14, 4), pady=6)

        self.severity_var = ctk.StringVar(value="All Severities")
        self.severity_combo = ctk.CTkComboBox(
            filter_bar,
            width=125,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            values=["All Severities", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            variable=self.severity_var,
            command=lambda _val: self._apply_filters(),
        )
        self.severity_combo.pack(side="left", padx=4, pady=6)

        # Stage Filter
        ctk.CTkLabel(
            filter_bar,
            text="Stage:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B",
        ).pack(side="left", padx=(12, 4), pady=6)

        self.stage_var = ctk.StringVar(value="All Stages")
        self.stage_combo = ctk.CTkComboBox(
            filter_bar,
            width=140,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            values=["All Stages"],
            variable=self.stage_var,
            command=lambda _val: self._apply_filters(),
        )
        self.stage_combo.pack(side="left", padx=4, pady=6)

        # Free-text Search (Item 16: Debounced)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            filter_bar,
            width=220,
            height=26,
            placeholder_text="🔍 Filter message, operation...",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            textvariable=self.search_var,
        )
        self.search_entry.pack(side="left", padx=(12, 4), pady=6)
        self.search_var.trace_add("write", self._on_search_text_changed)

        # Failures Only Toggle
        self.failures_only_var = ctk.BooleanVar(value=False)
        self.failures_switch = ctk.CTkSwitch(
            filter_bar,
            text="Failures Only",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#EF4444",
            variable=self.failures_only_var,
            command=self._apply_filters,
            progress_color="#EF4444",
        )
        self.failures_switch.pack(side="left", padx=(14, 8), pady=6)

        # Count Badge
        self.count_badge = ctk.CTkLabel(
            filter_bar,
            text="0 / 0 events",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38BDF8",
            fg_color="#0B263B",
            corner_radius=4,
        )
        self.count_badge.pack(side="right", padx=(0, 14), pady=6, ipady=2, ipadx=8)

    def _on_search_text_changed(self, *_: Any) -> None:
        """Debounce search query keystrokes (160ms) to ensure butter-smooth typing."""
        if self._search_debounce_job is not None:
            try:
                self.after_cancel(self._search_debounce_job)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        self._search_debounce_job = self.after(160, self._apply_filters)

    def _build_two_pane_content(self) -> None:
        """Construct the split layout: Events list on top, detail pane on bottom."""
        split_container = ctk.CTkFrame(self.forensic_frame, fg_color="transparent")
        split_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        split_container.grid_columnconfigure(0, weight=1)
        split_container.grid_rowconfigure(0, weight=6)  # Event List (60%)
        split_container.grid_rowconfigure(1, weight=0)  # Pagination Toolbar
        split_container.grid_rowconfigure(2, weight=4)  # Detail Inspector (40%)

        # Upper: Events List
        self.events_scroll = ctk.CTkScrollableFrame(
            split_container,
            fg_color="#0A0E17",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.events_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        self.events_scroll.grid_columnconfigure(0, weight=1)

        # Middle: Pagination Toolbar (Item 17: Fixed 100-event pages)
        pagination_bar = ctk.CTkFrame(
            split_container, fg_color="#0D131F", height=32, corner_radius=4
        )
        pagination_bar.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        pagination_bar.grid_columnconfigure(1, weight=1)

        self.prev_btn = ctk.CTkButton(
            pagination_bar,
            text="◀ Previous",
            width=85,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._prev_page,
            state="disabled",
        )
        self.prev_btn.pack(side="left", padx=8, pady=4)

        self.page_info_lbl = ctk.CTkLabel(
            pagination_bar,
            text="Page 1 of 1",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
        )
        self.page_info_lbl.pack(side="left", padx=16, pady=4)

        self.next_btn = ctk.CTkButton(
            pagination_bar,
            text="Next ▶",
            width=85,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._next_page,
            state="disabled",
        )
        self.next_btn.pack(side="left", padx=8, pady=4)

        # Lower: Detail Inspector (Item 19)
        detail_frame = ctk.CTkFrame(
            split_container,
            fg_color="#0E1422",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        detail_frame.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_rowconfigure(0, weight=0)  # Detail Header
        detail_frame.grid_rowconfigure(1, weight=1)  # Monospace Content

        detail_header = ctk.CTkFrame(detail_frame, fg_color="#151D2E", height=30, corner_radius=0)
        detail_header.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            detail_header,
            text="Telemetry & Exception Context Inspector",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
        ).pack(side="left", padx=10, pady=4)

        ctk.CTkButton(
            detail_header,
            text="📋 Copy JSON",
            width=90,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._copy_selected_event_json,
        ).pack(side="right", padx=8, pady=4)

        self.detail_text = ctk.CTkTextbox(
            detail_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#090D15",
            text_color="#E2E8F0",
            corner_radius=4,
            border_width=0,
        )
        self.detail_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.detail_text.insert("end", "Select an event above to inspect structured telemetry...")
        self.detail_text.configure(state="disabled")

    # ── 5. Run Discovery & Parsing ────────────────────────────────────────────

    def refresh_runs(self) -> None:
        """Scan logs directory for JSONL files and populate the run selector."""
        cfg_path = self.app_state.active_config_path if self.app_state else None
        self._discovered_files = self.engine.discover_log_files(cfg_path)

        if not self._discovered_files:
            self.runs_combo.configure(values=["No .jsonl log files found"])
            self.runs_combo.set("No .jsonl log files found")
            self._parsed_events = []
            self._active_trace = None
            self._apply_filters()
            return

        display_values: list[str] = []
        for file_path in self._discovered_files:
            try:
                st = file_path.stat()
                size_kb = st.st_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"
                display_values.append(f"{file_path.name}  ({size_str})")
            except Exception:  # pylint: disable=broad-exception-caught
                display_values.append(file_path.name)

        self.runs_combo.configure(values=display_values)
        if display_values:
            self.runs_combo.set(display_values[0])
            self._load_selected_file(self._discovered_files[0])

    def _on_run_selected(self, selected_str: str) -> None:
        """Handle selection change in the run selector combobox."""
        if not self._discovered_files:
            return
        for file_path in self._discovered_files:
            if file_path.name in selected_str:
                self._load_selected_file(file_path)
                break

    def _load_selected_file(self, file_path: Path) -> None:
        """Read and parse events from selected JSONL file asynchronously (Item 13 & 14)."""
        self._load_generation += 1
        current_gen = self._load_generation
        self.trace_status_lbl.configure(text="Parsing trace...")

        def _worker() -> ParsedTrace:
            cached = get_trace_cache().get(file_path)
            if cached is not None:
                return cached
            return parse_trace_file(file_path)

        def _on_success(trace: ParsedTrace) -> None:
            if current_gen != self._load_generation:
                return
            self.trace_status_lbl.configure(text="")
            self._active_trace = trace
            self._parsed_events = trace.events
            self._selected_event_index = None

            # Item 15: Dynamically populate stage & severity filters
            stages = ["All Stages"] + trace.available_stages
            self.stage_combo.configure(values=stages)
            if self.stage_var.get() not in stages:
                self.stage_var.set("All Stages")

            severities = ["All Severities"] + trace.available_severities
            self.severity_combo.configure(values=severities)
            if self.severity_var.get() not in severities:
                self.severity_var.set("All Severities")

            self._current_page = 1
            self._apply_filters()

        def _on_error(exc: Exception) -> None:
            if current_gen != self._load_generation:
                return
            self.trace_status_lbl.configure(text=f"Parse error: {exc}")

        get_background_runner().run(
            _worker,
            on_success=_on_success,
            on_error=_on_error,
            parent_widget=self,
            generation=current_gen,
        )

    # ── 6. Filtering & List Rendering ─────────────────────────────────────────

    def _apply_filters(self) -> None:
        """Filter events using multi-field inverted index intersection (Item 12 & 16)."""
        selected_sev = self.severity_var.get().strip().upper()
        selected_stage = self.stage_var.get().strip().upper()
        search_query = self.search_var.get().strip().lower()
        failures_only = self.failures_only_var.get()

        # Handle parsed trace
        if self._active_trace is not None:
            self._filtered_indices = self._active_trace.filter_events(
                severity=selected_sev,
                stage=selected_stage,
                failures_only=failures_only,
                query=search_query,
            )
            self._filtered_events = [self._active_trace.events[i] for i in self._filtered_indices]
        elif self._parsed_events:
            # Fallback for directly injected mock dicts in unit tests
            events: list[ForensicEvent] = []
            for idx, item in enumerate(self._parsed_events):
                if isinstance(item, dict):
                    events.append(ForensicEvent.from_dict(item, idx))
                elif isinstance(item, ForensicEvent):
                    events.append(item)

            mock_trace = ParsedTrace(
                path=Path("mock_trace.jsonl"),
                file_size=0,
                mtime_ns=0,
                events=events,
            )
            for idx, e in enumerate(events):
                if e.severity:
                    mock_trace.severity_index.setdefault(e.severity, set()).add(idx)
                if e.stage:
                    mock_trace.stage_index.setdefault(e.stage, set()).add(idx)
                if (
                    e.severity in ("ERROR", "CRITICAL", "FATAL")
                    or e.outcome in ("FAILED", "ABORTED")
                    or e.error_type
                ):
                    mock_trace.failures_indices.add(idx)

            self._active_trace = mock_trace
            self._filtered_indices = self._active_trace.filter_events(
                severity=selected_sev,
                stage=selected_stage,
                failures_only=failures_only,
                query=search_query,
            )
            self._filtered_events = [self._active_trace.events[i] for i in self._filtered_indices]
        else:
            self._filtered_indices = []
            self._filtered_events = []

        total_events = len(self._active_trace.events) if self._active_trace else 0
        self.count_badge.configure(text=f"{len(self._filtered_indices)} / {total_events} events")

        # Reset to page 1 on filter mutation
        self._current_page = 1
        self._render_events_page()

    @property
    def total_pages(self) -> int:
        """Total number of 100-event pages based on current filtered indices."""
        return max(1, math.ceil(len(self._filtered_indices) / PAGE_SIZE))

    def _render_events_page(self) -> None:
        """Render the current fixed page (100 rows) of filtered events (Items 17 & 18)."""
        self._rendered_row_frames.clear()
        for widget in self.events_scroll.winfo_children():
            widget.destroy()

        total_items = len(self._filtered_indices)
        total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
        self._current_page = max(1, min(self._current_page, total_pages))

        self.page_info_lbl.configure(text=f"Page {self._current_page} of {total_pages}")
        self.prev_btn.configure(state="normal" if self._current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self._current_page < total_pages else "disabled")

        if not self._filtered_indices or self._active_trace is None:
            empty_lbl = ctk.CTkLabel(
                self.events_scroll,
                text="No events match the selected criteria.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#64748B",
            )
            empty_lbl.pack(pady=40)
            self._clear_detail_pane()
            return

        start_idx = (self._current_page - 1) * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_items)
        page_indices = self._filtered_indices[start_idx:end_idx]

        selected_on_this_page: int | None = None

        for slot, global_idx in enumerate(page_indices):
            evt = self._active_trace.events[global_idx]
            self._render_event_row(slot, global_idx, evt)
            # Item 20: Intelligent selection preservation
            if (
                self._selected_event_key is not None
                and (evt.timestamp_iso, evt.event_code) == self._selected_event_key
            ):
                selected_on_this_page = global_idx

        # Select preserved event or default to first event on page
        if selected_on_this_page is not None:
            self._select_event(selected_on_this_page)
        elif page_indices:
            self._select_event(page_indices[0])

    def _prev_page(self) -> None:
        """Navigate to the previous page of events."""
        if self._current_page > 1:
            self._current_page -= 1
            self._render_events_page()

    def _next_page(self) -> None:
        """Navigate to the next page of events."""
        total_items = len(self._filtered_indices)
        total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
        if self._current_page < total_pages:
            self._current_page += 1
            self._render_events_page()

    def _render_event_row(self, slot: int, global_idx: int, evt: ForensicEvent) -> None:
        """Render a single lightweight compact row in the scrollable view (Item 18)."""
        sev_colors = {
            "DEBUG": ("#94A3B8", "#1E293B"),
            "INFO": ("#38BDF8", "#0B263B"),
            "WARNING": ("#FBBF24", "#2D1E04"),
            "ERROR": ("#F87171", "#2E0B0B"),
            "CRITICAL": ("#EF4444", "#450A0A"),
        }
        text_col, bg_col = sev_colors.get(evt.severity, ("#94A3B8", "#1E293B"))

        row = ctk.CTkFrame(
            self.events_scroll,
            fg_color="#101726" if slot % 2 == 0 else "#0C121E",
            corner_radius=4,
            height=26,
            border_width=0,
            border_color="#1E293B",
        )
        row.pack(fill="x", padx=4, pady=1)
        row.grid_columnconfigure(4, weight=1)
        self._rendered_row_frames[global_idx] = row

        # 1. Timestamp
        time_lbl = ctk.CTkLabel(
            row,
            text=evt.timestamp_display,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#64748B",
            width=65,
        )
        time_lbl.grid(row=0, column=0, padx=(8, 4), pady=2)

        # 2. Severity Badge
        sev_badge = ctk.CTkLabel(
            row,
            text=evt.severity,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=text_col,
            fg_color=bg_col,
            corner_radius=3,
            width=58,
        )
        sev_badge.grid(row=0, column=1, padx=4, pady=2, ipady=1)

        # 3. Stage Badge
        stage_text = f"[{evt.stage}]" if evt.stage else "[-]"
        stage_lbl = ctk.CTkLabel(
            row,
            text=stage_text,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#94A3B8",
            width=100,
            anchor="w",
        )
        stage_lbl.grid(row=0, column=2, padx=4, pady=2)

        # 4. Event Code
        outcome_symbol = (
            "✓" if evt.outcome == "COMPLETED" else ("✗" if evt.outcome == "FAILED" else "•")
        )
        code_lbl = ctk.CTkLabel(
            row,
            text=f"{outcome_symbol} {evt.event_code}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#CBD5E1",
            width=180,
            anchor="w",
        )
        code_lbl.grid(row=0, column=3, padx=4, pady=2)

        # 5. Message preview
        msg_lbl = ctk.CTkLabel(
            row,
            text=evt.message,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#E2E8F0",
            anchor="w",
        )
        msg_lbl.grid(row=0, column=4, sticky="ew", padx=(4, 8), pady=2)

        def _on_row_click(_e: Any) -> None:
            self._select_event(global_idx)

        # Bind click handler and pointer cursor to row and all sub-widgets for reliable selection
        for widget in (row, time_lbl, sev_badge, stage_lbl, code_lbl, msg_lbl):
            try:
                widget.configure(cursor="hand2")
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            widget.bind("<Button-1>", _on_row_click)
            for inner in ("_label", "_canvas", "_text_label"):
                inner_w = getattr(widget, inner, None)
                if inner_w is not None and hasattr(inner_w, "bind"):
                    try:
                        inner_w.configure(cursor="hand2")
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                    inner_w.bind("<Button-1>", _on_row_click)

    # ── 7. Detail Inspector Rendering ─────────────────────────────────────────

    def _select_event(self, idx: int) -> None:
        """Display comprehensive structured telemetry for selected event (Item 19 & 20).

        Accepts either:
        - A global trace index (e.g. from a rendered row frame click), OR
        - A filtered list index (e.g. 0 to select the first filtered event).
        """
        evt: Any = None
        global_idx: int = idx

        if self._active_trace is not None and self._filtered_indices:
            if idx in self._rendered_row_frames or idx in self._filtered_indices:
                global_idx = idx
                if 0 <= global_idx < len(self._active_trace.events):
                    evt = self._active_trace.events[global_idx]
            elif 0 <= idx < len(self._filtered_indices):
                global_idx = self._filtered_indices[idx]
                if 0 <= global_idx < len(self._active_trace.events):
                    evt = self._active_trace.events[global_idx]
            elif 0 <= idx < len(self._active_trace.events):
                global_idx = idx
                evt = self._active_trace.events[global_idx]
        elif 0 <= idx < len(self._filtered_events):
            evt = self._filtered_events[idx]
            global_idx = idx
        elif self._active_trace is not None and 0 <= idx < len(self._active_trace.events):
            evt = self._active_trace.events[idx]
            global_idx = idx

        if evt is None:
            return

        # Update highlighted row borders
        prev_idx = self._selected_event_index
        if prev_idx is not None and prev_idx in self._rendered_row_frames:
            try:
                self._rendered_row_frames[prev_idx].configure(border_width=0)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        self._selected_event_index = global_idx
        if global_idx in self._rendered_row_frames:
            try:
                self._rendered_row_frames[global_idx].configure(
                    border_width=1, border_color="#38BDF8"
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if isinstance(evt, ForensicEvent):
            self._selected_event_key = (evt.timestamp_iso, evt.event_code)
        elif isinstance(evt, dict):
            self._selected_event_key = (evt.get("timestamp", "-"), evt.get("event_code", "-"))

        formatted_text = _format_event_details(evt)

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", formatted_text)
        self.detail_text.see("1.0")
        self.detail_text.configure(state="disabled")

    def _clear_detail_pane(self) -> None:
        """Clear detail pane contents when no events match."""
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "No events match the selected criteria.")
        self.detail_text.configure(state="disabled")

    def _copy_selected_event_json(self) -> None:
        """Copy the complete raw JSON representation of the selected event to clipboard."""
        if self._selected_event_index is None or not self._active_trace:
            return
        if self._selected_event_index >= len(self._active_trace.events):
            return
        evt = self._active_trace.events[self._selected_event_index]
        json_str = json.dumps(evt.raw_data, indent=2, default=str)
        self.clipboard_clear()
        self.clipboard_append(json_str)

    def _open_logs_folder(self) -> None:
        """Open the active logs folder in host system file explorer."""
        cfg_path = self.app_state.active_config_path if self.app_state else None
        log_dir = self.engine.get_logs_directory(cfg_path)
        _open_directory(log_dir)


def _clean_field(val: Any, default: str = "-") -> str:
    """Safely format string or scalar field, falling back to default on None or blank."""
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def _format_event_details(evt: ForensicEvent | dict[str, Any]) -> str:
    """Format structured telemetry and execution lineage into human-readable inspector text."""
    if isinstance(evt, ForensicEvent):
        code = _clean_field(evt.event_code, "UNKNOWN_EVENT")
        sev = _clean_field(evt.severity, "INFO")
        outcome = _clean_field(evt.outcome, "COMPLETED")
        raw_ts = _clean_field(evt.timestamp_iso, "")
        ts = format_full_local_timestamp(raw_ts) if raw_ts else "-"
        msg = _clean_field(evt.message)

        run_id = _clean_field(evt.run_id)
        stage = _clean_field(evt.stage)
        component = _clean_field(evt.component)
        commit_state = _clean_field(evt.commit_state)
        settings_hash = _clean_field(evt.settings_hash)
        rules_hash = _clean_field(evt.rules_hash)

        operation = _clean_field(evt.operation)
        op_id = _clean_field(evt.operation_id)
        parent_op_id = _clean_field(evt.parent_operation_id)
        entity_type = _clean_field(evt.entity_type)
        entity_id = _clean_field(evt.entity_id)
        dur = f"{evt.duration_ms} ms" if evt.duration_ms is not None else "-"
        rows = _clean_field(evt.rows)
        attempt = _clean_field(evt.attempt)
        provider = _clean_field(evt.provider)
        worker_batch = f"{_clean_field(evt.worker_id)} / {_clean_field(evt.batch_id)}"

        has_error = bool(evt.error_type or evt.error_message)
        err_type = _clean_field(evt.error_type)
        err_msg = _clean_field(evt.error_message)
        err_details = _clean_field(evt.error_details, "None")
    else:
        # Fallback for raw dict
        raw_ctx = evt.get("context")
        ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
        raw_err = evt.get("error")
        err: dict[str, Any] | None = raw_err if isinstance(raw_err, dict) else None

        code = _clean_field(evt.get("event_code"), "UNKNOWN_EVENT")
        sev = _clean_field(evt.get("severity"), "INFO")
        outcome = _clean_field(evt.get("outcome"), "COMPLETED")
        raw_ts = _clean_field(evt.get("timestamp"), "")
        ts = format_full_local_timestamp(raw_ts) if raw_ts else "-"
        msg = _clean_field(evt.get("message"))

        run_id = _clean_field(ctx.get("run_id"))
        stage = _clean_field(ctx.get("stage"))
        component = _clean_field(ctx.get("component"))
        commit_state = _clean_field(ctx.get("commit_state"))
        settings_hash = _clean_field(ctx.get("settings_fingerprint") or ctx.get("settings_hash"))
        rules_hash = _clean_field(ctx.get("rules_fingerprint") or ctx.get("rules_hash"))

        operation = _clean_field(ctx.get("operation"))
        op_id = _clean_field(ctx.get("operation_id"))
        parent_op_id = _clean_field(ctx.get("parent_operation_id"))
        entity_type = _clean_field(ctx.get("entity_type"))
        entity_id = _clean_field(ctx.get("entity_id"))
        dur = f"{ctx.get('duration_ms')} ms" if ctx.get("duration_ms") is not None else "-"
        rows = _clean_field(ctx.get("rows"))
        attempt = _clean_field(ctx.get("attempt"))
        provider = _clean_field(ctx.get("provider"))
        worker_batch = f"{_clean_field(ctx.get('worker_id'))} / {_clean_field(ctx.get('batch_id'))}"

        has_error = err is not None
        err_type = _clean_field(err.get("exception_type") if err else None)
        err_msg = _clean_field(err.get("exception_message") if err else None)
        err_details = _clean_field(
            err.get("details") or err.get("traceback_summary") if err else None
        )

    has_operational_metrics = any(
        v not in ("-", "", "None") for v in (operation, rows, entity_id, provider)
    )

    lines: list[str] = [
        "=" * 82,
        f" EVENT RECORD: {code} [{sev}]",
        "=" * 82,
        f"  Event Code:        {code}",
        f"  Severity:          {sev}",
        f"  Outcome:           {outcome}",
        f"  Timestamp:         {ts}",
        f"  Message:           {msg}",
        "",
        "─" * 82,
        " EXECUTION LINEAGE & CONFIGURATION STATE",
        "─" * 82,
        f"  Run ID:            {run_id}",
        f"  Pipeline Stage:    {stage}",
        f"  Component:         {component}",
        f"  Commit State:      {commit_state}",
        f"  Settings Hash:     {settings_hash}",
        f"  Rules Hash:        {rules_hash}",
        "",
        "─" * 82,
        " OPERATIONAL TELEMETRY & PERFORMANCE METRICS",
        "─" * 82,
    ]

    if has_operational_metrics:
        lines.extend(
            [
                f"  Operation:         {operation}",
                f"  Operation ID:      {op_id}",
                f"  Parent Op ID:      {parent_op_id}",
                f"  Entity Type / ID:  {entity_type} : {entity_id}",
                f"  Duration:          {dur}",
                f"  Rows Processed:    {rows}",
                f"  Attempt:           {attempt}",
                f"  Provider:          {provider}",
                f"  Worker / Batch:    {worker_batch}",
            ]
        )
    else:
        lines.extend(
            [
                "  Event Type:        Diagnostic & Lifecycle Event",
                "  Operational State: No task processing metrics attached to this event.",
                "                     (Rows, duration, and provider metrics are recorded during",
                "                     active statement extraction and warehouse transformation.)",
            ]
        )

    lines.append("")

    if has_error:
        lines.extend(
            [
                "─" * 82,
                " EXCEPTION & DIAGNOSTIC DETAILS [FAILURE DETECTED]",
                "─" * 82,
                f"  Exception Type:    {err_type}",
                f"  Exception Message: {err_msg}",
                f"  Details:           {err_details}",
            ]
        )
    else:
        lines.extend(
            [
                "─" * 82,
                " DIAGNOSTIC HEALTH STATUS",
                "─" * 82,
                "  Status:            HEALTHY / NOMINAL",
                "  Diagnostics:       No unhandled exceptions or failure states recorded for this event.",
            ]
        )

    return "\n".join(lines)
