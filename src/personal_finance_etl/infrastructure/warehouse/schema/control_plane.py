"""Declarative SQLite Control Plane DDL schemas (re-exported).

Owns
----
- Re-export of RAW_DDL for backward compatibility.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.schema import RAW_DDL

__all__ = ["RAW_DDL"]
