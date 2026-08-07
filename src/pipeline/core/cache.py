import glob
import os
import sqlite3
import duckdb
import polars as pl
from typing import Optional

from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, LogLevel
from src.utils.helpers import get_temp_dir


class DatabaseCacheManager:
    """
    Centralized cache manager for extracting historical tables from the most recent database build.
    Supports both SQLite and DuckDB backwards compatibility for Benchmark data, and pure DuckDB
    for Medallion ETL architecture (Silver tables).
    """

    def __init__(
        self,
        target_db_base_path: str | None,
        current_db_path: str | None = None,
        status_queue: ILogger | None = None,
    ):
        self.target_db_base_path = target_db_base_path
        self.current_db_path = current_db_path
        self.status_queue = status_queue

    def _find_latest_db(self, include_sqlite: bool = False) -> str | None:
        if not self.target_db_base_path or not os.path.exists(self.target_db_base_path):
            return None

        db_files = glob.glob(
            os.path.join(self.target_db_base_path, "**", "*.duckdb"), recursive=True
        )
        if include_sqlite:
            db_files.extend(
                glob.glob(os.path.join(self.target_db_base_path, "**", "*.db"), recursive=True)
            )

        if not db_files:
            return None

        if self.current_db_path:
            db_files = [
                f for f in db_files if os.path.abspath(f) != os.path.abspath(self.current_db_path)
            ]

        if not db_files:
            return None

        return max(db_files, key=os.path.getmtime)

    # =========================================================================
    # BENCHMARK CACHE SPECIFIC LOGIC
    # =========================================================================

    @staticmethod
    def rescue_benchmark_cache(db_path: str) -> None:
        """Rescues existing benchmark cache to a temporary parquet file before DB wipe."""
        if not os.path.exists(db_path):
            return

        cache_path = os.path.join(get_temp_dir(), "benchmark_cache.parquet")
        try:
            if db_path.endswith(".db"):
                conn = sqlite3.connect(db_path)
                try:
                    df_cache = pl.read_database("SELECT * FROM f_Investment_Benchmark_Data", conn)
                    if not df_cache.is_empty():
                        df_cache.with_columns(pl.col("Date").cast(pl.Date)).write_parquet(
                            cache_path
                        )
                finally:
                    conn.close()
            else:
                with duckdb.connect(db_path) as conn:
                    df_cache = conn.execute("SELECT * FROM f_Investment_Benchmark_Data").pl()
                    if not df_cache.is_empty():
                        df_cache.with_columns(pl.col("Date").cast(pl.Date)).write_parquet(
                            cache_path
                        )
        except Exception:
            pass

    def get_cached_benchmark_data(self) -> pl.DataFrame:
        """Extracts historical benchmark data, attempting to read a rescued cache first."""
        if not self.target_db_base_path or not os.path.exists(self.target_db_base_path):
            return pl.DataFrame()

        cache_path = os.path.join(get_temp_dir(), "benchmark_cache.parquet")
        if os.path.exists(cache_path):
            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Found rescued benchmark cache from current month",
                        data=None,
                        progress=0.05,
                        level=LogLevel.STEP,
                    )
                )
            try:
                df = pl.read_parquet(cache_path)
                return df
            finally:
                try:
                    os.remove(cache_path)
                except OSError:
                    pass

        latest_db = self._find_latest_db(include_sqlite=True)
        if not latest_db:
            return pl.DataFrame()

        if self.status_queue:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Found recent cache DB: {os.path.basename(latest_db)}",
                    data=None,
                    progress=0.05,
                    level=LogLevel.STEP,
                )
            )

        try:
            if latest_db.endswith(".db"):
                with sqlite3.connect(latest_db) as conn:
                    df = pl.read_database("SELECT * FROM f_Investment_Benchmark_Data", conn)
            else:
                with duckdb.connect(latest_db) as conn:
                    df = conn.execute("SELECT * FROM f_Investment_Benchmark_Data").pl()

            if not df.is_empty():
                df = df.with_columns(pl.col("Date").cast(pl.Date))
                return df
        except Exception as e:
            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg=f"Warning: Failed to load cached benchmark data from {latest_db}: {e}",
                        data=None,
                        progress=0.05,
                        level=LogLevel.WARNING,
                    )
                )
        return pl.DataFrame()


