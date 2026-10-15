"""Legacy SQLite extractor shim.

DEACTIVATED: This module is superseded by infrastructure.providers.files.sqlite.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)

__all__ = ["SQLiteExtractor"]
