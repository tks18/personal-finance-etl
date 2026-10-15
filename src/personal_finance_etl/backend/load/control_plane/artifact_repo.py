"""Pass-through delegation shim for artifact repository.

Superseded by personal_finance_etl.infrastructure.control_plane.artifact_repository.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.artifact_repository import ArtifactRepository

__all__ = ["ArtifactRepository"]
