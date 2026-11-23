"""Run Tab component for orchestrating ETL pipelines and backups.

Owns
----
- RunTab: Primary execution dashboard for running pipelines, managing database snapshots,
  restoring backups, and viewing live logs and progress.
- UnifiedETLTab: Backward-compatible alias for RunTab.
- Two-way state synchronization with AppState.

Does not own
-------------
- TOML settings editing and field serialization (owned by settings_tab).
- Backend pipeline execution (owned by application.pipeline).
"""

from __future__ import annotations

from collections.abc import Callable
from tkinter import filedialog
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.presentation.desktop.base_tab import BaseEngineTab
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = ["RunTab", "UnifiedETLTab"]


class RunTab(BaseEngineTab):
    """Unified Control Panel for the ETL, Benchmark, and Quant Engines."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
        on_config_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state
        self.on_config_changed = on_config_changed
        self._run_btn_text = "▶  Run Pipeline"

        recents_cfg = self.engine.get_recent_configs()
        recents_rules = self.engine.get_recent_rules()

        initial_cfg = (
            self.app_state.active_config_path
            if self.app_state
            else (recents_cfg[0] if recents_cfg else "")
        )
        initial_rules = (
            self.app_state.active_rules_path
            if self.app_state
            else (recents_rules[0] if recents_rules else "")
        )

        self.config_path_var = ctk.StringVar(value=initial_cfg)
        self.rules_path_var = ctk.StringVar(value=initial_rules)

        self._build_header()
        self._build_log_panel()
        self._configure_log_tags()

        if self.app_state is not None:
            self.app_state.subscribe_config(self._on_external_config_changed)
            self.app_state.subscribe_rules(self._on_external_rules_changed)

    def _on_external_config_changed(self, path: str, source: Any) -> None:
        """Handle active config update originating from another tab or state."""
        if source is self:
            return
        self.set_config_path(path)

    def _on_external_rules_changed(self, path: str, source: Any) -> None:
        """Handle active rules update originating from another tab or state."""
        if source is self:
            return
        if not path:
            return
        self.rules_path_var.set(path)
        recents = self.engine.get_recent_rules()
        if hasattr(self, "rules_combo") and recents:
            self.rules_combo.configure(values=recents)

    def set_config_path(self, path: str) -> None:
        """Update active configuration path externally (e.g. from Settings tab)."""
        if not path:
            return
        self.config_path_var.set(path)
        recents = self.engine.get_recent_configs()
        if hasattr(self, "cfg_combo") and recents:
            self.cfg_combo.configure(values=recents)
        self._on_config_selected(path, notify=False)

    def ensure_config_loaded(self, path: str) -> None:
        """Ensure the specified configuration is reflected in the active selection."""
        if path and path != self.config_path_var.get():
            self.set_config_path(path)

    def _build_header(self) -> None:
        """Construct the top control header including paths, actions, and mission banner."""
        hdr_container = ctk.CTkFrame(self, fg_color="transparent")
        hdr_container.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        hdr_container.grid_columnconfigure(0, weight=1)

        # Control Card
        card = ctk.CTkFrame(
            hdr_container,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=3)  # Left column (Paths)
        card.grid_columnconfigure(1, weight=1)  # Right column (Action buttons)

        self._build_path_inputs(card)
        self._build_action_buttons(card)
        self._build_info_box(hdr_container)

    def _build_path_inputs(self, card: ctk.CTkFrame) -> None:
        """Render configuration and rules path selectors in the control card."""
        left_col = ctk.CTkFrame(card, fg_color="transparent")
        left_col.grid(row=0, column=0, padx=(12, 12), pady=12, sticky="nsew")
        left_col.grid_columnconfigure(1, weight=1)

        # ── Pipeline Config Row ──────────────────────────────────
        ctk.CTkLabel(
            left_col,
            text="Pipeline Config",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#7DD3FC",
            fg_color="#0E2235",
            corner_radius=4,
            width=100,
            anchor="center",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8), ipady=4, ipadx=6)

        recents = self.engine.get_recent_configs()
        self.cfg_combo = ctk.CTkComboBox(
            left_col,
            variable=self.config_path_var,
            values=recents if recents else [""],
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
            command=self._on_combo_config_select,
        )
        self.cfg_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))

        ctk.CTkButton(
            left_col,
            text="Browse…",
            width=72,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=lambda: self._select_file(self.config_path_var, "TOML", "*.toml"),
        ).grid(row=0, column=2, pady=(0, 8))

        # ── Financial Rules Row ──────────────────────────────────
        ctk.CTkLabel(
            left_col,
            text="Financial Rules",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#86EFAC",
            fg_color="#0E2318",
            corner_radius=4,
            width=100,
            anchor="center",
        ).grid(row=1, column=0, sticky="w", padx=(0, 8), ipady=4, ipadx=6)

        recent_rules = self.engine.get_recent_rules()
        self.rules_combo = ctk.CTkComboBox(
            left_col,
            variable=self.rules_path_var,
            values=recent_rules if recent_rules else [""],
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
            command=self._on_combo_rules_select,
        )
        self.rules_combo.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            left_col,
            text="Browse…",
            width=72,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=lambda: self._select_file(self.rules_path_var, "Rules TOML", "*.toml"),
        ).grid(row=1, column=2)

    def _build_action_buttons(self, card: ctk.CTkFrame) -> None:
        """Render execution and snapshot action buttons."""
        right_col = ctk.CTkFrame(card, fg_color="transparent")
        right_col.grid(row=0, column=1, padx=(0, 12), pady=12, sticky="nsew")
        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_columnconfigure(1, weight=1)

        # Main Run Button spanning top
        self.run_btn = ctk.CTkButton(
            right_col,
            text=self._run_btn_text,
            height=34,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            corner_radius=6,
            command=self._start_pipeline,
        )
        self.run_btn.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        # Secondary Buttons side by side
        self.snapshot_btn = ctk.CTkButton(
            right_col,
            text="📸 Snapshot",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self._snapshot_db,
        )
        self.snapshot_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4))

        self.restore_btn = ctk.CTkButton(
            right_col,
            text="♻ Restore",
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self._restore_db,
        )
        self.restore_btn.grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def _build_info_box(self, hdr_container: ctk.CTkFrame) -> None:
        """Render informational mission banner."""
        info = ctk.CTkFrame(
            hdr_container,
            fg_color="#090D15",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
        )
        info.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        info_text = (
            "Preserve financial evidence  •  Canonicalize meaning  •  Reconstruct state  •  "
            "Reconcile against reality  •  Support decisions across Investments, Tax, Household, and FIRE."
        )
        ctk.CTkLabel(
            info,
            text=info_text,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#64748B",
            justify="center",
            anchor="center",
        ).pack(padx=10, pady=5)

    def _build_log_panel(self) -> None:
        """Construct the progress bar, telemetry header, and scrollable log text box panel."""
        panel = ctk.CTkFrame(self, fg_color=Color.BG, corner_radius=0)
        panel.grid(row=1, column=0, sticky="nsew", padx=14, pady=(6, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # Telemetry Bar
        tel_bar = ctk.CTkFrame(panel, fg_color="transparent")
        tel_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tel_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            tel_bar,
            text="Console Telemetry",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
        ).grid(row=0, column=0, sticky="w", padx=(2, 10))

        prog_box = ctk.CTkFrame(tel_bar, fg_color="transparent")
        prog_box.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        prog_box.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            prog_box,
            height=4,
            corner_radius=2,
            fg_color="#1E293B",
            progress_color=Color.ACCENT,
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)

        self.pct_label = ctk.CTkLabel(
            prog_box,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#94A3B8",
            width=36,
            anchor="e",
        )
        self.pct_label.grid(row=0, column=1, padx=(6, 0))

        # Clear Console button
        ctk.CTkButton(
            tel_bar,
            text="Clear",
            width=50,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1E293B",
            hover_color="#334155",
            corner_radius=4,
            command=self._clear_console,
        ).grid(row=0, column=2, sticky="e")

        # Monospace Log Console
        self.status_log = ctk.CTkTextbox(
            panel,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=Color.LOG_BG,
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
            state="disabled",
            wrap="word",
        )
        self.status_log.grid(row=1, column=0, sticky="nsew")

    def _clear_console(self) -> None:
        """Clear the text contents of the status console."""
        self.status_log.configure(state="normal")
        self.status_log.delete("1.0", "end")
        self.status_log.configure(state="disabled")

    def _on_combo_config_select(self, path: str) -> None:
        """Handle config selection from dropdown."""
        self._on_config_selected(path, notify=True)

    def _on_combo_rules_select(self, path: str) -> None:
        """Handle rules selection from dropdown."""
        if path:
            self.engine.add_recent_rules(path)
            if self.app_state is not None:
                self.app_state.set_active_rules(path, source=self)

    def _on_config_selected(self, path: str, notify: bool = True) -> None:
        """Handle user selection of configuration file and validate syntax."""
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
        else:
            self.engine.add_recent_config(path)
            if notify and self.app_state is not None:
                self.app_state.set_active_config(path, source=self)
            if notify and self.on_config_changed:
                self.on_config_changed(path)

    def _select_file(
        self, str_var: ctk.StringVar, type_name: str = "TOML", ext: str = "*.toml"
    ) -> None:
        """Open native file dialog to pick a configuration file."""
        path = filedialog.askopenfilename(
            title=f"Select {type_name} Config",
            filetypes=[(f"{type_name} files", ext), ("All files", "*.*")],
        )
        if path:
            str_var.set(path)
            if type_name == "TOML":
                self._on_config_selected(path, notify=True)
            else:
                self.engine.add_recent_rules(path)
                if self.app_state is not None:
                    self.app_state.set_active_rules(path, source=self)

    def _start_pipeline(self) -> None:
        """Initiate asynchronous pipeline execution from the desktop UI tab."""
        self.run_btn.configure(state="disabled", text="Running...")
        self._clear_console()

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
            self.restore_btn.configure(state="normal", text="♻ Restore")

    def _execute_restore(self, zip_path: str) -> None:
        """Execute database restore and propagate status messages."""
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


# Backward compatibility alias
UnifiedETLTab = RunTab
