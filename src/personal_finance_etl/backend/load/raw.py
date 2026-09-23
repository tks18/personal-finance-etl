import hashlib
import os
import sqlite3
from datetime import datetime

from personal_finance_etl.backend.config.settings import FileHashPolicy
from personal_finance_etl.backend.utils.logger import logger

RAW_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_file_registry (
    file_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    file_category TEXT NOT NULL,
    file_type TEXT,
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
    "column_master": "csv",
}


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
    """The absolute source of truth for file state management.

    Manages an embedded SQLite WAL-optimized database that:
      - Stores raw binary file payloads as BLOBs.
      - Tracks file change detection (new, modified, obsolete) via SHA-256 hashing.
      - Returns the exact actionable file set the pipeline must process.
    """

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

    # ─────────────────────────────────────────────────────────────────────
    # PRIMARY SYNC ENTRY POINT — The Source of Truth for all Phase 1 logic
    # ─────────────────────────────────────────────────────────────────────

    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
        """The single, authoritative Phase 1 method.

        Compares discovered disk files against the internal SQLite registry to
        determine what is new or changed, prunes obsolete full-replace blobs,
        ingests new/changed binaries into the Raw Store, and returns the exact
        set of actionable files the pipeline must process.

        Returns:
            (new_files, changed_files, files_skipped)
        """
        if not self._conn:
            raise RuntimeError("RawDocumentStore connection not opened.")

        registry = self._get_registry()

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}

        for category, filepaths in discovered_files.items():
            new_files[category] = []
            changed_files[category] = []

            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = getattr(hash_policy, file_type, False)

            for filepath in filepaths:
                unique_path = filepath.replace("\\", "/")
                if unique_path not in registry:
                    new_files[category].append(filepath)
                elif should_check_hash:
                    current_hash = compute_file_hash(filepath)
                    if current_hash != registry[unique_path]:
                        changed_files[category].append(filepath)

        # Log the discovery breakdown
        logger.info("File Tracker Discovery Breakdown:")
        for category in discovered_files.keys():
            n_new = len(new_files.get(category, []))
            n_mod = len(changed_files.get(category, []))
            if n_new == 0 and n_mod == 0:
                logger.info(f"  -> [{category}] 0 actionable file(s) detected. Cache intact.")
            else:
                if n_new > 0:
                    logger.info(f"  -> [{category}] {n_new} new file(s) detected.")
                if n_mod > 0:
                    logger.info(f"  -> [{category}] {n_mod} modified file(s) detected.")

        # Prune obsolete full-replace category blobs before ingesting
        for cat in full_replace_categories:
            self._prune_category(cat, discovered_files.get(cat, []))

        # Ingest new/changed binaries into the Raw Store
        actionable_all: dict[str, list[str]] = {
            k: new_files.get(k, []) + changed_files.get(k, []) for k in discovered_files.keys()
        }
        self._ingest_binaries(actionable_all)

        files_skipped = sum(len(f) for f in discovered_files.values()) - (
            sum(len(f) for f in new_files.values()) + sum(len(f) for f in changed_files.values())
        )

        return new_files, changed_files, files_skipped

    def _get_registry(self) -> dict[str, str]:
        """Returns dict of relative_path -> file_hash for all known files."""
        rows = self.conn.execute(
            "SELECT relative_path, file_hash FROM raw_file_registry"
        ).fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    def _prune_category(self, category: str, keep_filepaths: list[str]) -> None:
        """Deletes all files in a full-replace category except the current ones."""
        unique_paths = [p.replace("\\", "/") for p in keep_filepaths]

        if unique_paths:
            placeholders = ",".join("?" * len(unique_paths))
            rows = self.conn.execute(
                f"SELECT file_id FROM raw_file_registry WHERE file_category = ? AND relative_path NOT IN ({placeholders})",
                [category] + unique_paths,
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT file_id FROM raw_file_registry WHERE file_category = ?", [category]
            ).fetchall()

        file_ids_to_delete = [str(r[0]) for r in rows]

        if file_ids_to_delete:
            p_ids = ",".join("?" * len(file_ids_to_delete))
            self.conn.execute(
                f"DELETE FROM raw_payloads WHERE file_id IN ({p_ids})", file_ids_to_delete
            )
            self.conn.execute(
                f"DELETE FROM raw_file_registry WHERE file_id IN ({p_ids})", file_ids_to_delete
            )
            logger.info(
                f"Raw Store: Pruned {len(file_ids_to_delete)} obsolete file(s) from category '{category}'."
            )

    def _ingest_binaries(self, actionable_files: dict[str, list[str]]) -> None:
        """Reads actionable disk files and upserts them as BLOBs into the Raw Store."""
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
                    file_type = FILE_TYPE_MAP.get(category, "csv")
                    now = datetime.now().isoformat()

                    self.conn.execute(
                        """
                        INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, sync_status, first_ingested, last_ingested)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING_BRONZE', ?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET
                            file_name = excluded.file_name,
                            relative_path = excluded.relative_path,
                            file_category = excluded.file_category,
                            file_type = excluded.file_type,
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
                            file_type,
                            file_hash,
                            file_size,
                            now,
                            now,
                        ),
                    )

                    self.conn.execute(
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

    # ─────────────────────────────────────────────────────────────────────
    # VIRTUAL FILE INJECTION — For in-memory Parquet chunks (Benchmark)
    # ─────────────────────────────────────────────────────────────────────

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
            INSERT INTO raw_file_registry (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, sync_status, first_ingested, last_ingested)
            VALUES (?, ?, ?, ?, 'parquet', ?, ?, 'PENDING_BRONZE', ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                file_name = excluded.file_name,
                relative_path = excluded.relative_path,
                file_category = excluded.file_category,
                file_type = excluded.file_type,
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

    # ─────────────────────────────────────────────────────────────────────
    # READ OPERATIONS
    # ─────────────────────────────────────────────────────────────────────

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
            pending.setdefault(str(category), []).append(str(path))
        return pending

    def get_all_paths_by_category(self) -> dict[str, list[str]]:
        """Returns all registered relative_paths grouped by category."""
        if not self._conn:
            return {}
        rows = self._conn.execute(
            "SELECT file_category, relative_path FROM raw_file_registry"
        ).fetchall()
        result: dict[str, list[str]] = {}
        for cat, path in rows:
            result.setdefault(str(cat), []).append(str(path))
        return result

    def get_all_registry(self) -> dict[str, str]:
        """Returns a dict of relative_path -> file_hash."""
        if not self._conn:
            return {}
        rows = self._conn.execute(
            "SELECT relative_path, file_hash FROM raw_file_registry"
        ).fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    # ─────────────────────────────────────────────────────────────────────
    # STATE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def mark_synced(self, filepaths: list[str]) -> None:
        """Marks a list of files as SYNCED in the registry."""
        if not self._conn or not filepaths:
            return
        unique_paths = [p.replace("\\", "/") for p in filepaths]
        placeholders = ",".join("?" * len(unique_paths))
        self._conn.execute(
            f"UPDATE raw_file_registry SET sync_status = 'SYNCED' WHERE relative_path IN ({placeholders})",
            unique_paths,
        )
