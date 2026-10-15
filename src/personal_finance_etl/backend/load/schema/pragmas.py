"""Pass-through delegation shim for SQLite PRAGMAs.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.pragmas.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.pragmas import SQLITE_PRAGMAS

__all__ = ["SQLITE_PRAGMAS"]
