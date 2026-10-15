"""Pass-through delegation shim for SQLite connection management.

Superseded by personal_finance_etl.infrastructure.control_plane.connection.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager

__all__ = ["SQLiteManager"]
