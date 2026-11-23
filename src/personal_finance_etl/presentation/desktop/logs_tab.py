"""Forensic telemetry and live narrative observability log viewer tab.

Owns
----
- LogsTab: Dual sub-view presentation container (Live Narrative and Forensic JSONL).
- Live narrative terminal with text streaming, copy, and clear controls.
- Forensic JSONL inspector: run/trace selector, multi-dimensional filters
  (severity, stage, search query, failures only), scrollable event list,
  and deep structured context/error drill-down pane.

Does not own
-------------
- JSONL file persistence or event emission (owned by infrastructure.observability).
- Database querying or pipeline execution (owned by application.pipeline).
"""

from __future__ import annotations

import os
import subprocess
import sys
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
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import LOG_TAG_COLORS, Color

__all__ = ["LogsTab"]


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
class LogsTab(ctk.CTkFrame):  # type: ignore[misc]
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
        self._parsed_events: list[dict[str, Any]] = []
        self._filtered_events: list[dict[str, Any]] = []
        self._selected_event_index: int | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top sub-navigation
        self.grid_rowconfigure(1, weight=1)  # Sub-tab content area

        self._build_top_bar()
        self._build_subviews()

        # Lazy loading state
        self._loaded: bool = False
        self._display_limit: int = 100

    def ensure_loaded(self) -> None:
        """Lazily scan and load log traces on first view."""
        if not self._loaded:
            self._loaded = True
            self.refresh_runs()

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
        elif sub_id == "forensic":
            self.narrative_frame.grid_remove()
            self.forensic_frame.grid(row=0, column=0, sticky="nsew")

    # ── 2. Sub-views Construction ─────────────────────────────────────────────

    def _build_subviews(self) -> None:
        """Create container frames for both narrative and forensic sub-views."""
        self.content_container = ctk.CTkFrame(self, fg_color=Color.BG, corner_radius=0)
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self._build_narrative_view()
        self._build_forensic_view()

        # Default display is Forensic JSONL
        self.forensic_frame.grid(row=0, column=0, sticky="nsew")

    # ── 3. Live Narrative View ────────────────────────────────────────────────

    def _build_narrative_view(self) -> None:
        """Build the full-height live narrative terminal."""
        self.narrative_frame = ctk.CTkFrame(self.content_container, fg_color=Color.BG)
        self.narrative_frame.grid_columnconfigure(0, weight=1)
        self.narrative_frame.grid_rowconfigure(0, weight=0)  # Toolbar
        self.narrative_frame.grid_rowconfigure(1, weight=1)  # Log box

        toolbar = ctk.CTkFrame(self.narrative_frame, fg_color="#101624", height=38, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))

        ctk.CTkLabel(
            toolbar,
            text="Real-time Execution Narrative & Telemetry",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#E2E8F0",
        ).pack(side="left", padx=12, pady=6)

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
            ts_str = event.timestamp.strftime("%H:%M:%S")
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
        severity_combo = ctk.CTkComboBox(
            filter_bar,
            width=125,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            values=["All Severities", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            variable=self.severity_var,
            command=lambda _val: self._apply_filters(),
        )
        severity_combo.pack(side="left", padx=4, pady=6)

        # Stage Filter
        ctk.CTkLabel(
            filter_bar,
            text="Stage:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B",
        ).pack(side="left", padx=(12, 4), pady=6)

        self.stage_var = ctk.StringVar(value="All Stages")
        stage_combo = ctk.CTkComboBox(
            filter_bar,
            width=140,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            values=[
                "All Stages",
                "DISCOVERY",
                "INGESTION",
                "TRANSFORMATION",
                "VALUATION",
                "TAX",
                "WEALTH",
                "FIRE",
                "OBSERVABILITY",
            ],
            variable=self.stage_var,
            command=lambda _val: self._apply_filters(),
        )
        stage_combo.pack(side="left", padx=4, pady=6)

        # Free-text Search
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            filter_bar,
            width=220,
            height=26,
            placeholder_text="🔍 Filter message, operation...",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            textvariable=self.search_var,
        )
        search_entry.pack(side="left", padx=(12, 4), pady=6)
        self.search_var.trace_add("write", lambda *_: self._apply_filters())

        # Failures Only Toggle
        self.failures_only_var = ctk.BooleanVar(value=False)
        failures_switch = ctk.CTkSwitch(
            filter_bar,
            text="Failures Only",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#EF4444",
            variable=self.failures_only_var,
            command=self._apply_filters,
            progress_color="#EF4444",
        )
        failures_switch.pack(side="left", padx=(14, 8), pady=6)

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

    def _build_two_pane_content(self) -> None:
        """Construct the split layout: Events list on top, detail pane on bottom."""
        split_container = ctk.CTkFrame(self.forensic_frame, fg_color="transparent")
        split_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        split_container.grid_columnconfigure(0, weight=1)
        split_container.grid_rowconfigure(0, weight=6)  # Event List (60%)
        split_container.grid_rowconfigure(1, weight=4)  # Detail Inspector (40%)

        # Upper: Events List
        self.events_scroll = ctk.CTkScrollableFrame(
            split_container,
            fg_color="#0A0E17",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        self.events_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.events_scroll.grid_columnconfigure(0, weight=1)

        # Lower: Detail Inspector
        detail_frame = ctk.CTkFrame(
            split_container,
            fg_color="#0E1422",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        detail_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
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
            self._apply_filters()
            return

        display_values: list[str] = []
        for file_path in self._discovered_files:
            try:
                st = file_path.stat()
                size_kb = st.st_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb / 1024:.2f} MB"
                display_values.append(f"{file_path.name}  ({size_str})")
            except Exception:
                display_values.append(file_path.name)

        self.runs_combo.configure(values=display_values)
        if display_values:
            self.runs_combo.set(display_values[0])
            self._load_selected_file(self._discovered_files[0])

    def _on_run_selected(self, selected_str: str) -> None:
        """Handle selection change in the run selector combobox."""
        if not self._discovered_files:
            return
        # Match filename prefix
        for file_path in self._discovered_files:
            if file_path.name in selected_str:
                self._load_selected_file(file_path)
                break

    def _load_selected_file(self, file_path: Path) -> None:
        """Read and parse events from selected JSONL file."""
        events, detected_run_id = self.engine.read_jsonl_log(file_path)
        self._parsed_events = events
        self._selected_event_index = None

        if detected_run_id:
            # Highlight detected run id in title or status if desired
            pass

        self._apply_filters()

    # ── 6. Filtering & List Rendering ─────────────────────────────────────────

    def _apply_filters(self) -> None:
        """Filter parsed events according to active toolbar controls."""
        selected_sev = self.severity_var.get().strip().upper()
        selected_stage = self.stage_var.get().strip().upper()
        search_query = self.search_var.get().strip().lower()
        failures_only = self.failures_only_var.get()

        filtered: list[dict[str, Any]] = []

        for evt in self._parsed_events:
            sev = str(evt.get("severity", "")).upper()
            if selected_sev != "ALL SEVERITIES" and sev != selected_sev:
                continue

            raw_ctx = evt.get("context")
            ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
            stage = str(ctx.get("stage", "")).upper()
            if selected_stage != "ALL STAGES" and stage != selected_stage:
                continue

            outcome = str(evt.get("outcome", "")).upper()
            has_error = evt.get("error") is not None
            is_failure = (
                outcome in ("FAILED", "ABORTED") or sev in ("ERROR", "CRITICAL") or has_error
            )
            if failures_only and not is_failure:
                continue

            if search_query:
                msg = str(evt.get("message", "")).lower()
                op = str(ctx.get("operation", "")).lower()
                code = str(evt.get("event_code", "")).lower()
                entity = str(ctx.get("entity_id", "")).lower()
                if (
                    search_query not in msg
                    and search_query not in op
                    and search_query not in code
                    and search_query not in entity
                ):
                    continue

            filtered.append(evt)

        self._filtered_events = filtered
        self._display_limit = 100
        self.count_badge.configure(text=f"{len(filtered)} / {len(self._parsed_events)} events")
        self._render_events_list()

    def _render_events_list(self) -> None:
        """Populate the scrollable list of filtered event cards with virtual pagination."""
        for widget in self.events_scroll.winfo_children():
            widget.destroy()

        if not self._filtered_events:
            empty_lbl = ctk.CTkLabel(
                self.events_scroll,
                text="No events match the selected criteria.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color="#64748B",
            )
            empty_lbl.pack(pady=40)
            return

        visible_events = self._filtered_events[: self._display_limit]
        for idx, evt in enumerate(visible_events):
            self._render_event_row(idx, evt)

        # If more events exist, render Load More button
        if len(self._filtered_events) > self._display_limit:
            more_frame = ctk.CTkFrame(self.events_scroll, fg_color="transparent")
            more_frame.pack(fill="x", pady=8)

            remaining = len(self._filtered_events) - self._display_limit
            step_add = min(100, remaining)
            more_btn = ctk.CTkButton(
                more_frame,
                text=f"⬇️  Load More (+{step_add} events)  —  Showing {len(visible_events)} of {len(self._filtered_events)}",
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color="#1E293B",
                hover_color="#334155",
                text_color="#38BDF8",
                command=self._load_more_events,
            )
            more_btn.pack(pady=4)

        # Select first event by default if available
        if self._filtered_events and self._selected_event_index is None:
            self._select_event(0)

    def _load_more_events(self) -> None:
        """Increment display limit and re-render list."""
        self._display_limit += 100
        self._render_events_list()

    def _render_event_row(self, idx: int, evt: dict[str, Any]) -> None:
        """Render a single interactive event card in the scrollable list."""
        sev = str(evt.get("severity", "INFO")).upper()
        ts_raw = str(evt.get("timestamp", ""))
        ts_time = ts_raw[11:19] if len(ts_raw) >= 19 else ts_raw

        raw_ctx = evt.get("context")
        ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
        stage = str(ctx.get("stage", "-"))
        event_code = str(evt.get("event_code", ""))
        outcome = str(evt.get("outcome", ""))
        message = str(evt.get("message", ""))

        sev_colors = {
            "DEBUG": ("#94A3B8", "#1E293B"),
            "INFO": ("#38BDF8", "#0B263B"),
            "WARNING": ("#FBBF24", "#2D1E04"),
            "ERROR": ("#F87171", "#2E0B0B"),
            "CRITICAL": ("#EF4444", "#450A0A"),
        }
        text_col, bg_col = sev_colors.get(sev, ("#94A3B8", "#1E293B"))

        row = ctk.CTkFrame(
            self.events_scroll,
            fg_color="#101726" if idx % 2 == 0 else "#0C121E",
            corner_radius=4,
            height=32,
        )
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(4, weight=1)

        # 1. Timestamp
        ctk.CTkLabel(
            row,
            text=ts_time,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#64748B",
            width=65,
        ).grid(row=0, column=0, padx=(8, 4), pady=4)

        # 2. Severity Badge
        ctk.CTkLabel(
            row,
            text=sev,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=text_col,
            fg_color=bg_col,
            corner_radius=3,
            width=58,
        ).grid(row=0, column=1, padx=4, pady=4, ipady=1)

        # 3. Stage Badge
        ctk.CTkLabel(
            row,
            text=f"[{stage}]",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#94A3B8",
            width=100,
            anchor="w",
        ).grid(row=0, column=2, padx=4, pady=4)

        # 4. Event Code
        outcome_symbol = "✓" if outcome == "COMPLETED" else ("✗" if outcome == "FAILED" else "•")
        ctk.CTkLabel(
            row,
            text=f"{outcome_symbol} {event_code}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#CBD5E1",
            width=180,
            anchor="w",
        ).grid(row=0, column=3, padx=4, pady=4)

        # 5. Message
        msg_lbl = ctk.CTkLabel(
            row,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#E2E8F0",
            anchor="w",
        )
        msg_lbl.grid(row=0, column=4, sticky="ew", padx=(4, 8), pady=4)

        # Click handlers
        def _on_row_click(_event: Any, target_idx: int = idx) -> None:
            self._select_event(target_idx)

        row.bind("<Button-1>", _on_row_click)
        msg_lbl.bind("<Button-1>", _on_row_click)

    # ── 7. Detail Inspector Rendering ─────────────────────────────────────────

    def _select_event(self, idx: int) -> None:
        """Display comprehensive structured telemetry for selected event."""
        if idx >= len(self._filtered_events):
            return

        self._selected_event_index = idx
        evt = self._filtered_events[idx]
        formatted_text = _format_event_details(evt)

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", formatted_text)
        self.detail_text.see("1.0")
        self.detail_text.configure(state="disabled")

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


def _format_event_details(evt: dict[str, Any]) -> str:
    """Format structured telemetry and execution lineage into human-readable inspector text."""
    raw_ctx = evt.get("context")
    ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
    raw_err = evt.get("error")
    err: dict[str, Any] | None = raw_err if isinstance(raw_err, dict) else None

    code = _clean_field(evt.get("event_code"), "UNKNOWN_EVENT")
    sev = _clean_field(evt.get("severity"), "INFO")
    outcome = _clean_field(evt.get("outcome"), "COMPLETED")
    ts = _clean_field(evt.get("timestamp"))
    event_id = _clean_field(evt.get("event_id"))
    msg = _clean_field(evt.get("message"))

    lines: list[str] = [
        "=" * 82,
        f" EVENT RECORD: {code} [{sev}]",
        "=" * 82,
        f"  Event Code:        {code}",
        f"  Severity:          {sev}",
        f"  Outcome:           {outcome}",
        f"  Timestamp:         {ts}",
        f"  Event ID:          {event_id}",
        f"  Message:           {msg}",
        "",
        "─" * 82,
        " EXECUTION LINEAGE & CONFIGURATION STATE",
        "─" * 82,
        f"  Run ID:            {_clean_field(ctx.get('run_id'))}",
        f"  Pipeline Stage:    {_clean_field(ctx.get('stage'))}",
        f"  Component:         {_clean_field(ctx.get('component'))}",
        f"  Commit State:      {_clean_field(ctx.get('commit_state'))}",
        f"  Settings Hash:     {_clean_field(ctx.get('settings_fingerprint'))}",
        f"  Rules Hash:        {_clean_field(ctx.get('rules_fingerprint'))}",
        "",
        "─" * 82,
        " OPERATIONAL TELEMETRY & PERFORMANCE METRICS",
        "─" * 82,
    ]

    has_operational_metrics = any(
        ctx.get(k) is not None and str(ctx.get(k)).strip() != ""
        for k in (
            "operation",
            "rows",
            "duration_ms",
            "entity_type",
            "entity_id",
            "attempt",
            "provider",
            "worker_id",
        )
    )

    if has_operational_metrics:
        dur = f"{ctx.get('duration_ms')} ms" if ctx.get("duration_ms") is not None else "-"
        lines.extend(
            [
                f"  Operation:         {_clean_field(ctx.get('operation'))}",
                f"  Operation ID:      {_clean_field(ctx.get('operation_id'))}",
                f"  Parent Op ID:      {_clean_field(ctx.get('parent_operation_id'))}",
                f"  Entity Type / ID:  {_clean_field(ctx.get('entity_type'))} : {_clean_field(ctx.get('entity_id'))}",
                f"  Duration:          {dur}",
                f"  Rows Processed:    {_clean_field(ctx.get('rows'))}",
                f"  Attempt:           {_clean_field(ctx.get('attempt'))}",
                f"  Provider:          {_clean_field(ctx.get('provider'))}",
                f"  Worker / Batch:    {_clean_field(ctx.get('worker_id'))} / {_clean_field(ctx.get('batch_id'))}",
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
    if err:
        lines.extend(
            [
                "─" * 82,
                " EXCEPTION & DIAGNOSTIC DETAILS [FAILURE DETECTED]",
                "─" * 82,
                f"  Exception Type:    {_clean_field(err.get('exception_type'))}",
                f"  Exception Message: {_clean_field(err.get('exception_message'))}",
                f"  Failure Domain:    {_clean_field(err.get('failure_domain'))}",
                f"  Retryable:         {err.get('retryable', False)}",
                f"  Remediation Hint:  {_clean_field(err.get('remediation_hint'), 'None')}",
            ]
        )
        ctx_vars = err.get("context_variables")
        if isinstance(ctx_vars, dict) and ctx_vars:
            lines.append("  Context Variables:")
            for k, v in ctx_vars.items():
                lines.append(f"    {k} = {v}")

        tb = err.get("traceback_summary")
        if tb:
            lines.extend(
                [
                    "",
                    "─" * 82,
                    " TRACEBACK SUMMARY",
                    "─" * 82,
                    str(tb).strip(),
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
