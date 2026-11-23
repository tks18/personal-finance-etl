"""Configuration field editor widgets mapping Pydantic schema to CustomTkinter.

Owns
----
- ConfigFieldEditor: Individual field widget renderer supporting text, files, directories,
  switches, dropdown choices, integers, floats, and string lists.
- Input-level keystroke enforcement, steppers, live path validation, and range clamping.
- Conversion between GUI widget representations and typed Python values.

Does not own
-------------
- TOML disk serialization (owned by infrastructure.configuration.toml_store).
- Pydantic schema validation (owned by config.settings).
"""

from __future__ import annotations

import os
from tkinter import filedialog
from typing import Any, cast

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
from pydantic.fields import FieldInfo

from personal_finance_etl.presentation.desktop.theme import Color

__all__ = ["ConfigFieldEditor"]


class ConfigFieldEditor(ctk.CTkFrame):  # type: ignore[misc]
    """GUI input row bound to a single Pydantic configuration field with input-level enforcement."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        field_name: str,
        field_info: FieldInfo,
        initial_value: Any,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.field_name = field_name
        self.field_info = field_info
        self.metadata: dict[str, Any] = (
            cast("dict[str, Any]", field_info.json_schema_extra)
            if isinstance(field_info.json_schema_extra, dict)
            else {}
        )
        self.widget_type = self._determine_widget_type(field_info)

        # 2-column layout: Left (Labels & info) takes flexible space, Right (Controls) aligns neatly
        self.grid_columnconfigure(0, weight=1)  # Left column
        self.grid_columnconfigure(1, weight=0)  # Right column (controls container)

        self._build_label()
        self._build_input(initial_value)

        # Bottom row separator
        sep = ctk.CTkFrame(self, fg_color="#1E293B", height=1, corner_radius=0)
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))

    def _determine_widget_type(self, field_info: FieldInfo) -> str:
        """Infer UI widget type from json_schema_extra or type annotation."""
        if "ui_widget" in self.metadata:
            return cast(str, self.metadata["ui_widget"])

        annotation = field_info.annotation
        if annotation is bool:
            return "switch"
        if annotation is int:
            return "int"
        if annotation is float:
            return "float"
        if annotation in (list, list[str]):
            return "list"
        return "text"

    def _build_label(self) -> None:
        """Render field name, documentation caption, and constraint badge."""
        lbl_frame = ctk.CTkFrame(self, fg_color="transparent")
        lbl_frame.grid(row=0, column=0, sticky="nw", padx=(4, 16), pady=4)

        title = self.field_name.replace("_", " ").title()
        title_row = ctk.CTkFrame(lbl_frame, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=Color.TEXT,
            anchor="w",
        ).pack(side="left")

        # Constraint badge (if min/max defined)
        min_val = self.metadata.get("min")
        max_val = self.metadata.get("max")
        unit = self.metadata.get("unit")
        if min_val is not None or max_val is not None:
            badge_text = f"[{min_val} – {max_val} {unit or ''}]".strip()
            ctk.CTkLabel(
                title_row,
                text=badge_text,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#38BDF8",
                fg_color="#0B263B",
                corner_radius=4,
            ).pack(side="left", padx=(8, 0), ipady=1, ipadx=4)

        desc = self.field_info.description
        if desc:
            ctk.CTkLabel(
                lbl_frame,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#94A3B8",
                anchor="w",
                wraplength=380,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

    def _build_input(self, initial_value: Any) -> None:
        """Render the appropriate CustomTkinter control aligned on the right."""
        ctl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctl_frame.grid(row=0, column=1, sticky="e", padx=(0, 4), pady=4)

        if self.widget_type == "switch":
            self._build_switch_control(ctl_frame, initial_value)
        elif self.widget_type in ("int", "float"):
            self._build_number_control(ctl_frame, initial_value)
        elif self.widget_type == "choice":
            self._build_choice_control(ctl_frame, initial_value)
        elif self.widget_type in ("directory", "file"):
            self._build_path_control(ctl_frame, initial_value)
        elif self.widget_type == "list":
            self._build_list_control(ctl_frame, initial_value)
        else:
            self._build_text_control(ctl_frame, initial_value)

    # ── Switch Control ───────────────────────────────────────────

    def _build_switch_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render switch toggle with status indicator badge."""
        bool_val = bool(initial_value)
        self._var = ctk.BooleanVar(value=bool_val)

        self._switch_badge = ctk.CTkLabel(
            parent,
            text=self._get_switch_text(bool_val),
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#4ADE80" if not bool_val else "#F59E0B",
            fg_color="#062817" if not bool_val else "#362408",
            corner_radius=4,
            width=160,
            anchor="center",
        )
        self._switch_badge.pack(side="left", padx=(0, 10), ipady=2, ipadx=6)

        self._control = ctk.CTkSwitch(
            parent,
            text="",
            variable=self._var,
            progress_color=Color.ACCENT,
            command=self._on_switch_toggle,
            width=46,
        )
        self._control.pack(side="left")

    def _get_switch_text(self, is_on: bool) -> str:
        """Return user-friendly switch description text."""
        if is_on:
            return str(self.metadata.get("active_label", "Bypassed (Skip Scan)"))
        return str(self.metadata.get("inactive_label", "Active (Full Scan)"))

    def _on_switch_toggle(self) -> None:
        """Update switch status pill badge on toggle."""
        is_on = bool(self._var.get())
        if hasattr(self, "_switch_badge"):
            self._switch_badge.configure(
                text=self._get_switch_text(is_on),
                text_color="#F59E0B" if is_on else "#4ADE80",
                fg_color="#362408" if is_on else "#062817",
            )

    # ── Number Stepper Control ───────────────────────────────────

    def _build_number_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render number input with keystroke validation, bounds clamping, and steppers."""
        init_str = str(initial_value if initial_value is not None else "")
        self._var = ctk.StringVar(value=init_str)

        stepper_frame = ctk.CTkFrame(
            parent,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
        )
        stepper_frame.pack(side="left")

        # Decrement Button
        minus_btn = ctk.CTkButton(
            stepper_frame,
            text="−",
            width=28,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="transparent",
            hover_color="#1E293B",
            text_color="#94A3B8",
            corner_radius=4,
            command=self._decrement_number,
        )
        minus_btn.pack(side="left", padx=2, pady=2)

        # Keystroke Validator
        vcmd = (self.register(self._validate_number_keystroke), "%P")
        self._control = ctk.CTkEntry(
            stepper_frame,
            textvariable=self._var,
            width=70,
            height=28,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            justify="center",
            fg_color="#080C14",
            border_width=0,
            validate="key",
            validatecommand=vcmd,
        )
        self._control.pack(side="left", padx=2, pady=2)
        self._control.bind("<FocusOut>", lambda _: self._clamp_number_bounds())

        # Increment Button
        plus_btn = ctk.CTkButton(
            stepper_frame,
            text="+",
            width=28,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="transparent",
            hover_color="#1E293B",
            text_color="#94A3B8",
            corner_radius=4,
            command=self._increment_number,
        )
        plus_btn.pack(side="left", padx=2, pady=2)

        # Unit Badge
        unit = self.metadata.get("unit")
        if unit:
            ctk.CTkLabel(
                parent,
                text=unit,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#94A3B8",
                width=55,
                anchor="w",
            ).pack(side="left", padx=(8, 0))

    def _validate_number_keystroke(self, proposed: str) -> bool:
        """Enforce numeric-only characters at the input keystroke level."""
        if proposed in ("", "-"):
            return True
        if self.widget_type == "int":
            try:
                int(proposed)
                return True
            except ValueError:
                return False
        else:  # float
            if proposed in (".", "-."):
                return True
            try:
                float(proposed)
                return True
            except ValueError:
                return False

    def _clamp_number_bounds(self) -> None:
        """Clamp current value within min and max boundaries on focus loss."""
        val = self.get_value()
        min_val = self.metadata.get("min")
        max_val = self.metadata.get("max")

        if self.widget_type == "int":
            val_int = int(val)
            if min_val is not None:
                val_int = max(val_int, int(min_val))
            if max_val is not None:
                val_int = min(val_int, int(max_val))
            self._var.set(str(val_int))
        else:  # float
            val_flt = round(float(val), 4)
            if min_val is not None:
                val_flt = max(val_flt, float(min_val))
            if max_val is not None:
                val_flt = min(val_flt, float(max_val))
            self._var.set(str(val_flt))

    def _increment_number(self) -> None:
        """Increment number value by configured step."""
        step = self.metadata.get("step", 1 if self.widget_type == "int" else 0.05)
        max_val = self.metadata.get("max")
        curr = self.get_value()

        if self.widget_type == "int":
            new_int = int(curr) + int(step)
            if max_val is not None:
                new_int = min(new_int, int(max_val))
            self._var.set(str(new_int))
        else:
            new_flt = round(float(curr) + float(step), 4)
            if max_val is not None:
                new_flt = min(new_flt, float(max_val))
            self._var.set(str(new_flt))

    def _decrement_number(self) -> None:
        """Decrement number value by configured step."""
        step = self.metadata.get("step", 1 if self.widget_type == "int" else 0.05)
        min_val = self.metadata.get("min")
        curr = self.get_value()

        if self.widget_type == "int":
            new_int = int(curr) - int(step)
            if min_val is not None:
                new_int = max(new_int, int(min_val))
            self._var.set(str(new_int))
        else:
            new_flt = round(float(curr) - float(step), 4)
            if min_val is not None:
                new_flt = max(new_flt, float(min_val))
            self._var.set(str(new_flt))

    # ── Choice / Dropdown Control ────────────────────────────────

    def _build_choice_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render styled choice selector."""
        options = ["CONTENT", "NONE"]
        if "options" in self.metadata:
            raw_opts = self.metadata["options"]
            if isinstance(raw_opts, (list, tuple)):
                options = [str(opt) for opt in raw_opts]

        curr_val = str(initial_value.value if hasattr(initial_value, "value") else initial_value)
        if curr_val not in options and options:
            curr_val = options[0]

        self._var = ctk.StringVar(value=curr_val)
        self._control = ctk.CTkOptionMenu(
            parent,
            variable=self._var,
            values=options,
            width=160,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1E293B",
            button_color="#334155",
            button_hover_color="#475569",
            corner_radius=5,
        )
        self._control.pack(side="left")

    # ── Path (Directory & File) Control ──────────────────────────

    def _build_path_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render path selector with live disk existence indicator badge."""
        init_str = str(initial_value or "")
        self._var = ctk.StringVar(value=init_str)
        self._var.trace_add("write", lambda *_: self._update_path_status_pill())

        # Path Status Pill
        self._path_pill = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            corner_radius=4,
            width=72,
            anchor="center",
        )
        self._path_pill.pack(side="left", padx=(0, 8), ipady=2, ipadx=4)

        # Path Text Entry
        placeholder = self.metadata.get(
            "placeholder",
            "Select directory path..."
            if self.widget_type == "directory"
            else "Select file path...",
        )
        self._control = ctk.CTkEntry(
            parent,
            textvariable=self._var,
            width=360,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            placeholder_text=placeholder,
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
        )
        self._control.pack(side="left", padx=(0, 8))

        # Browse Button
        ctk.CTkButton(
            parent,
            text="Browse…",
            width=74,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=1,
            border_color=Color.BORDER,
            corner_radius=5,
            command=self._on_browse,
        ).pack(side="left")

        self._update_path_status_pill()

    def _update_path_status_pill(self) -> None:
        """Update path existence pill dynamically."""
        if not hasattr(self, "_path_pill"):
            return
        path = self._var.get().strip()
        if not path:
            self._path_pill.configure(
                text="Required",
                text_color="#94A3B8",
                fg_color="#161F30",
            )
        elif os.path.exists(path):
            self._path_pill.configure(
                text="✓ Found",
                text_color="#4ADE80",
                fg_color="#062817",
            )
        else:
            self._path_pill.configure(
                text="⚠️ Missing",
                text_color="#F59E0B",
                fg_color="#362408",
            )

    def _on_browse(self) -> None:
        """Handle browse button click."""
        kind = self.metadata.get("kind", "")
        if self.widget_type == "directory":
            chosen = filedialog.askdirectory(title=f"Select {self.field_name}")
        elif kind == "excel":
            chosen = filedialog.askopenfilename(
                title=f"Select {self.field_name}",
                filetypes=[("Excel Files", "*.xlsx;*.xls"), ("All Files", "*.*")],
            )
        elif kind == "sqlite":
            chosen = filedialog.askopenfilename(
                title=f"Select {self.field_name}",
                filetypes=[("SQLite Databases", "*.sqlite;*.db"), ("All Files", "*.*")],
            )
        else:
            chosen = filedialog.askopenfilename(
                title=f"Select {self.field_name}",
                filetypes=[("All Files", "*.*")],
            )
        if chosen:
            self.set_value(chosen)

    # ── List Control ─────────────────────────────────────────────

    def _build_list_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render string list editor with placeholder."""
        raw_str = (
            ", ".join(str(item) for item in initial_value)
            if isinstance(initial_value, list)
            else str(initial_value or "")
        )
        self._var = ctk.StringVar(value=raw_str)
        self._control = ctk.CTkEntry(
            parent,
            textvariable=self._var,
            width=360,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            placeholder_text=self.metadata.get("placeholder", "Comma-separated patterns..."),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
        )
        self._control.pack(side="left")

    # ── Standard Text Control ────────────────────────────────────

    def _build_text_control(self, parent: ctk.CTkFrame, initial_value: Any) -> None:
        """Render standard text field."""
        self._var = ctk.StringVar(value=str(initial_value if initial_value is not None else ""))
        self._control = ctk.CTkEntry(
            parent,
            textvariable=self._var,
            width=360,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            placeholder_text=self.metadata.get("placeholder", ""),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
        )
        self._control.pack(side="left")

    # ── Value Getters & Setters ──────────────────────────────────

    def get_value(self) -> Any:
        """Retrieve and cast current UI value according to field type."""
        if self.widget_type == "switch":
            return bool(self._var.get())

        raw_str = self._var.get().strip()
        if self.widget_type == "int":
            try:
                return int(raw_str) if raw_str else 0
            except ValueError:
                return 0
        if self.widget_type == "float":
            try:
                return float(raw_str) if raw_str else 0.0
            except ValueError:
                return 0.0
        if self.widget_type == "list":
            return [x.strip() for x in raw_str.split(",") if x.strip()]
        return raw_str

    def set_value(self, value: Any) -> None:
        """Update the widget UI representation with an external value."""
        if self.widget_type == "switch":
            self._var.set(bool(value))
            self._on_switch_toggle()
        elif self.widget_type == "list":
            if isinstance(value, list):
                self._var.set(", ".join(str(item) for item in value))
            else:
                self._var.set(str(value or ""))
        elif self.widget_type == "choice":
            str_val = str(value.value if hasattr(value, "value") else value)
            self._var.set(str_val)
        else:
            self._var.set(str(value if value is not None else ""))
            if hasattr(self, "_update_path_status_pill"):
                self._update_path_status_pill()
