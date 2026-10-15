"""Control plane infrastructure facade and lifecycle wrapper.

Owns
----
- Unified facade encapsulating SQLite connection, run repo, artifact repo, and file sync.
- Inter-process file locking for the pipeline control plane (pipeline.lock).
- Atomic run ID propagation across control plane subsystems.
- Schema verification and crash recovery trigger upon startup.

Does not own
-------------
- Overall pipeline stage coordination (owned by application.pipeline.orchestrator).
- Analytical DuckDB warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import os
from typing import Any

from filelock import FileLock, Timeout

from personal_finance_etl.infrastructure.control_plane.artifact_repository import ArtifactRepository
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.file_sync import FileSyncService
from personal_finance_etl.infrastructure.control_plane.run_repository import RunRepository


class ControlPlane:
    """Authoritative lifecycle wrapper and facade for the SQLite ETL control plane.

    Parameters
    ----------
    base_path : str
        Base directory containing the SQLite database and lock files.
    db_name : str, default="Raw_Documents.sqlite"
        Database file name.
    """

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite") -> None:
        self.base_path = base_path
        self.db = SQLiteManager(base_path, db_name)
        self.artifacts = ArtifactRepository(self.db)
        self.runs = RunRepository(self.db)
        self.file_sync = FileSyncService(self.artifacts)
        self.lock_path = os.path.join(base_path or ".", "pipeline.lock")
        self._lock: Any = FileLock(self.lock_path)
        self._lock_acquired = False
        self._active_run_id: str | None = None

    @property
    def active_run_id(self) -> str | None:
        """Active run ID propagated across artifacts and file-sync services."""
        return self._active_run_id

    @active_run_id.setter
    def active_run_id(self, value: str | None) -> None:
        self._active_run_id = value
        self.artifacts.active_run_id = value
        self.file_sync.active_run_id = value

    def set_active_run_id(self, run_id: str | None) -> None:
        """Set the active run once and propagate it to every event-producing component."""
        self.active_run_id = run_id

    def open(self) -> None:
        """Acquire the process file lock and open the SQLite database connection.

        Raises
        ------
        RuntimeError
            If another pipeline instance already holds the lock.
        """
        if self._lock_acquired and self.db.is_open:
            return
        os.makedirs(self.base_path or ".", exist_ok=True)
        try:
            self._lock.acquire(timeout=0)
            self._lock_acquired = True
        except Timeout:
            raise RuntimeError(
                "Another instance of the production pipeline is currently running."
            ) from None
        try:
            self.db.open()
        except Exception:
            self._lock.release()
            self._lock_acquired = False
            raise

    def close(self) -> None:
        """Close SQLite database connection and release the process file lock."""
        try:
            self.db.close()
        finally:
            if self._lock_acquired:
                self._lock.release()
                self._lock_acquired = False
            self.active_run_id = None

    def ensure_schema(self) -> None:
        """Initialize database schema, apply migrations, and recover interrupted runs."""
        self.db.ensure_schema()
        self.runs.recover_stale_runs()

    def begin_transaction(self) -> None:
        """Begin an immediate SQLite transaction."""
        self.db.begin_transaction()

    def commit(self) -> None:
        """Commit the active SQLite transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Rollback the active SQLite transaction if one is open."""
        self.db.rollback()
