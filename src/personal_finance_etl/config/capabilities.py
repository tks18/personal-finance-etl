"""Application capability selection configuration model.

Owns
----
- CapabilitySelection: Declarative capability selection model for execution settings.

Does not own
-------------
- CapabilityId vocabulary or graph logic (owned by contracts.capabilities).
- Evidence source models (owned by config.sources).
- Application runtime settings (owned by config.settings).
"""

from __future__ import annotations

from pydantic import BaseModel

from personal_finance_etl.contracts.capabilities import CapabilityId

__all__ = ["CapabilitySelection"]


class CapabilitySelection(BaseModel):
    """User-configured capability selection specification.

    Parameters
    ----------
    enabled : tuple[CapabilityId, ...] | None, default None
        Explicit list of requested financial execution capabilities.
        If None, all registered capabilities are requested by default.
    """

    enabled: tuple[CapabilityId, ...] | None = None

    @property
    def resolved_capabilities(self) -> frozenset[CapabilityId]:
        """Resolve requested capabilities to a set of CapabilityId enums.

        Returns
        -------
        frozenset[CapabilityId]
            Requested capabilities, or all registered capabilities if not explicitly configured.
        """
        if self.enabled is not None:
            return frozenset(self.enabled)
        return frozenset(CapabilityId)
