"""Authoritative bounded semantic interpretation and route predicate models.

Owns
----
- PredicateOperator: Closed enumeration of permissible row-local comparison operators.
- IncludeWhen: Declarative predicate rule keeping rows that satisfy a condition.
- ExcludeWhen: Declarative predicate rule discarding rows that satisfy a condition.
- PredicateRule: Discriminated union of all bounded route predicate operations.
- SemanticMapRule: Categorical mapping rule translating source values to canonical values.
- SemanticConstantRule: Scalar assignment rule injecting a canonical constant.
- SemanticRule: Discriminated union of all bounded semantic transformation operations.

Does not own
------------
- Representation normalization (owned by config.sources.normalization).
- Column rename mappings (owned by config.sources.mapping).
- Polars vectorized execution (owned by application.ingestion.route_executor).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

PredicateScalar = str | int | float | bool
PredicateValue = PredicateScalar | list[PredicateScalar] | tuple[PredicateScalar, ...] | None

__all__ = [
    "ExcludeWhen",
    "IncludeWhen",
    "PredicateOperator",
    "PredicateRule",
    "PredicateScalar",
    "PredicateValue",
    "SemanticConstantRule",
    "SemanticMapRule",
    "SemanticRule",
]


class PredicateOperator(StrEnum):
    """Authoritative closed enumeration of permissible row-local comparison operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IS_IN = "is_in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


class _BasePredicateRule(BaseModel):
    """Base class for route predicate rules with field and operator validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    operator: PredicateOperator
    value: PredicateValue = None

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        """Validate that target field name is non-empty.

        Parameters
        ----------
        v : str
            Candidate column name.

        Returns
        -------
        str
            Validated column name.

        Raises
        ------
        ValueError
            If field is empty or whitespace only.
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Predicate field name cannot be empty or whitespace only.")
        return trimmed

    @field_validator("operator", mode="before")
    @classmethod
    def _coerce_operator(cls, v: object) -> PredicateOperator:
        """Coerce raw strings into PredicateOperator enum.

        Parameters
        ----------
        v : object
            Input operator candidate.

        Returns
        -------
        PredicateOperator
            Validated PredicateOperator.
        """
        if isinstance(v, PredicateOperator):
            return v
        if isinstance(v, str):
            return PredicateOperator(v.lower().strip())
        raise TypeError(f"Invalid operator type: {type(v).__name__}")

    @field_validator("value")
    @classmethod
    def _validate_value_for_operator(
        cls, v: PredicateValue, info: ValidationInfo
    ) -> PredicateValue:
        """Validate value requirements according to operator semantics.

        Parameters
        ----------
        v : PredicateValue
            Predicate operand value.
        info : ValidationInfo
            Pydantic validation context.

        Returns
        -------
        PredicateValue
            Validated operand value.

        Raises
        ------
        ValueError
            If operand value does not match operator expectations.
        """
        op = info.data.get("operator")
        if op in (PredicateOperator.IS_IN, PredicateOperator.NOT_IN):
            if v is None or not isinstance(v, (list, tuple)):
                raise ValueError(
                    f"Operator '{op}' requires a sequence of values (list/tuple), got {type(v).__name__}."
                )
        elif op in (PredicateOperator.EQUALS, PredicateOperator.NOT_EQUALS):
            if v is None:
                raise ValueError(
                    f"Operator '{op}' requires a non-null operand value. Use 'is_null' or 'is_not_null' instead."
                )
        return v


class IncludeWhen(_BasePredicateRule):
    """Declarative predicate retaining rows that evaluate to True.

    Parameters
    ----------
    field : str
        Target column name to evaluate.
    operator : PredicateOperator
        Comparison operation.
    value : object | None, default None
        Comparison operand value.
    """

    rule: Literal["include_when"] = "include_when"


class ExcludeWhen(_BasePredicateRule):
    """Declarative predicate dropping rows that evaluate to True.

    Parameters
    ----------
    field : str
        Target column name to evaluate.
    operator : PredicateOperator
        Comparison operation.
    value : object | None, default None
        Comparison operand value.
    """

    rule: Literal["exclude_when"] = "exclude_when"


PredicateRule = Annotated[
    IncludeWhen | ExcludeWhen,
    Field(discriminator="rule"),
]


class SemanticMapRule(BaseModel):
    """Categorical mapping rule translating source values into canonical values.

    Parameters
    ----------
    field : str
        Target column name containing categorical source values.
    mapping : dict[str, str]
        Discrete translation table from source string encodings to canonical values.
    on_unmapped : Literal["error", "default"], default "error"
        Policy when encountering unmapped values: 'error' to fail-fast, or 'default' to fall back.
    default : str | None, default None
        Fallback canonical value used only when on_unmapped is 'default'.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Literal["map_values"] = "map_values"
    field: str
    mapping: dict[str, str]
    on_unmapped: Literal["error", "default"] = "error"
    default: str | None = None

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        """Validate that field name is non-empty.

        Parameters
        ----------
        v : str
            Candidate column name.

        Returns
        -------
        str
            Validated column name.
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field name cannot be empty or whitespace only.")
        return trimmed

    @field_validator("mapping")
    @classmethod
    def _validate_mapping(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate that mapping dictionary is non-empty.

        Parameters
        ----------
        v : dict[str, str]
            Candidate mapping dictionary.

        Returns
        -------
        dict[str, str]
            Validated mapping dictionary.
        """
        if not v:
            raise ValueError("Semantic mapping dictionary cannot be empty.")
        return v


class SemanticConstantRule(BaseModel):
    """Scalar assignment rule injecting or overriding a canonical constant.

    Parameters
    ----------
    field : str
        Canonical target column name to inject.
    value : str | int | float | bool
        Scalar constant value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Literal["constant"] = "constant"
    field: str
    value: str | int | float | bool

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        """Validate that field name is non-empty.

        Parameters
        ----------
        v : str
            Candidate column name.

        Returns
        -------
        str
            Validated column name.
        """
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field name cannot be empty or whitespace only.")
        return trimmed


SemanticRule = Annotated[
    SemanticMapRule | SemanticConstantRule,
    Field(discriminator="rule"),
]
