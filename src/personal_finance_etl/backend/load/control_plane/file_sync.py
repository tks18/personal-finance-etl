"""Pass-through delegation shim for file synchronization service.

Superseded by personal_finance_etl.infrastructure.control_plane.file_sync.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.file_sync import FileSyncService

__all__ = ["FileSyncService"]
