"""Concrete database backup and snapshot archive management.

Owns
----
- Physical snapshot zip/tar archive creation.
- Physical database file restoration from backup archives.
- File lock management and concurrency safety during backup/restore.

Does not own
-------------
- Recovery workflow policy or orchestration (owned by application.recovery).
- Control Plane run lifecycle updates (owned by infrastructure.control_plane).
"""

