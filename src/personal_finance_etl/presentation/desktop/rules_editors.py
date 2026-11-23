"""Dynamic editor components for financial rules models and statutory structures.

Owns
----
- InlineListEditor: Compact inline list row with live count badge and modal manager.
- InvestmentInstrumentsEditor: Dynamic table manager for investment instruments.
- TaxHeadSectionEditor: Dynamic hierarchy manager for statutory tax heads and sub-heads.

Does not own
-------------
- Financial rules TOML serialization (owned by infrastructure.configuration.toml_store).
- Tab navigation or AppState coordination (owned by presentation.desktop.financial_rules_tab).
"""

from __future__ import annotations

from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

from personal_finance_etl.config.financial_rules.investments import InvestmentInstrumentRules
from personal_finance_etl.config.financial_rules.tax import TaxSubHeadConfig
from personal_finance_etl.presentation.desktop.config_editor import (
    ListEditorModal,
)
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = [
    "InlineListEditor",
    "InvestmentInstrumentsEditor",
    "TaxHeadSectionEditor",
]


class InlineListEditor(ctk.CTkFrame):  # type: ignore[misc]
    """Compact inline list editor with item counter badge and modal list management trigger."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        label: str,
        initial_items: list[str] | None = None,
        unit_text: str = "IDs",
        description: str = "",
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.label_text = label
        self.unit_text = unit_text
        self.description = description
        items = [str(x).strip() for x in (initial_items or []) if str(x).strip()]

        self.pack(fill="x", pady=2)
        self.grid_columnconfigure(2, weight=1)

        # Label
        ctk.CTkLabel(
            self,
            text=f"{label}:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
            width=125,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(4, 6))

        # Counter Badge
        self.count_badge = ctk.CTkLabel(
            self,
            text=f"{len(items)} {unit_text}",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#38BDF8",
            fg_color="#0B263B",
            corner_radius=4,
            width=58,
            anchor="center",
        )
        self.count_badge.grid(row=0, column=1, padx=(0, 6), ipady=1, ipadx=4)

        # Preview Entry
        self.entry_var = ctk.StringVar(value=", ".join(items))
        self.entry_var.trace_add("write", self._on_text_change)
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.entry_var,
            font=ctk.CTkFont(family="Consolas", size=10),
            placeholder_text="Comma-separated IDs...",
            height=28,
            fg_color="#080C14",
            border_color="#1E293B",
            border_width=1,
            corner_radius=4,
        )
        self.entry.grid(row=0, column=2, sticky="ew", padx=(0, 6))

        # Manage Button
        ctk.CTkButton(
            self,
            text="📝 Manage",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            height=28,
            width=76,
            corner_radius=4,
            command=self._open_modal,
        ).grid(row=0, column=3, padx=(0, 4))

    def _on_text_change(self, *_: Any) -> None:
        """Update count badge live when typing in the entry."""
        raw = self.entry_var.get().strip()
        items = [x.strip() for x in raw.split(",") if x.strip()]
        self.count_badge.configure(text=f"{len(items)} {self.unit_text}")

    def _open_modal(self) -> None:
        """Launch the full-featured ListEditorModal dialog."""
        items = self.get_value()

        def _on_apply(updated: list[str]) -> None:
            self.set_value(updated)

        ListEditorModal(
            self,
            field_name=self.label_text,
            initial_items=items,
            description=self.description,
            unit_text=self.unit_text,
            on_apply=_on_apply,
        )

    def get_value(self) -> list[str]:
        """Retrieve cleaned list of values from the input entry."""
        raw = self.entry_var.get().strip()
        return [x.strip() for x in raw.split(",") if x.strip()]

    def set_value(self, items: list[str]) -> None:
        """Update entry text and count badge with external list."""
        self.entry_var.set(", ".join(items))
        self.count_badge.configure(text=f"{len(items)} {self.unit_text}")


class InvestmentInstrumentsEditor(ctk.CTkFrame):  # type: ignore[misc]
    """Dynamic visual editor for market investment instruments with add and remove triggers."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        initial_instruments: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            parent,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        self.instruments: dict[str, Any] = {}

        self.pack(fill="x", pady=6)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self.body_container = ctk.CTkFrame(self, fg_color="transparent")
        self.body_container.pack(fill="x", padx=12, pady=(8, 12))
        self.body_container.grid_columnconfigure(0, weight=1)

        if initial_instruments:
            self.load_from_data(initial_instruments)

    def _build_header(self) -> None:
        """Render header with title and + Add Instrument trigger."""
        header = ctk.CTkFrame(self, fg_color="#0C121D", corner_radius=8, height=38)
        header.pack(fill="x", padx=1, pady=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=12, pady=6)

        ctk.CTkLabel(
            left,
            text="📈  Investment Instruments",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left")

        self.count_badge = ctk.CTkLabel(
            left,
            text="0 instruments",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#94A3B8",
            fg_color="#1E293B",
            corner_radius=4,
        )
        self.count_badge.pack(side="left", padx=(8, 0), ipady=1, ipadx=4)

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=12, pady=4)

        ctk.CTkButton(
            right,
            text="+ Add Instrument",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            height=26,
            width=120,
            corner_radius=4,
            command=self._on_add_instrument_clicked,
        ).pack(side="left")

    def _on_add_instrument_clicked(self) -> None:
        """Prompt user for new instrument key and create its card."""
        dialog = ctk.CTkInputDialog(
            text="Enter instrument name (e.g. Stocks, Mutual_Funds, Gold, Crypto):",
            title="Add Investment Instrument",
        )
        val = dialog.get_input()
        if not val:
            return
        inst_key = val.strip().replace(" ", "_")
        if inst_key in self.instruments:
            return
        self.add_instrument(
            inst_key, InvestmentInstrumentRules(category_ids=[], sub_category_ids=[])
        )

    def add_instrument(self, inst_key: str, inst_rules: Any) -> None:
        """Instantiate an instrument card with category and subcategory editors."""
        if inst_key in self.instruments:
            return

        sub_card = ctk.CTkFrame(
            self.body_container,
            fg_color="#0C121D",
            corner_radius=6,
            border_color=Color.BORDER,
            border_width=1,
        )
        sub_card.pack(fill="x", pady=4, padx=2)
        sub_card.grid_columnconfigure(0, weight=1)

        h = ctk.CTkFrame(sub_card, fg_color="transparent")
        h.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            h,
            text=f"Instrument: {inst_key}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38BDF8",
        ).pack(side="left")

        ctk.CTkButton(
            h,
            text="🗑️ Delete",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            fg_color="#1E293B",
            hover_color="#7F1D1D",
            text_color="#F87171",
            height=22,
            width=65,
            corner_radius=4,
            command=lambda k=inst_key: self.remove_instrument(k),
        ).pack(side="right")

        body = ctk.CTkFrame(sub_card, fg_color="transparent")
        body.pack(fill="x", padx=8, pady=(2, 6))

        cat_val = (
            inst_rules.category_ids
            if hasattr(inst_rules, "category_ids")
            else inst_rules.get("category_ids", [])
        )
        ed_cat = InlineListEditor(body, "Category IDs", cat_val, unit_text="IDs")

        sub_val = (
            inst_rules.sub_category_ids
            if hasattr(inst_rules, "sub_category_ids")
            else inst_rules.get("sub_category_ids", [])
        )
        ed_sub = InlineListEditor(body, "Subcategory UIDs", sub_val, unit_text="IDs")

        self.instruments[inst_key] = {
            "frame": sub_card,
            "ed_cat": ed_cat,
            "ed_sub": ed_sub,
        }
        self.count_badge.configure(text=f"{len(self.instruments)} instruments")

    def remove_instrument(self, inst_key: str) -> None:
        """Remove instrument from visual editor."""
        if inst_key in self.instruments:
            self.instruments[inst_key]["frame"].destroy()
            del self.instruments[inst_key]
            self.count_badge.configure(text=f"{len(self.instruments)} instruments")

    def load_from_data(self, instruments_dict: dict[str, Any]) -> None:
        """Rebuild all instrument cards from a dictionary."""
        for child in self.body_container.winfo_children():
            child.destroy()
        self.instruments.clear()
        for k, v in instruments_dict.items():
            self.add_instrument(k, v)

    def get_value(self) -> dict[str, Any]:
        """Collect current values from all instrument editors."""
        result: dict[str, Any] = {}
        for k, entry in self.instruments.items():
            result[k] = {
                "category_ids": entry["ed_cat"].get_value(),
                "sub_category_ids": entry["ed_sub"].get_value(),
            }
        return result


class TaxHeadSectionEditor(ctk.CTkFrame):  # type: ignore[misc]
    """Dynamic container editor for statutory tax heads and sub-heads in a given section."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        section_key: str,
        section_title: str,
        icon: str,
    ) -> None:
        super().__init__(
            parent,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        self.section_key = section_key
        self.section_title = section_title
        self.icon = icon
        self.heads: dict[str, Any] = {}

        self.pack(fill="x", pady=6)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self.body_container = ctk.CTkFrame(self, fg_color="transparent")
        self.body_container.pack(fill="x", padx=12, pady=(8, 12))
        self.body_container.grid_columnconfigure(0, weight=1)

    def _build_header(self) -> None:
        """Construct section header with title and + Add Head button."""
        header = ctk.CTkFrame(self, fg_color="#0C121D", corner_radius=8, height=38)
        header.pack(fill="x", padx=1, pady=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=12, pady=6)

        ctk.CTkLabel(
            left,
            text=f"{self.icon}  {self.section_title}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left")

        self.count_badge = ctk.CTkLabel(
            left,
            text="0 heads (0 sub-heads)",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color="#94A3B8",
            fg_color="#1E293B",
            corner_radius=4,
        )
        self.count_badge.pack(side="left", padx=(8, 0), ipady=1, ipadx=4)

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=12, pady=4)

        ctk.CTkButton(
            right,
            text="+ Add Tax Head",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#38BDF8",
            height=26,
            width=110,
            corner_radius=4,
            command=self._on_add_head_clicked,
        ).pack(side="left")

    def _on_add_head_clicked(self) -> None:
        """Prompt user for a new head name and create its section."""
        dialog = ctk.CTkInputDialog(
            text="Enter new Tax Head identifier (e.g. Salary, Capital_Gains, Other_Sources):",
            title=f"Add Tax Head to {self.section_title}",
        )
        val = dialog.get_input()
        if not val:
            return
        head_key = val.strip().replace(" ", "_")
        if head_key in self.heads:
            return
        self.add_head(head_key)

    def add_head(self, head_name: str) -> None:
        """Create a visual card for a tax head containing subhead controls."""
        if head_name in self.heads:
            return

        head_frame = ctk.CTkFrame(
            self.body_container,
            fg_color="#0B132B",
            corner_radius=7,
            border_color="#1E293B",
            border_width=1,
        )
        head_frame.pack(fill="x", pady=6)
        head_frame.grid_columnconfigure(0, weight=1)

        head_hdr = ctk.CTkFrame(head_frame, fg_color="#0A0E1A", corner_radius=6, height=34)
        head_hdr.pack(fill="x", padx=1, pady=1)

        left = ctk.CTkFrame(head_hdr, fg_color="transparent")
        left.pack(side="left", padx=10, pady=4)

        ctk.CTkLabel(
            left,
            text=f"🏛️  Head: {head_name}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#7DD3FC",
        ).pack(side="left")

        right = ctk.CTkFrame(head_hdr, fg_color="transparent")
        right.pack(side="right", padx=10, pady=4)

        ctk.CTkButton(
            right,
            text="+ Add Sub-Head",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color="#1E293B",
            hover_color="#22C55E",
            text_color="#86EFAC",
            height=24,
            width=110,
            corner_radius=4,
            command=lambda hn=head_name: self._on_add_subhead_clicked(hn),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            right,
            text="🗑️",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="transparent",
            hover_color="#7F1D1D",
            text_color="#F87171",
            height=24,
            width=28,
            corner_radius=4,
            command=lambda hn=head_name: self.remove_head(hn),
        ).pack(side="left")

        sub_container = ctk.CTkFrame(head_frame, fg_color="transparent")
        sub_container.pack(fill="x", padx=8, pady=(4, 8))
        sub_container.grid_columnconfigure(0, weight=1)

        self.heads[head_name] = {
            "frame": head_frame,
            "subheads_container": sub_container,
            "sub_heads": {},
        }
        self._update_badges()

    def remove_head(self, head_name: str) -> None:
        """Remove a tax head and all its subheads from UI."""
        if head_name in self.heads:
            self.heads[head_name]["frame"].destroy()
            del self.heads[head_name]
            self._update_badges()

    def _on_add_subhead_clicked(self, head_name: str) -> None:
        """Prompt user for a subhead identifier and instantiate it."""
        dialog = ctk.CTkInputDialog(
            text=f"Enter Sub-Head identifier under '{head_name}' (e.g. Base, HRA, Bonus):",
            title=f"Add Sub-Head to {head_name}",
        )
        val = dialog.get_input()
        if not val:
            return
        sub_key = val.strip().replace(" ", "_")
        if head_name not in self.heads or sub_key in self.heads[head_name]["sub_heads"]:
            return

        default_sub = TaxSubHeadConfig(
            tax_head_display_name=head_name.replace("_", " "),
            sub_head_display_name=sub_key.replace("_", " "),
            taxability="taxable" if "heads_of_income" in self.section_key else "non_taxable",
            tax_method="ordinary_rate" if "heads_of_income" in self.section_key else "exempt",
            cat_ids=[],
            sub_cat_ids=[],
            tax_credit_sub_cat_ids=[],
        )
        self.add_sub_head(head_name, sub_key, default_sub)

    def add_sub_head(self, head_name: str, sub_key: str, sub_config: TaxSubHeadConfig) -> None:
        """Instantiate a full subhead card with all statutory fields."""
        if head_name not in self.heads:
            self.add_head(head_name)

        head_entry = self.heads[head_name]
        if sub_key in head_entry["sub_heads"]:
            return

        sub_card = ctk.CTkFrame(
            head_entry["subheads_container"],
            fg_color="#0C121D",
            corner_radius=6,
            border_color=Color.BORDER,
            border_width=1,
        )
        sub_card.pack(fill="x", pady=4, padx=2)
        sub_card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(sub_card, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            hdr,
            text=f"↳ Sub-Head: {sub_key}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#38BDF8",
        ).pack(side="left")

        del_btn = ctk.CTkButton(
            hdr,
            text="🗑️ Delete Sub-Head",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            fg_color="#1E293B",
            hover_color="#7F1D1D",
            text_color="#F87171",
            height=22,
            corner_radius=4,
            command=lambda hn=head_name, sk=sub_key: self.remove_sub_head(hn, sk),
        )
        del_btn.pack(side="right")

        inner = ctk.CTkFrame(sub_card, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=(2, 6))

        # Row 1: Display Names & Policy controls
        ctl_row = ctk.CTkFrame(inner, fg_color="transparent")
        ctl_row.pack(fill="x", pady=2)
        ctl_row.grid_columnconfigure(1, weight=1)
        ctl_row.grid_columnconfigure(3, weight=1)

        # Head Display
        ctk.CTkLabel(
            ctl_row,
            text="Head:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
            width=38,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(4, 2))

        th_var = ctk.StringVar(value=sub_config.tax_head_display_name)
        ed_th = ctk.CTkEntry(
            ctl_row,
            textvariable=th_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color="#1E293B",
            border_width=1,
            corner_radius=4,
            height=28,
        )
        ed_th.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        # Sub-head Display
        ctk.CTkLabel(
            ctl_row,
            text="Sub:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#94A3B8",
            width=32,
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(2, 2))

        sh_var = ctk.StringVar(value=sub_config.sub_head_display_name)
        ed_sh = ctk.CTkEntry(
            ctl_row,
            textvariable=sh_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#080C14",
            border_color="#1E293B",
            border_width=1,
            corner_radius=4,
            height=28,
        )
        ed_sh.grid(row=0, column=3, sticky="ew", padx=(0, 6))

        # Taxability
        tax_var = ctk.StringVar(value=sub_config.taxability)
        ed_tax = ctk.CTkOptionMenu(
            ctl_row,
            variable=tax_var,
            values=["taxable", "non_taxable", "review"],
            width=105,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#101624",
            button_color="#1E293B",
            corner_radius=4,
        )
        ed_tax.grid(row=0, column=4, padx=(0, 4))

        # Tax Method
        mth_var = ctk.StringVar(value=sub_config.tax_method)
        ed_mth = ctk.CTkOptionMenu(
            ctl_row,
            variable=mth_var,
            values=["ordinary_rate", "capital_gains", "exempt", "review"],
            width=120,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#101624",
            button_color="#1E293B",
            corner_radius=4,
        )
        ed_mth.grid(row=0, column=5, padx=(0, 2))

        # Rows 2, 3, 4: List editors with live count badges and manage modal
        ed_cat = InlineListEditor(inner, "Category IDs", sub_config.cat_ids, unit_text="IDs")
        ed_sub = InlineListEditor(
            inner, "Subcategory UIDs", sub_config.sub_cat_ids, unit_text="IDs"
        )
        ed_crd = InlineListEditor(
            inner, "Tax Credit UIDs", sub_config.tax_credit_sub_cat_ids, unit_text="IDs"
        )

        head_entry["sub_heads"][sub_key] = {
            "frame": sub_card,
            "th_var": th_var,
            "sh_var": sh_var,
            "tax_var": tax_var,
            "mth_var": mth_var,
            "ed_cat": ed_cat,
            "ed_sub": ed_sub,
            "ed_crd": ed_crd,
        }
        self._update_badges()

    def remove_sub_head(self, head_name: str, sub_key: str) -> None:
        """Remove a single subhead from a head."""
        if head_name in self.heads and sub_key in self.heads[head_name]["sub_heads"]:
            self.heads[head_name]["sub_heads"][sub_key]["frame"].destroy()
            del self.heads[head_name]["sub_heads"][sub_key]
            self._update_badges()

    def _update_badges(self) -> None:
        """Update header head and sub-head counter badge."""
        total_heads = len(self.heads)
        total_sub = sum(len(h["sub_heads"]) for h in self.heads.values())
        self.count_badge.configure(text=f"{total_heads} heads ({total_sub} sub-heads)")

    def load_from_data(self, heads_dict: dict[str, Any]) -> None:
        """Rebuild all heads and subheads from a dictionary or model mapping."""
        for child in self.body_container.winfo_children():
            child.destroy()
        self.heads.clear()

        for head_name, head_config in heads_dict.items():
            self.add_head(head_name)
            sub_heads = (
                head_config.sub_heads
                if hasattr(head_config, "sub_heads")
                else head_config.get("sub_heads", {})
            )
            for sub_key, sub_cfg in sub_heads.items():
                if not isinstance(sub_cfg, TaxSubHeadConfig):
                    sub_cfg = TaxSubHeadConfig.model_validate(sub_cfg)
                self.add_sub_head(head_name, sub_key, sub_cfg)

    def get_value(self) -> dict[str, Any]:
        """Aggregate current UI values from all heads and subheads into a dict."""
        result: dict[str, Any] = {}
        for head_name, head_entry in self.heads.items():
            sub_dict: dict[str, Any] = {}
            for sub_key, editors in head_entry["sub_heads"].items():
                sub_dict[sub_key] = {
                    "tax_head_display_name": editors["th_var"].get().strip(),
                    "sub_head_display_name": editors["sh_var"].get().strip(),
                    "taxability": editors["tax_var"].get().strip(),
                    "tax_method": editors["mth_var"].get().strip(),
                    "cat_ids": editors["ed_cat"].get_value(),
                    "sub_cat_ids": editors["ed_sub"].get_value(),
                    "tax_credit_sub_cat_ids": editors["ed_crd"].get_value(),
                }
            result[head_name] = {"sub_heads": sub_dict}
        return result
