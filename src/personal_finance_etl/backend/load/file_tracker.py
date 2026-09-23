import hashlib
import os
import uuid
from datetime import datetime

import duckdb

from personal_finance_etl.backend.config.settings import FileHashPolicy
from personal_finance_etl.backend.load.raw import (
    RawDocumentStore,
    compute_file_hash,
    generate_file_id,
)
from personal_finance_etl.backend.utils.logger import logger

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
    """Tracks source file ingestion state using SQLite Raw Store as the primary source of truth.
    Synchronizes state with DuckDB meta.m_File_Registry."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        hash_policy: FileHashPolicy,
        raw_store: RawDocumentStore,
    ):
        self.conn = conn
        self.hash_policy = hash_policy
        self.raw_store = raw_store
        self.run_id: str | None = None
        self._sync_first_run()

    def _should_hash_check(self, category: str) -> bool:
        """Looks up the file type for a category and returns the hash policy."""
        file_type = FILE_TYPE_MAP.get(category, "csv")
        return getattr(self.hash_policy, file_type, False)

    def _sync_first_run(self) -> None:
        """Handles first-run migration: if DuckDB has files but SQLite doesn't, sync SQLite up."""

        duckdb_records = self.conn.execute(
            "SELECT relative_path, file_hash, file_name, file_category, file_size_bytes FROM meta.m_File_Registry"
        ).fetchall()

        sqlite_records = self.raw_store.get_all_registry()

        if duckdb_records and not sqlite_records:
            logger.info(
                "First-run migration detected: Syncing historical metadata to SQLite Raw Store..."
            )
            for rel_path, f_hash, f_name, f_cat, f_size in duckdb_records:
                file_id = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()
                now = datetime.now().isoformat()

                # We do not have the bytes during migration unless we read the disk
                # Attempt to read disk to populate payloads, if available
                # If file is missing, we insert NULL for bytes but mark SYNCED
                raw_bytes = None
                if os.path.exists(rel_path):
                    try:
                        with open(rel_path, "rb") as f:
                            raw_bytes = f.read()
                    except Exception:
                        pass

                self.raw_store.conn.execute(
                    """
                    INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_hash, file_size_bytes, sync_status, first_ingested, last_ingested)
                    VALUES (?, ?, ?, ?, ?, ?, 'SYNCED', ?, ?)
                    """,
                    (file_id, f_name, rel_path, f_cat, f_hash, f_size, now, now),
                )
                self.raw_store.conn.execute(
                    """
                    INSERT INTO raw_payloads (file_id, file_bytes)
                    VALUES (?, ?)
                    """,
                    (file_id, raw_bytes),
                )
            self.raw_store.commit()
            msg = f"Successfully migrated {len(duckdb_records)} historical records to Raw Store."
            logger.info(msg)

    def get_actionable_files(
        self, discovered_files: dict[str, list[str]]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Returns (new_files, changed_files) per category.
        Uses SQLite Raw Store as the source of truth."""
        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}

        registry = self.raw_store.get_all_registry()

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
                        current_hash = compute_file_hash(filepath)
                        stored_hash = registry[unique_path]
                        if current_hash != stored_hash:
                            changed_files[category].append(filepath)

        return new_files, changed_files

    def register_file(self, filepath: str, category: str, row_count: int) -> None:
        """Upserts a record into meta.file_registry after successful Bronze ingestion.
        Also triggers Raw Store state update to SYNCED."""
        unique_path = filepath.replace("\\", "/")
        file_name = os.path.basename(filepath)
        file_hash = compute_file_hash(filepath)

        try:
            file_size = os.path.getsize(filepath)
        except OSError:
            file_size = 0

        file_id = generate_file_id(filepath)
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

        # Update SQLite Sync Status
        self.raw_store.mark_synced([filepath])

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
