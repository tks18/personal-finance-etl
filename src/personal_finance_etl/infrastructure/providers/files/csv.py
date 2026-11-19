"""CSV parsing and evidence extraction adapter.

Owns
----
- Parsing in-memory CSV binary payloads into Polars LazyFrames.
- Applying source-level schema overrides for configuration and mapping assets.
- Ingestion metadata tagging (artifact_id).

Does not own
-------------
- Validation of business logic (owned by domain.common.validation).
- File reading from disk (payloads provided via Control Plane Raw Store).
"""

from __future__ import annotations

import io

import polars as pl

from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = [
    "CSVExtractor",
]

diagnostics = get_observability_diagnostics(__name__)


class CSVExtractor:
    """Extracts raw Polars LazyFrames from external CSV evidence payloads.

    Parameters
    ----------
    folder_path : str, default ""
        Base source folder path for the extractor instance.
    """

    def __init__(self, folder_path: str = "") -> None:
        self.folder_path = folder_path

    def extract_csv(
        self,
        filename: str,
        folder_path: str,
        raw_bytes: bytes,
        *,
        delimiter: str = ",",
        encoding: str = "utf8",
        has_header: bool = True,
        try_parse_dates: bool = True,
    ) -> pl.LazyFrame:
        """Parse in-memory CSV bytes into an annotated Polars LazyFrame.

        Parameters
        ----------
        filename : str
            Source file basename.
        folder_path : str
            Source directory path.
        raw_bytes : bytes
            Binary CSV payload.
        delimiter : str, default ","
            Single-character column separator delimiter.
        encoding : str, default "utf8"
            Character encoding codec.
        has_header : bool, default True
            Whether the first line contains column headers.
        try_parse_dates : bool, default True
            Whether to attempt automatic date parsing for date columns.

        Returns
        -------
        pl.LazyFrame
            Source-shaped LazyFrame tagged with source file provenance.
        """
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)
        norm_encoding = "utf8" if encoding.lower() in ("utf-8", "utf8") else encoding
        df = pl.read_csv(
            io.BytesIO(raw_bytes),
            separator=delimiter,
            encoding=norm_encoding,
            has_header=has_header,
            infer_schema_length=10000,
            try_parse_dates=try_parse_dates,
        )
        return df.lazy().with_columns(
            pl.lit(artifact_id).alias("artifact_id"),
        )
