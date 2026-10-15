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

