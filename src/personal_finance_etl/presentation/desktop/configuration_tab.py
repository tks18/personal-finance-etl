"""Unified configuration container hosting Settings and Financial Rules editors.

Owns
----
- ConfigurationTab: Dual-subtab container orchestrating SettingsTab
  and FinancialRulesTab with clean segmented switching.
- Coordinating lazy loading and ensure_loaded() dispatching across sub-editors.

Does not own
-------------
- Concrete settings persistence or UI widgets (owned by settings_tab and config_editor).
- Concrete rules persistence or UI widgets (owned by financial_rules_tab and rules_editors).
- Application-level top navigation (owned by app.py).
"""

from __future__ import annotations

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.presentation.desktop.financial_rules_tab import FinancialRulesTab
from personal_finance_etl.presentation.desktop.settings_tab import SettingsTab
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = ["ConfigurationTab"]


# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: Subclassing untyped third-party ctk.CTkFrame base class
class ConfigurationTab(ctk.CTkFrame):  # type: ignore[misc]
    """Container tab hosting both Pipeline Settings and Financial Rules editors."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
    ) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state
        self.active_subtab: str = "settings"
        self.subtab_buttons: dict[str, ctk.CTkButton] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Sub-nav header
        self.grid_rowconfigure(1, weight=1)  # Editor views container

        self._build_sub_header()
        self._build_editors()

    def _build_sub_header(self) -> None:
        """Construct the secondary sub-navigation bar switching settings vs rules."""
        sub_nav = ctk.CTkFrame(
            self,
            fg_color="#0F1420",
            height=42,
            corner_radius=0,
            border_width=0,
        )
        sub_nav.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        sub_nav.grid_columnconfigure(0, weight=1)

        switcher_frame = ctk.CTkFrame(
            sub_nav,
            fg_color="#151D2E",
            corner_radius=6,
            border_width=1,
            border_color="#1E293B",
        )
        switcher_frame.pack(side="left", padx=16, pady=6)

        specs = [
            ("settings", "⚙️  Pipeline Settings"),
            ("rules", "📜  Financial Rules"),
        ]

        for sub_id, label in specs:
            btn = ctk.CTkButton(
                switcher_frame,
                text=label,
                width=160,
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

    def _build_editors(self) -> None:
        """Instantiate SettingsTab in the editor container, lazily deferring FinancialRulesTab."""
        self.container = ctk.CTkFrame(self, fg_color=Color.BG, corner_radius=0)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.settings_editor = SettingsTab(
            self.container,
            engine=self.engine,
            app_state=self.app_state,
        )
        self._rules_editor: FinancialRulesTab | None = None

        # Show initial view
        self.settings_editor.grid(row=0, column=0, sticky="nsew")

    @property
    def rules_editor(self) -> FinancialRulesTab:
        """Lazily instantiate FinancialRulesTab on first access."""
        if self._rules_editor is None:
            self._rules_editor = FinancialRulesTab(
                self.container,
                engine=self.engine,
                app_state=self.app_state,
            )
        return self._rules_editor

    def switch_subtab(self, sub_id: str) -> None:
        """Switch active configuration sub-view and synchronize state."""
        if sub_id == self.active_subtab:
            return

        self.active_subtab = sub_id

        # Update button highlights
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

        if sub_id == "settings":
            if self._rules_editor is not None:
                self._rules_editor.grid_remove()
            self.settings_editor.grid(row=0, column=0, sticky="nsew")
            if self.app_state and self.app_state.active_config_path:
                self.settings_editor.ensure_config_loaded(self.app_state.active_config_path)
        elif sub_id == "rules":
            self.settings_editor.grid_remove()
            self.rules_editor.grid(row=0, column=0, sticky="nsew")
            if self.app_state and self.app_state.active_rules_path:
                self.rules_editor.ensure_rules_loaded(self.app_state.active_rules_path)

    def ensure_loaded(self) -> None:
        """Ensure active sub-tab has loaded its respective configuration model."""
        if self.active_subtab == "settings":
            if self.app_state and self.app_state.active_config_path:
                self.settings_editor.ensure_config_loaded(self.app_state.active_config_path)
        elif self.active_subtab == "rules":
            if self.app_state and self.app_state.active_rules_path:
                self.rules_editor.ensure_rules_loaded(self.app_state.active_rules_path)
