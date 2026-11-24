"""Abstract base tab component for CustomTkinter GUI applications.

Owns
----
- BaseEngineTab: Common 2-column layout with header and progress/log output panel.
- Thread-safe queue polling and main-thread status updates via Tkinter after().
- Progress bar and colored log text box state management.
- Processing structured ObservabilityEvents across process boundaries.

Does not own
-------------
- Specific ETL buttons or file selectors (owned by concrete tab implementations like RunTab).
- Application orchestration logic or execution pipelines (owned by application.facade).
"""

from __future__ import annotations

import queue
import time
from collections.abc import Callable
from tkinter import messagebox
from typing import Any, Final

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.presentation.desktop.state import OperationState
from personal_finance_etl.presentation.desktop.theme import (
    LOG_TAG_COLORS,
    Color,
    ExportMode,
)

__all__ = ["BaseEngineTab"]

_DESKTOP_TAG_MAP: Final[dict[PresentationKind, str]] = {
    PresentationKind.STEP: "step",
    PresentationKind.PROGRESS: "info",
    PresentationKind.SUCCESS: "success",
    PresentationKind.SKIP: "skip",
    PresentationKind.WARNING: "warning",
    PresentationKind.FAILURE: "error",
    PresentationKind.RECOVERY: "recovery",
}

_DESKTOP_PREFIX_MAP: Final[dict[PresentationKind, str]] = {
    PresentationKind.STEP: ">>",
    PresentationKind.PROGRESS: "•",
    PresentationKind.SUCCESS: "✓",
    PresentationKind.SKIP: "↷",
    PresentationKind.WARNING: "!",
    PresentationKind.FAILURE: "✗ FAILURE:",
    PresentationKind.RECOVERY: "♻ RECOVERY:",
}


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTkFrame base class
class BaseEngineTab(ctk.CTkFrame):  # type: ignore[misc]
    """Base tab handling standard 2-column layout and log/queue operations."""

    def __init__(self, parent: ctk.CTk | ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.save_target = ""
        self.save_type = ExportMode.CONSOLIDATED
        self._run_btn_text = "▶  Run"
        self.on_status_listener: Callable[[ObservabilityEvent], None] | None = None
        self.on_batch_status_listener: Callable[[list[ObservabilityEvent]], None] | None = None
        self.app_state: Any | None = None
        self._event_queue: queue.Queue[tuple[ctk.CTkButton | None, ObservabilityEvent]] = (
            queue.Queue()
        )
        self._drain_scheduled: bool = False

        # 1-column layout — header | log
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

    def _build_log_panel(self) -> None:
        """Construct the progress bar and scrollable log text box panel."""
        panel = ctk.CTkFrame(self, fg_color=Color.BG, corner_radius=0)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        content = ctk.CTkFrame(panel, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        prog = ctk.CTkFrame(content, fg_color="transparent")
        prog.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        prog.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            prog,
            height=3,
            corner_radius=2,
            fg_color=Color.SIDEBAR,
            progress_color=Color.ACCENT,
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)

        self.pct_label = ctk.CTkLabel(
            prog,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.DIM,
            width=32,
            anchor="e",
        )
        self.pct_label.grid(row=0, column=1, padx=(6, 0))

        self.status_log = ctk.CTkTextbox(
            content,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=Color.LOG_BG,
            text_color=LOG_TAG_COLORS["info"],
            border_width=0,
            corner_radius=0,
            state="disabled",
            wrap="word",
        )
        self.status_log.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(6, 0))

    def _configure_log_tags(self) -> None:
        """Bind syntax color tags to the status log text widget."""
        tb = self.status_log._textbox
        for tag, colour in LOG_TAG_COLORS.items():
            tb.tag_config(tag, foreground=colour)
        tb.tag_config("ts", foreground=LOG_TAG_COLORS["ts"], font=("Consolas", 10))

    def _set_progress(self, value: float) -> None:
        """Update progress bar fill and percentage text."""
        self.progress.set(value)
        self.pct_label.configure(text=f"{int(value * 100)}%")

    def _log(self, msg: str, level: str = "info") -> None:
        """Append a timestamped log line to the disabled text widget."""
        ts = time.strftime("%H:%M:%S")
        self.status_log.configure(state="normal")
        tb = self.status_log._textbox
        tb.insert("end", f"[{ts}] ", "ts")
        tb.insert("end", f"{msg}\n", level)
        self.status_log.see("end")
        self.status_log.configure(state="disabled")

    def _section_label(self, parent: ctk.CTkFrame, text: str, row: int) -> int:
        """Create a standard styled section header label."""
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=Color.DIM,
            anchor="w",
        ).grid(row=row, column=0, padx=10, pady=(12, 4), sticky="w")
        return row + 1

    def handle_status(
        self,
        run_btn: ctk.CTkButton | None,
        status: ObservabilityEvent,
    ) -> None:
        """Enqueue status update thread-safely and trigger batched main-thread processing."""
        self._event_queue.put((run_btn, status))
        if not self._drain_scheduled:
            self._drain_scheduled = True
            try:
                self.after(20, self._drain_event_queue)
            except Exception:
                self._drain_event_queue()

    def _drain_event_queue(self) -> None:
        """Drain queued events in high-performance batches on the main Tkinter thread."""
        self._drain_scheduled = False
        if not self.winfo_exists():
            return

        batch: list[tuple[ctk.CTkButton | None, ObservabilityEvent]] = []
        while len(batch) < 100:
            try:
                batch.append(self._event_queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            self._process_event_batch(batch)

        if not self._event_queue.empty():
            self._drain_scheduled = True
            try:
                self.after(20, self._drain_event_queue)
            except Exception:
                self._drain_event_queue()

    def _process_event_batch(
        self,
        batch: list[tuple[ctk.CTkButton | None, ObservabilityEvent]],
    ) -> None:
        """Process a batch of ObservabilityEvents atomically on the main Tkinter thread."""
        raw_events = [evt for _, evt in batch]
        if self.on_batch_status_listener is not None:
            try:
                self.on_batch_status_listener(raw_events)
            except Exception:
                pass
        elif self.on_status_listener is not None:
            for evt in raw_events:
                try:
                    self.on_status_listener(evt)
                except Exception:
                    pass

        ts = time.strftime("%H:%M:%S")
        lines_to_log: list[tuple[str, str]] = []
        latest_progress: float | None = None
        last_btn: ctk.CTkButton | None = None
        failure_event: ObservabilityEvent | None = None
        run_complete = False

        for run_btn, event in batch:
            if run_btn is not None:
                last_btn = run_btn
            if event.progress is not None:
                latest_progress = float(event.progress)

            formatted = _format_event_message(event, ts)
            if formatted is not None:
                lines_to_log.append(formatted)

            if event.presentation_kind == PresentationKind.FAILURE:
                failure_event = event

            if event.progress == 1.0 or (
                event.presentation_kind == PresentationKind.SUCCESS
                and event.event_code == EventCode.SYSTEM_TEARDOWN
            ):
                run_complete = True

        if latest_progress is not None:
            self._set_progress(latest_progress)

        if lines_to_log:
            self.status_log.configure(state="normal")
            tb = self.status_log._textbox
            for text, tag in lines_to_log:
                tb.insert("end", text, tag)
            line_count = int(tb.index("end-1c").split(".", maxsplit=1)[0])
            if line_count > 5000:
                tb.delete("1.0", f"{line_count - 4500}.0")
            self.status_log.see("end")
            self.status_log.configure(state="disabled")

        if (run_complete or failure_event is not None) and last_btn is not None:
            last_btn.configure(state="normal", text=self._run_btn_text)
            if hasattr(self, "app_state") and self.app_state is not None:
                if failure_event is not None:
                    self.app_state.set_operation(OperationState.FAILED, "Pipeline execution failed")
                else:
                    self.app_state.set_operation(OperationState.READY)

        if failure_event is not None:
            messagebox.showerror("Execution Failure", _build_failure_dialog_text(failure_event))

    def _process_observability_event(
        self,
        run_btn: ctk.CTkButton | None,
        event: ObservabilityEvent,
    ) -> None:
        """Process a single event immediately for test and backwards compatibility."""
        self._process_event_batch([(run_btn, event)])

    def _process_status(
        self,
        run_btn: ctk.CTkButton | None,
        status: ObservabilityEvent,
    ) -> None:
        """Process status message on the Tkinter event loop thread."""
        self._process_observability_event(run_btn, status)


def _format_event_message(event: ObservabilityEvent, ts: str) -> tuple[str, str] | None:
    """Format structured observability event into a narrative display line, or None if suppressed."""
    if event.presentation_kind == PresentationKind.INTERNAL or not event.message.strip():
        return None

    if event.event_code in (
        EventCode.MARKET_TICKER_SUCCESS,
        EventCode.MARKET_TICKER_CACHE_HIT,
        EventCode.QUANT_ISIN_PROCESSED,
    ) and event.presentation_kind in (PresentationKind.STEP, PresentationKind.SUCCESS):
        return None

    tag = _DESKTOP_TAG_MAP.get(event.presentation_kind, "info")
    prefix = _DESKTOP_PREFIX_MAP.get(event.presentation_kind, "•")

    parts: list[str] = [f"{prefix} {event.message}"]
    if event.context.entity_type and event.context.entity_id and event.context.entity_type != "Run":
        parts.append(f"[{event.context.entity_type}: {event.context.entity_id}]")
    elif (
        event.context.entity_id
        and not event.context.entity_type
        and event.context.entity_id != event.context.run_id
    ):
        parts.append(f"[{event.context.entity_id}]")

    if event.context.rows is not None:
        parts.append(f"({event.context.rows:,} items)")

    if event.context.cache_hit is True:
        parts.append("(cached)")

    if event.context.duration_ms is not None:
        dur_sec = event.context.duration_ms / 1000.0
        dur_str = f"({dur_sec:.2f}s)" if dur_sec >= 1.0 else f"({event.context.duration_ms:.1f}ms)"
        parts.append(dur_str)

    if event.presentation_kind == PresentationKind.FAILURE and event.error is not None:
        if event.error.remediation_hint:
            parts.append(f"\n  ↳ Remediation: {event.error.remediation_hint}")
        if event.error.context_variables:
            ctx_summary = ", ".join(
                f"{k}={v}" for k, v in sorted(event.error.context_variables.items())
            )
            parts.append(f"\n  ↳ Context: [{ctx_summary}]")

    msg = " ".join(parts)
    return (f"[{ts}] {msg}\n", tag)


def _build_failure_dialog_text(event: ObservabilityEvent) -> str:
    """Build dialog message string for an execution failure event."""
    dialog_lines: list[str] = []
    if event.error is not None:
        dialog_lines.append(f"Failure Domain: {event.error.failure_domain.value}")
        dialog_lines.append(
            f"Error: {event.error.exception_type} - {event.error.exception_message}"
        )
        if event.error.failing_stage:
            dialog_lines.append(f"Stage: {event.error.failing_stage}")
        if event.error.failing_entity:
            dialog_lines.append(f"Entity: {event.error.failing_entity}")
        if event.error.remediation_hint:
            dialog_lines.append(f"\nRemediation: {event.error.remediation_hint}")
        if event.error.context_variables:
            dialog_lines.append("\nDiagnostic State:")
            for ck, cv in sorted(event.error.context_variables.items()):
                dialog_lines.append(f"  • {ck}: {cv}")
        dialog_lines.append("")
        dialog_lines.append(f"Run ID: {event.context.run_id}")
        dialog_lines.append("Inspect forensic log for complete trace and stack context.")
        if event.error.retryable:
            dialog_lines.append("Status: Transient failure eligible for retry.")
    else:
        dialog_lines.append(event.message)
        dialog_lines.append(f"Run ID: {event.context.run_id}")

    return "\n".join(dialog_lines)
