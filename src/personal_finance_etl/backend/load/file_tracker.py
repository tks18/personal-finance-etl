import hashlib
import os
import uuid
from datetime import datetime

import duckdb

from personal_finance_etl.backend.load.raw import FILE_TYPE_MAP, RawDocumentStore, generate_file_id
from personal_finance_etl.backend.utils.logger import logger


class FileTracker:
    """Pure DuckDB telemetry layer for the ETL Lakehouse.

    Responsible ONLY for:
      - Logging file ingestion metadata into meta.m_File_Registry after Bronze writes.
      - Recording pipeline run lifecycle in meta.m_Run_Log.
      - First-run sync: if DuckDB is missing entries that the Raw Store has, re-queues them.

    All file change detection, hashing, pruning, and binary ingestion is
    owned exclusively by RawDocumentStore.
    """

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        raw_store: RawDocumentStore,
    ):
        self.conn = conn
        self.raw_store = raw_store
        self.run_id: str | None = None
        self._sync_duckdb_from_raw_store()

    def _sync_duckdb_from_raw_store(self) -> None:
        """First-run heal: re-queues any files the Raw Store knows about but DuckDB doesn't.

        This is the reverse of the old first-run migration. Since the Raw Store is the
        absolute source of truth, DuckDB's meta.m_File_Registry is simply a telemetry
        projection of what actually exists in the Raw Store + Bronze layer.

        If DuckDB is ever blown away and rebuilt, this method detects the gap on the
        very next run and forces the pipeline to re-extract and re-register those files
        properly through the Bronze layer — not via a shortcut metadata insert.
        """
        duckdb_rows = self.conn.execute("SELECT relative_path FROM meta.m_File_Registry").fetchall()
        duckdb_paths = {str(r[0]) for r in duckdb_rows}

        raw_all = self.raw_store.get_all_paths_by_category()

        missing_count = 0
        for _cat, paths in raw_all.items():
            for path in paths:
                if path not in duckdb_paths:
                    # Force it back to PENDING_BRONZE so the pipeline re-extracts it
                    if self.raw_store.conn:
                        self.raw_store.conn.execute(
                            "UPDATE raw_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                            [path],
                        )
                    missing_count += 1

        if missing_count > 0:
            logger.info(
                f"Self-Healing: {missing_count} file(s) in Raw Store are missing from DuckDB. "
                "Re-queued as PENDING_BRONZE for re-extraction into Bronze layer."
            )

    def register_file(self, filepath: str, category: str, row_count: int) -> None:
        """Upserts a record into meta.m_File_Registry after successful Bronze ingestion.
        Also marks the file as SYNCED in the Raw Store."""
        unique_path = filepath.replace("\\", "/")
        file_name = os.path.basename(filepath)
        file_type = (
            "parquet" if filepath.startswith("virtual://") else FILE_TYPE_MAP.get(category, "csv")
        )

        # For virtual files, we cannot hash or stat them from disk
        # Retrieve metadata from Raw Store registry directly
        if filepath.startswith("virtual://"):
            reg = self.raw_store.get_all_registry()
            file_hash = reg.get(unique_path, "")
            file_size = 0
            file_id = generate_file_id(filepath)
        else:
            file_hash = self._safe_hash(filepath)
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
                SET file_hash = ?, file_type = ?, file_size_bytes = ?, last_ingested = ?, row_count = ?
                WHERE relative_path = ?
                """,
                [file_hash, file_type, file_size, now, row_count, unique_path],
            )
        else:
            self.conn.execute(
                """
                INSERT INTO meta.m_File_Registry 
                (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, first_ingested, last_ingested, row_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    file_id,
                    file_name,
                    unique_path,
                    category,
                    file_type,
                    file_hash,
                    file_size,
                    now,
                    now,
                    row_count,
                ],
            )

        # Mark as SYNCED in Raw Store
        self.raw_store.mark_synced([filepath])

    def start_run(self) -> str:
        """Creates a record in meta.m_Run_Log and returns the run_id."""
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

    @staticmethod
    def _safe_hash(filepath: str) -> str:
        """SHA-256 hash of a file, returns empty string if file is missing."""
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (FileNotFoundError, OSError):
            return ""
