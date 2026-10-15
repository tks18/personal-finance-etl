"""Pass-through delegation shim for run repository.

Superseded by personal_finance_etl.infrastructure.control_plane.run_repository.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.run_repository import RunRepository

__all__ = ["RunRepository"]
