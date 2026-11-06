"""Authoritative bounded normalization rule models for source evidence ingestion.

Owns
----
- CanonicalDtype: Permitted scalar target data types for Bronze casting rules.
- CastRule: Casts a column to a bounded canonical data type.
- ParseDateRule: Parses a date string into a canonical date using explicit format directives.
- TrimRule: Strips leading, trailing, or bidirectional whitespace from strings.
- NormalizeCaseRule: Transforms string casing to upper, lower, or title case.
- ConstantRule: Injects or overrides a column with a constant scalar value.
- DefaultRule: Fills null values with a specified fallback scalar default.
- NormalizeNullRule: Converts recognized string null representations into null values.
- MapValuesRule: Replaces categorical source values using an explicit mapping table.
- NormalizationRule: Discriminated union of all bounded normalization operations.

Does not own
-------------
- Column rename mappings (owned by config.sources.mapping).
- Polars vectorized execution (owned by application.normalization.executor).
- Canonical Bronze field definitions (owned by contracts.canonical_fields).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CanonicalDtype",
    "CastRule",
    "ConstantRule",
    "DefaultRule",
    "MapValuesRule",
    "NormalizeCaseRule",
    "NormalizeNullRule",
    "NormalizationRule",
    "ParseDateRule",
    "TrimRule",
]

CanonicalDtype = Literal["string", "int64", "float64", "boolean", "date"]

DEFAULT_NULL_STRINGS: list[str] = [
    "",
    "null",
    "None",
    "NULL",
    "N/A",
    "nan",
    "NaN",
]


class _BaseFieldRule(BaseModel):
    """Base class providing field name validation for normalization rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        """Validate that the target field name is non-empty.

        Parameters
        ----------
        v : str
            Candidate column name.

        Returns
        -------
        str
            Trimmed column name.

        Raises
        ------
        ValueError
            If the field is empty or whitespace only.
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field name cannot be empty or whitespace only.")
        return trimmed


class CastRule(_BaseFieldRule):
    """Cast a column to a bounded canonical data type."""

    rule: Literal["cast"] = "cast"
    target_type: CanonicalDtype


class ParseDateRule(_BaseFieldRule):
    """Parse a date string into a canonical date using explicit format directives."""

    rule: Literal["parse_date"] = "parse_date"
    format: str | None = None
    strict: bool = True


class TrimRule(_BaseFieldRule):
    """Strip leading, trailing, or bidirectional whitespace from string columns."""

    rule: Literal["trim"] = "trim"
    mode: Literal["both", "left", "right"] = "both"


class NormalizeCaseRule(_BaseFieldRule):
    """Transform string column values to upper, lower, or title case."""

    rule: Literal["normalize_case"] = "normalize_case"
    case: Literal["upper", "lower", "title"] = "upper"


class ConstantRule(_BaseFieldRule):
    """Inject or override a column with a constant scalar value."""

    rule: Literal["constant"] = "constant"
    value: str | int | float | bool


class DefaultRule(_BaseFieldRule):
    """Fill null values in an existing column with a fallback scalar default."""

    rule: Literal["default"] = "default"
    value: str | int | float | bool


class NormalizeNullRule(_BaseFieldRule):
    """Convert recognized string representations of null into actual null values."""

    rule: Literal["normalize_null"] = "normalize_null"
    null_values: list[str] = Field(default_factory=lambda: list(DEFAULT_NULL_STRINGS))


class MapValuesRule(_BaseFieldRule):
    """Replace categorical source values using an explicit discrete mapping dictionary."""

    rule: Literal["map_values"] = "map_values"
    mapping: dict[str, str]
    default: str | None = None


NormalizationRule = Annotated[
    CastRule
    | ParseDateRule
    | TrimRule
    | NormalizeCaseRule
    | ConstantRule
    | DefaultRule
    | NormalizeNullRule
    | MapValuesRule,
    Field(discriminator="rule"),
]
