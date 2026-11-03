"""Authoritative Bronze dataset row identity strategies.

Owns
----
- SourceFieldIdentity: Authoritative row identity supplied directly by a source column.
- CompositeIdentity: Natural composite multi-field row identity.
- DerivedDeterministicIdentity: Cryptographically derived deterministic SHA-256 row identity.
- BronzeIdentityStrategy: Discriminated union of all supported Bronze row identity strategies.
- Validation preventing empty fields, duplicate fields, and collision with protected financial namespaces.

Does not own
-------------
- Identity plan compilation or execution (owned by application.ingestion.identity).
- Downstream financial identity generation (owned by domain.common.identity and domain.*).
- Bronze contract definitions (owned by infrastructure.warehouse.contracts).
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

__all__ = [
    "BronzeIdentityStrategy",
    "CompositeIdentity",
    "DerivedDeterministicIdentity",
    "PROTECTED_FINANCIAL_NAMESPACES",
    "SourceFieldIdentity",
]

# Protected downstream financial namespaces that must never be hijacked by Bronze identity
PROTECTED_FINANCIAL_NAMESPACES: frozenset[str] = frozenset(
    {
        "PURCHASE",
        "SALE",
        "LOT",
        "REALIZED",
        "RECON_GROUP",
        "RECON_EVENT",
        "RECON_LOT_GROUP",
        "TAX",
    }
)


def _validate_field_name(field_name: str, context: str) -> str:
    """Validate that a field name is a non-empty, clean string."""
    clean = field_name.strip()
    if not clean:
        raise ValueError(f"{context} field name cannot be empty or whitespace.")
    return clean


class SourceFieldIdentity(BaseModel):
    """Row identity strategy referencing an authoritative unique ID supplied by the source.

    Parameters
    ----------
    strategy_type : Literal["source_field"], default "source_field"
        Discriminator identifying this strategy type.
    field : str
        Source column name containing the trusted unique row identifier.
    """

    strategy_type: Literal["source_field"] = "source_field"
    field: str

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        return _validate_field_name(v, "SourceFieldIdentity")


class CompositeIdentity(BaseModel):
    """Row identity strategy composed of multiple natural source fields.

    Parameters
    ----------
    strategy_type : Literal["composite"], default "composite"
        Discriminator identifying this strategy type.
    fields : list[str]
        Ordered collection of natural source fields forming the unique identity.
    """

    strategy_type: Literal["composite"] = "composite"
    fields: list[str]

    @field_validator("fields")
    @classmethod
    def _validate_fields(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("CompositeIdentity must specify at least one field.")
        clean_fields = [_validate_field_name(f, "CompositeIdentity") for f in v]
        if len(clean_fields) != len(set(clean_fields)):
            raise ValueError(f"CompositeIdentity fields contain duplicates: {clean_fields}")
        return clean_fields


class DerivedDeterministicIdentity(BaseModel):
    """Row identity strategy cryptographically derived from source/canonical fields.

    Parameters
    ----------
    strategy_type : Literal["derived_deterministic"], default "derived_deterministic"
        Discriminator identifying this strategy type.
    fields : list[str]
        Ordered collection of fields used as input for deterministic hashing.
    namespace : str | None, default None
        Optional custom namespace prefix. Must not collide with protected
        financial namespaces.
    version : str, default "v2"
        Canonical ID serialization version.
    """

    strategy_type: Literal["derived_deterministic"] = "derived_deterministic"
    fields: list[str]
    namespace: str | None = None
    version: str = "v2"

    @field_validator("fields")
    @classmethod
    def _validate_fields(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("DerivedDeterministicIdentity must specify at least one field.")
        clean_fields = [_validate_field_name(f, "DerivedDeterministicIdentity") for f in v]
        if len(clean_fields) != len(set(clean_fields)):
            raise ValueError(
                f"DerivedDeterministicIdentity fields contain duplicates: {clean_fields}"
            )
        return clean_fields

    @model_validator(mode="after")
    def _validate_namespace(self) -> Self:
        if self.namespace is not None:
            clean_ns = self.namespace.strip()
            if not clean_ns:
                raise ValueError("DerivedDeterministicIdentity namespace cannot be empty.")
            if clean_ns.upper() in PROTECTED_FINANCIAL_NAMESPACES:
                raise ValueError(
                    f"Namespace '{clean_ns}' collides with protected financial namespace "
                    f"({', '.join(sorted(PROTECTED_FINANCIAL_NAMESPACES))}). "
                    "Bronze row identity must not use downstream financial namespaces."
                )
            self.namespace = clean_ns
        return self


BronzeIdentityStrategy = Annotated[
    SourceFieldIdentity | CompositeIdentity | DerivedDeterministicIdentity,
    Field(discriminator="strategy_type"),
]
