import glob
import os

import adbc_driver_sqlite.dbapi as adbc_sqlite
import polars as pl


class ADBCSQLiteExtractor:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def _get_latest_sqlite_backup(self) -> str:
        """Finds the most recently modified SQLite file in the given folder."""
        files = glob.glob(os.path.join(self.folder_path, "*.mmbak")) + glob.glob(
            os.path.join(self.folder_path, "*.sqlite")
        )
        if not files:
            raise FileNotFoundError(f"No database backup found in {self.folder_path}")
        return max(files, key=os.path.getmtime)

    def extract_base_tables(
        self,
    ) -> tuple[pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame]:
        """Connects to SQLite once and returns LazyFrames for all base tables."""
        source_db_path = self._get_latest_sqlite_backup()

        filename = os.path.basename(source_db_path)
        folder = os.path.dirname(source_db_path)

        def add_file_info(lf: pl.LazyFrame) -> pl.LazyFrame:
            return lf.with_columns(
                pl.lit(filename).alias("__file_name__"), pl.lit(folder).alias("__folder_path__")
            )

        with adbc_sqlite.connect(source_db_path) as conn:
            zcategory_lazy = add_file_info(
                pl.read_database("SELECT * FROM ZCATEGORY", connection=conn).lazy()
            )
            assetgroup_lazy = add_file_info(
                pl.read_database("SELECT * FROM ASSETGROUP", connection=conn).lazy()
            )
            assets_lazy = add_file_info(
                pl.read_database("SELECT * FROM ASSETS", connection=conn).lazy()
            )
            currency_lazy = add_file_info(
                pl.read_database("SELECT * FROM CURRENCY", connection=conn).lazy()
            )
            inoutcome_lazy = add_file_info(
                pl.read_database("SELECT * FROM INOUTCOME", connection=conn).lazy()
            )

        return zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy
