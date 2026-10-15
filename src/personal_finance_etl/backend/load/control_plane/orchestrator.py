"""Pass-through delegation shim for ControlPlane facade.

Superseded by personal_finance_etl.infrastructure.control_plane.facade.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane

__all__ = ["ControlPlane"]
