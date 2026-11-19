# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""External household SQLite source adapter.

Owns
----
- In-memory deserialization of SQLite binary backups (:memory: via conn.deserialize).
- Dynamic extraction of configured SQLite tables into Polars LazyFrames.
- Discovery of the latest SQLite/mmbak backup file from a local directory.

Does not own
-------------
- Control Plane database management (owned by infrastructure.control_plane.connection).
- Financial ledger transformations (owned by domain.household).
"""

from __future__ import annotations

import glob
import os
import sqlite3

import polars as pl

from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["SQLiteExtractor"]

diagnostics = get_observability_diagnostics(__name__)


class SQLiteExtractor:
    """Extracts raw Polars LazyFrames from external household SQLite backups."""

    def __init__(self, folder_path: str) -> None:
        self.folder_path = folder_path

    def get_latest_sqlite_backup(self) -> str:
        """Find the most recently modified SQLite backup in the folder.

        Returns
        -------
        str
            Filesystem path to the latest .mmbak or .sqlite file.

        Raises
        ------
        FileNotFoundError
            If no matching database backup file is found.
        """
        files = glob.glob(os.path.join(self.folder_path, "*.mmbak")) + glob.glob(
            os.path.join(self.folder_path, "*.sqlite")
        )
        if not files:
            raise FileNotFoundError(f"No database backup found in {self.folder_path}")
        return max(files, key=os.path.getmtime)

    def extract_table(
        self, filename: str, folder_path: str, raw_bytes: bytes, table_name: str
    ) -> pl.LazyFrame:
        """Deserialize in-memory bytes and extract an individual table into a Polars LazyFrame.

        Parameters
        ----------
        filename : str
            Source file basename.
        folder_path : str
            Source directory path.
        raw_bytes : bytes
            Binary database backup payload.
        table_name : str
            Target SQLite table name.

        Returns
        -------
        pl.LazyFrame
            Source-shaped LazyFrame tagged with source file provenance.
        """
        filepath = f"{folder_path}/{filename}" if folder_path else filename
        artifact_id = generate_file_id(filepath)

        clean_table = table_name.replace('"', '""')
        with sqlite3.connect(":memory:") as conn:
            conn.deserialize(raw_bytes)
            return (
                pl.read_database(
                    f'SELECT * FROM "{clean_table}"',
                    connection=conn,
                    infer_schema_length=10000,  # nosec B608
                )
                .lazy()
                .with_columns(
                    pl.lit(artifact_id).alias("artifact_id"),
                )
            )
