"""TOML storage and persistence preserving AST, comments, and structure.

Owns
----
- Reading TOML configuration files into TOMLDocument AST and Pydantic Settings models.
- Atomic persistence with verification reload and fallback rollback.
- Merging in-memory Settings mutations into TOMLDocument structures while preserving comments.

Does not own
-------------
- Pydantic schema validation rules (owned by config.settings).
- Presentation GUI state or event listeners (owned by presentation.desktop).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.toml_document import TOMLDocument

from personal_finance_etl.config.settings import Settings


class TomlSettingsStore:
    """Atomic file store for TOML configuration documents."""

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
            self._merge_into_doc(doc, settings.model_dump(mode="json"))
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
        self._merge_into_doc(doc, data)

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

    def _merge_into_doc(self, target: Any, data: dict[str, Any]) -> None:
        """Recursively merge dictionary data into a tomlkit container or table."""
        for key, value in data.items():
            if isinstance(value, dict):
                if key not in target:
                    target.add(key, tomlkit.table())
                self._merge_into_doc(target[key], cast("dict[str, Any]", value))
            elif isinstance(value, list):
                target[key] = value
            elif value is None:
                pass
            else:
                target[key] = value
