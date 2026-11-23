# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false
"""Unit test suite for CustomTkinter Financial Rules Editor, TOML store, and AppState sync.

Owns
----
- Round-trip financial rules save equality tests.
- Comment, trivia, and section ordering preservation tests across updates.
- Atomic persistence and validation rejection tests (tax overlaps, invalid ladders).
- Specialized widget tests (Matrix3x3Editor, Tuple3Editor, KeyValueDictEditor).
- Save-As financial rules profile creation and recents history tracking tests.
- FinancialRulesTab UI gathering, sub-tab switching, and AppState continuous two-way sync.

Does not own
-------------
- Settings TOML persistence (owned by test_settings_editor.py).
- Numerical end-to-end analytical pipeline tests (owned by test_*_golden.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.infrastructure.configuration.toml_store import TomlRulesStore
from personal_finance_etl.presentation.desktop.config_editor import (
    KeyValueDictEditor,
    ListEditorModal,
    Matrix3x3Editor,
    Tuple3Editor,
)
from personal_finance_etl.presentation.desktop.financial_rules_tab import (
    FinancialRulesTab,
    InvestmentInstrumentsEditor,
    TaxHeadSectionEditor,
)
from personal_finance_etl.presentation.desktop.run_tab import RunTab
from personal_finance_etl.presentation.desktop.state import AppState

FIXTURE_RULES_PATH = Path("tests/fixtures/financial_rules.toml").resolve()


def test_round_trip_save_equality(tmp_path: Path) -> None:
    """Verify that loading and re-saving an existing financial rules file preserves all values."""
    store = TomlRulesStore()
    rules, doc = store.load_document(FIXTURE_RULES_PATH)

    out_file = tmp_path / "roundtrip_rules.toml"
    store.save_document(out_file, rules, original_doc=doc)

    reloaded = FinancialRules.from_toml(out_file)
    assert reloaded.model_dump() == rules.model_dump()


def test_comment_and_structure_preservation(tmp_path: Path) -> None:
    """Verify that user comments and section headers are preserved during atomic save."""
    store = TomlRulesStore()
    rules, doc = store.load_document(FIXTURE_RULES_PATH)

    out_file = tmp_path / "comments_preserved_rules.toml"
    store.save_document(out_file, rules, original_doc=doc)

    content = out_file.read_text(encoding="utf-8")
    assert "# Mutual Fund Scheme Normalization Mappings" in content
    assert "# Income Classification Rules" in content
    assert "# Core / Essential Expenses" in content
    assert "# Statutory Tax Policy and Assumptions" in content
    assert 'DEFAULT_CURRENCY_ID = "INR_INR"' in content


def test_edit_nested_scalar_and_persistence(tmp_path: Path) -> None:
    """Verify modifying nested scalar parameters mutates data and persists correctly."""
    store = TomlRulesStore()
    rules, doc = store.load_document(FIXTURE_RULES_PATH)

    rules.portfolio_management.rebalance_tolerance_pct_points = 8.5
    rules.assumptions.fire.swr_multiplier = 32.0

    out_file = tmp_path / "edited_rules.toml"
    store.save_document(out_file, rules, original_doc=doc)

    reloaded = FinancialRules.from_toml(out_file)
    assert reloaded.portfolio_management.rebalance_tolerance_pct_points == 8.5
    assert reloaded.assumptions.fire.swr_multiplier == 32.0


def test_matrix_3x3_editor_component(tk_root: Any) -> None:
    """Verify Matrix3x3Editor parses rows, validates sum to 1.0, and reflects mutations."""
    container = ctk.CTkFrame(tk_root)
    container.pack()

    init_matrix = [
        [0.85, 0.12, 0.03],
        [0.45, 0.50, 0.05],
        [0.30, 0.10, 0.60],
    ]
    editor = Matrix3x3Editor(container, initial_matrix=init_matrix)
    val = editor.get_value()
    assert val == init_matrix

    for badge in editor.sum_badges:
        assert badge.cget("text_color") == "#4ADE80"

    # Set new matrix
    new_matrix = [
        [0.70, 0.20, 0.10],
        [0.20, 0.60, 0.20],
        [0.10, 0.30, 0.60],
    ]
    editor.set_value(new_matrix)
    assert editor.get_value() == new_matrix
    for badge in editor.sum_badges:
        assert badge.cget("text_color") == "#4ADE80"

    # Unbalanced row
    editor.matrix_vars[0][0].set("0.500")
    assert "Σ = 0.800" in editor.sum_badges[0].cget("text")
    assert editor.sum_badges[0].cget("text_color") == "#F59E0B"

    container.destroy()


def test_tuple_3_editor_component(tk_root: Any) -> None:
    """Verify Tuple3Editor binds (drift, volatility, inflation) triples cleanly."""
    container = ctk.CTkFrame(tk_root)
    container.pack()

    t_editor = Tuple3Editor(container, "state_bull", initial_value=(0.18, 0.18, 0.05))
    assert t_editor.get_value() == (0.18, 0.18, 0.05)

    t_editor.set_value((0.12, 0.14, 0.03))
    assert t_editor.get_value() == (0.12, 0.14, 0.03)

    container.destroy()


def test_key_value_dict_editor_dynamic_rows(tk_root: Any) -> None:
    """Verify KeyValueDictEditor supports additions, deletions, filtering, and value retrieval."""
    container = ctk.CTkFrame(tk_root)
    container.pack()

    initial = {
        "Quant Tax Plan": "Quant ELSS Tax Saver",
        "Tata Digital": "Tata Digital India",
    }
    editor = KeyValueDictEditor(container, "MF Schemes", initial_dict=initial, value_type="str")
    assert editor.get_value() == initial

    # Add a row
    editor._add_row("HDFC Top 100", "HDFC Top 100 Large Cap")
    updated = editor.get_value()
    assert "HDFC Top 100" in updated
    assert updated["HDFC Top 100"] == "HDFC Top 100 Large Cap"

    # Remove a row
    first_row = editor.rows[0]
    editor._remove_row(first_row[2], first_row)
    after_del = editor.get_value()
    assert "Quant Tax Plan" not in after_del
    assert len(after_del) == 2

    container.destroy()


def test_target_allocations_sum_badge(tk_root: Any) -> None:
    """Verify KeyValueDictEditor with sum_to_one calculates live allocation percentage."""
    container = ctk.CTkFrame(tk_root)
    container.pack()

    initial = {"Stocks": 0.60, "Bonds": 0.40}
    editor = KeyValueDictEditor(
        container,
        "Target Allocations",
        initial_dict=initial,
        value_type="float",
        sum_to_one=True,
    )
    assert editor.sum_badge.cget("text") == "Total: 100.0%"
    assert editor.sum_badge.cget("text_color") == "#4ADE80"

    # Unbalance allocations
    editor.rows[0][1].set("0.30")
    assert editor.sum_badge.cget("text") == "Total: 70.0%"
    assert editor.sum_badge.cget("text_color") == "#F59E0B"

    container.destroy()


def test_validation_blocks_tax_overlap_before_write(tmp_path: Path) -> None:
    """Verify that overlapping income UID and credit UID raises ValidationError and blocks write."""
    rules = FinancialRules.from_toml(FIXTURE_RULES_PATH)
    overlap_uid = "CONFLICT-UID-1234"

    sub_head = rules.assumptions.tax.heads_of_income["Salary"].sub_heads["Base"]
    sub_head.sub_cat_ids.append(overlap_uid)
    sub_head.tax_credit_sub_cat_ids.append(overlap_uid)

    engine = PersonalFinanceEngine()
    with pytest.raises(ValidationError):
        engine.validate_financial_rules_model(rules)


def test_validation_blocks_invalid_ladder() -> None:
    """Verify that non-ascending or non-4-length maturity ladder raises ValidationError."""
    rules = FinancialRules.from_toml(FIXTURE_RULES_PATH)
    rules_dict = rules.model_dump()

    rules_dict["assumptions"]["tax"]["ltcg_maturity_ladder_days"] = [30, 20, 10]
    with pytest.raises(ValidationError):
        FinancialRules.model_validate(rules_dict)

    rules_dict["assumptions"]["tax"]["ltcg_maturity_ladder_days"] = [30, 90, 90, 365]
    with pytest.raises(ValidationError):
        FinancialRules.model_validate(rules_dict)


def test_save_as_profile_creation(tmp_path: Path) -> None:
    """Verify save_financial_rules_document_as clones structure and tracks recent rules."""
    engine = PersonalFinanceEngine()
    rules = FinancialRules.from_toml(FIXTURE_RULES_PATH)

    dest_file = tmp_path / "cloned_rules.toml"
    engine.save_financial_rules_document_as(
        str(dest_file),
        rules,
        source_filepath=str(FIXTURE_RULES_PATH),
    )

    assert dest_file.is_file()
    recents = engine.get_recent_rules()
    assert str(dest_file) in recents

    content = dest_file.read_text(encoding="utf-8")
    assert "# Mutual Fund Scheme Normalization Mappings" in content


def test_financial_rules_tab_gather_and_save(tk_root: Any, tmp_path: Path) -> None:
    """Verify FinancialRulesTab gathers fields from UI editors and saves atomically."""
    engine = PersonalFinanceEngine()
    tab = FinancialRulesTab(tk_root, engine=engine)
    tab.load_rules(str(FIXTURE_RULES_PATH))

    gathered = tab.gather_rules_from_ui()
    assert isinstance(gathered, FinancialRules)
    assert gathered.DEFAULT_CURRENCY_ID == "INR_INR"
    assert gathered.portfolio_management.rebalance_tolerance_pct_points == 5.0

    # Save to new destination
    out_file = tmp_path / "tab_saved_rules.toml"
    tab.current_filepath = str(out_file)
    tab.rules_path_var.set(str(out_file))

    success = tab.save_rules()
    assert success is True
    assert out_file.is_file()

    reloaded = FinancialRules.from_toml(out_file)
    assert reloaded.DEFAULT_CURRENCY_ID == "INR_INR"

    tab.destroy()


def test_app_state_and_rules_tab_synchronization(tk_root: Any, tmp_path: Path) -> None:
    """Verify continuous two-way rules path synchronization between RunTab and FinancialRulesTab."""
    engine = PersonalFinanceEngine()
    state = AppState(engine)

    run_tab = RunTab(tk_root, engine=engine, app_state=state)
    rules_tab = FinancialRulesTab(tk_root, engine=engine, app_state=state)

    # 1. Update from RunTab
    run_tab.rules_path_var.set(str(FIXTURE_RULES_PATH))
    state.set_active_rules(str(FIXTURE_RULES_PATH), source=run_tab)

    assert state.active_rules_path == str(FIXTURE_RULES_PATH)
    assert rules_tab.current_filepath == str(FIXTURE_RULES_PATH)
    assert rules_tab.rules_path_var.get() == str(FIXTURE_RULES_PATH)

    # 2. Update from FinancialRulesTab
    dest = tmp_path / "synced_rules.toml"
    rules_tab.current_filepath = str(dest)
    rules_tab.rules_path_var.set(str(dest))
    saved = rules_tab.save_rules()

    assert saved is True
    assert state.active_rules_path == str(dest)
    assert run_tab.rules_path_var.get() == str(dest)

    run_tab.destroy()
    rules_tab.destroy()


def test_list_editor_modal_dialog(tk_root: Any) -> None:
    """Verify ListEditorModal supports viewing, adding, multi-add, deleting, and applying."""
    applied_result: list[str] = []

    def on_apply(items: list[str]) -> None:
        nonlocal applied_result
        applied_result = list(items)

    modal = ListEditorModal(
        tk_root,
        field_name="category_ids",
        initial_items=["CAT_A", "CAT_B"],
        description="Category IDs test",
        unit_text="IDs",
        on_apply=on_apply,
    )

    assert modal.items == ["CAT_A", "CAT_B"]

    # Test single and bulk add
    modal.add_entry_var.set("CAT_C, CAT_D\nCAT_E")
    modal._on_add_clicked()
    assert modal.items == ["CAT_A", "CAT_B", "CAT_C", "CAT_D", "CAT_E"]

    # Test removal
    modal._remove_item("CAT_B")
    assert "CAT_B" not in modal.items

    # Apply changes
    modal._on_apply_clicked()
    assert applied_result == ["CAT_A", "CAT_C", "CAT_D", "CAT_E"]


def test_tax_head_section_editor_dynamic(tk_root: Any) -> None:
    """Verify TaxHeadSectionEditor allows adding, mutating, deleting heads and sub-heads."""
    from personal_finance_etl.config.financial_rules.tax import TaxSubHeadConfig

    container = ctk.CTkFrame(tk_root)
    container.pack()

    editor = TaxHeadSectionEditor(
        container,
        section_key="heads_of_income",
        section_title="Taxable Heads of Income",
        icon="💼",
    )

    # Add a tax head
    editor.add_head("Salary")
    assert "Salary" in editor.heads

    # Add a sub-head
    sub_cfg = TaxSubHeadConfig(
        tax_head_display_name="Salary",
        sub_head_display_name="Basic Salary",
        taxability="taxable",
        tax_method="ordinary_rate",
        cat_ids=["CAT_SALARY"],
        sub_cat_ids=["SUB_BASIC"],
        tax_credit_sub_cat_ids=["CRED_TDS"],
    )
    editor.add_sub_head("Salary", "Base", sub_cfg)
    assert "Base" in editor.heads["Salary"]["sub_heads"]

    val = editor.get_value()
    assert "Salary" in val
    assert "Base" in val["Salary"]["sub_heads"]
    base_info = val["Salary"]["sub_heads"]["Base"]
    assert base_info["tax_head_display_name"] == "Salary"
    assert base_info["sub_head_display_name"] == "Basic Salary"
    assert base_info["cat_ids"] == ["CAT_SALARY"]
    assert base_info["sub_cat_ids"] == ["SUB_BASIC"]

    # Delete sub-head
    editor.remove_sub_head("Salary", "Base")
    assert "Base" not in editor.heads["Salary"]["sub_heads"]

    # Delete head
    editor.remove_head("Salary")
    assert "Salary" not in editor.heads
    assert editor.get_value() == {}

    container.destroy()


def test_investment_instruments_editor_dynamic(tk_root: Any) -> None:
    """Verify InvestmentInstrumentsEditor supports adding, modifying, and deleting instruments."""
    from personal_finance_etl.config.financial_rules.investments import InvestmentInstrumentRules

    container = ctk.CTkFrame(tk_root)
    container.pack()

    init_data = {
        "Stocks": InvestmentInstrumentRules(category_ids=["EQUITY"], sub_category_ids=["LARGE_CAP"])
    }
    editor = InvestmentInstrumentsEditor(container, initial_instruments=init_data)
    assert "Stocks" in editor.instruments

    # Add new instrument
    editor.add_instrument("Gold", InvestmentInstrumentRules(category_ids=["COMMODITY"], sub_category_ids=[]))
    assert "Gold" in editor.instruments

    val = editor.get_value()
    assert "Stocks" in val
    assert "Gold" in val
    assert val["Stocks"]["category_ids"] == ["EQUITY"]

    # Delete an instrument
    editor.remove_instrument("Stocks")
    assert "Stocks" not in editor.instruments
    val_after = editor.get_value()
    assert "Stocks" not in val_after
    assert "Gold" in val_after

    container.destroy()


def test_lazy_subtab_loading_and_ensure_rules_loaded(tk_root: Any) -> None:
    """Verify FinancialRulesTab only renders active subtab on load and caches visited tabs."""
    engine = PersonalFinanceEngine()
    tab = FinancialRulesTab(tk_root, engine=engine)
    tab.load_rules(str(FIXTURE_RULES_PATH))

    # Initial load: only active subtab (household) is rendered
    assert "household" in tab._rendered_subtabs
    assert "tax" not in tab._rendered_subtabs
    assert "investments" not in tab._rendered_subtabs

    # Switching to tax renders tax and caches it
    tab.switch_subtab("tax")
    assert "tax" in tab._rendered_subtabs
    assert hasattr(tab, "taxable_heads_editor")

    # Switching back to household does not require re-render
    tab.switch_subtab("household")
    assert "household" in tab._rendered_subtabs

    # ensure_rules_loaded on same path is a no-op (preserves render cache)
    cached_set = set(tab._rendered_subtabs)
    tab.ensure_rules_loaded(str(FIXTURE_RULES_PATH))
    assert tab._rendered_subtabs == cached_set

    tab.destroy()

