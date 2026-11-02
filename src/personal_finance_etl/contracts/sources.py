"""Authoritative source identity and provider contracts.

Owns
----
- SourceId: Validated immutable identifier for physical evidence sources.
- ProviderType: Closed vocabulary of supported external source provider types.
- validate_source_id: Deterministic validation for source identifier strings.

Does not own
------------
- Physical extraction implementations (owned by infrastructure.providers).
- Dataset selectors or source dataset bindings (owned by config.sources).
- Pydantic configuration models (owned by config.sources.model).
"""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

__all__ = ["ProviderType", "SourceId", "validate_source_id"]

SourceId = NewType("SourceId", str)


def validate_source_id(value: object) -> SourceId:
    """Validate and return a SourceId instance.

    Parameters
    ----------
    value : object
        Raw source identifier candidate.

    Returns
    -------
    SourceId
        Validated source identifier instance.

    Raises
    ------
    TypeError
        If value is not a string.
    ValueError
        If value is empty, whitespace, or contains filesystem path separators.
    """
    if not isinstance(value, str):
        raise TypeError(f"SourceId must be a string, got {type(value).__name__}")
    val = value.strip()
    if not val:
        raise ValueError("SourceId cannot be empty or whitespace.")
    if "/" in val or "\\" in val:
        raise ValueError(f"SourceId cannot contain path separators: {val}")
    return SourceId(val)


class ProviderType(StrEnum):
    """Closed vocabulary of supported external evidence source provider types."""

    CSV = "csv"
    EXCEL = "excel"
    SQLITE = "sqlite"

    @classmethod
    def _missing_(cls, value: object) -> ProviderType | None:
        """Resolve case-insensitive provider type strings.

        Parameters
        ----------
        value : object
            Input string representing a provider type.

        Returns
        -------
        ProviderType | None
            Matching ProviderType enum member if found, otherwise None.
        """
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower or member.name.lower() == val_lower:
                    return member
        return None
