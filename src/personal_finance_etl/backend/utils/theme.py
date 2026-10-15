"""Legacy theme shim delegating to presentation.desktop.theme.

Preserves 100% backward compatibility for Color, LogTag, LOG_TAG_COLORS, and ExportMode.
"""

from personal_finance_etl.presentation.desktop.theme import (
    LOG_TAG_COLORS,
    Color,
    ExportMode,
    LogTag,
)

__all__ = ["LOG_TAG_COLORS", "Color", "ExportMode", "LogTag"]
