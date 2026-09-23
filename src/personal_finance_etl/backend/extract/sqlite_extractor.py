# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import glob
import os
import sqlite3

import polars as pl


class SQLiteExtractor:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def get_latest_sqlite_backup(self) -> str:
        """Finds the most recently modified SQLite file in the given folder."""
        files = glob.glob(os.path.join(self.folder_path, "*.mmbak")) + glob.glob(
            os.path.join(self.folder_path, "*.sqlite")
        )
        if not files:
            raise FileNotFoundError(f"No database backup found in {self.folder_path}")
        return max(files, key=os.path.getmtime)

    def extract_base_tables(
        self, filename: str, folder_path: str, raw_bytes: bytes
    ) -> tuple[pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame]:
        """Writes the raw bytes to a temp file, connects via sqlite3, extracts tables, and cleans up."""

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

        # Eagerly collect to memory as LazyFrames defer execution and the memory db drops on exit
        return (
            zcategory_lazy.collect().lazy(),
            assetgroup_lazy.collect().lazy(),
            assets_lazy.collect().lazy(),
            currency_lazy.collect().lazy(),
            inoutcome_lazy.collect().lazy(),
        )
