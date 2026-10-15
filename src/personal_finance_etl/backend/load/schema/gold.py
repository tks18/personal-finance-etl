"""Pass-through delegation shim for Gold DDL schema.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.gold.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL

__all__ = ["GOLD_DDL"]
