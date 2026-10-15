"""Pass-through delegation shim for Silver DDL schema.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.silver.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

__all__ = ["SILVER_DDL"]
