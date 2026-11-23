# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false
"""Unit test suite for CustomTkinter Settings Editor and TOML store.

Owns
----
- Round-trip configuration save equality tests.
- Comment, trivia, and ordering preservation tests across updates.
- Atomic write and corrupted edit rollback protection tests.
- Save-As configuration profile cloning tests.
- UI ConfigFieldEditor widget casting and SettingsTab integration tests.

Does not own
-------------
- Financial domain calculation assertions (owned by test_*_golden.py).
- End-to-end multi-process pipeline execution (owned by test_pipeline_e2e.py).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.settings import HashPolicy, Settings
from personal_finance_etl.infrastructure.configuration.toml_store import TomlSettingsStore
from personal_finance_etl.presentation.desktop.config_editor import ConfigFieldEditor
from personal_finance_etl.presentation.desktop.run_tab import RunTab
from personal_finance_etl.presentation.desktop.settings_tab import SettingsTab
from personal_finance_etl.presentation.desktop.state import AppState


def test_round_trip_save_equality(tmp_path: Path, test_config_path: Path) -> None:
    """Verify that saving and reloading an existing configuration preserves all values."""
    store = TomlSettingsStore()
    settings, doc = store.load_document(test_config_path)

    out_file = tmp_path / "roundtrip.toml"
    store.save_document(out_file, settings, original_doc=doc)

    reloaded = Settings.from_toml(out_file)
    assert reloaded.model_dump() == settings.model_dump()


def test_comment_and_ordering_preservation(tmp_path: Path) -> None:
    """Verify that user comments and section ordering in TOML files are preserved on save."""
    sample_toml = """# File Header Comment
[database]
# Target database base path comment
target_db_base_path = "data/db"
target_db_name = "Personal_Finance_DB.duckdb"

[performance]
# Parallelism settings comment
market_workers = 8 # Inline comment on market workers
isin_workers = 4
duckdb_threads = 4
"""
    source_file = tmp_path / "config_with_comments.toml"
    source_file.write_text(sample_toml, encoding="utf-8")

    store = TomlSettingsStore()
    settings, doc = store.load_document(source_file)

    # Mutate performance setting
    settings.performance.market_workers = 16

    store.save_document(source_file, settings, original_doc=doc)

    saved_text = source_file.read_text(encoding="utf-8")
    assert "# File Header Comment" in saved_text
    assert "# Target database base path comment" in saved_text
    assert "# Parallelism settings comment" in saved_text
    assert "market_workers = 16" in saved_text

    reloaded = Settings.from_toml(source_file)
    assert reloaded.performance.market_workers == 16


def test_invalid_edit_protection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that if verification reload fails, original file is untouched and no tmp files linger."""
    sample_toml = """[database]
target_db_base_path = "valid/path"
target_db_name = "db.duckdb"
"""
    target_file = tmp_path / "safe.toml"
    target_file.write_text(sample_toml, encoding="utf-8")
    original_mtime = target_file.stat().st_mtime_ns

    store = TomlSettingsStore()
    settings, doc = store.load_document(target_file)

    # Simulate verification failure during save reload
    def _failing_from_toml(path: Any) -> Settings:
        raise ValueError("Simulated corrupt reload")

    monkeypatch.setattr(Settings, "from_toml", _failing_from_toml)

    with pytest.raises(ValueError, match="Simulated corrupt reload"):
        store.save_document(target_file, settings, original_doc=doc)

    # Assert original file untouched
    assert target_file.read_text(encoding="utf-8") == sample_toml
    assert target_file.stat().st_mtime_ns == original_mtime

    # Assert no lingering temporary files
    lingering = list(tmp_path.glob("*.tmp*"))
    assert len(lingering) == 0


def test_save_as_profile_creation(
    tmp_path: Path, test_config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cloning an existing configuration profile to a new destination."""
    monkeypatch.setenv("APPDATA", str(tmp_path))

    engine = PersonalFinanceEngine()
    settings, _ = engine.load_settings_document(str(test_config_path))
    settings.performance.market_workers = 12

    dest_file = tmp_path / "profiles" / "custom_profile.toml"
    engine.save_settings_document_as(
        str(dest_file), settings, source_filepath=str(test_config_path)
    )

    assert dest_file.is_file()
    reloaded = Settings.from_toml(dest_file)
    assert reloaded.performance.market_workers == 12

    recents = engine.get_recent_configs()
    assert str(dest_file) in recents


def test_config_field_editor_widgets(tk_root: Any) -> None:
    """Verify ConfigFieldEditor properly renders and casts values across schema types."""
    container = ctk.CTkFrame(tk_root)
    container.pack()

    # Switch editor
    bool_field = Settings.model_fields["database"].annotation.model_fields["disable_file_discoverer"]  # type: ignore[union-attr]
    switch_editor = ConfigFieldEditor(container, "disable_file_discoverer", bool_field, False)
    assert switch_editor.get_value() is False
    switch_editor.set_value(True)
    assert switch_editor.get_value() is True

    # Int editor with steppers and validation
    int_field = Settings.model_fields["performance"].annotation.model_fields["market_workers"]  # type: ignore[union-attr]
    int_editor = ConfigFieldEditor(container, "market_workers", int_field, 8)
    assert int_editor.get_value() == 8
    int_editor.set_value(16)
    assert int_editor.get_value() == 16
    # Test stepper increment and decrement
    int_editor._increment_number()
    assert int_editor.get_value() == 17
    int_editor._decrement_number()
    assert int_editor.get_value() == 16
    # Test keystroke validator
    assert int_editor._validate_number_keystroke("24") is True
    assert int_editor._validate_number_keystroke("abc") is False
    # Test bounds clamping (max is 64)
    int_editor.set_value(100)
    int_editor._clamp_number_bounds()
    assert int_editor.get_value() == 64

    # Float editor
    float_field = Settings.model_fields["market_data"].annotation.model_fields["anomalous_drop_threshold"]  # type: ignore[union-attr]
    float_editor = ConfigFieldEditor(container, "anomalous_drop_threshold", float_field, -0.5)
    assert float_editor.get_value() == -0.5
    float_editor.set_value(-0.35)
    assert float_editor.get_value() == -0.35

    # Choice editor
    choice_field = Settings.model_fields["hash_policy"].annotation.model_fields["household_database"]  # type: ignore[union-attr]
    choice_editor = ConfigFieldEditor(container, "household_database", choice_field, HashPolicy.CONTENT)
    assert choice_editor.get_value() == "CONTENT"
    choice_editor.set_value("NONE")
    assert choice_editor.get_value() == "NONE"

    # List editor
    list_field = Settings.model_fields["statement_patterns"].annotation.model_fields["us_stock_transactions"]  # type: ignore[union-attr]
    list_editor = ConfigFieldEditor(container, "us_stock_transactions", list_field, ["Pattern A", "Pattern B"])
    assert list_editor.get_value() == ["Pattern A", "Pattern B"]
    list_editor.set_value(["New 1", "New 2"])
    assert list_editor.get_value() == ["New 1", "New 2"]

    # Path editor with live validation pill
    path_field = Settings.model_fields["sources"].annotation.model_fields["household_database"]  # type: ignore[union-attr]
    path_editor = ConfigFieldEditor(container, "household_database", path_field, "")
    assert "Required" in path_editor._path_pill.cget("text")
    path_editor.set_value("nonexistent_path_xyz")
    assert "Missing" in path_editor._path_pill.cget("text")
    path_editor.set_value(os.getcwd())
    assert "Found" in path_editor._path_pill.cget("text")

    container.destroy()


def test_settings_tab_gather_and_validate(tk_root: Any, tmp_path: Path, test_config_path: Path) -> None:
    """Verify SettingsTab gathers UI fields and handles validation."""
    engine = PersonalFinanceEngine()
    tab = SettingsTab(tk_root, engine=engine)
    tab.load_config(str(test_config_path))

    # Gather settings from UI
    gathered = tab.gather_settings_from_ui()
    assert isinstance(gathered, Settings)
    assert gathered.database.target_db_name == "Personal_Finance_DB.duckdb"

    # Validate paths on disk
    valid_paths = tab.validate_paths()
    assert valid_paths is True

    # Test Save As from Tab
    dest_path = tmp_path / "tab_saved.toml"
    tab.current_filepath = str(dest_path)
    tab.config_path_var.set(str(dest_path))
    saved = tab.save_config()
    assert saved is True
    assert dest_path.is_file()

    tab.destroy()


def test_app_state_and_tab_synchronization(
    tk_root: Any, tmp_path: Path, test_config_path: Path
) -> None:
    """Verify continuous two-way configuration synchronization between RunTab and SettingsTab."""
    engine = PersonalFinanceEngine()
    state = AppState(engine)

    run_tab = RunTab(tk_root, engine=engine, app_state=state)
    settings_tab = SettingsTab(tk_root, engine=engine, app_state=state)

    # 1. Update from RunTab
    run_tab.set_config_path(str(test_config_path))
    state.set_active_config(str(test_config_path), source=run_tab)

    assert state.active_config_path == str(test_config_path)
    assert settings_tab.current_filepath == str(test_config_path)
    assert settings_tab.config_path_var.get() == str(test_config_path)

    # 2. Update from SettingsTab
    dest = tmp_path / "synced_profile.toml"
    settings_tab.current_filepath = str(dest)
    settings_tab.config_path_var.set(str(dest))
    saved = settings_tab.save_config()

    assert saved is True
    assert state.active_config_path == str(dest)
    assert run_tab.config_path_var.get() == str(dest)

    run_tab.destroy()
    settings_tab.destroy()

