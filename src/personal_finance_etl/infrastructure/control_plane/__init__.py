"""Control Plane SQLite persistence and repositories.

Owns
----
- SQLite connection management and PRAGMA settings.
- RunRepository: execution lifecycle and run history persistence.
- ArtifactRepository: file sync records, hashes, and provenance persistence.
- FileSyncService: detecting file changes via SHA-256 and tracking sync status.
- ControlPlane infrastructure façade.

Does not own
-------------
- High-level application ETL orchestration (owned by application.pipeline).
- Analytics warehouse tables (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.artifact_repository import ArtifactRepository
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.file_sync import FileSyncService
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
    hash_bytes,
    normalize_path,
)
from personal_finance_etl.infrastructure.control_plane.run_repository import RunRepository

__all__ = [
    "FILE_TYPE_MAP",
    "ArtifactRepository",
    "ControlPlane",
    "FileSyncService",
    "RunRepository",
    "SQLiteManager",
    "compute_file_hash",
    "generate_file_id",
    "hash_bytes",
    "normalize_path",
]
