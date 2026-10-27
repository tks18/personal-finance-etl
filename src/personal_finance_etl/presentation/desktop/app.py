"""Unified Desktop GUI application for personal-finance-etl.

Owns
----
- UnifiedETLTab: Main dashboard for running ETL pipeline, configuring settings and rules paths,
  and executing database snapshot / restore operations.
- DesktopApp: Root CustomTkinter window with application icon, minimum bounds, and theme configuration.
- main: Desktop GUI launcher entry point.

Does not own
-------------
- Pipeline orchestration and execution (owned by application.pipeline).
- Database backup snapshot / restore implementation (owned by infrastructure.recovery.backup).
- Base tab layout and log box rendering (owned by presentation.desktop.base_tab).
"""

from __future__ import annotations

import os
from tkinter import filedialog

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
from PIL import Image

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.filesystem.paths import resource_path
from personal_finance_etl.presentation.desktop.base_tab import BaseEngineTab
from personal_finance_etl.presentation.desktop.theme import Color
from personal_finance_etl.presentation.docs.guides_window import show_guides_window

__all__ = ["DesktopApp", "UnifiedETLTab", "main"]

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class UnifiedETLTab(BaseEngineTab):
    """Unified Control Panel for the ETL, Benchmark, and Quant Engines."""

    def __init__(self, parent: ctk.CTk | ctk.CTkFrame) -> None:
        super().__init__(parent)

        self.engine = PersonalFinanceEngine()
        self._run_btn_text = "▶  Run Pipeline"
        self.config_path_var = ctk.StringVar()
        self.rules_path_var = ctk.StringVar()

        self._build_header()
        self._build_log_panel()
        self._configure_log_tags()

    def _build_header(self) -> None:
        """Construct the top control header including branding, paths, and action triggers."""
        hdr = ctk.CTkFrame(self, fg_color=Color.HEADER, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")

        # 3/4 weight for config, 1/4 weight for run button
        hdr.grid_columnconfigure(0, weight=3)
        hdr.grid_columnconfigure(1, weight=1)

        self._build_title_block(hdr)
        self._build_path_inputs(hdr)
        self._build_action_buttons(hdr)
        self._build_info_box(hdr)

        # ── Divider Line ─────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=Color.BORDER, height=1, corner_radius=0).grid(
            row=0, column=0, sticky="sew"
        )

    def _build_title_block(self, hdr: ctk.CTkFrame) -> None:
        """Render logo, title branding, and documentation guide trigger.

        Parameters
        ----------
        hdr : ctk.CTkFrame
            Header container frame.
        """
        title_block = ctk.CTkFrame(hdr, fg_color="transparent")
        title_block.grid(row=0, column=0, columnspan=2, padx=(16, 16), pady=(12, 0), sticky="w")

        logo_path = resource_path("docs/assets/images/logo.png")
        if os.path.exists(logo_path):
            img = ctk.CTkImage(dark_image=Image.open(logo_path), size=(36, 36))
            ctk.CTkLabel(title_block, image=img, text="").grid(
                row=0, column=0, rowspan=2, padx=(0, 12), sticky="w"
            )

        text_block = ctk.CTkFrame(title_block, fg_color="transparent")
        text_block.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            text_block,
            text="Personal Finance ETL",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=Color.TEXT,
        ).pack(anchor="w")

        guides_btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        guides_btn_frame.grid(row=0, column=1, padx=(0, 16), pady=(12, 0), sticky="e")

        ctk.CTkButton(
            guides_btn_frame,
            text="📚 Guides & About",
            width=140,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            corner_radius=6,
            command=show_guides_window,
        ).pack(anchor="e")

        ctk.CTkLabel(
            text_block,
            text="Local-First Financial Data Engineering & Quantitative Decision-Support Platform",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.DIM,
        ).pack(anchor="w")

    def _build_path_inputs(self, hdr: ctk.CTkFrame) -> None:
        """Render configuration and rules path selectors in the desktop header.

        Parameters
        ----------
        hdr : ctk.CTkFrame
            Header container frame.
        """
        # ── Config Path (Row 1, Col 0) ─────────────────────────────
        cfg_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        cfg_frame.grid(row=1, column=0, padx=(16, 10), pady=(12, 4), sticky="ew")
        cfg_frame.grid_columnconfigure(0, weight=0)  # label
        cfg_frame.grid_columnconfigure(1, weight=1)  # entry

        recents = self.engine.get_recent_configs()
        if recents:
            self.config_path_var.set(recents[0])

        ctk.CTkLabel(
            cfg_frame,
            text="Pipeline Config",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#7DD3FC",
            fg_color="#0E2235",
            corner_radius=4,
            width=100,
            anchor="center",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), ipady=3, ipadx=6)

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
        cfg_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

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
            command=lambda: self._select_file(self.config_path_var, "TOML", "*.toml"),
        ).grid(row=0, column=2)

        # ── Rules Path (Row 2, Col 0) ──────────────────────────────
        rules_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        rules_frame.grid(row=2, column=0, padx=(16, 10), pady=(4, 4), sticky="ew")
        rules_frame.grid_columnconfigure(0, weight=0)  # label
        rules_frame.grid_columnconfigure(1, weight=1)  # entry

        recent_rules = self.engine.get_recent_rules()
        if recent_rules:
            self.rules_path_var.set(recent_rules[0])

        ctk.CTkLabel(
            rules_frame,
            text="Financial Rules",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#86EFAC",
            fg_color="#0E2318",
            corner_radius=4,
            width=100,
            anchor="center",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), ipady=3, ipadx=6)

        rules_entry = ctk.CTkComboBox(
            rules_frame,
            variable=self.rules_path_var,
            values=recent_rules if recent_rules else [""],
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
        )
        rules_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            rules_frame,
            text="…",
            width=32,
            height=32,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=Color.BORDER,
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=4,
            command=lambda: self._select_file(self.rules_path_var, "Rules TOML", "*.toml"),
        ).grid(row=0, column=2)

    def _build_action_buttons(self, hdr: ctk.CTkFrame) -> None:
        """Render execution and snapshot action buttons.

        Parameters
        ----------
        hdr : ctk.CTkFrame
            Header container frame.
        """
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=1, column=1, rowspan=2, padx=(0, 16), pady=(12, 4), sticky="ns")
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

        self.snapshot_btn = ctk.CTkButton(
            btn_frame,
            text="📸 Snapshot DB",
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            corner_radius=6,
            command=self._snapshot_db,
        )
        self.snapshot_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.restore_btn = ctk.CTkButton(
            btn_frame,
            text="♻️ Restore DB",
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            corner_radius=6,
            command=self._restore_db,
        )
        self.restore_btn.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _build_info_box(self, hdr: ctk.CTkFrame) -> None:
        """Render informational mission banner at the bottom of the header.

        Parameters
        ----------
        hdr : ctk.CTkFrame
            Header container frame.
        """
        info_block = ctk.CTkFrame(hdr, fg_color="transparent")
        info_block.grid(row=3, column=0, columnspan=2, padx=(16, 16), pady=(4, 16), sticky="ew")

        info = ctk.CTkFrame(info_block, fg_color=Color.BORDER, corner_radius=6)
        info.pack(fill="x", expand=True)

        info_text = (
            "Preserve financial evidence → Canonicalize meaning → Reconstruct state → "
            "Reconcile against reality → Support decisions across Investments, Tax, Household, and FIRE."
        )
        ctk.CTkLabel(
            info,
            text=info_text,
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
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.GENERIC_DIAGNOSTIC,
                    message=f"Error loading initial config: {e}",
                    progress=0.0,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                ),
            )

    def _on_config_selected(self, path: str) -> None:
        """Handle user selection of configuration file and validate syntax.

        Parameters
        ----------
        path : str
            File system path to chosen pipeline configuration file.
        """
        if not path:
            return
        if not self.engine.validate_config(path):
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.GENERIC_DIAGNOSTIC,
                    message=f"Failed to load config from {path}",
                    progress=0.0,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                ),
            )

    def _select_file(
        self, str_var: ctk.StringVar, type_name: str = "TOML", ext: str = "*.toml"
    ) -> None:
        """Open native desktop file dialog to pick a configuration file.

        Parameters
        ----------
        str_var : ctk.StringVar
            Tkinter String variable to store the selected file path.
        type_name : str, default "TOML"
            Configuration file type label.
        ext : str, default "*.toml"
            File extension filter glob.
        """
        path = filedialog.askopenfilename(
            title=f"Select {type_name} Config",
            filetypes=[(f"{type_name} files", ext), ("All files", "*.*")],
        )
        if path:
            str_var.set(path)
            if type_name == "TOML":  # Main Config TOML
                self._on_config_selected(path)
            else:
                # Save to recents immediately for rules
                self.engine.add_recent_rules(path)

    def _start_pipeline(self) -> None:
        """Initiate asynchronous pipeline execution from the desktop UI tab."""
        self.run_btn.configure(state="disabled", text="Running...")
        self.status_log.configure(state="normal")
        self.status_log.delete("1.0", "end")
        self.status_log.configure(state="disabled")

        self.engine.run_pipeline_async(
            config_path=self.config_path_var.get(),
            rules_path=self.rules_path_var.get(),
            on_status=lambda status: self.handle_status(self.run_btn, status),
        )

    def _snapshot_db(self) -> None:
        """Trigger an instant database snapshot backup from the desktop UI tab."""
        try:
            snap_path = self.engine.snapshot_database(self.config_path_var.get())
            if snap_path:
                self.handle_status(
                    self.run_btn,
                    ObservabilityEvent.create(
                        event_code=EventCode.RECOVERY_SNAPSHOT,
                        message=f"Database snapshot created at: {snap_path}",
                        progress=1.0,
                        severity=DiagnosticSeverity.INFO,
                        outcome=EventOutcome.COMPLETED,
                        presentation_kind=PresentationKind.SUCCESS,
                    ),
                )
            else:
                self.handle_status(
                    self.run_btn,
                    ObservabilityEvent.create(
                        event_code=EventCode.RECOVERY_SNAPSHOT,
                        message="Database file does not exist yet. Run the pipeline first.",
                        progress=0.0,
                        severity=DiagnosticSeverity.WARNING,
                        outcome=EventOutcome.FAILED,
                        presentation_kind=PresentationKind.FAILURE,
                    ),
                )
        except Exception as e:
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.RECOVERY_SNAPSHOT,
                    message=f"Failed to create snapshot: {e}",
                    progress=0.0,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                ),
            )

    def _restore_db(self) -> None:
        """Prompt user for snapshot archive and initiate database restoration."""
        zip_path = filedialog.askopenfilename(
            title="Select Snapshot ZIP",
            filetypes=[("Zip files", "*.zip")],
        )
        if not zip_path:
            return

        self.run_btn.configure(state="disabled")
        self.snapshot_btn.configure(state="disabled")
        self.restore_btn.configure(state="disabled", text="Restoring...")

        try:
            self._execute_restore(zip_path)
        finally:
            self.run_btn.configure(state="normal")
            self.snapshot_btn.configure(state="normal")
            self.restore_btn.configure(state="normal", text="♻️ Restore DB")

    def _execute_restore(self, zip_path: str) -> None:
        """Execute database restore and propagate status messages.

        Parameters
        ----------
        zip_path : str
            Absolute path to the snapshot zip file.
        """
        try:
            success = self.engine.restore_database(self.config_path_var.get(), zip_path)
            msg = (
                "Database snapshot restored successfully."
                if success
                else "Failed to restore snapshot."
            )
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.RECOVERY_RESTORE,
                    message=msg,
                    progress=1.0 if success else 0.0,
                    severity=(DiagnosticSeverity.INFO if success else DiagnosticSeverity.ERROR),
                    outcome=(EventOutcome.COMPLETED if success else EventOutcome.FAILED),
                    presentation_kind=(
                        PresentationKind.SUCCESS if success else PresentationKind.FAILURE
                    ),
                ),
            )
        except PermissionError as pe:
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.RECOVERY_RESTORE,
                    message=str(pe),
                    progress=0.0,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                ),
            )
        except Exception as e:
            self.handle_status(
                self.run_btn,
                ObservabilityEvent.create(
                    event_code=EventCode.RECOVERY_RESTORE,
                    message=f"Unexpected error restoring snapshot: {e}",
                    progress=0.0,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                ),
            )


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTk base class
class DesktopApp(ctk.CTk):  # type: ignore[misc]
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Personal Finance ETL")
        self.geometry("960x660")
        self.minsize(760, 500)
        self.configure(fg_color="#0D1117")

        icon_path = resource_path("docs/assets/images/logo.ico")
        if os.path.exists(icon_path):
            self.after(200, lambda: self.iconbitmap(icon_path))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        UnifiedETLTab(self).grid(row=0, column=0, sticky="nsew")


def main() -> None:
    """Initialize and run the CustomTkinter desktop user interface."""
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
