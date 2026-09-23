import hashlib
import os
import sqlite3
from datetime import datetime

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
    sync_status TEXT DEFAULT 'PENDING_BRONZE',
    first_ingested TIMESTAMP NOT NULL,
    last_ingested TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_payloads (
    file_id TEXT PRIMARY KEY,
    file_bytes BLOB,
    FOREIGN KEY(file_id) REFERENCES raw_file_registry(file_id) ON DELETE CASCADE
);
"""


def compute_file_hash(filepath: str) -> str:
    """SHA-256 of file contents."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return ""


def generate_file_id(filepath: str) -> str:
    """Generates a deterministic ID (SHA-256) across the platform based on relative path."""
    unique_path = filepath.replace("\\", "/")
    return hashlib.sha256(unique_path.encode("utf-8")).hexdigest()


class RawDocumentStore:
    """Manages an embedded SQLite database that stores raw binary files as BLOBs."""

    def __init__(self, base_path: str, db_name: str = "Raw_Documents.sqlite"):
        self.db_path = os.path.join(base_path, db_name)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Returns the active SQLite connection."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")
        return self._conn

    def open(self) -> None:
        """Opens the SQLite connection and sets optimized BLOB Pragmas."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)

        # Optimize for BLOB storage, high concurrency, and strict ACID compliance
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")  # High concurrency & ACID Write-Ahead Log
        self._conn.execute(
            "PRAGMA synchronous = NORMAL;"
        )  # Extremely fast in WAL mode while remaining safe
        self._conn.execute("PRAGMA cache_size = -64000;")  # 64 MB of RAM for SQLite page cache
        self._conn.execute("PRAGMA mmap_size = 2147483648;")  # 2 GB of memory-mapped I/O
        self._conn.execute("PRAGMA temp_store = MEMORY;")  # Store temp indices/tables in RAM

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

    def load_binaries(self, actionable_files: dict[str, list[str]]) -> None:
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
                    file_hash = compute_file_hash(filepath)

                    try:
                        file_size = os.path.getsize(filepath)
                    except OSError:
                        file_size = 0

                    file_id = generate_file_id(filepath)
                    now = datetime.now().isoformat()

                    self._conn.execute(
                        """
                        INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_hash, file_size_bytes, sync_status, first_ingested, last_ingested)
                        VALUES (?, ?, ?, ?, ?, ?, 'PENDING_BRONZE', ?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            file_name = excluded.file_name,
                            relative_path = excluded.relative_path,
                            file_category = excluded.file_category,
                            file_hash = excluded.file_hash,
                            file_size_bytes = excluded.file_size_bytes,
                            sync_status = excluded.sync_status,
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
                msg = f"  -> Raw Store [{category}]: Ingested {len(success_files)} file(s)."
                logger.info(msg)
                logger.debug(f"  -> Raw Store [{category}] Details: {', '.join(success_files)}")

        if total_count > 0:
            msg = f"Raw Store: Successfully ingested a total of {total_count} binary file(s)."
            logger.info(msg)

    def inject_virtual_file(self, filename: str, category: str, raw_bytes: bytes) -> str:
        """Injects in-memory bytes directly into the Raw Store without requiring a physical disk file.
        Returns the synthetic filepath used for registration."""
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")

        synthetic_filepath = f"virtual://{category}/{filename}"
        unique_path = synthetic_filepath.replace("\\", "/")
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_size = len(raw_bytes)
        file_id = generate_file_id(synthetic_filepath)
        now = datetime.now().isoformat()

        self._conn.execute(
            """
            INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_hash, file_size_bytes, sync_status, first_ingested, last_ingested)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING_BRONZE', ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                file_name = excluded.file_name,
                relative_path = excluded.relative_path,
                file_category = excluded.file_category,
                file_hash = excluded.file_hash,
                file_size_bytes = excluded.file_size_bytes,
                sync_status = excluded.sync_status,
                last_ingested = excluded.last_ingested
            """,
            (file_id, filename, unique_path, category, file_hash, file_size, now, now),
        )

        self._conn.execute(
            """
            INSERT INTO raw_payloads (file_id, file_bytes)
            VALUES (?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                file_bytes = excluded.file_bytes
            """,
            (file_id, raw_bytes),
        )
        return synthetic_filepath

    def get_file_bytes(self, filepath: str) -> bytes | None:
        """Retrieves raw bytes for a file by its unique relative path."""
        if not self._conn:
            return None
        unique_path = filepath.replace("\\", "/")
        row = self._conn.execute(
            """
            SELECT p.file_bytes 
            FROM raw_payloads p
            JOIN raw_file_registry r ON p.file_id = r.file_id
            WHERE r.relative_path = ?
            """,
            (unique_path,),
        ).fetchone()
        return row[0] if row else None

    def get_pending_files(self) -> dict[str, list[str]]:
        """Returns a dictionary of category -> list of file paths that are PENDING_BRONZE."""
        if not self._conn:
            return {}
        rows = self._conn.execute(
            "SELECT file_category, relative_path FROM raw_file_registry WHERE sync_status = 'PENDING_BRONZE'"
        ).fetchall()

        pending: dict[str, list[str]] = {}
        for category, path in rows:
            pending.setdefault(category, []).append(path)
        return pending

    def mark_synced(self, filepaths: list[str]) -> None:
        """Marks a list of files as SYNCED."""
        if not self._conn or not filepaths:
            return
        unique_paths = [p.replace("\\", "/") for p in filepaths]
        placeholders = ",".join("?" * len(unique_paths))
        self._conn.execute(
            f"UPDATE raw_file_registry SET sync_status = 'SYNCED' WHERE relative_path IN ({placeholders})",
            unique_paths,
        )

    def get_all_registry(self) -> dict[str, str]:
        """Returns a dict of relative_path -> file_hash."""
        if not self._conn:
            return {}
        rows = self._conn.execute(
            "SELECT relative_path, file_hash FROM raw_file_registry"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
