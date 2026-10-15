"""Pass-through delegation shim for Meta DDL schema.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.meta.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.meta import META_DDL

__all__ = ["META_DDL"]
