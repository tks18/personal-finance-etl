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
from collections.abc import Callable
from tkinter import filedialog
from typing import Any, cast

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
from pydantic.fields import FieldInfo

from personal_finance_etl.presentation.desktop.theme import Color

__all__ = [
    "ConfigFieldEditor",
    "KeyValueDictEditor",
    "ListEditorModal",
    "Matrix3x3Editor",
    "Tuple3Editor",
]


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
        self._error_label: ctk.CTkLabel | None = None

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
        elif self.widget_type in ("int", "float", "percentage"):
            self._build_number_control(ctl_frame, initial_value)
        elif self.widget_type == "choice":
            self._build_choice_control(ctl_frame, initial_value)
        elif self.widget_type in ("directory", "file"):
            self._build_path_control(ctl_frame, initial_value)
        elif self.widget_type in ("list", "id_list", "int_list"):
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
        """Render string or integer list editor with live count badge and modal manager."""
        raw_str = (
            ", ".join(str(item) for item in initial_value)
            if isinstance(initial_value, list)
            else str(initial_value or "")
        )
        self._var = ctk.StringVar(value=raw_str)

        initial_count = (
            len(initial_value)
            if isinstance(initial_value, list)
            else (len([x for x in raw_str.split(",") if x.strip()]) if raw_str else 0)
        )
        unit_text = "IDs" if self.widget_type == "id_list" else "items"
        self._list_count_badge = ctk.CTkLabel(
            parent,
            text=f"{initial_count} {unit_text}",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#94A3B8",
            fg_color="#0F172A",
            corner_radius=4,
            width=58,
            anchor="center",
        )
        self._list_count_badge.pack(side="left", padx=(0, 6), ipady=2, ipadx=4)
        self._var.trace_add("write", self._on_list_text_change)

        self._control = ctk.CTkEntry(
            parent,
            textvariable=self._var,
            width=240,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            placeholder_text=self.metadata.get("placeholder", "Comma-separated items..."),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=5,
        )
        self._control.pack(side="left")

        self._manage_btn = ctk.CTkButton(
            parent,
            text="📝 Manage",
            width=76,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            corner_radius=5,
            command=self._open_list_editor_modal,
        )
        self._manage_btn.pack(side="left", padx=(6, 0))

    def _open_list_editor_modal(self) -> None:
        """Open the interactive ListEditorModal for detailed list inspection and updates."""
        raw = self._var.get().strip()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        unit_text = "IDs" if self.widget_type == "id_list" else "items"
        is_int = self.widget_type == "int_list"

        def _on_modal_apply(new_items: list[str]) -> None:
            if is_int:
                int_list: list[int] = []
                for x in new_items:
                    try:
                        int_list.append(int(x))
                    except ValueError:
                        pass
                self.set_value(int_list)
            else:
                self.set_value(new_items)

        ListEditorModal(
            self,
            field_name=self.field_name,
            initial_items=items,
            description=self.field_info.description or "",
            unit_text=unit_text,
            is_int_list=is_int,
            on_apply=_on_modal_apply,
        )

    def _on_list_text_change(self, *_: Any) -> None:
        """Update the list count badge when text is edited."""
        if not hasattr(self, "_list_count_badge"):
            return
        raw = self._var.get().strip()
        items = [x for x in raw.split(",") if x.strip()]
        unit_text = "IDs" if self.widget_type == "id_list" else "items"
        self._list_count_badge.configure(text=f"{len(items)} {unit_text}")

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
        if self.widget_type in ("float", "percentage"):
            try:
                return float(raw_str) if raw_str else 0.0
            except ValueError:
                return 0.0
        if self.widget_type in ("list", "id_list"):
            return [x.strip() for x in raw_str.split(",") if x.strip()]
        if self.widget_type == "int_list":
            ints: list[int] = []
            for x in raw_str.split(","):
                x_clean = x.strip()
                if x_clean:
                    try:
                        ints.append(int(x_clean))
                    except ValueError:
                        pass
            return ints
        return raw_str

    def set_value(self, value: Any) -> None:
        """Update the widget UI representation with an external value."""
        if self.widget_type == "switch":
            self._var.set(bool(value))
            self._on_switch_toggle()
        elif self.widget_type in ("list", "id_list", "int_list"):
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
        self.clear_error()

    def set_error(self, message: str | None) -> None:
        """Set or clear inline validation error message and red border highlight (Item 22)."""
        if message:
            if hasattr(self, "_control") and hasattr(self._control, "configure"):
                try:
                    self._control.configure(border_color="#EF4444", border_width=1)
                except Exception:
                    pass
            if self._error_label is None:
                self._error_label = ctk.CTkLabel(
                    self,
                    text=f"⚠ {message}",
                    font=ctk.CTkFont(family="Segoe UI", size=9),
                    text_color="#EF4444",
                    anchor="w",
                )
                self._error_label.grid(
                    row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2)
                )
            else:
                self._error_label.configure(text=f"⚠ {message}")
        else:
            self.clear_error()

    def clear_error(self) -> None:
        """Clear error highlight and remove inline error label."""
        if hasattr(self, "_control") and hasattr(self._control, "configure"):
            try:
                self._control.configure(border_color=Color.BORDER, border_width=1)
            except Exception:
                pass
        if self._error_label is not None:
            try:
                self._error_label.destroy()
            except Exception:
                pass
            self._error_label = None


class Matrix3x3Editor(ctk.CTkFrame):  # type: ignore[misc]
    """Visual 3x3 Markov transition probability matrix editor with row sum validation."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        initial_matrix: list[list[float]] | None = None,
        row_labels: tuple[str, str, str] = ("Bull", "Bear", "Stag"),
        col_labels: tuple[str, str, str] = ("To Bull", "To Bear", "To Stag"),
    ) -> None:
        super().__init__(
            parent,
            fg_color="#0C121D",
            corner_radius=8,
            border_color=Color.BORDER,
            border_width=1,
        )
        self.row_labels = row_labels
        self.col_labels = col_labels
        self.matrix_vars: list[list[ctk.StringVar]] = []
        self.sum_badges: list[ctk.CTkLabel] = []

        matrix = initial_matrix or [
            [0.90, 0.08, 0.02],
            [0.15, 0.80, 0.05],
            [0.10, 0.15, 0.75],
        ]

        self._build_ui(matrix)

    def _build_ui(self, matrix: list[list[float]]) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text="State Transition Probabilities (Each row must sum to 1.0)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=Color.TEXT,
        ).pack(side="left")

        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(grid_frame, text="", width=70).grid(row=0, column=0, padx=4, pady=2)
        for c_idx, c_name in enumerate(self.col_labels):
            ctk.CTkLabel(
                grid_frame,
                text=c_name,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#94A3B8",
                width=85,
            ).grid(row=0, column=c_idx + 1, padx=4, pady=2)
        ctk.CTkLabel(
            grid_frame,
            text="Row Sum",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
            width=75,
        ).grid(row=0, column=4, padx=4, pady=2)

        for r_idx, r_name in enumerate(self.row_labels):
            ctk.CTkLabel(
                grid_frame,
                text=r_name,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#38BDF8",
                width=70,
                anchor="w",
            ).grid(row=r_idx + 1, column=0, padx=4, pady=3)
            row_vars: list[ctk.StringVar] = []
            for c_idx in range(3):
                val = (
                    matrix[r_idx][c_idx]
                    if r_idx < len(matrix) and c_idx < len(matrix[r_idx])
                    else 0.0
                )
                var = ctk.StringVar(value=f"{val:.3f}")
                var.trace_add("write", lambda *_, r=r_idx: self._update_row_sum(r))
                row_vars.append(var)

                entry = ctk.CTkEntry(
                    grid_frame,
                    textvariable=var,
                    width=85,
                    height=28,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#080C14",
                    border_color=Color.BORDER,
                    border_width=1,
                    corner_radius=4,
                    justify="right",
                )
                entry.grid(row=r_idx + 1, column=c_idx + 1, padx=4, pady=3)
            self.matrix_vars.append(row_vars)

            badge = ctk.CTkLabel(
                grid_frame,
                text="Σ = 1.000",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color="#4ADE80",
                fg_color="#062817",
                corner_radius=4,
                width=75,
            )
            badge.grid(row=r_idx + 1, column=4, padx=4, pady=3, ipady=2)
            self.sum_badges.append(badge)
            self._update_row_sum(r_idx)

    def _update_row_sum(self, r_idx: int) -> None:
        total = 0.0
        for c_idx in range(3):
            try:
                total += float(self.matrix_vars[r_idx][c_idx].get())
            except ValueError:
                pass
        badge = self.sum_badges[r_idx]
        if abs(total - 1.0) <= 0.005:
            badge.configure(text=f"Σ = {total:.3f}", text_color="#4ADE80", fg_color="#062817")
        else:
            badge.configure(text=f"Σ = {total:.3f}", text_color="#F59E0B", fg_color="#362408")

    def get_value(self) -> list[list[float]]:
        """Retrieve 3x3 transition probability matrix from current input cells."""
        result: list[list[float]] = []
        for r_idx in range(3):
            row: list[float] = []
            for c_idx in range(3):
                try:
                    row.append(float(self.matrix_vars[r_idx][c_idx].get()))
                except ValueError:
                    row.append(0.0)
            result.append(row)
        return result

    def set_value(self, matrix: list[list[float]]) -> None:
        """Update 3x3 transition probability cells and recompute row sum badges."""
        for r_idx in range(min(3, len(matrix))):
            for c_idx in range(min(3, len(matrix[r_idx]))):
                self.matrix_vars[r_idx][c_idx].set(f"{matrix[r_idx][c_idx]:.3f}")
                self._update_row_sum(r_idx)


class Tuple3Editor(ctk.CTkFrame):  # type: ignore[misc]
    """Visual editor for 3-element state parameters (drift, volatility, inflation target)."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        state_name: str,
        initial_value: tuple[float, float, float] | list[float] | None = None,
        labels: tuple[str, str, str] = (
            "Drift (μ)",
            "Volatility (σ)",
            "Inflation Target (π)",
        ),
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.state_name = state_name
        self.labels = labels
        self.vars: list[ctk.StringVar] = []

        vals = initial_value or (0.10, 0.15, 0.04)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        lbl_frame = ctk.CTkFrame(self, fg_color="transparent")
        lbl_frame.grid(row=0, column=0, sticky="nw", padx=(4, 16), pady=4)
        clean_name = self.state_name.replace("state_", "").capitalize()
        ctk.CTkLabel(
            lbl_frame,
            text=f"Regime State: {clean_name}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=Color.TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            lbl_frame,
            text=f"{clean_name} regime macro parameters: drift rate, volatility, and inflation target.",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#94A3B8",
        ).pack(anchor="w", pady=(2, 0))

        ctl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctl_frame.grid(row=0, column=1, sticky="e", padx=(0, 4), pady=4)

        for label_text, val in zip(self.labels, vals, strict=True):
            block = ctk.CTkFrame(
                ctl_frame,
                fg_color="#101624",
                border_color=Color.BORDER,
                border_width=1,
                corner_radius=6,
            )
            block.pack(side="left", padx=3)
            ctk.CTkLabel(
                block,
                text=label_text,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color="#94A3B8",
            ).pack(anchor="w", padx=8, pady=(4, 0))
            v = ctk.StringVar(value=f"{val:.3f}")
            self.vars.append(v)
            entry = ctk.CTkEntry(
                block,
                textvariable=v,
                width=100,
                height=26,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color="#080C14",
                border_color="#101624",
                border_width=0,
                justify="right",
            )
            entry.pack(padx=4, pady=(2, 4))

        sep = ctk.CTkFrame(self, fg_color="#1E293B", height=1, corner_radius=0)
        sep.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))

    def get_value(self) -> tuple[float, float, float]:
        """Retrieve state parameter triple (drift, volatility, inflation target)."""
        vals: list[float] = []
        for v in self.vars:
            try:
                vals.append(float(v.get()))
            except ValueError:
                vals.append(0.0)
        return (vals[0], vals[1], vals[2]) if len(vals) == 3 else (0.0, 0.0, 0.0)

    def set_value(self, value: tuple[float, float, float] | list[float]) -> None:
        """Set state parameter values from an external 3-element tuple or list."""
        for idx in range(min(3, len(value))):
            self.vars[idx].set(f"{value[idx]:.3f}")


class KeyValueDictEditor(ctk.CTkFrame):  # type: ignore[misc]
    """Dynamic table editor for key-value dictionaries with add/delete row controls."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        title: str,
        initial_dict: dict[str, Any] | None = None,
        key_label: str = "Key",
        value_label: str = "Value",
        value_type: str = "str",
        description: str = "",
        sum_to_one: bool = False,
        show_search: bool = False,
    ) -> None:
        super().__init__(
            parent,
            fg_color="#0C121D",
            corner_radius=8,
            border_color=Color.BORDER,
            border_width=1,
        )
        self.title = title
        self.key_label = key_label
        self.value_label = value_label
        self.value_type = value_type
        self.description = description
        self.sum_to_one = sum_to_one
        self.show_search = show_search

        self.rows: list[tuple[ctk.StringVar, ctk.StringVar, ctk.CTkFrame]] = []

        self._build_header()
        self._build_table_container()
        if initial_dict:
            for k, v in initial_dict.items():
                self._add_row(k, v)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left")

        title_row = ctk.CTkFrame(title_col, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text=self.title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=Color.TEXT,
        ).pack(side="left")

        self.count_badge = ctk.CTkLabel(
            title_row,
            text="0 items",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#38BDF8",
            fg_color="#0B263B",
            corner_radius=4,
        )
        self.count_badge.pack(side="left", padx=(8, 0), ipady=1, ipadx=4)

        if self.sum_to_one:
            self.sum_badge = ctk.CTkLabel(
                title_row,
                text="Total: 0.0%",
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color="#4ADE80",
                fg_color="#062817",
                corner_radius=4,
            )
            self.sum_badge.pack(side="left", padx=(6, 0), ipady=1, ipadx=4)

        if self.description:
            ctk.CTkLabel(
                title_col,
                text=self.description,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#94A3B8",
            ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        if self.show_search:
            self.search_var = ctk.StringVar()
            self.search_var.trace_add("write", self._on_filter)
            search_entry = ctk.CTkEntry(
                actions,
                textvariable=self.search_var,
                placeholder_text="Filter items...",
                width=160,
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="#080C14",
                border_color=Color.BORDER,
                border_width=1,
            )
            search_entry.pack(side="left", padx=(0, 8))

        add_btn = ctk.CTkButton(
            actions,
            text="+ Add Entry",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E3A8A",
            hover_color="#2563EB",
            text_color="#DBEAFE",
            height=28,
            width=90,
            command=lambda: self._add_row("", 0.0 if self.value_type == "float" else ""),
        )
        add_btn.pack(side="left")

    def _build_table_container(self) -> None:
        self.rows_container = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    def _add_row(self, key: str, val: Any) -> None:
        row_frame = ctk.CTkFrame(self.rows_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        key_var = ctk.StringVar(value=str(key))
        val_var = ctk.StringVar(value=str(val))

        key_entry = ctk.CTkEntry(
            row_frame,
            textvariable=key_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            height=28,
        )
        key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        val_entry = ctk.CTkEntry(
            row_frame,
            textvariable=val_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            height=28,
            width=110 if self.value_type in ("float", "int") else 240,
            justify="right" if self.value_type in ("float", "int") else "left",
        )
        val_entry.pack(side="left", padx=(0, 6))

        if self.sum_to_one:
            val_var.trace_add("write", lambda *_: self._update_sum())

        row_tuple = (key_var, val_var, row_frame)
        self.rows.append(row_tuple)

        del_btn = ctk.CTkButton(
            row_frame,
            text="✕",
            width=28,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="transparent",
            hover_color="#7F1D1D",
            text_color="#EF4444",
            command=lambda rf=row_frame, rt=row_tuple: self._remove_row(rf, rt),
        )
        del_btn.pack(side="left")

        self._update_count()
        if self.sum_to_one:
            self._update_sum()

    def _remove_row(
        self,
        frame: ctk.CTkFrame,
        tuple_item: tuple[ctk.StringVar, ctk.StringVar, ctk.CTkFrame],
    ) -> None:
        if tuple_item in self.rows:
            self.rows.remove(tuple_item)
        frame.destroy()
        self._update_count()
        if self.sum_to_one:
            self._update_sum()

    def _on_filter(self, *_: Any) -> None:
        query = self.search_var.get().strip().lower()
        for key_var, val_var, frame in self.rows:
            k = key_var.get().lower()
            v = val_var.get().lower()
            if not query or query in k or query in v:
                frame.pack(fill="x", pady=2)
            else:
                frame.pack_forget()

    def _update_count(self) -> None:
        self.count_badge.configure(text=f"{len(self.rows)} items")

    def _update_sum(self) -> None:
        if not hasattr(self, "sum_badge"):
            return
        total = 0.0
        for _, val_var, _ in self.rows:
            try:
                total += float(val_var.get())
            except ValueError:
                pass
        pct = total * 100.0
        if abs(total - 1.0) <= 0.005:
            self.sum_badge.configure(
                text=f"Total: {pct:.1f}%", text_color="#4ADE80", fg_color="#062817"
            )
        else:
            self.sum_badge.configure(
                text=f"Total: {pct:.1f}%", text_color="#F59E0B", fg_color="#362408"
            )

    def get_value(self) -> dict[str, Any]:
        """Retrieve dictionary mappings from non-empty rows, casting values by value_type."""
        result: dict[str, Any] = {}
        for key_var, val_var, _ in self.rows:
            k = key_var.get().strip()
            if not k:
                continue
            raw_v = val_var.get().strip()
            if self.value_type == "float":
                try:
                    result[k] = float(raw_v)
                except ValueError:
                    result[k] = 0.0
            elif self.value_type == "int":
                try:
                    result[k] = int(raw_v)
                except ValueError:
                    result[k] = 0
            else:
                result[k] = raw_v
        return result

    def set_value(self, data: dict[str, Any]) -> None:
        """Clear existing rows and populate table with dictionary entries."""
        for _, _, frame in self.rows:
            frame.destroy()
        self.rows.clear()
        for k, v in data.items():
            self._add_row(k, v)
        self._update_count()
        if self.sum_to_one:
            self._update_sum()


class ListEditorModal(ctk.CTkToplevel):  # type: ignore[misc]
    """Visual modal manager for viewing, filtering, adding, editing, and deleting list items."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        field_name: str,
        initial_items: list[str],
        description: str = "",
        unit_text: str = "items",
        is_int_list: bool = False,
        on_apply: Callable[[list[str]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.field_name = field_name
        self.items: list[str] = [str(x).strip() for x in initial_items if str(x).strip()]
        self.unit_text = unit_text
        self.is_int_list = is_int_list
        self.on_apply = on_apply

        self.item_entry_vars: list[tuple[ctk.StringVar, ctk.CTkFrame]] = []

        title_display = field_name.replace("_", " ").title()
        self.title(f"Manage {title_display}")
        self.geometry("560x580")
        self.minsize(460, 440)
        self.configure(fg_color=Color.BG)

        try:
            self.transient(parent.winfo_toplevel())
            self.grab_set()
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=0)  # Search filter
        self.grid_rowconfigure(2, weight=1)  # Items scroll area
        self.grid_rowconfigure(3, weight=0)  # Add new items card
        self.grid_rowconfigure(4, weight=0)  # Footer actions

        self._build_header(title_display, description)
        self._build_search_bar()
        self._build_items_scroll_area()
        self._build_add_box()
        self._build_footer()

        self._render_items()

    def _build_header(self, title_display: str, description: str) -> None:
        """Render header block with title, item count badge, and field description."""
        header = ctk.CTkFrame(self, fg_color="#101624", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(header, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            top_row,
            text=f"📝  {title_display}",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=Color.TEXT,
        ).pack(side="left")

        self.count_badge = ctk.CTkLabel(
            top_row,
            text=f"{len(self.items)} {self.unit_text}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38BDF8",
            fg_color="#0B263B",
            corner_radius=4,
        )
        self.count_badge.pack(side="right", ipady=2, ipadx=6)

        if description:
            ctk.CTkLabel(
                header,
                text=description,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#94A3B8",
                wraplength=520,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 10))

    def _build_search_bar(self) -> None:
        """Render real-time search and filter input bar."""
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 4))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render_items())

        self.search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="🔍 Filter items...",
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#0C121D",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")

    def _build_items_scroll_area(self) -> None:
        """Create scrollable viewport holding dynamic item rows."""
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def _build_add_box(self) -> None:
        """Construct input card for inserting new items singly or in bulk."""
        add_card = ctk.CTkFrame(
            self,
            fg_color="#0C121D",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
        )
        add_card.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 8))
        add_card.grid_columnconfigure(0, weight=1)

        lbl_row = ctk.CTkFrame(add_card, fg_color="transparent")
        lbl_row.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            lbl_row,
            text="+ Add New Item(s)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38BDF8",
        ).pack(side="left")

        ctk.CTkLabel(
            lbl_row,
            text="(single item or paste comma / newline-separated values)",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#64748B",
        ).pack(side="left", padx=(6, 0))

        input_row = ctk.CTkFrame(add_card, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(2, 8))
        input_row.grid_columnconfigure(0, weight=1)

        self.add_entry_var = ctk.StringVar()
        self.add_entry = ctk.CTkEntry(
            input_row,
            textvariable=self.add_entry_var,
            placeholder_text="Enter ID / value or paste multiple...",
            height=32,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#080C14",
            border_color="#1E293B",
            border_width=1,
            corner_radius=5,
        )
        self.add_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.add_entry.bind("<Return>", lambda _: self._on_add_clicked())

        ctk.CTkButton(
            input_row,
            text="+ Add",
            width=70,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            corner_radius=5,
            command=self._on_add_clicked,
        ).grid(row=0, column=1)

    def _build_footer(self) -> None:
        """Render modal action footer with Clear, Cancel, and Apply buttons."""
        footer = ctk.CTkFrame(self, fg_color="#101624", height=48, corner_radius=0)
        footer.grid(row=4, column=0, sticky="ew")

        ctk.CTkButton(
            footer,
            text="🗑️ Clear All",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1E293B",
            hover_color="#7F1D1D",
            text_color="#F87171",
            width=90,
            height=30,
            corner_radius=5,
            command=self._on_clear_all,
        ).pack(side="left", padx=16, pady=9)

        ctk.CTkButton(
            footer,
            text="✓ Apply Changes",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color=Color.ACC_HOV,
            width=130,
            height=32,
            corner_radius=5,
            command=self._on_apply_clicked,
        ).pack(side="right", padx=16, pady=8)

        ctk.CTkButton(
            footer,
            text="Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            width=80,
            height=32,
            corner_radius=5,
            command=self.destroy,
        ).pack(side="right", padx=(0, 6), pady=8)

    def _on_add_clicked(self) -> None:
        """Parse, validate, and append new items from add_entry input."""
        raw_text = self.add_entry_var.get().strip()
        if not raw_text:
            return

        parts = [
            p.strip().strip("'\"")
            for p in raw_text.replace("\n", ",").split(",")
            if p.strip().strip("'\"")
        ]
        for p in parts:
            if self.is_int_list:
                try:
                    int(p)
                except ValueError:
                    continue
            if p not in self.items:
                self.items.append(p)

        self.add_entry_var.set("")
        self._render_items()

    def _on_clear_all(self) -> None:
        """Remove all items from current staging list."""
        self.items.clear()
        self._render_items()

    def _remove_item(self, item_val: str) -> None:
        """Remove a specific item from staging list by value."""
        self.items = [x for x in self.items if x != item_val]
        self._render_items()

    def _render_items(self) -> None:
        """Re-render visible item cards based on active filter."""
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self.item_entry_vars.clear()

        query = self.search_var.get().strip().lower()
        displayed = [x for x in self.items if not query or query in x.lower()]

        self.count_badge.configure(text=f"{len(self.items)} {self.unit_text}")

        if not displayed:
            empty_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="No items match filter." if query else "No items configured.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#64748B",
            )
            empty_lbl.pack(pady=30)
            return

        for idx, item_str in enumerate(displayed, start=1):
            row_frame = ctk.CTkFrame(
                self.scroll_frame,
                fg_color="#101624",
                border_color="#1E293B",
                border_width=1,
                corner_radius=5,
            )
            row_frame.pack(fill="x", pady=2)
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_frame,
                text=f"#{idx}",
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#64748B",
                width=32,
            ).grid(row=0, column=0, padx=(8, 4), pady=4)

            item_var = ctk.StringVar(value=item_str)
            entry = ctk.CTkEntry(
                row_frame,
                textvariable=item_var,
                font=ctk.CTkFont(family="Consolas", size=11),
                fg_color="#080C14",
                border_color="#1E293B",
                border_width=1,
                corner_radius=4,
                height=28,
            )
            entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

            del_btn = ctk.CTkButton(
                row_frame,
                text="✕",
                width=28,
                height=26,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#1E293B",
                hover_color="#7F1D1D",
                text_color="#F87171",
                corner_radius=4,
                command=lambda val=item_str: self._remove_item(val),
            )
            del_btn.grid(row=0, column=2, padx=(4, 8), pady=4)

            self.item_entry_vars.append((item_var, row_frame))

    def _on_apply_clicked(self) -> None:
        """Collect current values from entries and propagate to parent callback."""
        if self.item_entry_vars:
            updated_items: list[str] = []
            for var, _ in self.item_entry_vars:
                val = var.get().strip()
                if val and val not in updated_items:
                    updated_items.append(val)
            self.items = updated_items

        if self.on_apply is not None:
            self.on_apply(self.items)
        self.destroy()
