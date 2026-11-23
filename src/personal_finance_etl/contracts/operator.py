"""Architectural contracts for operator diagnostic inspection and telemetry.

Owns
----
- OperatorInspector protocol for read-only system and diagnostic telemetry.
- Typed immutable inspection result containers (StorageInspection, ControlPlaneInspection,
  ControlPlaneHealth, WarehouseHealth, WarehouseInventory).

Does not own
-------------
- Concrete inspection execution or database drivers (owned by infrastructure.operator).
- Application health analysis or doctor check evaluation (owned by application.operator).
- User presentation or rich formatting (owned by presentation.*).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "ControlPlaneHealth",
    "ControlPlaneInspection",
    "OperatorInspector",
    "StorageInspection",
    "WarehouseHealth",
    "WarehouseInventory",
]


@dataclass(frozen=True)
class StorageInspection:
    """Read-only inspection result for pipeline lock and storage file sizes."""

    lock_path: str
    is_locked: bool
    duckdb_exists: bool
    duckdb_size_bytes: int | None
    sqlite_exists: bool
    sqlite_size_bytes: int | None


@dataclass(frozen=True)
class ControlPlaneInspection:
    """Read-only inspection result for control plane run telemetry and sync summary."""

    latest_run_id: str | None
    latest_run_status: str | None
    latest_run_started_at: str | None
    latest_run_finished_at: str | None
    latest_sync_summary: dict[str, object] | None
    stale_runs_count: int
    recovery_required_count: int


@dataclass(frozen=True)
class ControlPlaneHealth:
    """Diagnostic health state of the SQLite control plane database."""

    base_dir_exists: bool
    file_exists: bool
    is_readable: bool
    table_names: set[str]
    error_message: str | None = None


@dataclass(frozen=True)
class WarehouseHealth:
    """Diagnostic health state of the DuckDB analytical warehouse."""

    file_exists: bool
    is_readable: bool
    schema_names: set[str]
    error_message: str | None = None


@dataclass(frozen=True)
class WarehouseInventory:
    """Physical contract table counts and schemas registered in the warehouse."""

    bronze_tables_count: int
    silver_tables_count: int
    gold_tables_count: int
    warehouse_schemas: list[str]


@runtime_checkable
class OperatorInspector(Protocol):
    """Protocol defining strictly read-only inspection operations."""

    def discover_config_path(self) -> str | None:
        """Discover default or recent configuration file path."""
        ...

    def discover_rules_path(self) -> str | None:
        """Discover default or recent financial rules file path."""
        ...

    def inspect_storage(
        self, base_path: str, duckdb_name: str, sqlite_name: str
    ) -> StorageInspection:
        """Inspect pipeline lock and database file health read-only."""
        ...

    def inspect_control_plane(self, sqlite_path: str) -> ControlPlaneInspection:
        """Query latest execution telemetry and sync summary from SQLite control plane."""
        ...

    def inspect_warehouse_inventory(self) -> WarehouseInventory:
        """Inspect registered warehouse contracts and active schema inventory."""
        ...

    def check_control_plane_health(self, base_dir: str, sqlite_name: str) -> ControlPlaneHealth:
        """Check SQLite control plane directory, database accessibility, and tables."""
        ...

    def check_warehouse_health(self, base_dir: str, duckdb_name: str) -> WarehouseHealth:
        """Check DuckDB warehouse file accessibility and canonical schemas."""
        ...

    def probe_market_data_provider(self, timeout: float = 2.5) -> bool:
        """Probe external market data provider connectivity without throwing."""
        ...
