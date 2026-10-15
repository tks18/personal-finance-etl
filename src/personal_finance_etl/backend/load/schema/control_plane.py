"""Pass-through delegation shim for Control Plane DDL schema.

Superseded by personal_finance_etl.infrastructure.warehouse.schema.control_plane.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.schema.control_plane import RAW_DDL

__all__ = ["RAW_DDL"]
