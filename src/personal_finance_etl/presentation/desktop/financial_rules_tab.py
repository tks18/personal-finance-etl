"""Financial Rules Tab component for interactive TOML rules and assumptions editing.

Owns
----
- FinancialRulesTab: CustomTkinter frame presenting categorized FinancialRules sub-tabs
  (Household, Investments, Tax, FIRE & Simulation, Mappings).
- Coordinating file loading, field binding, matrix/dictionary editing, and reloading.
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
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.financial_rules.fire import MonteCarloAssumptions
from personal_finance_etl.config.financial_rules.tax import (
    TaxAssumptions,
)
from personal_finance_etl.presentation.desktop.config_editor import (
    ConfigFieldEditor,
    KeyValueDictEditor,
    Matrix3x3Editor,
    Tuple3Editor,
)
from personal_finance_etl.presentation.desktop.rules_editors import (
    InlineListEditor,
    InvestmentInstrumentsEditor,
    TaxHeadSectionEditor,
)
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import Color

__all__ = [
    "FinancialRulesTab",
    "InlineListEditor",
    "InvestmentInstrumentsEditor",
    "TaxHeadSectionEditor",
]


class FinancialRulesTab(ctk.CTkFrame):  # type: ignore[misc]
    """Visual rules editor tab for reviewing and modifying financial rules TOML files."""

    def __init__(
        self,
        parent: ctk.CTk | ctk.CTkFrame,
        engine: PersonalFinanceEngine | None = None,
        app_state: AppState | None = None,
        on_rules_saved: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color=Color.BG)

        self.engine = engine or PersonalFinanceEngine()
        self.app_state = app_state
        self.on_rules_saved = on_rules_saved

        self.current_filepath: str = ""
        self.original_doc: TOMLDocument | None = None
        self.active_rules: FinancialRules | None = None

        self.editors: dict[str, ConfigFieldEditor] = {}
        self.special_editors: dict[str, Any] = {}
        self.subtab_buttons: dict[str, ctk.CTkButton] = {}
        self.subtab_frames: dict[str, ctk.CTkScrollableFrame] = {}
        self.active_subtab_id: str = "household"
        self._rendered_subtabs: set[str] = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Toolbar
        self.grid_rowconfigure(1, weight=0)  # Subtab navigation switcher
        self.grid_rowconfigure(2, weight=0)  # Status banner
        self.grid_rowconfigure(3, weight=1)  # Subtab body area

        self._build_toolbar()
        self._build_subtab_nav()
        self._build_status_banner()
        self._build_subtab_frames()

        if self.app_state is not None:
            self.app_state.subscribe_rules(self._on_external_rules_changed)
            initial_path = self.app_state.active_rules_path
        else:
            recents = self.engine.get_recent_rules()
            initial_path = recents[0] if recents else ""

        if initial_path and os.path.isfile(initial_path):
            self.load_rules(initial_path, notify_state=False)
        else:
            sample_fixture = "tests/fixtures/financial_rules.toml"
            if os.path.isfile(sample_fixture):
                self.load_rules(sample_fixture, notify_state=False)

    # ── Top Toolbar ──────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        """Construct top control bar with rules profile selector and action buttons."""
        toolbar_card = ctk.CTkFrame(
            self,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        toolbar_card.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        toolbar_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            toolbar_card,
            text="Financial Rules",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#86EFAC",
            fg_color="#062817",
            corner_radius=4,
            width=100,
            anchor="center",
        ).grid(row=0, column=0, sticky="w", padx=(10, 8), pady=8, ipady=4, ipadx=6)

        recents = self.engine.get_recent_rules()
        self.rules_path_var = ctk.StringVar(value=recents[0] if recents else "")
        self.rules_combo = ctk.CTkComboBox(
            toolbar_card,
            variable=self.rules_path_var,
            values=recents if recents else [""],
            height=32,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#080C14",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=6,
            command=self._on_rules_combo_selected,
        )
        self.rules_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

        btn_bar = ctk.CTkFrame(toolbar_card, fg_color="transparent")
        btn_bar.grid(row=0, column=2, sticky="e", padx=(8, 10), pady=8)

        ctk.CTkButton(
            btn_bar,
            text="Browse...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            width=75,
            command=self._on_browse_file,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="↻ Reload",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            width=75,
            command=self._on_reload,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="🔍 Validate",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            width=80,
            command=self._on_validate_clicked,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="Save As...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            width=78,
            command=self._on_save_as,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="💾 Save Rules",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=Color.ACCENT,
            hover_color="#1D4ED8",
            height=32,
            width=100,
            command=self._on_save,
        ).pack(side="left", padx=(3, 0))

    # ── Subtab Navigation ────────────────────────────────────────

    def _build_subtab_nav(self) -> None:
        """Construct segmented navigation switcher for the 5 financial rule domains."""
        nav_card = ctk.CTkFrame(self, fg_color="transparent")
        nav_card.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 4))

        subtabs = [
            ("household", "🏠  Household"),
            ("investments", "📈  Investments"),
            ("tax", "⚖️  Tax Statutory"),
            ("fire", "🎯  FIRE & Simulation"),
            ("mappings", "🔀  Mappings"),
        ]

        for tab_id, tab_label in subtabs:
            btn = ctk.CTkButton(
                nav_card,
                text=tab_label,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#1E293B" if tab_id == self.active_subtab_id else "transparent",
                text_color=Color.TEXT if tab_id == self.active_subtab_id else "#94A3B8",
                hover_color="#2D3B55",
                height=30,
                corner_radius=6,
                command=lambda t=tab_id: self.switch_subtab(t),
            )
            btn.pack(side="left", padx=(0, 6))
            self.subtab_buttons[tab_id] = btn

    # ── Status Banner ────────────────────────────────────────────

    def _build_status_banner(self) -> None:
        """Render notification bar showing success messages or validation errors."""
        self.status_banner = ctk.CTkFrame(
            self,
            fg_color="#062817",
            border_color="#166534",
            border_width=1,
            corner_radius=6,
            height=32,
        )
        self.status_banner.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 4))
        self.status_banner.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_banner,
            text="✓ Ready to configure financial rules.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#4ADE80",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=12, pady=4)

    # ── Subtab Scrollable Frames ─────────────────────────────────

    def _build_subtab_frames(self) -> None:
        """Instantiate scrollable containers for each subtab."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 8))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        for tab_id in ("household", "investments", "tax", "fire", "mappings"):
            frame = ctk.CTkScrollableFrame(container, fg_color="transparent")
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_columnconfigure(0, weight=1)
            self.subtab_frames[tab_id] = frame

        self.switch_subtab("household")

    def switch_subtab(self, tab_id: str) -> None:
        """Switch active visible subtab view with lazy on-demand rendering."""
        self.active_subtab_id = tab_id
        if tab_id not in self._rendered_subtabs and self.active_rules is not None:
            self._populate_subtab(tab_id, self.active_rules)
            self._rendered_subtabs.add(tab_id)

        for t_id, frame in self.subtab_frames.items():
            if t_id == tab_id:
                frame.lift()
            else:
                frame.lower()

        for t_id, btn in self.subtab_buttons.items():
            if t_id == tab_id:
                btn.configure(fg_color="#1E293B", text_color=Color.TEXT)
            else:
                btn.configure(fg_color="transparent", text_color="#94A3B8")

    def _populate_subtab(self, tab_id: str, rules: FinancialRules) -> None:
        """Render controls for an individual subtab when first visited."""
        if tab_id == "household":
            self._populate_household_tab(rules)
        elif tab_id == "investments":
            self._populate_investments_tab(rules)
        elif tab_id == "tax":
            self._populate_tax_tab(rules)
        elif tab_id == "fire":
            self._populate_fire_tab(rules)
        elif tab_id == "mappings":
            self._populate_mappings_tab(rules)

    # ── Population & Rendering ───────────────────────────────────

    def _build_card_header(
        self,
        parent: ctk.CTkFrame,
        title: str,
        icon: str,
        subtitle: str = "",
        count_badge: str | None = None,
    ) -> ctk.CTkFrame:
        """Create a stylized card container with header title, icon, and optional badge."""
        card = ctk.CTkFrame(
            parent,
            fg_color="#101624",
            border_color=Color.BORDER,
            border_width=1,
            corner_radius=8,
        )
        card.pack(fill="x", pady=6)
        card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(card, fg_color="#0C121D", corner_radius=8, height=38)
        header.pack(fill="x", padx=1, pady=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=12, pady=6)

        ctk.CTkLabel(
            left,
            text=f"{icon}  {title}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left")

        if count_badge:
            ctk.CTkLabel(
                left,
                text=count_badge,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#94A3B8",
                fg_color="#1E293B",
                corner_radius=4,
            ).pack(side="left", padx=(8, 0), ipady=1, ipadx=4)

        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color="#64748B",
            ).pack(side="right", padx=12, pady=6)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(8, 12))
        body.grid_columnconfigure(0, weight=1)
        return body

    def _render_model_fields(
        self,
        parent: ctk.CTkFrame,
        model_instance: BaseModel,
        prefix: str,
    ) -> None:
        """Iterate over fields of a Pydantic model and render ConfigFieldEditors."""
        for field_name, field_info in type(model_instance).model_fields.items():
            full_key = f"{prefix}.{field_name}" if prefix else field_name
            val = getattr(model_instance, field_name)
            editor = ConfigFieldEditor(parent, field_name, field_info, val)
            editor.pack(fill="x", pady=2)
            self.editors[full_key] = editor

    # ── 1. Household Subtab ──────────────────────────────────────

    def _populate_household_tab(self, rules: FinancialRules) -> None:
        frame = self.subtab_frames["household"]

        # Income Classifications
        b1 = self._build_card_header(frame, "Active Earned Income", "💼", "[income.active]")
        self._render_model_fields(b1, rules.income.active, "income.active")

        b2 = self._build_card_header(frame, "Dividend Income", "💵", "[income.dividends]")
        self._render_model_fields(b2, rules.income.dividends, "income.dividends")

        b3 = self._build_card_header(frame, "Interest Income", "🏦", "[income.interest]")
        self._render_model_fields(b3, rules.income.interest, "income.interest")

        b4 = self._build_card_header(frame, "Non-Cash Income & Accruals", "🧾", "[income.non_cash]")
        self._render_model_fields(b4, rules.income.non_cash, "income.non_cash")

        b5 = self._build_card_header(frame, "Income Subcategory Grouping", "🏷️", "[income.grouping]")
        self._render_model_fields(b5, rules.income.grouping, "income.grouping")

        # Core Expenses
        b6 = self._build_card_header(frame, "Core & Essential Expenses", "🛒", "[expense.core]")
        self._render_model_fields(b6, rules.expense.core, "expense.core")

        b7 = self._build_card_header(
            frame, "Expense Analytics & Creep Policy", "📊", "[expense.analytics]"
        )
        self._render_model_fields(b7, rules.expense.analytics, "expense.analytics")

        # Assets
        b8 = self._build_card_header(frame, "Illiquid Physical Assets", "🏠", "[assets.illiquid]")
        self._render_model_fields(b8, rules.assets.illiquid, "assets.illiquid")

        b9 = self._build_card_header(
            frame, "Cashflow Activity & Conduit Mappings", "🔄", "[assets.cashflow]"
        )
        self._render_model_fields(b9, rules.assets.cashflow, "assets.cashflow")

        b10 = self._build_card_header(frame, "Digital & Virtual Assets", "🪙", "[assets.digital]")
        self._render_model_fields(b10, rules.assets.digital, "assets.digital")

        # Budget
        b11 = self._build_card_header(
            frame, "Budget Allocations (Income Allocation)", "⚖️", "[budget.income_allocation]"
        )
        self._render_model_fields(b11, rules.budget.income_allocation, "budget.income_allocation")

        b12 = self._build_card_header(
            frame, "Budget Overspend Alerts & Emergency Target", "🚨", "[budget.alerts]"
        )
        self._render_model_fields(b12, rules.budget.alerts, "budget.alerts")

        b13 = self._build_card_header(frame, "Income Smoothing Window", "🌊", "[budget.smoothing]")
        self._render_model_fields(b13, rules.budget.smoothing, "budget.smoothing")

    # ── 2. Investments Subtab ────────────────────────────────────

    def _populate_investments_tab(self, rules: FinancialRules) -> None:
        frame = self.subtab_frames["investments"]

        # Dynamic Investment Instruments
        self.instruments_editor = InvestmentInstrumentsEditor(frame, rules.investments)

        # Portfolio Management
        pm_body = self._build_card_header(
            frame, "Portfolio Drift & Validation Tolerances", "🎯", "[portfolio_management]"
        )
        self._render_model_fields(pm_body, rules.portfolio_management, "portfolio_management")

        # CMA
        cma_body = self._build_card_header(
            frame, "Capital Market Assumptions (CMA)", "🌐", "[assumptions.cma]"
        )
        self._render_model_fields(cma_body, rules.assumptions.cma, "assumptions.cma")

        # Target Allocations (KeyValueDictEditor with sum_to_one)
        alloc_editor = KeyValueDictEditor(
            frame,
            title="Target Asset Allocations",
            initial_dict=rules.assumptions.target_allocations,
            key_label="Asset Class",
            value_label="Target Weight",
            value_type="float",
            description="Target portfolio asset class allocations (must sum to 1.0 / 100%).",
            sum_to_one=True,
        )
        alloc_editor.pack(fill="x", pady=6)
        self.special_editors["assumptions.target_allocations"] = alloc_editor

    # ── 3. Tax Subtab ────────────────────────────────────────────

    def _populate_tax_tab(self, rules: FinancialRules) -> None:
        frame = self.subtab_frames["tax"]

        # Statutory Tax Rates
        rates_body = self._build_card_header(
            frame, "Statutory Capital Gains Tax Rates", "🏛️", "[assumptions.tax.rates]"
        )
        self._render_model_fields(rates_body, rules.assumptions.tax.rates, "assumptions.tax.rates")

        # Policies & Thresholds
        thresh_card = ctk.CTkFrame(
            frame, fg_color="#101624", border_color=Color.BORDER, border_width=1, corner_radius=8
        )
        thresh_card.pack(fill="x", pady=6)
        thresh_card.grid_columnconfigure(0, weight=1)

        h = ctk.CTkFrame(thresh_card, fg_color="#0C121D", corner_radius=8, height=38)
        h.pack(fill="x", padx=1, pady=1)
        ctk.CTkLabel(
            h,
            text="⏱️  Statutory Thresholds & Policies",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left", padx=12, pady=6)

        b = ctk.CTkFrame(thresh_card, fg_color="transparent")
        b.pack(fill="x", padx=12, pady=(8, 12))

        # Scalar tax fields
        for fname in (
            "debt_mf_cutoff_date",
            "harvest_wait_days_threshold",
            "fallback_equity_ltcg_exemption",
            "ltcg_maturity_ladder_days",
        ):
            finfo = TaxAssumptions.model_fields[fname]
            fval = getattr(rules.assumptions.tax, fname)
            ed = ConfigFieldEditor(b, fname, finfo, fval)
            ed.pack(fill="x", pady=2)
            self.editors[f"assumptions.tax.{fname}"] = ed

        # Holding periods dict
        hp_editor = KeyValueDictEditor(
            frame,
            title="LTCG Holding Period Thresholds",
            initial_dict=rules.assumptions.tax.ltcg_threshold_months,
            key_label="Asset Class / Tag",
            value_label="Months",
            value_type="int",
            description="Holding period thresholds in months defining Long Term Capital Gains across instrument classes.",
        )
        hp_editor.pack(fill="x", pady=6)
        self.special_editors["assumptions.tax.ltcg_threshold_months"] = hp_editor

        # Investment Exclusions
        excl_body = self._build_card_header(
            frame,
            "Capital Gains Subcategory Exclusions",
            "🛡️",
            "[assumptions.tax.investment_exclusions]",
        )
        self._render_model_fields(
            excl_body,
            rules.assumptions.tax.investment_exclusions,
            "assumptions.tax.investment_exclusions",
        )

        # Dynamic Statutory Heads of Income hierarchy
        self.taxable_heads_editor = TaxHeadSectionEditor(
            frame,
            "heads_of_income",
            "Taxable Heads of Income",
            "💼",
        )
        self.taxable_heads_editor.load_from_data(rules.assumptions.tax.heads_of_income)

        self.exempt_heads_editor = TaxHeadSectionEditor(
            frame,
            "exempt_income",
            "Exempt Income Heads",
            "🌱",
        )
        self.exempt_heads_editor.load_from_data(rules.assumptions.tax.exempt_income)

        self.residual_heads_editor = TaxHeadSectionEditor(
            frame,
            "residual_income",
            "Residual Income Heads",
            "📑",
        )
        self.residual_heads_editor.load_from_data(rules.assumptions.tax.residual_income)

    # ── 4. FIRE & Simulation Subtab ──────────────────────────────

    def _populate_fire_tab(self, rules: FinancialRules) -> None:
        frame = self.subtab_frames["fire"]

        # Macro
        macro_body = self._build_card_header(
            frame, "Macroeconomic Baseline Assumptions", "🌐", "[assumptions.macro]"
        )
        self._render_model_fields(macro_body, rules.assumptions.macro, "assumptions.macro")

        # FIRE
        fire_body = self._build_card_header(
            frame, "Financial Independence & SWR Rules", "🎯", "[assumptions.fire]"
        )
        self._render_model_fields(fire_body, rules.assumptions.fire, "assumptions.fire")

        # Monte Carlo General
        mc = rules.assumptions.monte_carlo
        mc_body = self._build_card_header(
            frame, "Monte Carlo General Parameters", "🎲", "[assumptions.monte_carlo]"
        )
        for fname in (
            "iterations",
            "max_months",
            "annual_volatility",
            "real_return_floor",
            "sorr_cagr_window_months",
            "desired_target_age",
            "date_of_birth",
        ):
            finfo = MonteCarloAssumptions.model_fields[fname]
            fval = getattr(mc, fname)
            ed = ConfigFieldEditor(mc_body, fname, finfo, fval)
            ed.pack(fill="x", pady=2)
            self.editors[f"assumptions.monte_carlo.{fname}"] = ed

        # Jump Diffusion
        jd_body = self._build_card_header(
            frame,
            "Jump Diffusion Black Swan Model",
            "⚡",
            "[assumptions.monte_carlo.jump_diffusion]",
        )
        self._render_model_fields(
            jd_body, mc.jump_diffusion, "assumptions.monte_carlo.jump_diffusion"
        )

        # Markov Regime Switching: Matrix3x3 + Tuples
        markov_card = ctk.CTkFrame(
            frame, fg_color="#101624", border_color=Color.BORDER, border_width=1, corner_radius=8
        )
        markov_card.pack(fill="x", pady=6)
        markov_card.grid_columnconfigure(0, weight=1)

        mh = ctk.CTkFrame(markov_card, fg_color="#0C121D", corner_radius=8, height=38)
        mh.pack(fill="x", padx=1, pady=1)
        ctk.CTkLabel(
            mh,
            text="🔄  Markov Regime Switching (3-State Model)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#F8FAFC",
        ).pack(side="left", padx=12, pady=6)

        mb = ctk.CTkFrame(markov_card, fg_color="transparent")
        mb.pack(fill="x", padx=12, pady=(8, 12))

        matrix_ed = Matrix3x3Editor(mb, initial_matrix=mc.markov_regime.transition_matrix)
        matrix_ed.pack(fill="x", pady=(0, 8))
        self.special_editors["assumptions.monte_carlo.markov_regime.transition_matrix"] = matrix_ed

        t_bull = Tuple3Editor(mb, "state_bull", initial_value=mc.markov_regime.state_bull)
        t_bull.pack(fill="x", pady=2)
        self.special_editors["assumptions.monte_carlo.markov_regime.state_bull"] = t_bull

        t_bear = Tuple3Editor(mb, "state_bear", initial_value=mc.markov_regime.state_bear)
        t_bear.pack(fill="x", pady=2)
        self.special_editors["assumptions.monte_carlo.markov_regime.state_bear"] = t_bear

        t_stag = Tuple3Editor(mb, "state_stag", initial_value=mc.markov_regime.state_stag)
        t_stag.pack(fill="x", pady=2)
        self.special_editors["assumptions.monte_carlo.markov_regime.state_stag"] = t_stag

        # Human Capital
        hc_body = self._build_card_header(
            frame, "Human Capital Shock Model", "🛡️", "[assumptions.monte_carlo.human_capital]"
        )
        self._render_model_fields(
            hc_body, mc.human_capital, "assumptions.monte_carlo.human_capital"
        )

        # Glide Path
        gp_body = self._build_card_header(
            frame, "Retirement Glide Path Model", "📉", "[assumptions.monte_carlo.glide_path]"
        )
        self._render_model_fields(gp_body, mc.glide_path, "assumptions.monte_carlo.glide_path")

        # Guyton-Klinger
        gk_body = self._build_card_header(
            frame, "Guyton-Klinger Guardrails", "🛡️", "[assumptions.monte_carlo.guyton_klinger]"
        )
        self._render_model_fields(
            gk_body, mc.guyton_klinger, "assumptions.monte_carlo.guyton_klinger"
        )

        # Inflation Model
        inf_body = self._build_card_header(
            frame,
            "Ornstein-Uhlenbeck Inflation Model",
            "📈",
            "[assumptions.monte_carlo.inflation_model]",
        )
        self._render_model_fields(
            inf_body, mc.inflation_model, "assumptions.monte_carlo.inflation_model"
        )

    # ── 5. Mappings Subtab ───────────────────────────────────────

    def _populate_mappings_tab(self, rules: FinancialRules) -> None:
        frame = self.subtab_frames["mappings"]

        # Default Currency
        cur_body = self._build_card_header(
            frame, "Primary Reporting Currency", "💱", "[DEFAULT_CURRENCY_ID]"
        )
        cur_finfo = FinancialRules.model_fields["DEFAULT_CURRENCY_ID"]
        cur_ed = ConfigFieldEditor(
            cur_body, "DEFAULT_CURRENCY_ID", cur_finfo, rules.DEFAULT_CURRENCY_ID
        )
        cur_ed.pack(fill="x", pady=2)
        self.editors["DEFAULT_CURRENCY_ID"] = cur_ed

        # MF Scheme Mappings
        mf_editor = KeyValueDictEditor(
            frame,
            title="Mutual Fund Scheme Normalization Mappings",
            initial_dict=rules.MF_SCHEME_MAPPINGS,
            key_label="Statement Scheme Name",
            value_label="Canonical Scheme Name",
            value_type="str",
            description="Normalized mutual fund scheme aliases mapping varied broker statement strings to canonical fund names.",
            show_search=True,
        )
        mf_editor.pack(fill="x", pady=6)
        self.special_editors["MF_SCHEME_MAPPINGS"] = mf_editor

    # ── File Operations & State Binding ──────────────────────────

    def ensure_rules_loaded(self, filepath: str) -> None:
        """Ensure requested financial rules are loaded without redundant re-parsing."""
        if not filepath:
            return
        if filepath != self.current_filepath or self.active_rules is None:
            self.load_rules(filepath, notify_state=False)

    def load_rules(self, filepath: str, notify_state: bool = True) -> None:
        """Load financial rules from disk into UI editors with lazy subtab rendering."""
        try:
            rules, doc = self.engine.load_financial_rules_document(filepath)
            self.current_filepath = filepath
            self.original_doc = doc
            self.active_rules = rules

            recents = self.engine.get_recent_rules()
            self.rules_combo.configure(values=recents)
            self.rules_path_var.set(filepath)

            # Invalidate subtab cache and clear frames
            self._rendered_subtabs.clear()
            self.editors.clear()
            self.special_editors.clear()
            for frame in self.subtab_frames.values():
                for child in frame.winfo_children():
                    child.destroy()

            # Render ONLY active subtab on demand
            self._populate_subtab(self.active_subtab_id, rules)
            self._rendered_subtabs.add(self.active_subtab_id)

            self._set_status(f"✓ Loaded rules: '{Path(filepath).name}'", is_error=False)

            if notify_state and self.app_state is not None:
                self.app_state.set_active_rules(filepath, source=self)
        except Exception as exc:
            self._set_status(f"✗ Failed to load financial rules: {exc}", is_error=True)

    def _collect_ui_payload(self) -> dict[str, Any]:
        """Aggregate values from all field editors and specialized editors into a dictionary."""
        if self.active_rules is None:
            raise ValueError("No active financial rules loaded to update.")

        payload = self.active_rules.model_dump(mode="json")

        # Standard field editors
        for path_str, editor in self.editors.items():
            val = editor.get_value()
            keys = path_str.split(".")
            curr = payload
            for k in keys[:-1]:
                if k not in curr or not isinstance(curr[k], dict):
                    curr[k] = {}
                curr = curr[k]
            curr[keys[-1]] = val

        # Dynamic instruments editor (if investments subtab was rendered)
        if hasattr(self, "instruments_editor") and "investments" in self._rendered_subtabs:
            payload["investments"] = self.instruments_editor.get_value()

        # Dynamic tax heads editors (if tax subtab was rendered)
        if "tax" in self._rendered_subtabs:
            if hasattr(self, "taxable_heads_editor"):
                payload["assumptions"]["tax"]["heads_of_income"] = (
                    self.taxable_heads_editor.get_value()
                )
            if hasattr(self, "exempt_heads_editor"):
                payload["assumptions"]["tax"]["exempt_income"] = (
                    self.exempt_heads_editor.get_value()
                )
            if hasattr(self, "residual_heads_editor"):
                payload["assumptions"]["tax"]["residual_income"] = (
                    self.residual_heads_editor.get_value()
                )

        # Specialized editors
        for path_str, sp_editor in self.special_editors.items():
            val = sp_editor.get_value()
            keys = path_str.split(".")
            curr = payload
            for k in keys[:-1]:
                if k not in curr or not isinstance(curr[k], dict):
                    curr[k] = {}
                curr = curr[k]
            curr[keys[-1]] = val

        return payload

    def _on_validate_clicked(self) -> None:
        """Validate UI values against Pydantic schema and statutory constraints."""
        try:
            payload = self._collect_ui_payload()
            validated_rules = FinancialRules.model_validate(payload)
            self.engine.validate_financial_rules_model(validated_rules)
            self._set_status(
                "✓ Financial rules model validation passed successfully.", is_error=False
            )
        except ValidationError as ve:
            err = ve.errors()[0]
            loc = " ➔ ".join(str(p) for p in err["loc"])
            self._set_status(f"✗ Validation Error at [{loc}]: {err['msg']}", is_error=True)
        except Exception as exc:
            self._set_status(f"✗ Validation Error: {exc}", is_error=True)

    def gather_rules_from_ui(self) -> FinancialRules:
        """Construct and validate a FinancialRules instance from current UI state."""
        payload = self._collect_ui_payload()
        return FinancialRules.model_validate(payload)

    def save_rules(self) -> bool:
        """Validate and atomically persist financial rules to current file.

        Returns
        -------
        bool
            True if saved successfully, False if validation or persistence failed.
        """
        if not self.current_filepath:
            return False

        try:
            validated_rules = self.gather_rules_from_ui()
            self.engine.validate_financial_rules_model(validated_rules)

            self.engine.save_financial_rules_document(
                self.current_filepath,
                validated_rules,
                original_doc=self.original_doc,
            )
            self.active_rules = validated_rules
            self._set_status(
                f"✓ Saved financial rules to '{Path(self.current_filepath).name}'.",
                is_error=False,
            )

            if self.app_state is not None:
                self.app_state.set_active_rules(self.current_filepath, source=self)
            if self.on_rules_saved is not None:
                self.on_rules_saved(self.current_filepath)
            return True
        except ValidationError as ve:
            err = ve.errors()[0]
            loc = " ➔ ".join(str(p) for p in err["loc"])
            self._set_status(
                f"✗ Cannot save: Validation Error at [{loc}]: {err['msg']}", is_error=True
            )
            return False
        except Exception as exc:
            self._set_status(f"✗ Cannot save: {exc}", is_error=True)
            return False

    def _on_save(self) -> None:
        """Validate and atomically persist financial rules to current file."""
        if not self.current_filepath:
            self._on_save_as()
            return
        self.save_rules()

    def _on_save_as(self) -> None:
        """Prompt user for target destination and save rules as a new profile."""
        chosen = filedialog.asksaveasfilename(
            title="Save Financial Rules As",
            defaultextension=".toml",
            filetypes=[("TOML Files", "*.toml"), ("All Files", "*.*")],
        )
        if not chosen:
            return

        try:
            payload = self._collect_ui_payload()
            validated_rules = FinancialRules.model_validate(payload)
            self.engine.validate_financial_rules_model(validated_rules)

            self.engine.save_financial_rules_document_as(
                chosen,
                validated_rules,
                source_filepath=self.current_filepath
                if os.path.isfile(self.current_filepath)
                else None,
            )
            self.current_filepath = chosen
            self.active_rules = validated_rules

            recents = self.engine.get_recent_rules()
            self.rules_combo.configure(values=recents)
            self.rules_path_var.set(chosen)

            self._set_status(
                f"✓ Saved as new rules profile: '{Path(chosen).name}'.", is_error=False
            )
            if self.app_state is not None:
                self.app_state.set_active_rules(chosen, source=self)
            if self.on_rules_saved is not None:
                self.on_rules_saved(chosen)
        except Exception as exc:
            self._set_status(f"✗ Save As Failed: {exc}", is_error=True)

    def _on_browse_file(self) -> None:
        """Open file dialog to choose an existing financial rules TOML file."""
        chosen = filedialog.askopenfilename(
            title="Open Financial Rules Configuration",
            filetypes=[("TOML Files", "*.toml"), ("All Files", "*.*")],
        )
        if chosen:
            self.load_rules(chosen, notify_state=True)

    def _on_reload(self) -> None:
        """Reload configuration from disk."""
        if self.current_filepath and os.path.isfile(self.current_filepath):
            self.load_rules(self.current_filepath, notify_state=False)

    def _on_rules_combo_selected(self, chosen: str) -> None:
        """Handle selection of a different rules file from the dropdown."""
        if chosen and os.path.isfile(chosen) and chosen != self.current_filepath:
            self.load_rules(chosen, notify_state=True)

    def _on_external_rules_changed(self, new_path: str, source: Any) -> None:
        """Handle rules path changes triggered by other tabs via AppState."""
        if source is self:
            return
        if new_path and os.path.isfile(new_path) and new_path != self.current_filepath:
            self.load_rules(new_path, notify_state=False)

    def _set_status(self, message: str, is_error: bool = False) -> None:
        """Update status notification banner."""
        if is_error:
            self.status_banner.configure(fg_color="#361014", border_color="#7F1D1D")
            self.status_label.configure(text=message, text_color="#F87171")
        else:
            self.status_banner.configure(fg_color="#062817", border_color="#166534")
            self.status_label.configure(text=message, text_color="#4ADE80")
