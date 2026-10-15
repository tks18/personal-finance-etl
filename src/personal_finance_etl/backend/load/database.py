"""Pass-through delegation shim for DuckDBManager.

Superseded by personal_finance_etl.infrastructure.warehouse.connection.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager

__all__ = ["DuckDBManager"]
