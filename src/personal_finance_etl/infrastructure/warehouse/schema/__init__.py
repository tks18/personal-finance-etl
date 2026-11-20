"""Declarative warehouse DDL and schema catalogs.

Owns
----
- Declarative DDL statements for Pre-Bronze, Bronze, Silver, Gold, and Meta tables.
- Database pragmas and index definitions.
- Control plane schema catalog.

Does not own
-------------
- Connection lifecycle (owned by infrastructure.warehouse.connection).
- Runtime table data insertions (owned by layer persistence modules).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.bronze import (
    BRONZE_DDL,
    generate_bronze_ddl,
)
from personal_finance_etl.infrastructure.warehouse.schema.control_plane import RAW_DDL
from personal_finance_etl.infrastructure.warehouse.schema.gold import (
    GOLD_DDL,
    generate_gold_ddl,
)
from personal_finance_etl.infrastructure.warehouse.schema.meta import META_DDL
from personal_finance_etl.infrastructure.warehouse.schema.pragmas import SQLITE_PRAGMAS
from personal_finance_etl.infrastructure.warehouse.schema.pre_bronze import (
    PRE_BRONZE_DDL,
    generate_pre_bronze_ddl,
)
from personal_finance_etl.infrastructure.warehouse.schema.silver import (
    SILVER_DDL,
    generate_silver_ddl,
)

__all__ = [
    "BRONZE_DDL",
    "GOLD_DDL",
    "META_DDL",
    "PRE_BRONZE_DDL",
    "RAW_DDL",
    "SILVER_DDL",
    "SQLITE_PRAGMAS",
    "generate_bronze_ddl",
    "generate_gold_ddl",
    "generate_pre_bronze_ddl",
    "generate_silver_ddl",
]
