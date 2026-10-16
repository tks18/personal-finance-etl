"""Abstract base tab component for CustomTkinter GUI applications.

Owns
----
- BaseEngineTab: Common 2-column layout with header and progress/log output panel.
- Thread-safe queue polling and main-thread status updates via Tkinter after().
- Progress bar and colored log text box state management.

Does not own
-------------
- Specific ETL buttons or file selectors (owned by concrete tab implementations like UnifiedETLTab).
- Application orchestration logic or execution pipelines (owned by application.facade).
"""

from __future__ import annotations

import time
from tkinter import messagebox

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.presentation.desktop.theme import (
    LOG_TAG_COLORS,
    Color,
    ExportMode,
)

__all__ = ["BaseEngineTab"]


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
        """Helper to create a standard styled section header label."""
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=Color.DIM,
            anchor="w",
        ).grid(row=row, column=0, padx=10, pady=(12, 4), sticky="w")
        return row + 1

    def handle_status(self, run_btn: ctk.CTkButton, status: EngineStatusMessage) -> None:
        """Handle status updates from the backend engine with thread-safe UI dispatch."""
        self.after(0, lambda: self._process_status(run_btn, status))

    def _process_status(self, run_btn: ctk.CTkButton, status: EngineStatusMessage) -> None:
        """Process status message on the Tkinter event loop thread."""
        if not self.winfo_exists():
            return

        prog = getattr(status, "progress", None)
        if prog is not None:
            self._set_progress(float(prog))

        msg = getattr(status, "msg", "") or getattr(status, "message", "")
        lvl = getattr(status, "level", LogLevel.INFO)
        level_str = lvl.value if isinstance(lvl, LogLevel) else str(lvl).lower()

        if msg:
            self._log(msg, level_str)
            if lvl == LogLevel.ERROR or level_str == "error":
                run_btn.configure(state="normal", text=self._run_btn_text)
                messagebox.showerror("Error", msg)

        if prog == 1.0:
            run_btn.configure(state="normal", text=self._run_btn_text)
