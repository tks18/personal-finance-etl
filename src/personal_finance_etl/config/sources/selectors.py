"""Discriminated physical dataset selectors for external evidence sources.

Owns
----
- CsvSelector: File-level dataset selector and parsing options for CSV providers.
- ExcelSelector: Sheet-level dataset selector and header configuration for Excel providers.
- SqliteSelector: Table-level dataset selector for SQLite database providers.
- DatasetSelector: Discriminated union of all supported provider dataset selectors.

Does not own
------------
- SourceId and ProviderType cross-boundary contract definitions (owned by contracts.sources).
- DatasetId canonical enum registry (owned by contracts.datasets).
- In-memory parsing execution or physical file reading (owned by infrastructure.providers).
"""

from __future__ import annotations

import codecs
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from personal_finance_etl.contracts.sources import ProviderType

__all__ = [
    "CsvSelector",
    "DatasetSelector",
    "ExcelSelector",
    "SqliteSelector",
]

_IDENTIFIER_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CsvSelector(BaseModel):
    """File-level dataset selector and bounded parsing configuration for CSV sources.

    Parameters
    ----------
    provider_type : Literal[ProviderType.CSV], default ProviderType.CSV
        Discriminator identifying the CSV provider type.
    file_pattern : str | None, default None
        Optional glob pattern or exact filename identifying target files within the source location.
    delimiter : str, default ","
        Single-character field delimiter string.
    encoding : str, default "utf-8"
        Character encoding codec used for text decoding.
    has_header : bool, default True
        Flag indicating whether the first line contains tabular column headers.
    """

    provider_type: Literal[ProviderType.CSV] = ProviderType.CSV
    file_pattern: str | None = None
    delimiter: str = ","
    encoding: str = "utf-8"
    has_header: bool = True

    @field_validator("file_pattern", mode="before")
    @classmethod
    def _validate_file_pattern(cls, v: object) -> str | None:
        """Validate that file_pattern, if provided, is a non-empty string.

        Parameters
        ----------
        v : object
            Input file pattern candidate.

        Returns
        -------
        str | None
            Cleaned file pattern or None.

        Raises
        ------
        ValueError
            If v is provided and is not a string, or is empty or whitespace only.
        """
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError(f"file_pattern must be a string, got {type(v).__name__}")
        pattern = v.strip()
        if not pattern:
            raise ValueError("file_pattern cannot be empty or whitespace.")
        return pattern

    @field_validator("delimiter", mode="before")
    @classmethod
    def _validate_delimiter(cls, v: object) -> str:
        """Validate delimiter string.

        Parameters
        ----------
        v : object
            Input delimiter candidate.

        Returns
        -------
        str
            Validated delimiter string.

        Raises
        ------
        ValueError
            If delimiter is not a string or is empty.
        """
        if not isinstance(v, str):
            raise ValueError(f"delimiter must be a string, got {type(v).__name__}")
        if not v:
            raise ValueError("delimiter cannot be empty.")
        return v

    @field_validator("encoding", mode="before")
    @classmethod
    def _validate_encoding(cls, v: object) -> str:
        """Validate that encoding is a valid Python codec string.

        Parameters
        ----------
        v : object
            Input encoding codec name.

        Returns
        -------
        str
            Validated encoding codec name.

        Raises
        ------
        ValueError
            If encoding is not a string, is empty, whitespace, or unrecognized by Python codecs.
        """
        if not isinstance(v, str):
            raise ValueError(f"encoding must be a string, got {type(v).__name__}")
        enc = v.strip()
        if not enc:
            raise ValueError("encoding cannot be empty or whitespace.")
        try:
            codecs.lookup(enc)
        except LookupError as exc:
            raise ValueError(f"Unknown text encoding codec: '{enc}'") from exc
        return enc


class ExcelSelector(BaseModel):
    """Sheet-level dataset selector and layout configuration for Excel statement sources.

    Parameters
    ----------
    provider_type : Literal[ProviderType.EXCEL], default ProviderType.EXCEL
        Discriminator identifying the Excel provider type.
    sheet_name : str | None, default None
        Target worksheet name. If None, default/first worksheet resolution applies.
    header_row : int | None, default None
        Zero-based row index containing column headers if header detection is not automatic.
    """

    provider_type: Literal[ProviderType.EXCEL] = ProviderType.EXCEL
    sheet_name: str | None = None
    header_row: int | None = None

    @field_validator("sheet_name", mode="before")
    @classmethod
    def _validate_sheet_name(cls, v: object) -> str | None:
        """Validate that sheet_name, if provided, is a non-empty string.

        Parameters
        ----------
        v : object
            Input sheet name candidate.

        Returns
        -------
        str | None
            Cleaned sheet name or None.

        Raises
        ------
        ValueError
            If v is provided and is not a string, or is an empty string or whitespace only.
        """
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError(f"sheet_name must be a string, got {type(v).__name__}")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("sheet_name cannot be empty or whitespace.")
        return cleaned

    @field_validator("header_row", mode="before")
    @classmethod
    def _validate_header_row(cls, v: object) -> int | None:
        """Validate that header_row, if provided, is a non-negative integer.

        Parameters
        ----------
        v : object
            Input header row index candidate.

        Returns
        -------
        int | None
            Validated header row index or None.

        Raises
        ------
        ValueError
            If v is not an integer or is negative.
        """
        if v is None:
            return None
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError(f"header_row must be an integer, got {type(v).__name__}")
        if v < 0:
            raise ValueError(f"header_row must be non-negative, got {v}")
        return v


class SqliteSelector(BaseModel):
    """Table-level dataset selector for SQLite database backup sources.

    Parameters
    ----------
    provider_type : Literal[ProviderType.SQLITE], default ProviderType.SQLITE
        Discriminator identifying the SQLite provider type.
    table_name : str
        Target SQLite database table name. Must be a valid identifier without arbitrary SQL.
    """

    provider_type: Literal[ProviderType.SQLITE] = ProviderType.SQLITE
    table_name: str

    @field_validator("table_name", mode="before")
    @classmethod
    def _validate_table_name(cls, v: object) -> str:
        """Validate that table_name is a non-empty SQL identifier and rejects arbitrary SQL.

        Parameters
        ----------
        v : object
            Input table name candidate.

        Returns
        -------
        str
            Validated table identifier.

        Raises
        ------
        ValueError
            If v is not a string, is empty, whitespace, or is not a valid SQL identifier.
        """
        if not isinstance(v, str):
            raise ValueError(f"table_name must be a string, got {type(v).__name__}")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("table_name cannot be empty or whitespace.")
        if not _IDENTIFIER_REGEX.match(cleaned):
            raise ValueError(
                f"table_name must be a valid SQL identifier (alphanumeric and underscores only), "
                f"got '{cleaned}'."
            )
        return cleaned


type DatasetSelector = Annotated[
    CsvSelector | ExcelSelector | SqliteSelector,
    Field(discriminator="provider_type"),
]
