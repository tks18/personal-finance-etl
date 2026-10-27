"""Declarative SQLite Control Plane DDL schemas (re-exported).

Owns
----
- Re-export of RAW_DDL schema definitions.

Does not own
-------------
- Database connection lifecycle or driver pooling (owned by infrastructure.control_plane.connection).
- Repository query, persistence, or serialization behaviors (owned by infrastructure.control_plane.*_repository).
- Schema migrations, catalog synchronization, or pipeline orchestration (owned by application.pipeline).
- Operational business logic or analytical domain calculations (owned by domain).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.schema import RAW_DDL

__all__ = ["RAW_DDL"]
