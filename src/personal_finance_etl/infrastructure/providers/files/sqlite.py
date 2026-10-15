# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""External household SQLite source adapter.

Owns
----
- In-memory deserialization of SQLite binary backups (:memory: via conn.deserialize).
- Extraction of 5 core household base tables (ZCATEGORY, ASSETGROUP, ASSETS, CURRENCY, INOUTCOME).
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

from personal_finance_etl.infrastructure.logging import logger

__all__ = ["SQLiteExtractor"]


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

    def extract_base_tables(
        self, filename: str, folder_path: str, raw_bytes: bytes
    ) -> tuple[pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame]:
        """Deserialize in-memory bytes, extract tables into Polars LazyFrames, and tag file info."""

        def add_file_info(lf: pl.LazyFrame) -> pl.LazyFrame:
            return lf.with_columns(
                pl.lit(filename).alias("__file_name__"),
                pl.lit(folder_path).alias("__folder_path__"),
            )

        with sqlite3.connect(":memory:") as conn:
            conn.deserialize(raw_bytes)
            zcategory_lazy = add_file_info(
                pl.read_database(
                    "SELECT * FROM ZCATEGORY", connection=conn, infer_schema_length=10000
                ).lazy()
            )
            assetgroup_lazy = add_file_info(
                pl.read_database(
                    "SELECT * FROM ASSETGROUP", connection=conn, infer_schema_length=10000
                ).lazy()
            )
            assets_lazy = add_file_info(
                pl.read_database(
                    "SELECT * FROM ASSETS", connection=conn, infer_schema_length=10000
                ).lazy()
            )
            currency_lazy = add_file_info(
                pl.read_database(
                    "SELECT * FROM CURRENCY", connection=conn, infer_schema_length=10000
                ).lazy()
            )
            inoutcome_lazy = add_file_info(
                pl.read_database(
                    "SELECT * FROM INOUTCOME", connection=conn, infer_schema_length=10000
                ).lazy()
            )

            logger.debug(f"[EXTRACT:SQLITE] Successfully extracted 5 base tables from {filename}")

        # Eagerly collect to memory as LazyFrames defer execution and the memory db drops on exit
        return (
            zcategory_lazy.collect().lazy(),
            assetgroup_lazy.collect().lazy(),
            assets_lazy.collect().lazy(),
            currency_lazy.collect().lazy(),
            inoutcome_lazy.collect().lazy(),
        )
