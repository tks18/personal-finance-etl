"""Pass-through delegation shim for schema package exports.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema import (
    BRONZE_DDL,
    GOLD_DDL,
    META_DDL,
    RAW_DDL,
    SILVER_DDL,
    SQLITE_PRAGMAS,
)

__all__ = [
    "BRONZE_DDL",
    "GOLD_DDL",
    "META_DDL",
    "RAW_DDL",
    "SILVER_DDL",
    "SQLITE_PRAGMAS",
]
