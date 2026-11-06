"""Authoritative source-to-canonical column mapping configuration models.

Owns
----
- ColumnMapping: Typed declaration of a source column to canonical Bronze column translation.
- dict_to_mapping_list: Helper converting a key-value dictionary to a list of ColumnMapping models.
- mapping_list_to_dict: Helper converting a list of ColumnMapping models to a key-value dictionary.

Does not own
-------------
- Normalization operations or transformations (owned by config.sources.normalization).
- Canonical Bronze field schema definitions (owned by contracts.canonical_fields).
- Mapping compilation or execution mechanics (owned by application.normalization).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

__all__ = [
    "ColumnMapping",
    "dict_to_mapping_list",
    "mapping_list_to_dict",
]


class ColumnMapping(BaseModel):
    """Declarative binding of a single source evidence column to a canonical Bronze column.

    Parameters
    ----------
    source_field : str
        Name of the column as it exists in the external physical source schema.
    canonical_field : str
        Target canonical field name defined by the canonical Bronze schema.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_field: str
    canonical_field: str

    @field_validator("source_field", "canonical_field")
    @classmethod
    def _validate_field_non_empty(cls, v: str) -> str:
        """Validate that field names are non-empty and free of extraneous whitespace.

        Parameters
        ----------
        v : str
            Candidate field name string.

        Returns
        -------
        str
            Trimmed field name string.

        Raises
        ------
        ValueError
            If the field name is empty or contains only whitespace.
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field names cannot be empty or whitespace only.")
        return trimmed


def dict_to_mapping_list(d: dict[str, str]) -> list[ColumnMapping]:
    """Convert a dictionary of source-to-canonical field names into a list of ColumnMapping models.

    Parameters
    ----------
    d : dict[str, str]
        Dictionary mapping raw source column names to canonical Bronze names.

    Returns
    -------
    list[ColumnMapping]
        List of validated ColumnMapping models.
    """
    return [ColumnMapping(source_field=src, canonical_field=target) for src, target in d.items()]


def mapping_list_to_dict(mappings: list[ColumnMapping]) -> dict[str, str]:
    """Convert a list of ColumnMapping models into a dictionary of source-to-canonical names.

    Parameters
    ----------
    mappings : list[ColumnMapping]
        List of ColumnMapping instances.

    Returns
    -------
    dict[str, str]
        Dictionary mapping source fields to canonical fields.
    """
    return {m.source_field: m.canonical_field for m in mappings}
