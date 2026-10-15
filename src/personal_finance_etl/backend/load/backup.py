"""Pass-through delegation shim for system backup manager and recovery contracts.

Superseded by personal_finance_etl.infrastructure.recovery.backup and
personal_finance_etl.contracts.recovery.
"""

from __future__ import annotations

from personal_finance_etl.contracts.recovery import (
    ActiveDatabaseState,
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager

__all__ = [
    "ActiveDatabaseState",
    "RestoreOutcome",
    "RestoreResult",
    "SnapshotOutcome",
    "SnapshotResult",
    "SystemBackupManager",
]
