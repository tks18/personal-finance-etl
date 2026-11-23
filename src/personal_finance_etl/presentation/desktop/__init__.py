"""Desktop Graphical User Interface (GUI) presentation.

Owns
----
- CustomTkinter window, application lifecycle, and views.
- Base tab abstraction, tabs, and interactive components.
- Theme management and UI styles.
- AppState cross-tab coordination.

Does not own
-------------
- Pipeline execution or multi-process queue consumers (delegates to application.facade).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.presentation.desktop.app import (
    DesktopApp,
    RunTab,
    SettingsTab,
    UnifiedETLTab,
)
from personal_finance_etl.presentation.desktop.base_tab import BaseEngineTab
from personal_finance_etl.presentation.desktop.config_editor import ConfigFieldEditor
from personal_finance_etl.presentation.desktop.state import AppState
from personal_finance_etl.presentation.desktop.theme import (
    LOG_TAG_COLORS,
    Color,
    ExportMode,
    LogTag,
)

__all__ = [
    "LOG_TAG_COLORS",
    "AppState",
    "BaseEngineTab",
    "Color",
    "ConfigFieldEditor",
    "DesktopApp",
    "ExportMode",
    "LogTag",
    "RunTab",
    "SettingsTab",
    "UnifiedETLTab",
]
