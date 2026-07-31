import glob
import os
import sqlite3
import tempfile

import duckdb
import polars as pl

from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class BenchmarkCacheManager:
    """Manages the cached benchmark SQLite database."""

    def __init__(
        self, target_db_base_path: str | None, current_db_path: str | None, status_queue: ILogger
    ):
        self.target_db_base_path = target_db_base_path
        self.current_db_path = current_db_path
        self.status_queue = status_queue

    @staticmethod
    def rescue_benchmark_cache(db_path: str) -> None:
        """Rescues existing benchmark cache to a temporary parquet file before DB wipe."""
        if not os.path.exists(db_path):
            return

        cache_path = os.path.join(tempfile.gettempdir(), "benchmark_cache.parquet")
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
                    # duckdb connection returns a relation, we can convert to polars
                    df_cache = conn.execute("SELECT * FROM f_Investment_Benchmark_Data").pl()
                    if not df_cache.is_empty():
                        df_cache.with_columns(pl.col("Date").cast(pl.Date)).write_parquet(
                            cache_path
                        )
        except Exception:
            pass

    def get_cached_benchmark_data(self) -> pl.DataFrame:
        if not self.target_db_base_path or not os.path.exists(self.target_db_base_path):
            return pl.DataFrame()

        # Check for rescued cache first
        cache_path = os.path.join(tempfile.gettempdir(), "benchmark_cache.parquet")
        if os.path.exists(cache_path):
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

        db_files = glob.glob(
            os.path.join(self.target_db_base_path, "**", "*.duckdb"), recursive=True
        )
        db_files.extend(
            glob.glob(os.path.join(self.target_db_base_path, "**", "*.db"), recursive=True)
        )
        if not db_files:
            return pl.DataFrame()

        if self.current_db_path:
            db_files = [
                f for f in db_files if os.path.abspath(f) != os.path.abspath(self.current_db_path)
            ]

        if not db_files:
            return pl.DataFrame()

        latest_db = max(db_files, key=os.path.getmtime)
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
            self.status_queue.put(
                EngineStatus(
                    msg=f"Warning: Failed to load cached benchmark data from {latest_db}: {e}",
                    data=None,
                    progress=0.05,
                    level=LogLevel.WARNING,
                )
            )
        return pl.DataFrame()
