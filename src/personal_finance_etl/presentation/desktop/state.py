"""Observable desktop UI application state coordinating active configurations and paths.

Owns
----
- AppState: Central state container managing active configuration TOML path,
  active financial rules TOML path, operational state machine, and subscriber notifications.
- OperationState: Canonical operational status lifecycle enumeration.

Does not own
-------------
- Disk persistence (owned by application.facade and infrastructure).
- Tkinter widget layout (owned by presentation tabs).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from personal_finance_etl.application.facade import PersonalFinanceEngine

__all__ = ["AppState", "OperationState"]


class OperationState(StrEnum):
    """Lifecycle and operational state of the desktop application."""

    READY = "READY"
    PIPELINE_RUNNING = "PIPELINE_RUNNING"
    CHECKING = "CHECKING"
    SNAPSHOTTING = "SNAPSHOTTING"
    RESTORING = "RESTORING"
    ATTENTION = "ATTENTION"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    FAILED = "FAILED"


class AppState:
    """Central state manager for the desktop GUI."""

    def __init__(self, engine: PersonalFinanceEngine) -> None:
        self.engine = engine

        recents_cfg = self.engine.get_recent_configs()
        recents_rules = self.engine.get_recent_rules()

        self.active_config_path: str = recents_cfg[0] if recents_cfg else ""
        self.active_rules_path: str = recents_rules[0] if recents_rules else ""

        self.operation_state: OperationState = OperationState.READY
        self.operation_message: str = ""

        self._config_subscribers: list[Callable[[str, Any], None]] = []
        self._rules_subscribers: list[Callable[[str, Any], None]] = []
        self._operation_subscribers: list[Callable[[OperationState, str], None]] = []

    def subscribe_config(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked when active configuration path changes."""
        if callback not in self._config_subscribers:
            self._config_subscribers.append(callback)

    def subscribe_rules(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked when active financial rules path changes."""
        if callback not in self._rules_subscribers:
            self._rules_subscribers.append(callback)

    def subscribe_operation(self, callback: Callable[[OperationState, str], None]) -> None:
        """Register a callback invoked when operational lifecycle state changes."""
        if callback not in self._operation_subscribers:
            self._operation_subscribers.append(callback)

    def set_active_config(self, path: str, source: Any = None) -> None:
        """Update active configuration path and notify all subscribers."""
        if not path:
            return
        self.active_config_path = path
        self.engine.add_recent_config(path)
        for cb in list(self._config_subscribers):
            try:
                cb(path, source)
            except Exception:  # pylint: disable=broad-exception-caught
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
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def set_operation(self, state: OperationState, message: str = "") -> None:
        """Update active operational state and message, notifying all subscribers."""
        self.operation_state = state
        self.operation_message = message
        for cb in list(self._operation_subscribers):
            try:
                cb(state, message)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def is_busy(self) -> bool:
        """Whether a long-running exclusive operation is active."""
        return self.operation_state in (
            OperationState.PIPELINE_RUNNING,
            OperationState.SNAPSHOTTING,
            OperationState.RESTORING,
        )

    def can_run_pipeline(self) -> bool:
        """Whether a new pipeline execution can be triggered."""
        return not self.is_busy() and self.operation_state != OperationState.RECOVERY_REQUIRED

    def can_snapshot(self) -> bool:
        """Whether a database snapshot can be initiated."""
        return not self.is_busy()

    def can_restore(self) -> bool:
        """Whether a database backup restore can be initiated."""
        return not self.is_busy()

    def can_check_system(self) -> bool:
        """Whether system status or diagnostics checks can be initiated."""
        return self.operation_state not in (
            OperationState.PIPELINE_RUNNING,
            OperationState.SNAPSHOTTING,
            OperationState.RESTORING,
            OperationState.CHECKING,
        )
