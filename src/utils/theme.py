"""
Theme definitions for the Investment Manager App.
Centralizes all color codes and UI tokens to maintain DRY principles.
"""

from enum import Enum


class Color(str, Enum):
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


class LogTag(str, Enum):
    TS = "#3D5A80"
    INFO = "#7B93B0"
    STEP = "#60A5FA"
    SUCCESS = "#22C55E"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"


LOG_TAG_COLORS = {
    "ts":      LogTag.TS.value,
    "info":    LogTag.INFO.value,
    "step":    LogTag.STEP.value,
    "success": LogTag.SUCCESS.value,
    "warning": LogTag.WARNING.value,
    "error":   LogTag.ERROR.value,
}
