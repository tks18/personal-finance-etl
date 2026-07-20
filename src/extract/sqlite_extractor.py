import polars as pl
import os
import glob


class ADBCSQLiteExtractor:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def _get_latest_sqlite_backup(self) -> str:
        """Finds the most recently modified SQLite file in the given folder."""
        files = glob.glob(os.path.join(self.folder_path, "*.*"))
        if not files:
            raise FileNotFoundError(
                f"No database backup found in {self.folder_path}")
        return max(files, key=os.path.getmtime)

    def extract_base_tables(self) -> tuple[pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame]:
        """Connects to SQLite once and returns LazyFrames for all base tables."""
        source_db_path = self._get_latest_sqlite_backup()
        uri = f"sqlite:///{source_db_path}"

        zcategory_lazy = pl.read_database_uri(
            "SELECT * FROM ZCATEGORY", uri, engine="adbc").lazy()
        assetgroup_lazy = pl.read_database_uri(
            "SELECT * FROM ASSETGROUP", uri, engine="adbc").lazy()
        assets_lazy = pl.read_database_uri(
            "SELECT * FROM ASSETS", uri, engine="adbc").lazy()
        currency_lazy = pl.read_database_uri(
            "SELECT * FROM CURRENCY", uri, engine="adbc").lazy()
        inoutcome_lazy = pl.read_database_uri(
            "SELECT * FROM INOUTCOME", uri, engine="adbc").lazy()

        return zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy
