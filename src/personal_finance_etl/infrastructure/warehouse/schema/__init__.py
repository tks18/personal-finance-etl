"""Declarative warehouse DDL and schema catalogs.

Owns
----
- Declarative DDL statements for Bronze, Silver, Gold, and Meta tables.
- Database pragmas and index definitions.
- Control plane schema catalog.

Does not own
-------------
- Connection lifecycle (owned by infrastructure.warehouse.connection).
- Runtime table data insertions (owned by layer persistence modules).
"""

