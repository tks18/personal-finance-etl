"""Declarative DuckDB Pre-Bronze layer schema definitions.

Owns
----
- Pre-Bronze lakehouse table schema DDL comments and structure documentation.

Does not own
-------------
- Physical Pre-Bronze table synchronization (owned by infrastructure.warehouse.pre_bronze).
- Higher warehouse layers (owned by bronze.py, silver.py, gold.py, meta.py).
"""

from __future__ import annotations

PRE_BRONZE_DDL = """
-- Pre-Bronze schema DDL is source-shaped and managed dynamically by PreBronzeLayer.
-- When evidence files are extracted, tables are populated according to source shapes.
"""
