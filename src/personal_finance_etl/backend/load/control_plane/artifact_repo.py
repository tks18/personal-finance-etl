from __future__ import annotations

import os
import uuid
from datetime import datetime

from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager
from personal_finance_etl.backend.load.control_plane.utils import (
    FILE_TYPE_MAP,
    generate_file_id,
    hash_bytes,
    normalize_path,
)
from personal_finance_etl.backend.utils.logger import logger


class ArtifactRepository:
    """Persistence and lifecycle transitions for source-file artifacts."""

    def __init__(self, db: SQLiteManager):
        self.db = db
        self.active_run_id: str | None = None

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _insert_event(
        self,
        *,
        file_id: str,
        event_type: str,
        event_at: str,
        path: str | None,
        content_hash: str | None = None,
        previous_status: str | None = None,
        new_status: str | None = None,
        reason: str | None = None,
    ) -> None:
        if not self.active_run_id:
            return
        self.db.conn.execute(
            """INSERT INTO cp_artifact_run_events
               (event_id, run_id, file_id, event_type, event_at, observed_path,
                content_hash, previous_status, new_status, event_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                self.active_run_id,
                file_id,
                event_type,
                event_at,
                path,
                content_hash,
                previous_status,
                new_status,
                reason,
            ),
        )

    def get_registry(self) -> dict[str, tuple[str, str]]:
        cursor = self.db.conn.execute(
            "SELECT relative_path, file_hash, file_category FROM cp_file_registry"
        )
        return {
            normalize_path(path): (file_hash, category)
            for path, file_hash, category in cursor.fetchall()
        }

    def get_registry_with_status(self) -> dict[str, tuple[str, str, str]]:
        """Return canonical path -> (hash, category, status), retaining historical rows."""
        cursor = self.db.conn.execute(
            "SELECT relative_path, file_hash, file_category, sync_status FROM cp_file_registry"
        )
        result: dict[str, tuple[str, str, str]] = {}
        for path, file_hash, category, status in cursor.fetchall():
            canonical = normalize_path(path)
            if canonical in result:
                raise RuntimeError(f"Duplicate canonical artifact path in registry: {canonical}")
            result[canonical] = (file_hash, category, status or "PENDING_BRONZE")
        return result

    def has_payload(self, filepath: str) -> bool:
        path = normalize_path(filepath)
        row = self.db.conn.execute(
            """SELECT 1 FROM cp_file_payloads p
               JOIN cp_file_registry r ON r.file_id = p.file_id
               WHERE r.relative_path = ? AND p.file_bytes IS NOT NULL""",
            (path,),
        ).fetchone()
        return row is not None

    def prune_category(self, category: str, keep_filepaths: list[str]) -> None:
        """Prune payloads for missing files, never hard-delete audit identities."""
        keep_paths = {normalize_path(path) for path in keep_filepaths}
        rows = self.db.conn.execute(
            "SELECT file_id, relative_path FROM cp_file_registry WHERE file_category = ?",
            (category,),
        ).fetchall()
        obsolete_ids = [file_id for file_id, path in rows if normalize_path(path) not in keep_paths]
        if not obsolete_ids:
            return
        with self.db.atomic():
            for offset in range(0, len(obsolete_ids), 500):
                batch = obsolete_ids[offset : offset + 500]
                placeholders = ",".join("?" for _ in batch)
                self.db.conn.execute(
                    f"DELETE FROM cp_file_payloads WHERE file_id IN ({placeholders})", batch
                )
        logger.info(
            "[ARTIFACT] Pruned payloads for %d obsolete files from category '%s'; "
            "registry identities and historical events retained.",
            len(obsolete_ids),
            category,
        )

    def migrate_identity(
        self,
        old_rel_path: str,
        new_filepath: str,
        *,
        observed_hash: str | None = None,
        file_size_bytes: int | None = None,
    ) -> bool:
        """Atomically move an artifact's current identity, retaining the old history.

        Returns False if the source has no payload to transfer. The caller should
        ingest the destination as a new artifact rather than claiming a successful rename.
        """
        old_path = normalize_path(old_rel_path)
        new_path = normalize_path(new_filepath)
        if old_path == new_path:
            return True

        row = self.db.conn.execute(
            """SELECT file_id, file_name, file_category, file_type, file_hash,
                      file_size_bytes, first_seen_run_id, first_seen_at,
                      last_seen_run_id, last_seen_at, last_changed_run_id,
                      last_changed_at, last_synced_run_id, last_synced_at, sync_status
               FROM cp_file_registry WHERE relative_path = ?""",
            (old_path,),
        ).fetchone()
        if not row:
            return False

        (
            old_id,
            _old_name,
            category,
            file_type,
            old_hash,
            old_size,
            first_run,
            first_at,
            last_run,
            _,
            changed_run,
            changed_at,
            synced_run,
            synced_at,
            old_status,
        ) = row
        payload_row = self.db.conn.execute(
            "SELECT file_bytes FROM cp_file_payloads WHERE file_id = ?", (old_id,)
        ).fetchone()
        if not payload_row or payload_row[0] is None:
            logger.warning(
                "[SYNC:RENAME] Cannot migrate %s because its payload is missing; "
                "destination will be ingested as new.",
                old_path,
            )
            return False

        new_id = generate_file_id(new_path)
        conflict = self.db.conn.execute(
            "SELECT file_id FROM cp_file_registry WHERE relative_path = ? OR file_id = ?",
            (new_path, new_id),
        ).fetchone()
        if conflict:
            raise ValueError(
                f"Cannot migrate artifact to already-registered path or ID: {new_path}"
            )

        now = self._now()
        new_status = old_status or "PENDING_BRONZE"
        current_hash = observed_hash or old_hash
        current_size = file_size_bytes if file_size_bytes is not None else old_size
        with self.db.atomic():
            self.db.conn.execute(
                """INSERT INTO cp_file_registry (
                       file_id, file_name, relative_path, file_category, file_type, file_hash,
                       file_size_bytes, first_seen_run_id, first_seen_at, last_seen_run_id,
                       last_seen_at, last_changed_run_id, last_changed_at, last_synced_run_id,
                       last_synced_at, sync_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id,
                    new_path.rsplit("/", 1)[-1],
                    new_path,
                    category,
                    file_type,
                    current_hash,
                    current_size,
                    first_run,
                    first_at,
                    self.active_run_id or last_run,
                    now,
                    changed_run,
                    changed_at,
                    synced_run,
                    synced_at,
                    new_status,
                ),
            )
            self.db.conn.execute(
                "INSERT INTO cp_file_payloads (file_id, file_bytes) VALUES (?, ?) "
                "ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes",
                (new_id, payload_row[0]),
            )
            self.db.conn.execute("DELETE FROM cp_file_payloads WHERE file_id = ?", (old_id,))
            self._insert_event(
                file_id=new_id,
                event_type="RENAMED",
                event_at=now,
                path=new_path,
                content_hash=current_hash,
                previous_status=old_status,
                new_status=new_status,
                reason=f"Migrated identity from {old_path}",
            )
            self.db.conn.execute(
                "UPDATE cp_file_registry SET sync_status = 'REMOVED' WHERE file_id = ?",
                (old_id,),
            )
        return True

    def _upsert_registry(
        self,
        *,
        filepath: str,
        filename: str,
        category: str,
        file_type: str,
        file_hash: str,
        file_size: int,
        now: str,
    ) -> tuple[str, str | None]:
        """Upsert metadata without assuming the persisted ID is path-derived."""
        path = normalize_path(filepath)
        existing = self.db.conn.execute(
            "SELECT file_id, sync_status FROM cp_file_registry WHERE relative_path = ?", (path,)
        ).fetchone()
        if existing:
            file_id, previous_status = existing
            self.db.conn.execute(
                """UPDATE cp_file_registry
                   SET file_name = ?, file_category = ?, file_type = ?, file_hash = ?,
                       file_size_bytes = ?, last_seen_run_id = COALESCE(?, last_seen_run_id), last_seen_at = ?,
                       last_changed_run_id = COALESCE(?, last_changed_run_id), last_changed_at = ?, sync_status = 'PENDING_BRONZE'
                   WHERE relative_path = ?""",
                (
                    filename,
                    category,
                    file_type,
                    file_hash,
                    file_size,
                    self.active_run_id,
                    now,
                    self.active_run_id,
                    now,
                    path,
                ),
            )
            return file_id, previous_status

        file_id = generate_file_id(path)
        self.db.conn.execute(
            """INSERT INTO cp_file_registry (
                   file_id, file_name, relative_path, file_category, file_type, file_hash,
                   file_size_bytes, first_seen_run_id, first_seen_at, last_seen_run_id,
                   last_seen_at, last_changed_run_id, last_changed_at, sync_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_BRONZE')""",
            (
                file_id,
                filename,
                path,
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
        return file_id, None

    def ingest_binaries(
        self,
        actionable_files: dict[str, list[str]],
        new_files: dict[str, list[str]] | None = None,
        changed_files: dict[str, list[str]] | None = None,
    ) -> None:
        new_paths = {normalize_path(path) for paths in (new_files or {}).values() for path in paths}
        changed_paths = {
            normalize_path(path) for paths in (changed_files or {}).values() for path in paths
        }
        total_count = 0
        for category, filepaths in actionable_files.items():
            file_type = FILE_TYPE_MAP.get(category, "csv")
            for filepath in filepaths:
                path = normalize_path(filepath)
                try:
                    # Read once so the persisted bytes and their hash always describe the same content.
                    with open(filepath, "rb") as file_handle:
                        raw_bytes = file_handle.read()
                    digest = hash_bytes(raw_bytes)
                    size = len(raw_bytes)
                    now = self._now()
                    filename = os.path.basename(path)
                    with self.db.atomic():
                        file_id, previous_status = self._upsert_registry(
                            filepath=path,
                            filename=filename,
                            category=category,
                            file_type=file_type,
                            file_hash=digest,
                            file_size=size,
                            now=now,
                        )
                        self.db.conn.execute(
                            "INSERT INTO cp_file_payloads (file_id, file_bytes) VALUES (?, ?) "
                            "ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes",
                            (file_id, raw_bytes),
                        )
                        if path in new_paths:
                            event_type = "DISCOVERED"
                        elif path in changed_paths:
                            event_type = "CHANGED"
                        else:
                            event_type = "REINGESTED"
                        self._insert_event(
                            file_id=file_id,
                            event_type=event_type,
                            event_at=now,
                            path=path,
                            content_hash=digest,
                            previous_status=previous_status,
                            new_status="PENDING_BRONZE",
                            reason="Binary payload stored in control-plane vault",
                        )
                    total_count += 1
                except Exception:
                    logger.exception("[INGEST:ERROR] Failed to ingest %s", filepath)
                    raise
        if total_count:
            logger.info("[INGEST] Safely vaulted %d payloads into SQLite Raw Store.", total_count)

    def inject_virtual_file(self, filename: str, category: str, raw_bytes: bytes) -> str:
        path = normalize_path(f"virtual://{category}/{filename}")
        now = self._now()
        file_type = FILE_TYPE_MAP.get(category, "csv")
        digest = hash_bytes(raw_bytes)
        with self.db.atomic():
            file_id, previous_status = self._upsert_registry(
                filepath=path,
                filename=filename,
                category=category,
                file_type=file_type,
                file_hash=digest,
                file_size=len(raw_bytes),
                now=now,
            )
            self.db.conn.execute(
                "INSERT INTO cp_file_payloads (file_id, file_bytes) VALUES (?, ?) "
                "ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes",
                (file_id, raw_bytes),
            )
            self._insert_event(
                file_id=file_id,
                event_type="VIRTUAL_UPDATED" if previous_status else "VIRTUAL_CREATED",
                event_at=now,
                path=path,
                content_hash=digest,
                previous_status=previous_status,
                new_status="PENDING_BRONZE",
                reason="Virtual configuration artifact injected",
            )
        return path

    def get_file_bytes(self, filepath: str) -> bytes | None:
        path = normalize_path(filepath)
        row = self.db.conn.execute(
            """SELECT p.file_bytes FROM cp_file_payloads p
               JOIN cp_file_registry r ON r.file_id = p.file_id
               WHERE r.relative_path = ?""",
            (path,),
        ).fetchone()
        return row[0] if row else None

    def get_pending_files(self) -> dict[str, list[str]]:
        cursor = self.db.conn.execute(
            "SELECT file_category, relative_path FROM cp_file_registry WHERE sync_status = 'PENDING_BRONZE' ORDER BY file_category, relative_path"
        )
        pending: dict[str, list[str]] = {}
        for category, path in cursor.fetchall():
            pending.setdefault(category, []).append(normalize_path(path))
        return pending

    def get_all_paths_by_category(self) -> dict[str, list[str]]:
        cursor = self.db.conn.execute(
            "SELECT file_category, relative_path FROM cp_file_registry ORDER BY file_category, relative_path"
        )
        result: dict[str, list[str]] = {}
        for category, path in cursor.fetchall():
            result.setdefault(category, []).append(normalize_path(path))
        return result

    def get_all_registry(self) -> dict[str, str]:
        cursor = self.db.conn.execute("SELECT relative_path, sync_status FROM cp_file_registry")
        return {normalize_path(path): status for path, status in cursor.fetchall()}

    def mark_synced(self, filepaths: list[str]) -> None:
        if not filepaths:
            return
        now = self._now()
        marked = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    "SELECT file_id, sync_status, last_synced_run_id, file_hash FROM cp_file_registry WHERE relative_path = ?",
                    (path,),
                ).fetchone()
                if not row:
                    logger.warning("[ARTIFACT] Cannot mark unknown file as SYNCED: %s", path)
                    continue
                file_id, previous_status, last_run, digest = row
                if previous_status == "SYNCED" and last_run == self.active_run_id:
                    continue
                self._insert_event(
                    file_id=file_id,
                    event_type="SYNCED",
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=previous_status,
                    new_status="SYNCED",
                    reason="Bronze Sync Successful",
                )
                self.db.conn.execute(
                    "UPDATE cp_file_registry SET sync_status = 'SYNCED', last_synced_run_id = COALESCE(?, last_synced_run_id), last_synced_at = ? WHERE relative_path = ?",
                    (self.active_run_id, now, path),
                )
                marked += 1
        if marked:
            logger.debug("[ARTIFACT] Marked %d file(s) as SYNCED.", marked)

    def mark_healed(self, filepaths: list[str]) -> None:
        if not filepaths:
            return
        now = self._now()
        healed = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    "SELECT file_id, sync_status, file_hash FROM cp_file_registry WHERE relative_path = ?",
                    (path,),
                ).fetchone()
                if not row or row[1] != "REMOVED":
                    continue
                file_id, previous_status, digest = row
                self._insert_event(
                    file_id=file_id,
                    event_type="HEALED",
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=previous_status,
                    new_status="PENDING_BRONZE",
                    reason="File re-appeared after prior removal",
                )
                self.db.conn.execute(
                    "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE', last_seen_run_id = COALESCE(?, last_seen_run_id), last_seen_at = ? WHERE relative_path = ?",
                    (self.active_run_id, now, path),
                )
                healed += 1
        if healed:
            logger.info("[ARTIFACT] Marked %d file(s) as HEALED.", healed)

    def mark_removed(self, filepaths: list[str]) -> None:
        if not filepaths:
            return
        now = self._now()
        removed = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    "SELECT file_id, sync_status, file_hash FROM cp_file_registry WHERE relative_path = ?",
                    (path,),
                ).fetchone()
                if not row or row[1] == "REMOVED":
                    continue
                file_id, previous_status, digest = row
                self._insert_event(
                    file_id=file_id,
                    event_type="REMOVED",
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=previous_status,
                    new_status="REMOVED",
                    reason="File no longer present on disk",
                )
                self.db.conn.execute(
                    "UPDATE cp_file_registry SET sync_status = 'REMOVED' WHERE relative_path = ?",
                    (path,),
                )
                # Keep payloads for non-full-replacement categories. Full-replacement
                # categories already prune payloads in prune_category(); retaining the
                # others preserves the existing raw-store recovery/audit contract.
                removed += 1
        if removed:
            logger.info("[ARTIFACT] Marked %d file(s) as REMOVED.", removed)
