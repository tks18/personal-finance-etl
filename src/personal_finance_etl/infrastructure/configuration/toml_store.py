"""TOML storage and persistence preserving AST, comments, and structure.

Owns
----
- Reading TOML configuration and financial rules files into TOMLDocument AST.
- Validating loaded ASTs into Pydantic Settings and FinancialRules models.
- Atomic persistence with verification reload and fallback rollback.
- Merging in-memory mutations into TOMLDocument structures while preserving comments.

Does not own
-------------
- Pydantic schema validation rules (owned by config.settings and config.financial_rules).
- Presentation GUI state or event listeners (owned by presentation.desktop).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.toml_document import TOMLDocument

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings

__all__ = ["TomlRulesStore", "TomlSettingsStore"]


def _merge_dict_into_toml(target: Any, data: dict[str, Any]) -> None:
    """Recursively merge dictionary data into a tomlkit container or table.

    Prunes removed dictionary keys while preserving existing comments and ordering.
    """
    if hasattr(target, "keys"):
        for k in list(target.keys()):
            if k not in data:
                del target[k]

    for key, value in data.items():
        if isinstance(value, dict):
            if key not in target:
                target.add(key, tomlkit.table())
            _merge_dict_into_toml(target[key], cast("dict[str, Any]", value))
        elif isinstance(value, list):
            target[key] = value
        elif value is None:
            pass
        else:
            target[key] = value


class TomlSettingsStore:
    """Atomic file store for TOML Settings configuration documents."""

    def load_document(self, filepath: Path | str) -> tuple[Settings, TOMLDocument]:
        """Read a TOML configuration, parse with tomlkit, and validate into Settings.

        Parameters
        ----------
        filepath : Path | str
            Path to the TOML configuration file.

        Returns
        -------
        tuple[Settings, TOMLDocument]
            Loaded Settings instance and the underlying TOMLDocument AST.
        """
        path = Path(filepath).resolve()
        if not path.is_file():
            settings = Settings()
            doc = tomlkit.document()
            _merge_dict_into_toml(doc, settings.model_dump(mode="json"))
            return settings, doc

        text = path.read_text(encoding="utf-8")
        doc = tomlkit.parse(text)
        unwrapped = doc.unwrap()
        settings = Settings.model_validate(unwrapped)
        return settings, doc

    def save_document(
        self,
        filepath: Path | str,
        settings: Settings,
        original_doc: TOMLDocument | None = None,
    ) -> None:
        """Atomically persist validated Settings to disk while preserving comments and structure.

        Parameters
        ----------
        filepath : Path | str
            Target destination path.
        settings : Settings
            Validated settings instance to persist.
        original_doc : TOMLDocument | None
            Existing TOMLDocument AST to merge into for preserving comments. If None,
            a new document is constructed or read from filepath if it exists.
        """
        target_path = Path(filepath).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if original_doc is None:
            if target_path.is_file():
                doc = tomlkit.parse(target_path.read_text(encoding="utf-8"))
            else:
                doc = tomlkit.document()
        else:
            doc = original_doc

        data = settings.model_dump(mode="json")
        _merge_dict_into_toml(doc, data)

        tmp_path = target_path.with_name(f"{target_path.name}.tmp.{os.getpid()}")
        try:
            tmp_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

            # Verification: reload tmp file to verify syntactic and semantic validity
            reloaded_settings = Settings.from_toml(tmp_path)
            _ = reloaded_settings.database.target_db_name

            # Atomic replace
            os.replace(tmp_path, target_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise


class TomlRulesStore:
    """Atomic file store for TOML FinancialRules configuration documents."""

    def load_document(self, filepath: Path | str) -> tuple[FinancialRules, TOMLDocument]:
        """Read a TOML financial rules file, parse with tomlkit, and validate into FinancialRules.

        Parameters
        ----------
        filepath : Path | str
            Path to the financial rules TOML file.

        Returns
        -------
        tuple[FinancialRules, TOMLDocument]
            Loaded FinancialRules instance and the underlying TOMLDocument AST.
        """
        path = Path(filepath).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Financial rules config not found at {path}")

        text = path.read_text(encoding="utf-8")
        doc = tomlkit.parse(text)
        unwrapped = doc.unwrap()
        rules = FinancialRules.model_validate(unwrapped)
        return rules, doc

    def save_document(
        self,
        filepath: Path | str,
        rules: FinancialRules,
        original_doc: TOMLDocument | None = None,
    ) -> None:
        """Atomically persist validated FinancialRules to disk while preserving comments and structure.

        Parameters
        ----------
        filepath : Path | str
            Target destination path.
        rules : FinancialRules
            Validated FinancialRules instance to persist.
        original_doc : TOMLDocument | None
            Existing TOMLDocument AST to merge into for preserving comments. If None,
            a new document is constructed or read from filepath if it exists.
        """
        target_path = Path(filepath).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if original_doc is None:
            if target_path.is_file():
                doc = tomlkit.parse(target_path.read_text(encoding="utf-8"))
            else:
                doc = tomlkit.document()
        else:
            doc = original_doc

        data = rules.model_dump(mode="json")
        _merge_dict_into_toml(doc, data)

        tmp_path = target_path.with_name(f"{target_path.name}.tmp.{os.getpid()}")
        try:
            tmp_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

            # Verification: reload tmp file to verify syntactic and semantic validity
            reloaded_rules = FinancialRules.from_toml(tmp_path)
            _ = reloaded_rules.DEFAULT_CURRENCY_ID

            # Atomic replace
            os.replace(tmp_path, target_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
