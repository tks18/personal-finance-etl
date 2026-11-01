"""Authoritative physical evidence source configuration models.

Owns
----
- SourceConfig: User-authored declarative evidence source configuration model.

Does not own
------------
- SourceId and ProviderType cross-boundary contract definitions (owned by contracts.sources).
- Root settings or financial rules models (owned by config.settings and config.financial_rules).
- Physical provider extraction mechanics (owned by infrastructure.providers).
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, field_validator, model_validator

from personal_finance_etl.contracts.sources import (
    ProviderType,
    SourceId,
    validate_source_id,
)

__all__ = ["SourceConfig"]


class SourceConfig(BaseModel):
    """User-authored physical evidence source configuration.

    Parameters
    ----------
    source_id : SourceId
        Stable logical identity for this evidence source.
    provider_type : ProviderType
        Physical extractor provider type (CSV, EXCEL, SQLITE).
    location : str
        Path-like or URI configuration value specifying file or folder location.
    enabled : bool, default True
        Operational toggle to enable or disable ingestion from this source.
    description : str | None, default None
        Optional human-readable documentation for this source.
    """

    source_id: SourceId
    provider_type: ProviderType
    location: str
    enabled: bool = True
    description: str | None = None

    @field_validator("source_id", mode="before")
    @classmethod
    def _validate_source_id(cls, v: object) -> SourceId:
        """Validate that source_id is a non-empty, path-independent identifier.

        Parameters
        ----------
        v : object
            Input source identifier candidate.

        Returns
        -------
        SourceId
            Validated SourceId instance.

        Raises
        ------
        TypeError
            If v is not a string.
        ValueError
            If v is empty, whitespace, or contains path separators.
        """
        if not isinstance(v, str):
            raise TypeError(f"SourceId must be a string, got {type(v).__name__}")
        return validate_source_id(v)

    @model_validator(mode="after")
    def validate_location_if_enabled(self) -> Self:
        """Ensure enabled sources have a non-empty location.

        Returns
        -------
        Self
            The validated SourceConfig instance.

        Raises
        ------
        ValueError
            If the source is enabled and the location is empty or whitespace.
        """
        if self.enabled and not self.location.strip():
            raise ValueError(
                f"Enabled source '{self.source_id}' must specify a non-empty location."
            )
        return self
