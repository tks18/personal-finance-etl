"""Pass-through delegation shim for Bronze DDL schema.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.bronze.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.bronze import BRONZE_DDL

__all__ = ["BRONZE_DDL"]
