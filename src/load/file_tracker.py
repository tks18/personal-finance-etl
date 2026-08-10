import hashlib
import os
import uuid
from datetime import datetime

import duckdb

from src.config.settings import FileHashPolicy

FILE_TYPE_MAP: dict[str, str] = {
    "mf_holdings": "excel",
    "mf_orders": "excel",
    "stock_pl": "excel",
    "stock_orders": "excel",
    "sqlite_source": "sqlite",
    "benchmark_master": "csv",
    "macro_parameters": "csv",
    "opening_balances": "csv",
    "mf_isin": "csv",
    "benchmark_mapping": "csv",
}


class FileTracker:
    """Tracks source file ingestion state via meta.file_registry.
    Determines which files are new or changed based on per-type hash policy."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, hash_policy: FileHashPolicy):
        self.conn = conn
        self.hash_policy = hash_policy
        self.run_id: str | None = None

    def _should_hash_check(self, category: str) -> bool:
        """Looks up the file type for a category and returns the hash policy."""
        file_type = FILE_TYPE_MAP.get(category, "csv")
        return getattr(self.hash_policy, file_type, False)

    def compute_file_hash(self, filepath: str) -> str:
        """SHA-256 of file contents."""
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            return ""

    def get_actionable_files(
        self, discovered_files: dict[str, list[str]]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Returns (new_files, changed_files) per category.
        For each category:
          - New files (not in registry) are always returned.
          - Changed files returned ONLY if hash policy is True for that type."""
        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}

        # Fetch existing registry into a dictionary for fast lookup
        # mapping relative_path -> file_hash
        existing_records = self.conn.execute(
            "SELECT relative_path, file_hash FROM meta.m_File_Registry"
        ).fetchall()
        registry = {record[0]: record[1] for record in existing_records}

        for category, filepaths in discovered_files.items():
            new_files[category] = []
            changed_files[category] = []

            should_check_hash = self._should_hash_check(category)

            for filepath in filepaths:
                unique_path = filepath.replace("\\", "/")

                if unique_path not in registry:
                    new_files[category].append(filepath)
                else:
                    if should_check_hash:
                        current_hash = self.compute_file_hash(filepath)
                        stored_hash = registry[unique_path]
                        if current_hash != stored_hash:
                            changed_files[category].append(filepath)

        return new_files, changed_files

    def register_file(self, filepath: str, category: str, row_count: int) -> None:
        """Upserts a record into meta.file_registry after successful Bronze ingestion."""
        unique_path = filepath.replace("\\", "/")
        file_name = os.path.basename(filepath)
        file_hash = self.compute_file_hash(filepath)

        try:
            file_size = os.path.getsize(filepath)
        except OSError:
            file_size = 0

        file_id = hashlib.sha256(unique_path.encode("utf-8")).hexdigest()
        now = datetime.now()

        exists = self.conn.execute(
            "SELECT 1 FROM meta.m_File_Registry WHERE relative_path = ?", [unique_path]
        ).fetchone()

        if exists:
            self.conn.execute(
                """
                UPDATE meta.m_File_Registry 
                SET file_hash = ?, file_size_bytes = ?, last_ingested = ?, row_count = ?
                WHERE relative_path = ?
                """,
                [file_hash, file_size, now, row_count, unique_path],
            )
        else:
            self.conn.execute(
                """
                INSERT INTO meta.m_File_Registry 
                (file_id, file_name, relative_path, file_category, file_hash, file_size_bytes, first_ingested, last_ingested, row_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    file_id,
                    file_name,
                    unique_path,
                    category,
                    file_hash,
                    file_size,
                    now,
                    now,
                    row_count,
                ],
            )

    def start_run(self) -> str:
        """Creates a record in meta.run_log and returns the run_id."""
        self.run_id = str(uuid.uuid4())
        now = datetime.now()
        self.conn.execute(
            """
            INSERT INTO meta.m_Run_Log (run_id, started_at, status)
            VALUES (?, ?, 'running')
            """,
            [self.run_id, now],
        )
        return self.run_id

    def finish_run(
        self, run_id: str, status: str, files_processed: int = 0, files_skipped: int = 0
    ) -> None:
        """Updates the run_log with final status and duration."""
        now = datetime.now()

        start_time_row = self.conn.execute(
            "SELECT started_at FROM meta.m_Run_Log WHERE run_id = ?", [run_id]
        ).fetchone()

        duration_sec = 0.0
        if start_time_row and start_time_row[0]:
            duration_sec = (now - start_time_row[0]).total_seconds()

        self.conn.execute(
            """
            UPDATE meta.m_Run_Log 
            SET finished_at = ?, status = ?, files_processed = ?, files_skipped = ?, duration_sec = ?
            WHERE run_id = ?
            """,
            [now, status, files_processed, files_skipped, duration_sec, run_id],
        )
