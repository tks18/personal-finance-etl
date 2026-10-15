"""Pass-through delegation shim for control plane package exports.

Superseded by personal_finance_etl.infrastructure.control_plane.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane

__all__ = [
    "ControlPlane",
]
