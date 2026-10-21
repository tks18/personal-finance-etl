"""Warehouse metadata projection and self-healing subsystem facade.

Owns
----
- MetaLayer: Manages DuckDB telemetry schemas, data contracts, and row count tracking.
- DuckDBRegistryHealer: Self-healing synchronization between SQLite Control Plane and DuckDB file registries.

Does not own
-------------
- Durable multi-run audit history (owned by control plane).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.meta.healing import (
    DuckDBRegistryHealer,
)
from personal_finance_etl.infrastructure.warehouse.meta.layer import MetaLayer

__all__ = ["DuckDBRegistryHealer", "MetaLayer"]
