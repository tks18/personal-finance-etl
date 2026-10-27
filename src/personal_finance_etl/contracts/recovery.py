"""Recovery, snapshot, and restore typed contracts.

Owns
----
- SnapshotOutcome and RestoreOutcome categorical statuses.
- ActiveDatabaseState enum for post-restore inspection and safety guarantees.
- SnapshotResult and RestoreResult structured result containers.

Does not own
-------------
- Concrete zip archive mechanics (owned by infrastructure.recovery.backup).
- Database connection lifecycle (owned by infrastructure.warehouse/control_plane).
- High-level snapshot/restore application workflows (owned by application.recovery).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

__all__ = [
    "ActiveDatabaseState",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
]


class SnapshotOutcome(StrEnum):
    """Categorical outcome of a coordinated database snapshot archive operation."""

    SNAPSHOT_STARTED = "SNAPSHOT_STARTED"
    SNAPSHOT_VALIDATED = "SNAPSHOT_VALIDATED"
    SNAPSHOT_PUBLISHED = "SNAPSHOT_PUBLISHED"
    SNAPSHOT_FAILED = "SNAPSHOT_FAILED"


class RestoreOutcome(StrEnum):
    """Categorical outcome of a coordinated database restore operation."""

    RESTORE_VALIDATION_FAILED = "RESTORE_VALIDATION_FAILED"
    RESTORE_INSTALL_STARTED = "RESTORE_INSTALL_STARTED"
    RESTORE_SUCCEEDED = "RESTORE_SUCCEEDED"
    RESTORE_INSTALL_FAILED_ROLLED_BACK = "RESTORE_INSTALL_FAILED_ROLLED_BACK"
    RESTORE_STATE_UNCERTAIN = "RESTORE_STATE_UNCERTAIN"


class ActiveDatabaseState(StrEnum):
    """Verification state of the active database pair after a restore attempt."""

    PREVIOUS_PAIR_INTACT = "PREVIOUS_PAIR_INTACT"
    NEW_PAIR_INSTALLED = "NEW_PAIR_INSTALLED"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"


@dataclass
class SnapshotResult:
    """Structured result of a coordinated database snapshot archive operation."""

    outcome: SnapshotOutcome
    zip_path: str | None = None
    error_message: str | None = None
    archive_path: Path | str | None = None
    files_archived: list[str] = field(default_factory=lambda: list[str]())
    archive_size_bytes: int = 0

    @property
    def is_success(self) -> bool:
        """Return True if the snapshot archive completed and was published successfully."""
        return self.outcome == SnapshotOutcome.SNAPSHOT_PUBLISHED and (
            self.zip_path is not None
            or self.archive_path is not None
            or len(self.files_archived) > 0
        )

    def __bool__(self) -> bool:
        """Return True if the snapshot operation was successful."""
        return self.is_success

    def __str__(self) -> str:
        """Return human-readable string representation of the snapshot result."""
        return str(self.zip_path or self.archive_path or self.error_message or self.outcome.value)


@dataclass
class RestoreResult:
    """Structured result of a coordinated database restore operation."""

    outcome: RestoreOutcome
    active_database_state: ActiveDatabaseState = ActiveDatabaseState.NEW_PAIR_INSTALLED
    error_message: str | None = None
    source_archive: Path | str | None = None
    files_restored: list[str] = field(default_factory=lambda: list[str]())

    @property
    def is_success(self) -> bool:
        """Return True if the restore succeeded and the new database pair was installed."""
        return (
            self.outcome == RestoreOutcome.RESTORE_SUCCEEDED
            and self.active_database_state == ActiveDatabaseState.NEW_PAIR_INSTALLED
        )

    def __bool__(self) -> bool:
        """Return True if the restore operation was successful."""
        return self.is_success
