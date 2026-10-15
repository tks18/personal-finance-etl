"""Theme definitions and UI styling tokens for Desktop GUI.

Owns
----
- Color palettes and hex codes for the CustomTkinter UI.
- Log tag text colors and console formatting tokens.
- ExportMode enumeration for report generation options.

Does not own
-------------
- Concrete Tkinter widget layouts or window dispatching (owned by base_tab and app).
- Terminal formatting or Rich markup (owned by presentation.cli.app).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["LOG_TAG_COLORS", "Color", "ExportMode", "LogTag"]


class Color(StrEnum):
    """Hex color palette tokens for CustomTkinter dark theme."""

    BG = "#0D1117"
    SIDEBAR = "#101624"
    HEADER = "#0D1117"
    BORDER = "#1E293B"
    ACCENT = "#3B82F6"
    ACC_HOV = "#2563EB"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    DIM = "#4B5563"
    TEXT = "#E2E8F0"
    LOG_BG = "#080C14"


class LogTag(StrEnum):
    """Hex color codes for tagged log line levels."""

    TS = "#3D5A80"
    INFO = "#7B93B0"
    STEP = "#60A5FA"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"


LOG_TAG_COLORS: dict[str, str] = {
    "ts": LogTag.TS.value,
    "info": LogTag.INFO.value,
    "step": LogTag.STEP.value,
    "success": LogTag.SUCCESS.value,
    "warning": LogTag.WARNING.value,
    "error": LogTag.ERROR.value,
}


class ExportMode(StrEnum):
    """Export mode options for generated presentations."""

    CONSOLIDATED = "consolidated"
    INDIVIDUAL = "individual"
