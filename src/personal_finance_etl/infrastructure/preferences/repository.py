"""Filesystem repository for user preferences and recent files.

Owns
----
- Reading and writing user preferences JSON under APPDATA or user home.
- Maintaining the LRU cache of recently opened configuration and rules files.
- Filtering nonexistent files when retrieving recent configurations.

Does not own
-------------
- Configuration model definitions (owned by config.settings).
- Presentation GUI state or event dispatch (owned by presentation.desktop).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import cast


class PreferencesManager:
    """Manages reading and writing application user preferences to disk.

    Parameters
    ----------
    prefs_path : str | None, optional
        Custom path to the preferences JSON file. If None, resolves to
        `%APPDATA%/PersonalFinanceETL/prefs.json` or `~/.PersonalFinanceETL/prefs.json`.
    """

    def __init__(self, prefs_path: str | None = None) -> None:
        if prefs_path is not None:
            self.prefs_path = prefs_path
            os.makedirs(os.path.dirname(prefs_path) or ".", exist_ok=True)
            return

        app_data = os.getenv("APPDATA")
        if not app_data:
            app_data = os.path.expanduser("~")

        prefs_dir = os.path.join(app_data, "PersonalFinanceETL")
        os.makedirs(prefs_dir, exist_ok=True)
        self.prefs_path = os.path.join(prefs_dir, "prefs.json")

    def _read_data(self) -> dict[str, object]:
        """Safely load JSON preferences from disk."""
        if not os.path.exists(self.prefs_path):
            return {}
        try:
            with open(self.prefs_path, encoding="utf-8") as f:
                content = json.load(f)
                return cast("dict[str, object]", content) if isinstance(content, dict) else {}
        except Exception:
            return {}

    def _write_data(self, data: Mapping[str, object]) -> None:
        """Safely write JSON preferences to disk."""
        try:
            with open(self.prefs_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_recent_config(self, filepath: str) -> None:
        """Add a configuration path to the recent list in preferences.

        Parameters
        ----------
        filepath : str
            Absolute or relative path to the configuration file.
        """
        recents = self.get_recent_configs()
        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)
        recents = recents[:10]

        data = self._read_data()
        data["recent_configs"] = recents
        self._write_data(data)

    def get_recent_configs(self) -> list[str]:
        """Return a list of recent configuration file paths that exist on disk.

        Returns
        -------
        list[str]
            List of existing file paths, sorted newest first, maximum 10 items.
        """
        data = self._read_data()
        raw = data.get("recent_configs", [])
        if not isinstance(raw, list):
            return []
        items = cast(list[object], raw)
        return [str(p) for p in items if isinstance(p, str) and os.path.exists(p)]

    def add_recent_rules(self, filepath: str) -> None:
        """Add a financial rules configuration path to the recent list.

        Parameters
        ----------
        filepath : str
            Absolute or relative path to the financial rules file.
        """
        recents = self.get_recent_rules()
        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)
        recents = recents[:10]

        data = self._read_data()
        data["recent_rules"] = recents
        self._write_data(data)

    def get_recent_rules(self) -> list[str]:
        """Return a list of recent financial rules file paths that exist on disk.

        Returns
        -------
        list[str]
            List of existing file paths, sorted newest first, maximum 10 items.
        """
        data = self._read_data()
        raw = data.get("recent_rules", [])
        if not isinstance(raw, list):
            return []
        items = cast(list[object], raw)
        return [str(p) for p in items if isinstance(p, str) and os.path.exists(p)]
