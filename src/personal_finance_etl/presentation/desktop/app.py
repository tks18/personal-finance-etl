"""Unified Desktop GUI application for personal-finance-etl.

Owns
----
- DesktopApp: Root CustomTkinter window hosting the sleek top navigation bar,
  AppState synchronization coordinator, and tab view switcher.
- main: Desktop GUI launcher entry point.

Does not own
-------------
- Pipeline orchestration and execution (owned by application.pipeline).
- Database backup snapshot / restore implementation (owned by infrastructure.recovery.backup).
- Base tab layout and log box rendering (owned by presentation.desktop.base_tab).
"""

from __future__ import annotations

import os

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
from PIL import Image

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.infrastructure.filesystem.paths import resource_path
from personal_finance_etl.presentation.desktop.configuration_tab import ConfigurationTab
from personal_finance_etl.presentation.desktop.financial_rules_tab import FinancialRulesTab
from personal_finance_etl.presentation.desktop.logs_tab import LogsTab
from personal_finance_etl.presentation.desktop.run_tab import RunTab
from personal_finance_etl.presentation.desktop.settings_tab import SettingsTab
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.system_tab import SystemTab
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = [
    "ConfigurationTab",
    "DesktopApp",
    "FinancialRulesTab",
    "LogsTab",
    "RunTab",
    "SettingsTab",
    "SystemTab",
    "main",
]

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTk base class
class DesktopApp(ctk.CTk):  # type: ignore[misc]
    """Root application window with unified header and synchronized tab navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Personal Finance ETL")
        self.geometry("1020x740")
        self.minsize(840, 580)
        self.configure(fg_color=Color.BG)

        icon_path = resource_path("presentation/assets/logo.ico")
        if os.path.exists(icon_path):
            self.after(200, lambda: self.iconbitmap(icon_path))

        self.engine = PersonalFinanceEngine()
        self.app_state = AppState(self.engine)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top Navigation Header
        self.grid_rowconfigure(1, weight=1)  # Tab Content Area

        self.tab_buttons: dict[str, ctk.CTkButton] = {}
        self.active_tab_id: str = "run"

        self._build_top_header()
        self._build_content_views()

    def _build_top_header(self) -> None:
        """Construct the full-width app header containing branding, tab navigation, and status."""
        header = ctk.CTkFrame(self, fg_color="#0A0E17", height=54, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=0)  # Brand
        header.grid_columnconfigure(1, weight=1)  # Tab navigation (centered)
        header.grid_columnconfigure(2, weight=0)  # Status badge

        # ── 1. Brand Block (Left) ────────────────────────────────
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=(16, 24), pady=10, sticky="w")

        logo_path = resource_path("presentation/assets/logo.png")
        if os.path.exists(logo_path):
            img = ctk.CTkImage(dark_image=Image.open(logo_path), size=(28, 28))
            ctk.CTkLabel(brand_frame, image=img, text="").pack(side="left", padx=(0, 10))

        title_col = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_col.pack(side="left")

        ctk.CTkLabel(
            title_col,
            text="Personal Finance ETL",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=Color.TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            title_col,
            text="Lakehouse",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#38BDF8",
            fg_color="#0B263B",
            corner_radius=4,
        ).pack(side="left", padx=(8, 0), ipady=1, ipadx=5)

        # ── 2. Tab Navigation Switcher (Center) ──────────────────
        nav_frame = ctk.CTkFrame(
            header, fg_color="#101624", corner_radius=7, border_width=1, border_color="#1E293B"
        )
        nav_frame.grid(row=0, column=1, pady=10)

        tabs_spec = [
            ("run", "▶  Pipeline Run"),
            ("config", "⚙️  Configuration"),
            ("logs", "📋  Forensic Logs"),
            ("system", "🩺  System & Health"),
        ]

        for tab_id, tab_label in tabs_spec:
            btn = ctk.CTkButton(
                nav_frame,
                text=tab_label,
                width=135,
                height=30,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=Color.ACCENT if tab_id == "run" else "transparent",
                hover_color=Color.ACC_HOV if tab_id == "run" else "#1E293B",
                text_color="#FFFFFF" if tab_id == "run" else "#94A3B8",
                corner_radius=5,
                command=lambda tid=tab_id: self.switch_tab(tid),
            )
            btn.pack(side="left", padx=2, pady=2)
            self.tab_buttons[tab_id] = btn

        # ── 3. Status Badge (Right) ──────────────────────────────
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=2, padx=(0, 16), pady=10, sticky="e")

        ctk.CTkLabel(
            status_frame,
            text="● Engine Ready",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#4ADE80",
            fg_color="#062817",
            corner_radius=4,
        ).pack(side="right", ipady=2, ipadx=8)

        # ── 4. Bottom Divider ────────────────────────────────────
        divider = ctk.CTkFrame(self, fg_color="#1E293B", height=1, corner_radius=0)
        divider.grid(row=0, column=0, sticky="sew")

    def _build_content_views(self) -> None:
        """Instantiate initial RunTab and initialize lazy container references."""
        self.content_container = ctk.CTkFrame(self, fg_color=Color.BG, corner_radius=0)
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        self.run_tab = RunTab(
            self.content_container,
            engine=self.engine,
            app_state=self.app_state,
        )
        self._config_tab: ConfigurationTab | None = None
        self._logs_tab: LogsTab | None = None
        self._system_tab: SystemTab | None = None

        # Stream pipeline execution narratives to logs tab if instantiated
        self.run_tab.on_batch_status_listener = self._on_pipeline_status_batch
        self.run_tab.on_status_listener = self._on_pipeline_status

        # Display initial tab
        self.run_tab.grid(row=0, column=0, sticky="nsew")

    def _on_pipeline_status_batch(self, events: list[ObservabilityEvent]) -> None:
        """Forward real-time status batch to logs tab if instantiated."""
        if self._logs_tab is not None:
            self._logs_tab.append_narrative_batch(events)

    def _on_pipeline_status(self, event: ObservabilityEvent) -> None:
        """Forward real-time status events to logs tab if instantiated."""
        if self._logs_tab is not None:
            self._logs_tab.append_narrative_event(event)

    @property
    def config_tab(self) -> ConfigurationTab:
        """Lazily instantiate ConfigurationTab on first access."""
        if self._config_tab is None:
            self._config_tab = ConfigurationTab(
                self.content_container,
                engine=self.engine,
                app_state=self.app_state,
            )
        return self._config_tab

    @property
    def logs_tab(self) -> LogsTab:
        """Lazily instantiate LogsTab on first access."""
        if self._logs_tab is None:
            self._logs_tab = LogsTab(
                self.content_container,
                engine=self.engine,
                app_state=self.app_state,
            )
        return self._logs_tab

    @property
    def system_tab(self) -> SystemTab:
        """Lazily instantiate SystemTab on first access."""
        if self._system_tab is None:
            self._system_tab = SystemTab(
                self.content_container,
                engine=self.engine,
                app_state=self.app_state,
            )
        return self._system_tab

    @property
    def settings_tab(self) -> SettingsTab:
        """Backward-compatible reference to settings editor."""
        return self.config_tab.settings_editor

    @property
    def financial_rules_tab(self) -> FinancialRulesTab:
        """Backward-compatible reference to financial rules editor."""
        return self.config_tab.rules_editor

    def switch_tab(self, tab_id: str) -> None:
        """Switch visible tab and maintain synchronicity with active state."""
        # Normalize alias tab IDs
        normalized_id = "config" if tab_id in ("settings", "rules") else tab_id

        if normalized_id == self.active_tab_id:
            # If requesting specific subtab within configuration
            if tab_id in ("settings", "rules"):
                self.config_tab.switch_subtab(tab_id)
            return

        self.active_tab_id = normalized_id

        # Update button visual styling
        for tid, btn in self.tab_buttons.items():
            if tid == normalized_id:
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

        # Hide all currently instantiated views
        self.run_tab.grid_remove()
        if self._config_tab is not None:
            self._config_tab.grid_remove()
        if self._logs_tab is not None:
            self._logs_tab.grid_remove()
        if self._system_tab is not None:
            self._system_tab.grid_remove()

        # Switch views with guaranteed synchronization
        if normalized_id == "run":
            self.run_tab.grid(row=0, column=0, sticky="nsew")
            self.run_tab.ensure_config_loaded(self.app_state.active_config_path)
        elif normalized_id == "config":
            tab = self.config_tab
            tab.grid(row=0, column=0, sticky="nsew")
            if tab_id in ("settings", "rules"):
                tab.switch_subtab(tab_id)
            tab.ensure_loaded()
        elif normalized_id == "logs":
            tab = self.logs_tab
            tab.grid(row=0, column=0, sticky="nsew")
            tab.ensure_loaded()
        elif normalized_id == "system":
            tab = self.system_tab
            tab.grid(row=0, column=0, sticky="nsew")
            tab.ensure_loaded()


def main() -> None:
    """Initialize and run the CustomTkinter desktop user interface."""
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
