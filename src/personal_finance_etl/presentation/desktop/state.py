"""Observable desktop UI application state coordinating active configurations and paths.

Owns
----
- AppState: Central state container managing active configuration TOML path,
  active financial rules TOML path, and notifying subscriber views on mutations.

Does not own
-------------
- Disk persistence (owned by application.facade and infrastructure).
- Tkinter widget layout (owned by presentation tabs).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from personal_finance_etl.application.facade import PersonalFinanceEngine

__all__ = ["AppState"]


class AppState:
    """Central state manager for the desktop GUI."""

    def __init__(self, engine: PersonalFinanceEngine) -> None:
        self.engine = engine

        recents_cfg = self.engine.get_recent_configs()
        recents_rules = self.engine.get_recent_rules()

        self.active_config_path: str = recents_cfg[0] if recents_cfg else ""
        self.active_rules_path: str = recents_rules[0] if recents_rules else ""

        self._config_subscribers: list[Callable[[str, Any], None]] = []
        self._rules_subscribers: list[Callable[[str, Any], None]] = []

    def subscribe_config(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked when active configuration path changes."""
        if callback not in self._config_subscribers:
            self._config_subscribers.append(callback)

    def subscribe_rules(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked when active financial rules path changes."""
        if callback not in self._rules_subscribers:
            self._rules_subscribers.append(callback)

    def set_active_config(self, path: str, source: Any = None) -> None:
        """Update active configuration path and notify all subscribers."""
        if not path:
            return
        self.active_config_path = path
        self.engine.add_recent_config(path)
        for cb in list(self._config_subscribers):
            try:
                cb(path, source)
            except Exception:
                pass

    def set_active_rules(self, path: str, source: Any = None) -> None:
        """Update active financial rules path and notify all subscribers."""
        if not path:
            return
        self.active_rules_path = path
        self.engine.add_recent_rules(path)
        for cb in list(self._rules_subscribers):
            try:
                cb(path, source)
            except Exception:
                pass
