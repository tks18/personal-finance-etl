"""
BaseEngineTab — Abstract base class for UI tabs.
Consolidates duplicated log panel, queue polling, and styling code.
"""

import queue
import time
from tkinter import messagebox
import customtkinter as ctk  # type: ignore[import-untyped]

from src.utils.models import EngineStatus, LogLevel, ExportMode
from src.utils.theme import Color, LOG_TAG_COLORS


import multiprocessing


class BaseEngineTab(ctk.CTkFrame):
    """Base tab handling standard 2-column layout and log/queue operations."""

    def __init__(self, parent: ctk.CTk | ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.status_queue: "multiprocessing.Queue[EngineStatus]" = multiprocessing.Queue()
        self.save_target = ""
        self.save_type = ExportMode.CONSOLIDATED
        self._run_btn_text = "▶  Run"

        # 1-column layout — header | log
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

    def _build_log_panel(self) -> None:
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
            prog, height=3, corner_radius=2,
            fg_color=Color.SIDEBAR, progress_color=Color.ACCENT,
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)

        self.pct_label = ctk.CTkLabel(
            prog, text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.DIM, width=32, anchor="e",
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
        self.status_log.grid(row=1, column=0, sticky="nsew",
                             padx=(8, 0), pady=(6, 0))

    def _configure_log_tags(self) -> None:
        tb = self.status_log._textbox
        for tag, colour in LOG_TAG_COLORS.items():
            tb.tag_config(tag, foreground=colour)
        tb.tag_config(
            "ts", foreground=LOG_TAG_COLORS["ts"], font=("Consolas", 10))

    def _set_progress(self, value: float) -> None:
        self.progress.set(value)
        self.pct_label.configure(text=f"{int(value * 100)}%")

    def _log(self, msg: str, level: str = "info") -> None:
        ts = time.strftime("%H:%M:%S")
        self.status_log.configure(state="normal")
        tb = self.status_log._textbox
        tb.insert("end", f"[{ts}] ", "ts")
        tb.insert("end", f"{msg}\n", level)
        self.status_log.see("end")
        self.status_log.configure(state="disabled")

    def _section_label(self, parent: ctk.CTkFrame, text: str, row: int) -> int:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=Color.DIM, anchor="w",
        ).grid(row=row, column=0, padx=10, pady=(12, 4), sticky="w")
        return row + 1

    def _poll_queue_base(self, run_btn: ctk.CTkButton) -> None:
        try:
            while True:
                item = self.status_queue.get_nowait()
                if not self.winfo_exists():
                    break

                # Support backwards compatibility during the refactor phase
                if isinstance(item, tuple):
                    msg, data, prog = item
                    status = EngineStatus(msg=msg, data=data, progress=prog)
                    # Infer level like before
                    if msg:
                        lw = msg.lower()
                        if "error" in lw or msg.startswith("Error"):
                            status.level = LogLevel.ERROR
                        elif "✅" in msg or "complete" in lw or "success" in lw or "✓" in msg or "exported" in lw:
                            status.level = LogLevel.SUCCESS
                        elif "warning" in lw:
                            status.level = LogLevel.WARNING
                        elif "fetching" in lw or "loading" in lw or "post-processing" in lw or msg.startswith("["):
                            status.level = LogLevel.STEP
                        else:
                            status.level = LogLevel.INFO
                else:
                    status = item

                if status.progress is not None:
                    self._set_progress(status.progress)

                if status.msg:
                    self._log(status.msg, status.level)
                    if status.level == LogLevel.ERROR:
                        run_btn.configure(
                            state="normal", text=self._run_btn_text)
                        messagebox.showerror("Error", status.msg)

                if status.progress == 1.0:
                    run_btn.configure(state="normal", text=self._run_btn_text)

        except queue.Empty:
            pass
        finally:
            self.after(100, lambda: self._poll_queue_base(run_btn))
