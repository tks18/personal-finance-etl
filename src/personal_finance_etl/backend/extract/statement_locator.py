"""Legacy statement locator shim.

DEACTIVATED: This module is superseded by infrastructure.providers.files.locator.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.files.locator import (
    categorize_statement_files,
)

__all__ = ["categorize_statement_files"]
