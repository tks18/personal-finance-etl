"""DEPRECATED - Legacy settings and preferences shim module.

This module has been deactivated as part of Phase 2 of the Grand Refactor.
Canonical models and repositories now reside in:
- `personal_finance_etl.config.settings` (Settings, FileHashPolicy)
- `personal_finance_etl.infrastructure.preferences` (PreferencesManager)

This file is maintained strictly as a backwards-compatible pass-through delegation shim.
Do not edit or add logic here.
"""

from personal_finance_etl.config.settings import FileHashPolicy, Settings
from personal_finance_etl.infrastructure.preferences.repository import PreferencesManager

__all__ = [
    "FileHashPolicy",
    "PreferencesManager",
    "Settings",
]
