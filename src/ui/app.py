"""
Unified App: Root application window for Personal Finance ETL.
"""

import multiprocessing
import os
import queue
import traceback
from tkinter import filedialog

import customtkinter as ctk  # type: ignore[import-untyped]
from PIL import Image

from src.config.settings import PreferencesManager, Settings
from src.pipeline.etl_pipeline import process_wrapper
from src.ui.base_tab import BaseEngineTab
from src.utils.helpers import resource_path
from src.utils.models import EngineStatus, LogLevel
from src.utils.theme import Color

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class UnifiedETLTab(BaseEngineTab):
    """Unified Control Panel for the ETL, Benchmark, and Tax Engines."""

    def __init__(self, parent: ctk.CTk | ctk.CTkFrame) -> None:
        super().__init__(parent)

        self._run_btn_text = "▶  Run Pipeline"
        self.config_path_var = ctk.StringVar()

        self._build_header()
        self._build_log_panel()
        self._configure_log_tags()

        self._poll_queue_base(self.run_btn)

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=Color.HEADER, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")

        # 3/4 weight for config, 1/4 weight for run button
        hdr.grid_columnconfigure(0, weight=3)
        hdr.grid_columnconfigure(1, weight=1)

        # ── 1. Title Block (Row 0) ─────────────────────────────────
        title_block = ctk.CTkFrame(hdr, fg_color="transparent")
        title_block.grid(row=0, column=0, columnspan=2, padx=(16, 16), pady=(12, 0), sticky="w")

        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            img = ctk.CTkImage(dark_image=Image.open(logo_path), size=(36, 36))
            ctk.CTkLabel(title_block, image=img, text="").grid(
                row=0, column=0, rowspan=2, padx=(0, 12), sticky="w"
            )

        text_block = ctk.CTkFrame(title_block, fg_color="transparent")
        text_block.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            text_block,
            text="Shan's Personal Finance ETL",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=Color.TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_block,
            text="Automated Pipeline Orchestrator & Tax Engine",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.DIM,
        ).pack(anchor="w")

        # ── 2. Config Path (Row 1, Col 0) (3/4th) ───────────────────
        cfg_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        cfg_frame.grid(row=1, column=0, padx=(16, 10), pady=(12, 4), sticky="ew")
        cfg_frame.grid_columnconfigure(0, weight=1)

        recents = PreferencesManager().get_recent_configs()
        if recents:
            self.config_path_var.set(recents[0])

        cfg_entry = ctk.CTkComboBox(
            cfg_frame,
            variable=self.config_path_var,
            values=recents if recents else [""],
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
            command=self._on_config_selected,
        )
        cfg_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            cfg_frame,
            text="…",
            width=32,
            height=32,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=Color.BORDER,
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=4,
            command=lambda: self._select_file(self.config_path_var),
        ).grid(row=0, column=1)

        # ── 3. Run Button (Row 1, Col 1) (1/4th) ────────────────────
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=1, column=1, padx=(0, 16), pady=(12, 4), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self.run_btn = ctk.CTkButton(
            btn_frame,
            text=self._run_btn_text,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            corner_radius=6,
            command=self._start_pipeline,
        )
        self.run_btn.grid(row=0, column=0, sticky="ew")

        # ── 4. Helper Info Box (Row 2) ──────────────────────────────
        info_block = ctk.CTkFrame(hdr, fg_color="transparent")
        info_block.grid(row=2, column=0, columnspan=2, padx=(16, 16), pady=(4, 16), sticky="ew")

        info = ctk.CTkFrame(info_block, fg_color=Color.BORDER, corner_radius=6)
        info.pack(fill="x", expand=True)

        ctk.CTkLabel(
            info,
            text="Pipeline fully automated: Automatically detects dates from Market Data for Benchmarks and skips manual CSV exports.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.DIM,
            justify="left",
            anchor="w",
        ).pack(padx=10, pady=6, anchor="w")

        # ── 5. Divider Line ─────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=Color.BORDER, height=1, corner_radius=0).grid(
            row=0, column=0, sticky="sew"
        )

        try:
            if self.config_path_var.get():
                self._on_config_selected(self.config_path_var.get())
        except Exception as e:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Error loading initial config: {e}",
                    data=None,
                    progress=0.0,
                    level=LogLevel.ERROR,
                )
            )

    def _on_config_selected(self, path: str) -> None:
        if not path:
            return
        try:
            Settings.from_toml(path)
        except Exception as e:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Failed to load config: {e}\n{traceback.format_exc()}",
                    data=None,
                    progress=0.0,
                    level=LogLevel.ERROR,
                )
            )

    def _select_file(self, str_var: ctk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Select Config", filetypes=[("TOML files", "*.toml"), ("All files", "*.*")]
        )
        if path:
            str_var.set(path)
            self._on_config_selected(path)

    def _start_pipeline(self) -> None:
        self.run_btn.configure(state="disabled", text="Running...")
        while not self.status_queue.empty():
            try:
                self.status_queue.get_nowait()
            except queue.Empty:
                break
        self.status_log.configure(state="normal")
        self.status_log.delete("1.0", "end")
        self.status_log.configure(state="disabled")

        multiprocessing.Process(
            target=process_wrapper,
            args=(self.status_queue, self.config_path_var.get()),
            daemon=True,
        ).start()


class App(ctk.CTk):
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Shan's Personal Finance ETL")
        self.geometry("960x660")
        self.minsize(760, 500)
        self.configure(fg_color="#0D1117")

        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.after(200, lambda: self.iconbitmap(icon_path))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        UnifiedETLTab(self).grid(row=0, column=0, sticky="nsew")


if __name__ == "__main__":
    app = App()
    app.mainloop()
