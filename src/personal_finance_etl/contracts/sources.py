"""Authoritative source identity and provider contracts.

Owns
----
- SourceId: Validated immutable identifier for physical evidence sources.
- SourceBindingId: Validated immutable identifier for configured physical tabular streams.
- CanonicalRouteId: Validated immutable identifier for routes within a source binding.
- CanonicalRouteRef: Immutable value object referencing a specific route within a binding.
- ProviderType: Closed vocabulary of supported external source provider types.
- validate_source_id: Deterministic validation for source identifier strings.
- validate_source_binding_id: Deterministic validation for source binding identifier strings.
- validate_canonical_route_id: Deterministic validation for canonical route identifier strings.

Does not own
------------
- Physical extraction implementations (owned by infrastructure.providers).
- Dataset selectors or source dataset bindings (owned by config.sources).
- Pydantic configuration models (owned by config.sources.model and config.sources.binding_model).
- Canonical production planning (owned by contracts.canonical_plans).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

__all__ = [
    "CanonicalRouteId",
    "CanonicalRouteRef",
    "ProviderType",
    "SourceBindingId",
    "SourceId",
    "validate_canonical_route_id",
    "validate_source_binding_id",
    "validate_source_id",
]

SourceId = NewType("SourceId", str)
SourceBindingId = NewType("SourceBindingId", str)
CanonicalRouteId = NewType("CanonicalRouteId", str)


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


def validate_source_binding_id(value: object) -> SourceBindingId:
    """Validate and return a SourceBindingId instance.

    Parameters
    ----------
    value : object
        Raw source binding identifier candidate.

    Returns
    -------
    SourceBindingId
        Validated source binding identifier instance.

    Raises
    ------
    TypeError
        If value is not a string.
    ValueError
        If value is empty, whitespace, or contains filesystem path separators.
    """
    if not isinstance(value, str):
        raise TypeError(f"SourceBindingId must be a string, got {type(value).__name__}")
    val = value.strip()
    if not val:
        raise ValueError("SourceBindingId cannot be empty or whitespace.")
    if "/" in val or "\\" in val:
        raise ValueError(f"SourceBindingId cannot contain path separators: {val}")
    return SourceBindingId(val)


def validate_canonical_route_id(value: object) -> CanonicalRouteId:
    """Validate and return a CanonicalRouteId instance.

    Parameters
    ----------
    value : object
        Raw canonical route identifier candidate.

    Returns
    -------
    CanonicalRouteId
        Validated canonical route identifier instance.

    Raises
    ------
    TypeError
        If value is not a string.
    ValueError
        If value is empty, whitespace, or contains filesystem path separators.
    """
    if not isinstance(value, str):
        raise TypeError(f"CanonicalRouteId must be a string, got {type(value).__name__}")
    val = value.strip()
    if not val:
        raise ValueError("CanonicalRouteId cannot be empty or whitespace.")
    if "/" in val or "\\" in val:
        raise ValueError(f"CanonicalRouteId cannot contain path separators: {val}")
    return CanonicalRouteId(val)


@dataclass(frozen=True, slots=True)
class CanonicalRouteRef:
    """Immutable reference to a specific route within a source binding.

    Parameters
    ----------
    binding_id : SourceBindingId
        Logical identifier of the owning source binding.
    route_id : CanonicalRouteId
        Logical route identifier within the binding.
    """

    binding_id: SourceBindingId
    route_id: CanonicalRouteId

    def to_string(self) -> str:
        """Format the route reference as a colon-delimited string 'binding_id:route_id'."""
        return f"{self.binding_id}:{self.route_id}"

    @classmethod
    def from_string(cls, value: object) -> CanonicalRouteRef:
        """Parse a colon-delimited string into a CanonicalRouteRef instance.

        Parameters
        ----------
        value : object
            Candidate string formatted as 'binding_id:route_id'.

        Returns
        -------
        CanonicalRouteRef
            Parsed CanonicalRouteRef instance.

        Raises
        ------
        TypeError
            If value is not a string.
        ValueError
            If value is not in 'binding_id:route_id' format or either part is empty.
        """
        if not isinstance(value, str):
            raise TypeError(f"CanonicalRouteRef string must be a str, got {type(value).__name__}")
        parts = value.strip().split(":", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValueError(
                f"Invalid CanonicalRouteRef string '{value}'. Expected 'binding_id:route_id'."
            )
        return cls(
            binding_id=validate_source_binding_id(parts[0]),
            route_id=validate_canonical_route_id(parts[1]),
        )


class ProviderType(StrEnum):
    """Closed vocabulary of supported external evidence source provider types."""

    CSV = "csv"
    EXCEL = "excel"
    SQLITE = "sqlite"
    MARKET_DATA = "market_data"

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
