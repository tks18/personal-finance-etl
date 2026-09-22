import os
import sqlite3
from datetime import datetime

from personal_finance_etl.backend.load.file_tracker import FileTracker
from personal_finance_etl.backend.utils.logger import logger

RAW_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_file_registry (
    file_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    file_category TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size_bytes BIGINT,
    first_ingested TIMESTAMP NOT NULL,
    last_ingested TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    file_id TEXT PRIMARY KEY,
    file_bytes BLOB,
    FOREIGN KEY(file_id) REFERENCES raw_file_registry(file_id) ON DELETE CASCADE
);
"""


class RawDocumentStore:
    """Manages an embedded SQLite database that stores raw binary files as BLOBs."""

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db_path = os.path.join(base_path, db_name)
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        """Opens the SQLite connection."""
        # Check if base path exists, if not, create it
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # isolation_level=None gives us explicit control over BEGIN/COMMIT/ROLLBACK
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON;")
        logger.info(f"Raw Document Store connected at {self.db_path}")

    def close(self) -> None:
        """Closes the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Raw Document Store connection closed.")

    def ensure_schema(self) -> None:
        """Creates the raw_landing table if it doesn't exist."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")
        self._conn.executescript(RAW_DDL)
        self._conn.commit()

    def begin_transaction(self) -> None:
        """Begins a SQLite transaction."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")
        self._conn.execute("BEGIN TRANSACTION;")

    def commit(self) -> None:
        """Commits the SQLite transaction."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")
        self._conn.commit()
        logger.info("Raw Document Store transaction committed.")

    def rollback(self) -> None:
        """Rolls back the SQLite transaction."""
        if not self._conn:
            return
        try:
            self._conn.rollback()
            logger.warning("Raw Document Store transaction rolled back.")
        except Exception as e:
            logger.error(f"Failed to rollback Raw Document Store transaction: {e}")

    def load_binaries(
        self, actionable_files: dict[str, list[str]], file_tracker: "FileTracker"
    ) -> None:
        """Reads actionable files as binary and INSERTS/UPSERTS them into raw_landing."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")

        total_count = 0
        for category, filepaths in actionable_files.items():
            success_files: list[str] = []
            for filepath in filepaths:
                if not os.path.exists(filepath):
                    logger.warning(f"Raw Store: File not found {filepath}, skipping.")
                    continue

                try:
                    with open(filepath, "rb") as f:
                        raw_bytes = f.read()

                    filename = os.path.basename(filepath)
                    unique_path = filepath.replace("\\", "/")
                    file_hash = file_tracker.compute_file_hash(filepath)

                    try:
                        file_size = os.path.getsize(filepath)
                    except OSError:
                        file_size = 0

                    file_id = file_tracker.generate_file_id(filepath)
                    now = datetime.now().isoformat()

                    # Upsert into raw_file_registry
                    self._conn.execute(
                        """
                        INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_hash, file_size_bytes, first_ingested, last_ingested)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            file_name = excluded.file_name,
                            relative_path = excluded.relative_path,
                            file_category = excluded.file_category,
                            file_hash = excluded.file_hash,
                            file_size_bytes = excluded.file_size_bytes,
                            last_ingested = excluded.last_ingested
                        """,
                        (
                            file_id,
                            filename,
                            unique_path,
                            category,
                            file_hash,
                            file_size,
                            now,
                            now,
                        ),
                    )

                    # Upsert into raw_payloads
                    self._conn.execute(
                        """
                        INSERT INTO raw_payloads (file_id, file_bytes)
                        VALUES (?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            file_bytes = excluded.file_bytes
                        """,
                        (file_id, raw_bytes),
                    )
                    success_files.append(filename)
                    total_count += 1
                except Exception as e:
                    logger.error(f"Raw Store: Failed to ingest {filepath}: {e}")
                    raise e

            if success_files:
                logger.info(f"  -> Raw Store [{category}]: Ingested {len(success_files)} file(s).")
                logger.debug(f"  -> Raw Store [{category}] Details: {', '.join(success_files)}")

        if total_count > 0:
            logger.info(
                f"Raw Store: Successfully ingested a total of {total_count} binary file(s)."
            )
