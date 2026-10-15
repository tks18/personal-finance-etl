"""Legacy desktop package shim delegating to presentation.desktop."""

from personal_finance_etl.presentation.desktop import (
    LOG_TAG_COLORS,
    BaseEngineTab,
    Color,
    DesktopApp,
    ExportMode,
    LogTag,
    UnifiedETLTab,
)

__all__ = [
    "LOG_TAG_COLORS",
    "BaseEngineTab",
    "Color",
    "DesktopApp",
    "ExportMode",
    "LogTag",
    "UnifiedETLTab",
]
