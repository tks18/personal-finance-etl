from __future__ import annotations

import os
from typing import Any

from filelock import FileLock, Timeout

from personal_finance_etl.backend.load.control_plane.artifact_repo import ArtifactRepository
from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager
from personal_finance_etl.backend.load.control_plane.file_sync import FileSyncService
from personal_finance_etl.backend.load.control_plane.run_repo import RunRepository


class ControlPlane:
    """Authoritative lifecycle wrapper for the SQLite ETL control plane."""

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
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
        try:
            self.db.close()
        finally:
            if self._lock_acquired:
                self._lock.release()
                self._lock_acquired = False
            self.active_run_id = None

    def ensure_schema(self) -> None:
        self.db.ensure_schema()
        self.runs.recover_stale_runs()

    def begin_transaction(self) -> None:
        self.db.begin_transaction()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
