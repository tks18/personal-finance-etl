"""Settings Tab component for interactive TOML configuration editing.

Owns
----
- SettingsTab: CustomTkinter frame presenting grouped Settings fields, field validations,
  and atomic persistence controls.
- Coordinating file loading, field binding, and reloading.
- Two-way state synchronization with AppState.

Does not own
-------------
- Low-level TOML AST manipulation or file writing (owned by infrastructure.configuration.toml_store).
- Engine façade and pipeline execution (owned by application.facade).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError
from tomlkit.toml_document import TOMLDocument

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.presentation.desktop.config_editor import ConfigFieldEditor
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = ["SettingsTab"]

_SECTION_META: dict[str, tuple[str, str]] = {
    "database": ("🗄️", "Runtime Database & Persistence Paths"),
    "sources": ("📁", "Evidence Source Directories & Master Files"),
    "statement_patterns": ("🔎", "Statement Discovery Patterns"),
    "hash_policy": ("🛡️", "Evidence Hashing & Deduplication Policies"),
    "observability": ("📊", "Forensic Logging & Run Retention"),
    "performance": ("⚡", "Concurrency & Worker Pool Allocations"),
    "market_data": ("📈", "Market Data Fetch Windows & Acceptance Thresholds"),
}


class SettingsTab(ctk.CTkFrame):  # type: ignore[misc]
    """Visual settings editor tab for reviewing and modifying configuration TOMLs."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
        on_config_saved: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state
        self.on_config_saved = on_config_saved

        self.current_filepath: str = ""
        self.original_doc: TOMLDocument | None = None
        self.active_settings: Settings = Settings()
        self.editors: dict[str, dict[str, ConfigFieldEditor]] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Toolbar
        self.grid_rowconfigure(1, weight=0)  # Status banner
        self.grid_rowconfigure(2, weight=1)  # Scrollable editor body

        self._build_toolbar()
        self._build_status_banner()
        self._build_editor_body()

        # Subscribe to central AppState changes
        if self.app_state is not None:
            self.app_state.subscribe_config(self._on_external_config_changed)
            initial_path = self.app_state.active_config_path
        else:
            recents = self.engine.get_recent_configs()
            initial_path = recents[0] if recents else ""

        if initial_path and os.path.isfile(initial_path):
            self.load_config(initial_path, notify_state=False)
        else:
            self._populate_fields(Settings())

    def _build_toolbar(self) -> None:
        """Construct the top control bar with configuration switching and persistence buttons."""
        toolbar_card = ctk.CTkFrame(
            self,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        toolbar_card.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        toolbar_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            toolbar_card,
            text="Settings File",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#7DD3FC",
            fg_color="#0E2235",
            corner_radius=4,
            width=92,
            anchor="center",
        ).grid(row=0, column=0, sticky="w", padx=(10, 8), pady=8, ipady=4, ipadx=6)

        recents = self.engine.get_recent_configs()
        self.config_path_var = ctk.StringVar(value=recents[0] if recents else "")
        self.cfg_combo = ctk.CTkComboBox(
            toolbar_card,
            variable=self.config_path_var,
            values=recents if recents else [""],
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
            command=self._on_combo_select,
        )
        self.cfg_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)

        # Browse Button
        ctk.CTkButton(
            toolbar_card,
            text="Browse…",
            width=72,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self._on_browse,
        ).grid(row=0, column=2, padx=(0, 6), pady=8)

        # Reload Button
        ctk.CTkButton(
            toolbar_card,
            text="↻ Reload",
            width=72,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self.reload_config,
        ).grid(row=0, column=3, padx=(0, 6), pady=8)

        # Validate Paths Button
        ctk.CTkButton(
            toolbar_card,
            text="🔍 Validate",
            width=76,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self.validate_paths,
        ).grid(row=0, column=4, padx=(0, 6), pady=8)

        # Save As Button
        ctk.CTkButton(
            toolbar_card,
            text="Save As…",
            width=78,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self.save_config_as,
        ).grid(row=0, column=5, padx=(0, 8), pady=8)

        # Save Button
        self.save_btn = ctk.CTkButton(
            toolbar_card,
            text="💾 Save Settings",
            width=110,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            corner_radius=5,
            command=self.save_config,
        )
        self.save_btn.grid(row=0, column=6, padx=(0, 10), pady=8)

    def _build_status_banner(self) -> None:
        """Construct the visual status and diagnostic banner."""
        self.banner_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=6)
        self.banner_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.banner_frame.grid_columnconfigure(0, weight=1)

        self.banner_label = ctk.CTkLabel(
            self.banner_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Color.TEXT,
            anchor="w",
            wraplength=900,
            justify="left",
        )
        self.banner_label.grid(row=0, column=0, padx=12, pady=6, sticky="ew")
        self.banner_frame.grid_remove()

    def _show_banner(self, text: str, is_error: bool = False, is_warning: bool = False) -> None:
        """Display an informational, warning, or error message in the status banner."""
        if not text:
            self.banner_frame.grid_remove()
            return

        if is_error:
            bg_color = "#3B1214"
            text_color = Color.ERROR
        elif is_warning:
            bg_color = "#362408"
            text_color = Color.WARNING
        else:
            bg_color = "#0B2D1B"
            text_color = Color.SUCCESS

        self.banner_frame.configure(fg_color=bg_color)
        self.banner_label.configure(text=text, text_color=text_color)
        self.banner_frame.grid()

    def _build_editor_body(self) -> None:
        """Construct scrollable container and dynamically render section cards."""
        self.scroll_body = ctk.CTkScrollableFrame(
            self,
            fg_color=Color.BG,
            border_width=0,
            corner_radius=0,
        )
        self.scroll_body.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.scroll_body.grid_columnconfigure(0, weight=1)

        default_settings = Settings()
        for sec_idx, (sec_name, field_info) in enumerate(Settings.model_fields.items()):
            model_cls = field_info.annotation
            if not isinstance(model_cls, type) or not issubclass(model_cls, BaseModel):
                continue

            icon, sec_title = _SECTION_META.get(sec_name, ("⚙️", sec_name.replace("_", " ").title()))
            card = ctk.CTkFrame(
                self.scroll_body,
                fg_color=Color.SIDEBAR,
                border_color=Color.BORDER,
                border_width=1,
                corner_radius=8,
            )
            card.grid(row=sec_idx, column=0, sticky="ew", pady=(0, 14), padx=2)
            card.grid_columnconfigure(0, weight=1)

            # Section Header Bar
            hdr = ctk.CTkFrame(card, fg_color="#161F30", corner_radius=6)
            hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            hdr.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                hdr,
                text=f"{icon}  [{sec_name}]  {sec_title}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color="#93C5FD",
                anchor="w",
            ).grid(row=0, column=0, padx=10, pady=5, sticky="w")

            num_fields = len(model_cls.model_fields)
            ctk.CTkLabel(
                hdr,
                text=f"{num_fields} items",
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#94A3B8",
                fg_color="#0D1117",
                corner_radius=4,
            ).grid(row=0, column=1, padx=(0, 10), pady=5, ipady=1, ipadx=6, sticky="e")

            sec_submodel = getattr(default_settings, sec_name)
            self.editors[sec_name] = {}

            # Render fields inside card
            for f_idx, (f_name, f_info) in enumerate(model_cls.model_fields.items()):
                init_val = getattr(sec_submodel, f_name, None)
                editor = ConfigFieldEditor(card, f_name, f_info, init_val)
                editor.grid(row=f_idx + 1, column=0, sticky="ew", padx=10, pady=4)
                self.editors[sec_name][f_name] = editor

    def _populate_fields(self, settings: Settings) -> None:
        """Update all GUI field widgets from a Settings model instance."""
        self.active_settings = settings
        for sec_name, field_dict in self.editors.items():
            if not hasattr(settings, sec_name):
                continue
            submodel = getattr(settings, sec_name)
            for f_name, editor in field_dict.items():
                if hasattr(submodel, f_name):
                    editor.set_value(getattr(submodel, f_name))

    def _on_external_config_changed(self, path: str, source: Any) -> None:
        """Handle active config update originating from another tab or state."""
        if source is self or path == self.current_filepath:
            return
        if path and os.path.isfile(path):
            self.load_config(path, notify_state=False)

    def _on_combo_select(self, path: str) -> None:
        """Handle user selection from the configuration dropdown."""
        self.load_config(path, notify_state=True)

    def ensure_config_loaded(self, filepath: str) -> None:
        """Ensure the specified configuration path is active and loaded in the editor."""
        if filepath and filepath != self.current_filepath and os.path.isfile(filepath):
            self.load_config(filepath, notify_state=False)

    def load_config(self, filepath: str, notify_state: bool = True) -> None:
        """Load configuration from disk, parse AST and populate editor."""
        if not filepath:
            return
        path = Path(filepath).resolve()
        if not path.is_file():
            self._show_banner(f"Configuration file not found: '{filepath}'", is_error=True)
            return

        try:
            settings, doc = self.engine.load_settings_document(str(path))
            self.current_filepath = str(path)
            self.original_doc = doc
            self.config_path_var.set(str(path))
            self._populate_fields(settings)
            self._show_banner(f"✓ Loaded configuration: '{path.name}'", is_error=False)
            self._refresh_recents_dropdown()

            if notify_state and self.app_state is not None:
                self.app_state.set_active_config(str(path), source=self)
        except Exception as e:
            self._show_banner(f"Error loading configuration '{filepath}': {e}", is_error=True)

    def reload_config(self) -> None:
        """Reload configuration from disk for current file."""
        target = self.current_filepath or self.config_path_var.get()
        if target:
            self.load_config(target, notify_state=False)

    def _on_browse(self) -> None:
        """Open file dialog to pick an existing TOML configuration."""
        chosen = filedialog.askopenfilename(
            title="Select Configuration TOML",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if chosen:
            self.load_config(chosen, notify_state=True)

    def _refresh_recents_dropdown(self) -> None:
        """Update combobox with latest recent configurations list."""
        recents = self.engine.get_recent_configs()
        if recents:
            self.cfg_combo.configure(values=recents)

    def gather_settings_from_ui(self) -> Settings:
        """Harvest input values from UI editors and validate through Pydantic."""
        payload: dict[str, dict[str, Any]] = {}
        for sec_name, field_dict in self.editors.items():
            sec_dict: dict[str, Any] = {}
            for f_name, editor in field_dict.items():
                sec_dict[f_name] = editor.get_value()
            payload[sec_name] = sec_dict
        return Settings.model_validate(payload)

    def save_config(self) -> bool:
        """Validate UI values and atomically persist to current file path."""
        target_path = self.current_filepath or self.config_path_var.get()
        if not target_path:
            return self.save_config_as()

        try:
            validated = self.gather_settings_from_ui()
        except ValidationError as ve:
            self._show_banner(f"Validation Error: {ve}", is_error=True)
            return False
        except Exception as e:
            self._show_banner(f"Input Parsing Error: {e}", is_error=True)
            return False

        try:
            self.engine.save_settings_document(
                target_path, validated, original_doc=self.original_doc
            )
            self.current_filepath = target_path
            self.active_settings = validated
            self._refresh_recents_dropdown()
            self._show_banner(
                f"✓ Settings saved successfully to '{Path(target_path).name}'", is_error=False
            )
            if self.app_state is not None:
                self.app_state.set_active_config(target_path, source=self)
            if self.on_config_saved:
                self.on_config_saved(target_path)
            return True
        except Exception as e:
            self._show_banner(f"Failed to persist settings: {e}", is_error=True)
            return False

    def save_config_as(self) -> bool:
        """Prompt user for target file path and save new configuration profile."""
        initial_dir = (
            str(Path(self.current_filepath).parent) if self.current_filepath else os.getcwd()
        )
        chosen = filedialog.asksaveasfilename(
            title="Save Configuration As",
            initialdir=initial_dir,
            defaultextension=".toml",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if not chosen:
            return False

        try:
            validated = self.gather_settings_from_ui()
        except ValidationError as ve:
            self._show_banner(f"Validation Error: {ve}", is_error=True)
            return False
        except Exception as e:
            self._show_banner(f"Input Parsing Error: {e}", is_error=True)
            return False

        try:
            self.engine.save_settings_document_as(
                chosen, validated, source_filepath=self.current_filepath
            )
            self.current_filepath = chosen
            self.config_path_var.set(chosen)
            self.active_settings = validated
            self._refresh_recents_dropdown()
            self._show_banner(
                f"✓ Settings saved to new profile: '{Path(chosen).name}'", is_error=False
            )
            if self.app_state is not None:
                self.app_state.set_active_config(chosen, source=self)
            if self.on_config_saved:
                self.on_config_saved(chosen)
            return True
        except Exception as e:
            self._show_banner(f"Failed to save as '{chosen}': {e}", is_error=True)
            return False

    def validate_paths(self) -> bool:
        """Validate whether all configured source directories and master files exist on disk."""
        try:
            validated = self.gather_settings_from_ui()
            self.engine.validate_settings_model(validated)
            self._show_banner(
                "✓ All configured source directories and dependency files exist on disk.",
                is_error=False,
            )
            return True
        except ValidationError as ve:
            self._show_banner(f"Validation Error: {ve}", is_error=True)
            return False
        except FileNotFoundError as fe:
            self._show_banner(f"Missing Files/Folders:\n{fe}", is_warning=True)
            return False
        except Exception as e:
            self._show_banner(f"Validation Error: {e}", is_error=True)
            return False
