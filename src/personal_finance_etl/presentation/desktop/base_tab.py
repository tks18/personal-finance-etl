"""Abstract base tab component for CustomTkinter GUI applications.

Owns
----
- BaseEngineTab: Common 2-column layout with header and progress/log output panel.
- Thread-safe queue polling and main-thread status updates via Tkinter after().
- Progress bar and colored log text box state management.
- Processing structured ObservabilityEvents across process boundaries.

Does not own
-------------
- Specific ETL buttons or file selectors (owned by concrete tab implementations like UnifiedETLTab).
- Application orchestration logic or execution pipelines (owned by application.facade).
"""

from __future__ import annotations

import time
from tkinter import messagebox
from typing import Final

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
    PresentationKind,
)
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
        """Handle status updates from backend engine with thread-safe UI dispatch.

        Parameters
        ----------
        run_btn : ctk.CTkButton | None
            Execution button to re-enable on termination, if provided.
        status : ObservabilityEvent
            Status payload to render.
        """
        self.after(0, lambda: self._process_status(run_btn, status))

    def _process_status(
        self,
        run_btn: ctk.CTkButton | None,
        status: ObservabilityEvent,
    ) -> None:
        """Process status message on the Tkinter event loop thread.

        Parameters
        ----------
        run_btn : ctk.CTkButton | None
            Execution trigger button.
        status : ObservabilityEvent
            Canonical observability event to process.
        """
        if not self.winfo_exists():
            return

        self._process_observability_event(run_btn, status)

    def _process_observability_event(
        self,
        run_btn: ctk.CTkButton | None,
        event: ObservabilityEvent,
    ) -> None:
        """Process canonical ObservabilityEvent on Tkinter event loop thread."""
        if event.presentation_kind == PresentationKind.INTERNAL:
            return

        if event.progress is not None:
            self._set_progress(float(event.progress))

        # Pure progress updates without narrative prose should not log empty lines
        if not event.message.strip():
            return

        tag = _DESKTOP_TAG_MAP.get(event.presentation_kind, "info")
        prefix = _DESKTOP_PREFIX_MAP.get(event.presentation_kind, "•")

        parts: list[str] = [f"{prefix} {event.message}"]

        if event.context.entity_type and event.context.entity_id:
            parts.append(f"[{event.context.entity_type}: {event.context.entity_id}]")
        elif event.context.entity_id:
            parts.append(f"[{event.context.entity_id}]")

        if event.context.rows is not None:
            parts.append(f"({event.context.rows:,} items)")

        if event.context.cache_hit is True:
            parts.append("(cached)")

        if event.context.duration_ms is not None:
            if event.context.duration_ms >= 1000.0:
                parts.append(f"({event.context.duration_ms / 1000.0:.2f}s)")
            else:
                parts.append(f"({event.context.duration_ms:.1f}ms)")

        msg = " ".join(parts)
        self._log(msg, tag)

        if event.presentation_kind == PresentationKind.FAILURE:
            if run_btn is not None:
                run_btn.configure(state="normal", text=self._run_btn_text)

            dialog_lines: list[str] = []
            if event.error is not None:
                dialog_lines.append(f"Domain: {event.error.failure_domain.value}")
                dialog_lines.append(
                    f"Error: {event.error.exception_type} - {event.error.exception_message}"
                )
                dialog_lines.append("")
                dialog_lines.append(f"Run ID: {event.context.run_id}")
                dialog_lines.append("Inspect forensic log for complete diagnostic details.")
                if event.error.retryable:
                    dialog_lines.append("Status: Transient failure eligible for retry.")
            else:
                dialog_lines.append(event.message)
                dialog_lines.append(f"Run ID: {event.context.run_id}")

            messagebox.showerror("Execution Failure", "\n".join(dialog_lines))

        if event.progress == 1.0 or (
            event.presentation_kind == PresentationKind.SUCCESS
            and event.event_code == EventCode.SYSTEM_TEARDOWN
        ):
            if run_btn is not None:
                run_btn.configure(state="normal", text=self._run_btn_text)
