import polars as pl
import os
import glob


def get_latest_sqlite_backup(folder_path):
    """Finds the most recently modified SQLite file in the MoneyManager folder."""
    files = glob.glob(os.path.join(folder_path, "*.*")
                      )  # Adjust extension if needed (e.g. *.db, *.sqlite)
    if not files:
        raise FileNotFoundError(f"No database backup found in {folder_path}")
    return max(files, key=os.path.getmtime)


def extract_base_tables(source_db_path):
    """Connects to SQLite once and returns LazyFrames for all base tables."""
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
