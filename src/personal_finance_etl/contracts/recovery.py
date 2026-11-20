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
    "ConfigChangeClass",
    "DatasetChangeDetail",
    "IdentityPolicyViolationError",
    "ReplayAction",
    "ReplayPlan",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
]


class ConfigChangeClass(StrEnum):
    """Categorical classification of source or runtime configuration deltas."""

    NO_CHANGE = "NO_CHANGE"
    SOURCE_METADATA = "SOURCE_METADATA"
    CHANGE_DETECTION = "CHANGE_DETECTION"
    MAPPING_SEMANTICS = "MAPPING_SEMANTICS"
    NORMALIZATION_SEMANTICS = "NORMALIZATION_SEMANTICS"
    IDENTITY_STRATEGY = "IDENTITY_STRATEGY"
    CAPABILITY_SELECTION = "CAPABILITY_SELECTION"
    DATASET_STATE = "DATASET_STATE"
    FINANCIAL_RULES = "FINANCIAL_RULES"


class ReplayAction(StrEnum):
    """Actionable remediation directives derived from configuration change classification."""

    NO_REPLAY = "NO_REPLAY"
    REPLAY_AFFECTED_DATASETS = "REPLAY_AFFECTED_DATASETS"
    REQUIRE_IDENTITY_REBUILD = "REQUIRE_IDENTITY_REBUILD"
    PRUNE_DISABLED_DATASETS = "PRUNE_DISABLED_DATASETS"
    REBUILD_ANALYTICAL = "REBUILD_ANALYTICAL"


class IdentityPolicyViolationError(RuntimeError):
    """Raised when an identity strategy change is detected without explicit rebuild authorization."""

    def __init__(self, dataset_id: str, old_identity: str, new_identity: str) -> None:
        message = (
            f"Identity policy change detected for dataset '{dataset_id}'. "
            f"Old strategy: {old_identity} -> New strategy: {new_identity}. "
            "Silent incremental continuation is strictly prohibited as it mixes distinct identity generations. "
            "To authorize an explicit full dataset rebuild and identity migration, set allow_identity_rebuild=True."
        )
        super().__init__(message)
        self.dataset_id = dataset_id
        self.old_identity = old_identity
        self.new_identity = new_identity


@dataclass(frozen=True, slots=True)
class DatasetChangeDetail:
    """Semantic change detail for a single dataset across configuration revisions."""

    dataset_id: str
    change_class: ConfigChangeClass
    action: ReplayAction
    details: dict[str, str] = field(default_factory=lambda: dict[str, str]())


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    """Authoritative execution plan for pipeline recovery, replay, and migration."""

    overall_action: ReplayAction
    dataset_changes: list[DatasetChangeDetail] = field(
        default_factory=lambda: list[DatasetChangeDetail]()
    )
    affected_dataset_ids: list[str] = field(default_factory=lambda: list[str]())
    requires_identity_rebuild: bool = False
    requires_analytical_rebuild: bool = False
    blocked_reason: str | None = None

    @property
    def is_blocked(self) -> bool:
        """Return True if execution is blocked by an uncertified change policy."""
        return self.overall_action == ReplayAction.REQUIRE_IDENTITY_REBUILD or bool(
            self.blocked_reason
        )


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
