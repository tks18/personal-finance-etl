import hashlib
import os
from datetime import datetime

from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager
from personal_finance_etl.backend.load.control_plane.utils import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
)
from personal_finance_etl.backend.utils.logger import logger


class ArtifactRepository:
    def __init__(self, db: SQLiteManager):
        self.db = db

    def get_registry(self) -> dict[str, str]:
        cursor = self.db.conn.execute("SELECT relative_path, file_hash FROM cp_file_registry")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def prune_category(self, category: str, keep_filepaths: list[str]) -> None:
        keep_paths = [p.replace("\\", "/") for p in keep_filepaths]
        cursor = self.db.conn.execute(
            "SELECT file_id, relative_path FROM cp_file_registry WHERE file_category = ?",
            (category,),
        )
        to_delete: list[str] = []
        for file_id, relative_path in cursor.fetchall():
            if relative_path not in keep_paths:
                to_delete.append(file_id)

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            self.db.conn.execute(
                f"DELETE FROM cp_file_registry WHERE file_id IN ({placeholders})", to_delete
            )
            logger.info(f"  -> Pruned {len(to_delete)} obsolete files from category '{category}'")

    def ingest_binaries(self, actionable_files: dict[str, list[str]]) -> None:
        now = datetime.now().isoformat()
        total_count = 0

        for category, filepaths in actionable_files.items():
            if not filepaths:
                continue
            file_type = FILE_TYPE_MAP.get(category, "csv")
            success_files: list[str] = []

            for filepath in filepaths:
                file_id = generate_file_id(filepath)
                filename = os.path.basename(filepath)
                file_hash = compute_file_hash(filepath)
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

                try:
                    with open(filepath, "rb") as f:
                        raw_bytes = f.read()

                    self.db.conn.execute(
                        """
                        INSERT INTO cp_file_registry (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, first_ingested, last_ingested)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(relative_path) DO UPDATE SET
                            file_hash = excluded.file_hash,
                            file_size_bytes = excluded.file_size_bytes,
                            last_ingested = excluded.last_ingested,
                            sync_status = 'PENDING_BRONZE'
                        """,
                        (
                            file_id,
                            filename,
                            filepath.replace("\\", "/"),
                            category,
                            file_type,
                            file_hash,
                            file_size,
                            now,
                            now,
                        ),
                    )

                    self.db.conn.execute(
                        """
                        INSERT INTO cp_file_payloads (file_id, file_bytes)
                        VALUES (?, ?)
                        ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes
                        """,
                        (file_id, raw_bytes),
                    )
                    success_files.append(filename)
                    total_count += 1
                except Exception as e:
                    logger.error(f"Raw Store: Failed to ingest {filepath}: {e}")
                    raise e

            if success_files:
                logger.info(
                    f"  -> ArtifactRepo [{category}]: Ingested {len(success_files)} file(s)."
                )

    def inject_virtual_file(self, filename: str, category: str, raw_bytes: bytes) -> str:
        now = datetime.now().isoformat()
        filepath = f"virtual://{category}/{filename}"
        file_id = generate_file_id(filepath)
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_type = FILE_TYPE_MAP.get(category, "csv")

        self.db.conn.execute(
            """
            INSERT INTO cp_file_registry (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, first_ingested, last_ingested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                file_size_bytes = excluded.file_size_bytes,
                last_ingested = excluded.last_ingested,
                sync_status = 'PENDING_BRONZE'
            """,
            (
                file_id,
                filename,
                filepath.replace("\\", "/"),
                category,
                file_type,
                file_hash,
                len(raw_bytes),
                now,
                now,
            ),
        )

        self.db.conn.execute(
            """
            INSERT INTO cp_file_payloads (file_id, file_bytes)
            VALUES (?, ?)
            ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes
            """,
            (file_id, raw_bytes),
        )
        return filepath

    def get_file_bytes(self, filepath: str) -> bytes | None:
        file_id = generate_file_id(filepath)
        cursor = self.db.conn.execute(
            "SELECT file_bytes FROM cp_file_payloads WHERE file_id = ?", (file_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_pending_files(self) -> dict[str, list[str]]:
        cursor = self.db.conn.execute(
            "SELECT file_category, relative_path FROM cp_file_registry WHERE sync_status = 'PENDING_BRONZE'"
        )
        pending: dict[str, list[str]] = {}
        for category, path in cursor.fetchall():
            pending.setdefault(category, []).append(path)
        return pending

    def get_all_paths_by_category(self) -> dict[str, list[str]]:
        cursor = self.db.conn.execute("SELECT file_category, relative_path FROM cp_file_registry")
        result: dict[str, list[str]] = {}
        for cat, path in cursor.fetchall():
            result.setdefault(cat, []).append(path)
        return result

    def get_all_registry(self) -> dict[str, str]:
        cursor = self.db.conn.execute("SELECT relative_path, sync_status FROM cp_file_registry")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def mark_synced(self, filepaths: list[str]) -> None:
        if not filepaths:
            return
        unique_paths = [p.replace("\\", "/") for p in filepaths]
        placeholders = ",".join("?" * len(unique_paths))
        self.db.conn.execute(
            f"UPDATE cp_file_registry SET sync_status = 'SYNCED' WHERE relative_path IN ({placeholders})",
            unique_paths,
        )
