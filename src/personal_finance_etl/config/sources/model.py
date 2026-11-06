"""Authoritative physical evidence source configuration models.

Owns
----
- SourceConfig: User-authored declarative evidence source configuration model.
- SourceDatasetConfig: Declarative binding of a physical source to a canonical dataset.

Does not own
------------
- SourceId and ProviderType cross-boundary contract definitions (owned by contracts.sources).
- DatasetId canonical enum registry (owned by contracts.datasets).
- Root settings or financial rules models (owned by config.settings and config.financial_rules).
- Physical provider extraction mechanics (owned by infrastructure.providers).
"""

from __future__ import annotations

from typing import Self, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from personal_finance_etl.config.sources.change_detection import ChangeDetectionPolicy
from personal_finance_etl.config.sources.identity import BronzeIdentityStrategy
from personal_finance_etl.config.sources.mapping import (
    ColumnMapping,
    dict_to_mapping_list,
)
from personal_finance_etl.config.sources.normalization import NormalizationRule
from personal_finance_etl.config.sources.selectors import DatasetSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    ProviderType,
    SourceId,
    validate_source_id,
)

__all__ = ["SourceConfig", "SourceDatasetConfig", "SourceFieldDeclaration"]


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


def _empty_column_mappings() -> list[ColumnMapping]:
    """Create an empty list of ColumnMapping instances."""
    return []


def _empty_normalization_rules() -> list[NormalizationRule]:
    """Create an empty list of NormalizationRule instances."""
    return []


class SourceFieldDeclaration(BaseModel):
    """Declarative specification of an expected source evidence field.

    Parameters
    ----------
    name : str
        Source field or column name as present in the raw tabular stream.
    data_type : str, default 'String'
        Declared data type string ('Int64', 'Float64', 'String', 'Date', 'Boolean').
    nullable : bool, default True
        Whether null or missing values are permitted in this source column.
    unique : bool, default False
        Whether values in this source column must be unique across rows.
    description : str | None, default None
        Optional human-readable documentation for this source field.
    """

    name: str
    data_type: str = "String"
    nullable: bool = True
    unique: bool = False
    description: str | None = None


def _empty_fields() -> list[SourceFieldDeclaration]:
    """Create an empty list of SourceFieldDeclaration instances."""
    return []


class SourceDatasetConfig(BaseModel):
    """Declarative binding of a physical evidence source to a canonical PFETL dataset.

    Parameters
    ----------
    source_id : SourceId
        Logical identity of the physical evidence source supplying this dataset.
    dataset_id : DatasetId
        Authoritative canonical dataset identifier from the lakehouse registry.
    selector : DatasetSelector
        Provider-specific typed selector (CsvSelector, ExcelSelector, SqliteSelector).
    enabled : bool, default True
        Operational toggle to enable or disable ingestion of this specific dataset.
    description : str | None, default None
        Optional human-readable documentation for this dataset binding.
    change_detection : ChangeDetectionPolicy | None, default None
        Optional explicit change-detection and synchronization policy override.
    identity : BronzeIdentityStrategy | None, default None
        Optional explicit Bronze row identity strategy override.
    mapping : list[ColumnMapping], default empty list
        Declarative column translation rules from source names to canonical Bronze names.
    normalization : list[NormalizationRule], default empty list
        Ordered list of bounded normalization transformations to apply during ingestion.
    fields : list[SourceFieldDeclaration], default empty list
        Declarative schema specification of expected source tabular fields.
    """

    source_id: SourceId
    dataset_id: DatasetId
    selector: DatasetSelector
    enabled: bool = True
    description: str | None = None
    change_detection: ChangeDetectionPolicy | None = None
    identity: BronzeIdentityStrategy | None = None
    mapping: list[ColumnMapping] = Field(default_factory=_empty_column_mappings)
    normalization: list[NormalizationRule] = Field(default_factory=_empty_normalization_rules)
    fields: list[SourceFieldDeclaration] = Field(default_factory=_empty_fields)

    @field_validator("fields", mode="before")
    @classmethod
    def _coerce_fields_dict(cls, v: object) -> object:
        """Coerce dictionary declarations into a list of SourceFieldDeclaration instances.

        Parameters
        ----------
        v : object
            Input candidate, either a dictionary or list of field declarations.

        Returns
        -------
        object
            Coerced list or original value.
        """
        if isinstance(v, dict):
            typed_dict = cast(dict[object, object], v)
            coerced: list[SourceFieldDeclaration] = []
            for k, val in typed_dict.items():
                col_name = str(k)
                if isinstance(val, str):
                    coerced.append(SourceFieldDeclaration(name=col_name, data_type=val))
                elif isinstance(val, dict):
                    inner_dict = cast(dict[object, object], val)
                    dtype = str(inner_dict.get("data_type", "String"))
                    nullable = bool(inner_dict.get("nullable", True))
                    unique = bool(inner_dict.get("unique", False))
                    desc = (
                        str(inner_dict.get("description"))
                        if "description" in inner_dict and inner_dict["description"] is not None
                        else None
                    )
                    coerced.append(
                        SourceFieldDeclaration(
                            name=col_name,
                            data_type=dtype,
                            nullable=nullable,
                            unique=unique,
                            description=desc,
                        )
                    )
            return coerced
        return v

    @field_validator("mapping", mode="before")
    @classmethod
    def _coerce_mapping_dict(cls, v: object) -> object:
        """Coerce dictionary mappings into a list of ColumnMapping instances.

        Parameters
        ----------
        v : object
            Input mapping candidate, either a dictionary or list of mappings.

        Returns
        -------
        object
            Coerced mapping list or original value.
        """
        if isinstance(v, dict):
            typed_dict = cast(dict[object, object], v)
            dict_mapping: dict[str, str] = {str(k): str(val) for k, val in typed_dict.items()}
            return dict_to_mapping_list(dict_mapping)
        return v

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
