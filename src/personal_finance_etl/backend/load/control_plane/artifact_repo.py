import hashlib
import os
import uuid
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
        self.active_run_id: str | None = None

    def get_registry(self) -> dict[str, tuple[str, str]]:
        cursor = self.db.conn.execute(
            "SELECT relative_path, file_hash, file_category FROM cp_file_registry"
        )
        return {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    def get_registry_with_status(self) -> dict[str, tuple[str, str, str]]:
        """Return ``{path: (hash, category, sync_status)}`` for all registered files.

        Used by :class:`FileSyncService` to detect HEALED (previously REMOVED
        files that reappeared) and newly REMOVED files.
        """
        cursor = self.db.conn.execute(
            "SELECT relative_path, file_hash, file_category, sync_status FROM cp_file_registry"
        )
        return {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}

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

    def migrate_identity(self, old_rel_path: str, new_filepath: str) -> None:
        """Migrates all path-derived identity for a renamed file transactionally."""
        new_rel_path = new_filepath.replace("\\", "/")
        new_file_id = generate_file_id(new_rel_path)
        new_file_name = os.path.basename(new_filepath)
        old_file_id = generate_file_id(old_rel_path)

        # 1. Fetch old registry row
        row = self.db.conn.execute(
            """
            SELECT file_category, file_type, file_hash, file_size_bytes, 
                   first_seen_run_id, first_seen_at, last_seen_run_id, last_seen_at, sync_status 
            FROM cp_file_registry WHERE relative_path = ?
            """,
            (old_rel_path,),
        ).fetchone()

        if not row:
            return

        # 2. Insert new registry row
        self.db.conn.execute(
            """
            INSERT INTO cp_file_registry 
            (file_id, file_name, relative_path, file_category, file_type, 
             file_hash, file_size_bytes, first_seen_run_id, first_seen_at, 
             last_seen_run_id, last_seen_at, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_file_id, new_file_name, new_rel_path, *row),
        )

        # 3. Update payloads to point to new identity
        self.db.conn.execute(
            """
            UPDATE cp_file_payloads
            SET file_id = ?
            WHERE file_id = ?
            """,
            (new_file_id, old_file_id),
        )

        now = datetime.now().isoformat()
        if self.active_run_id:
            self.db.conn.execute(
                """
                INSERT INTO cp_artifact_run_events 
                (event_id, run_id, file_id, event_type, event_at, observed_path, content_hash, event_reason)
                VALUES (?, ?, ?, 'RENAMED', ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    self.active_run_id,
                    new_file_id,
                    now,
                    new_rel_path,
                    row[2],
                    f"Migrated from {old_rel_path}",
                ),
            )

        # 4. Delete old registry row
        self.db.conn.execute(
            "DELETE FROM cp_file_registry WHERE relative_path = ?", (old_rel_path,)
        )

    def ingest_binaries(
        self,
        actionable_files: dict[str, list[str]],
        new_files: dict[str, list[str]] | None = None,
        changed_files: dict[str, list[str]] | None = None,
    ) -> None:
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
                        INSERT INTO cp_file_registry (
                            file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, 
                            first_seen_run_id, first_seen_at, last_seen_run_id, last_seen_at, last_changed_run_id, last_changed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(relative_path) DO UPDATE SET
                            file_hash = excluded.file_hash,
                            file_size_bytes = excluded.file_size_bytes,
                            last_seen_run_id = excluded.last_seen_run_id,
                            last_seen_at = excluded.last_seen_at,
                            last_changed_run_id = excluded.last_changed_run_id,
                            last_changed_at = excluded.last_changed_at,
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
                            self.active_run_id,
                            now,
                            self.active_run_id,
                            now,
                            self.active_run_id,
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

                    if self.active_run_id:
                        rel_path = filepath.replace("\\", "/")
                        is_new = rel_path in (new_files or {}).get(category, [])
                        event_type = "DISCOVERED" if is_new else "CHANGED"
                        self.db.conn.execute(
                            """
                            INSERT INTO cp_artifact_run_events 
                            (event_id, run_id, file_id, event_type, event_at, observed_path, content_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(uuid.uuid4()),
                                self.active_run_id,
                                file_id,
                                event_type,
                                now,
                                rel_path,
                                file_hash,
                            ),
                        )
                    logger.debug(
                        f"[SQLITE:QUERY] Upserted binary payload for '{filename}' ({file_size} bytes)."
                    )
                    success_files.append(filename)
                    total_count += 1
                except Exception as e:
                    logger.exception(f"[INGEST:ERROR] Failed to ingest {filepath}:")
                    raise e

            if success_files:
                logger.debug(
                    f"[INGEST:DETAIL] Vaulted {len(success_files)} file(s) into category '{category}'."
                )

        if total_count > 0:
            logger.info(f"[INGEST] Safely vaulted {total_count} payloads into SQLite Raw Store.")

    def inject_virtual_file(self, filename: str, category: str, raw_bytes: bytes) -> str:
        now = datetime.now().isoformat()
        filepath = f"virtual://{category}/{filename}"
        file_id = generate_file_id(filepath)
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_type = FILE_TYPE_MAP.get(category, "csv")

        self.db.conn.execute(
            """
            INSERT INTO cp_file_registry (
                file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, 
                first_seen_run_id, first_seen_at, last_seen_run_id, last_seen_at, last_changed_run_id, last_changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                file_size_bytes = excluded.file_size_bytes,
                last_seen_run_id = excluded.last_seen_run_id,
                last_seen_at = excluded.last_seen_at,
                last_changed_run_id = excluded.last_changed_run_id,
                last_changed_at = excluded.last_changed_at,
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
                self.active_run_id,
                now,
                self.active_run_id,
                now,
                self.active_run_id,
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
        now = datetime.now().isoformat()
        if self.active_run_id:
            for p in unique_paths:
                file_id = generate_file_id(p)
                self.db.conn.execute(
                    """
                    INSERT INTO cp_artifact_run_events 
                    (event_id, run_id, file_id, event_type, event_at, observed_path, event_reason)
                    VALUES (?, ?, ?, 'SYNCED', ?, ?, 'Bronze Sync Successful')
                    """,
                    (str(uuid.uuid4()), self.active_run_id, file_id, now, p),
                )

        self.db.conn.execute(
            f"UPDATE cp_file_registry SET sync_status = 'SYNCED', last_synced_run_id = ?, last_synced_at = ? WHERE relative_path IN ({placeholders})",
            [self.active_run_id, now] + unique_paths,
        )

    def mark_healed(self, filepaths: list[str]) -> None:
        """Record a HEALED event for files that re-appeared after a prior REMOVED/MISSING state."""
        if not filepaths:
            return
        now = datetime.now().isoformat()
        for p in [fp.replace("\\", "/") for fp in filepaths]:
            file_id = generate_file_id(p)
            if self.active_run_id:
                self.db.conn.execute(
                    """
                    INSERT INTO cp_artifact_run_events
                    (event_id, run_id, file_id, event_type, event_at, observed_path, event_reason)
                    VALUES (?, ?, ?, 'HEALED', ?, ?, 'File re-appeared after prior removal')
                    """,
                    (str(uuid.uuid4()), self.active_run_id, file_id, now, p),
                )
            self.db.conn.execute(
                "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                (p,),
            )
        logger.info(f"[ARTIFACT] Marked {len(filepaths)} file(s) as HEALED.")

    def mark_removed(self, filepaths: list[str]) -> None:
        """Record a REMOVED event for files that are no longer present on disk."""
        if not filepaths:
            return
        now = datetime.now().isoformat()
        for p in [fp.replace("\\", "/") for fp in filepaths]:
            file_id = generate_file_id(p)
            if self.active_run_id:
                self.db.conn.execute(
                    """
                    INSERT INTO cp_artifact_run_events
                    (event_id, run_id, file_id, event_type, event_at, observed_path, event_reason)
                    VALUES (?, ?, ?, 'REMOVED', ?, ?, 'File no longer present on disk')
                    """,
                    (str(uuid.uuid4()), self.active_run_id, file_id, now, p),
                )
            self.db.conn.execute(
                "UPDATE cp_file_registry SET sync_status = 'REMOVED' WHERE relative_path = ?",
                (p,),
            )
        logger.info(f"[ARTIFACT] Marked {len(filepaths)} file(s) as REMOVED.")
