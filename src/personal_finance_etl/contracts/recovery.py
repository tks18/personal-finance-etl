"""Recovery, snapshot, and restore contracts.

Owns
----
- SnapshotOutcome and RestoreOutcome categorical statuses.
- SnapshotResult and RestoreResult structured result containers.

Does not own
-------------
- Concrete tar/zip archive mechanics (owned by infrastructure.recovery).
- Database connection lifecycle (owned by infrastructure.warehouse/control_plane).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class SnapshotOutcome(StrEnum):
    """Categorical outcome of a database snapshot archive operation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RestoreOutcome(StrEnum):
    """Categorical outcome of a database restore operation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class SnapshotResult:
    """Structured result of a warehouse snapshot archive operation."""

    outcome: SnapshotOutcome
    archive_path: Path | None
    files_archived: list[str] = field(default_factory=lambda: list[str]())
    archive_hash: str | None = None
    archive_size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the snapshot archive completed successfully."""
        return self.outcome == SnapshotOutcome.SUCCESS


@dataclass(frozen=True)
class RestoreResult:
    """Structured result of a warehouse database restore operation."""

    outcome: RestoreOutcome
    source_archive: Path
    files_restored: list[str] = field(default_factory=lambda: list[str]())
    verification_hash: str | None = None
    restored_at: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the database restore completed successfully."""
        return self.outcome == RestoreOutcome.SUCCESS
