"""Declarative DuckDB Bronze layer schema definitions.

Owns
----
- Bronze lakehouse table schema DDL comments and structure documentation.

Does not own
-------------
- Physical bronze table synchronization (owned by infrastructure.warehouse.bronze).
- Higher warehouse layers (owned by silver.py, gold.py, meta.py).
"""

from __future__ import annotations

BRONZE_DDL = """
-- Bronze schema DDL is fully dynamic and managed by the BronzeLayer.
-- When files are ingested, the tables are automatically created via CREATE TABLE AS SELECT.
"""
