"""Artifact registry, payload vaulting, and lifecycle event logging in the control plane.

Owns
----
- Source file identity and metadata registration in cp_file_registry.
- Binary and text file payload storage in cp_file_payloads.
- Artifact audit events (DISCOVERED, CHANGED, RENAMED, REMOVED, HEALED, SYNCED) in cp_artifact_run_events.
- Identity migration and path normalization during file renames.
- Virtual configuration artifact injection (inject_virtual_file).
- Obsolete payload pruning for full-replacement categories (prune_category).
- Counting artifact lifecycle audit events for run observability.

Does not own
-------------
- Filesystem scanning and delta calculation (owned by file_sync).
- SQLite connection and low-level transaction primitives (owned by connection).
- DuckDB layer loading (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    generate_file_id,
    hash_bytes,
    normalize_path,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.registry import BRONZE_CONTRACT_REGISTRY

__all__ = ["ArtifactEventRecord", "ArtifactRepository"]

diagnostics = get_observability_diagnostics("personal_finance_etl.control_plane.artifact_repo")

# Static SQL query constants
SQL_SELECT_FILE_CATEGORY = "SELECT file_category FROM cp_file_registry WHERE file_id = ?"

SQL_INSERT_ARTIFACT_EVENT = """
INSERT INTO cp_artifact_run_events (
    event_id, run_id, file_id, event_type, event_at, observed_path,
    content_hash, previous_status, new_status, event_reason,
    affected_table, detecting_run_id, replay_run_id, convergence_result
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_SELECT_REGISTRY = "SELECT relative_path, file_hash, file_category FROM cp_file_registry"

SQL_SELECT_REGISTRY_WITH_STATUS = (
    "SELECT relative_path, file_hash, file_category, sync_status FROM cp_file_registry"
)

SQL_CHECK_PAYLOAD_EXISTS = """
SELECT 1 FROM cp_file_payloads p
JOIN cp_file_registry r ON r.file_id = p.file_id
WHERE r.relative_path = ? AND p.file_bytes IS NOT NULL
"""

SQL_SELECT_CATEGORY_FILES = (
    "SELECT file_id, relative_path FROM cp_file_registry WHERE file_category = ?"
)

SQL_DELETE_PAYLOAD = "DELETE FROM cp_file_payloads WHERE file_id = ?"

SQL_INSERT_MIGRATED_REGISTRY = """
INSERT INTO cp_file_registry (
    file_id, file_name, relative_path, file_category, file_type, file_hash,
    file_size_bytes, first_seen_run_id, first_seen_at, last_seen_run_id,
    last_seen_at, last_changed_run_id, last_changed_at, last_synced_run_id,
    last_synced_at, sync_status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_UPSERT_PAYLOAD = """
INSERT INTO cp_file_payloads (file_id, file_bytes) VALUES (?, ?)
ON CONFLICT(file_id) DO UPDATE SET file_bytes = excluded.file_bytes
"""

SQL_SELECT_FILE_FOR_MIGRATION = """
SELECT file_id, file_name, file_category, file_type, file_hash,
       file_size_bytes, first_seen_run_id, first_seen_at,
       last_seen_run_id, last_seen_at, last_changed_run_id,
       last_changed_at, last_synced_run_id, last_synced_at, sync_status
FROM cp_file_registry WHERE relative_path = ?
"""

SQL_SELECT_PAYLOAD_BYTES = "SELECT file_bytes FROM cp_file_payloads WHERE file_id = ?"

SQL_CHECK_PATH_OR_ID_CONFLICT = (
    "SELECT file_id FROM cp_file_registry WHERE relative_path = ? OR file_id = ?"
)

SQL_SELECT_FILE_ID_AND_STATUS = (
    "SELECT file_id, sync_status FROM cp_file_registry WHERE relative_path = ?"
)

SQL_UPDATE_FILE_REGISTRY_METADATA = """
UPDATE cp_file_registry
SET file_name = ?, file_category = ?, file_type = ?, file_hash = ?,
    file_size_bytes = ?, last_seen_run_id = COALESCE(?, last_seen_run_id), last_seen_at = ?,
    last_changed_run_id = COALESCE(?, last_changed_run_id), last_changed_at = ?, sync_status = 'PENDING_BRONZE'
WHERE relative_path = ?
"""

SQL_INSERT_NEW_FILE_REGISTRY = """
INSERT INTO cp_file_registry (
    file_id, file_name, relative_path, file_category, file_type, file_hash,
    file_size_bytes, first_seen_run_id, first_seen_at, last_seen_run_id,
    last_seen_at, last_changed_run_id, last_changed_at, sync_status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_BRONZE')
"""

SQL_SELECT_PAYLOAD_BYTES_BY_PATH = """
SELECT p.file_bytes FROM cp_file_payloads p
JOIN cp_file_registry r ON r.file_id = p.file_id
WHERE r.relative_path = ?
"""

SQL_SELECT_PENDING_FILES = (
    "SELECT file_category, relative_path FROM cp_file_registry "
    "WHERE sync_status = 'PENDING_BRONZE' ORDER BY file_category, relative_path"
)

SQL_SELECT_ALL_PATHS_BY_CATEGORY = "SELECT file_category, relative_path FROM cp_file_registry ORDER BY file_category, relative_path"

SQL_SELECT_ALL_REGISTRY_STATUS = "SELECT relative_path, sync_status FROM cp_file_registry"

SQL_SELECT_FILE_METADATA_FOR_SYNC = (
    "SELECT file_id, sync_status, last_synced_run_id, file_hash, file_category "
    "FROM cp_file_registry WHERE relative_path = ?"
)

SQL_UPDATE_FILE_SYNCED = (
    "UPDATE cp_file_registry "
    "SET sync_status = 'SYNCED', last_synced_run_id = COALESCE(?, last_synced_run_id), "
    "    last_synced_at = ? WHERE relative_path = ?"
)

SQL_SELECT_FILE_METADATA_FOR_STATUS = "SELECT file_id, sync_status, file_hash, file_category FROM cp_file_registry WHERE relative_path = ?"

SQL_UPDATE_FILE_HEALED = (
    "UPDATE cp_file_registry "
    "SET sync_status = 'PENDING_BRONZE', last_seen_run_id = COALESCE(?, last_seen_run_id), "
    "    last_seen_at = ? WHERE relative_path = ?"
)

SQL_UPDATE_FILE_REMOVED = (
    "UPDATE cp_file_registry SET sync_status = 'REMOVED' WHERE relative_path = ?"
)

SQL_COUNT_EVENTS = "SELECT COUNT(*) FROM cp_artifact_run_events WHERE run_id = ? AND event_type = ?"


@dataclass
class ArtifactEventRecord:
    """Parameters for recording an artifact lifecycle audit event."""

    file_id: str
    event_type: str
    event_at: str
    path: str | None
    content_hash: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    reason: str | None = None
    affected_table: str | None = None
    detecting_run_id: str | None = None
    replay_run_id: str | None = None
    convergence_result: str | None = None


class ArtifactRepository:
    """Persistence and lifecycle transitions for source-file artifacts.

    Parameters
    ----------
    db : SQLiteManager
        Active control plane SQLite connection manager.
    """

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db
        self.active_run_id: str | None = None

    @staticmethod
    def _now() -> str:
        """Return current ISO 8601 timestamp string with second precision.

        Returns
        -------
        str
            Current timestamp in ISO format.
        """
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _resolve_table(category: str | None) -> str | None:
        """Resolve physical Bronze lakehouse table from file category.

        Parameters
        ----------
        category : str | None
            File category string.

        Returns
        -------
        str | None
            Target physical table identifier or None.
        """
        if not category:
            return None
        if category == "sqlite_source":
            return "bronze.r_SQLite_Sources"
        for contract in BRONZE_CONTRACT_REGISTRY:
            if contract.sync_category == category:
                return contract.physical_table
        return f"bronze.{category}"

    def count_events(self, run_id: str, event_type: str) -> int:
        """Count artifact audit events matching run ID and event type.

        Parameters
        ----------
        run_id : str
            Pipeline execution ID.
        event_type : str
            Event type to filter on (e.g. 'HEALED', 'DISCOVERED', 'SYNCED').

        Returns
        -------
        int
            Count of matching event records.
        """
        row = self.db.conn.execute(SQL_COUNT_EVENTS, (run_id, event_type)).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _insert_event(self, event: ArtifactEventRecord) -> None:
        """Insert an immutable audit event into cp_artifact_run_events.

        Parameters
        ----------
        event : ArtifactEventRecord
            Event metadata to record.
        """
        if not self.active_run_id:
            return

        affected_table = event.affected_table
        if not affected_table and event.file_id:
            row = self.db.conn.execute(SQL_SELECT_FILE_CATEGORY, (event.file_id,)).fetchone()
            if row and row[0]:
                affected_table = self._resolve_table(row[0])

        effective_detecting = event.detecting_run_id or self.active_run_id
        effective_replay = event.replay_run_id or (
            self.active_run_id if event.event_type in ("SYNCED", "HEALED", "REINGESTED") else None
        )
        effective_convergence = event.convergence_result or (
            "CONVERGED"
            if event.event_type in ("SYNCED", "HEALED")
            else ("TOMBSTONED" if event.event_type == "REMOVED" else "PENDING")
        )

        self.db.conn.execute(
            SQL_INSERT_ARTIFACT_EVENT,
            (
                str(uuid.uuid4()),
                self.active_run_id,
                event.file_id,
                event.event_type,
                event.event_at,
                event.path,
                event.content_hash,
                event.previous_status,
                event.new_status,
                event.reason,
                affected_table,
                effective_detecting,
                effective_replay,
                effective_convergence,
            ),
        )

    def get_registry(self) -> dict[str, tuple[str, str]]:
        """Return canonical path -> (file_hash, file_category).

        Returns
        -------
        dict[str, tuple[str, str]]
            Map of normalized path to file hash and category.
        """
        cursor = self.db.conn.execute(SQL_SELECT_REGISTRY)
        return {
            normalize_path(path): (file_hash, file_category)
            for path, file_hash, file_category in cursor.fetchall()
        }

    def get_registry_with_status(self) -> dict[str, tuple[str, str, str]]:
        """Return canonical path -> (file_hash, file_category, sync_status).

        Returns
        -------
        dict[str, tuple[str, str, str]]
            Map of normalized path to file hash, category, and sync status.
        """
        cursor = self.db.conn.execute(SQL_SELECT_REGISTRY_WITH_STATUS)
        return {
            normalize_path(path): (
                file_hash or "",
                file_category,
                sync_status or "PENDING_BRONZE",
            )
            for path, file_hash, file_category, sync_status in cursor.fetchall()
        }

    def has_payload(self, filepath: str) -> bool:
        """Check whether binary payload exists in cp_file_payloads for path.

        Parameters
        ----------
        filepath : str
            Candidate file path.

        Returns
        -------
        bool
            True if payload exists and is non-null.
        """
        path = normalize_path(filepath)
        row = self.db.conn.execute(SQL_CHECK_PAYLOAD_EXISTS, (path,)).fetchone()
        return row is not None

    def prune_category(self, category: str, active_discovered_paths: list[str]) -> None:
        """Delete payloads for files no longer in active scan for full-replace categories.

        Parameters
        ----------
        category : str
            Category identifier to prune.
        active_discovered_paths : list[str]
            Active paths discovered on disk.
        """
        active_set = {normalize_path(p) for p in active_discovered_paths}
        rows = self.db.conn.execute(SQL_SELECT_CATEGORY_FILES, (category,)).fetchall()
        obsolete_ids = [row[0] for row in rows if normalize_path(row[1]) not in active_set]
        if not obsolete_ids:
            return

        with self.db.atomic():
            for fid in obsolete_ids:
                self.db.conn.execute(SQL_DELETE_PAYLOAD, (fid,))
        diagnostics.info(
            "Artifact registry: Pruned payloads for %d obsolete files from category '%s'; "
            "registry identities and historical events retained.",
            len(obsolete_ids),
            category,
        )

    def _execute_identity_swap(
        self,
        old_id: str,
        new_id: str,
        old_path: str,
        new_path: str,
        row_data: tuple[object, ...],
        observed_hash: str | None,
        file_size_bytes: int | None,
        payload_bytes: bytes,
    ) -> None:
        """Atomically persist new identity row and move payload bytes.

        Parameters
        ----------
        old_id : str
            Original file identifier.
        new_id : str
            Target new file identifier.
        old_path : str
            Original relative path.
        new_path : str
            New target relative path.
        row_data : tuple[object, ...]
            Existing row columns.
        observed_hash : str | None
            Precomputed file hash.
        file_size_bytes : int | None
            File size in bytes.
        payload_bytes : bytes
            Binary payload bytes.
        """
        (
            _old_id,
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
        ) = row_data

        now = self._now()
        new_status = old_status or "PENDING_BRONZE"
        current_hash = observed_hash or old_hash
        current_size = file_size_bytes if file_size_bytes is not None else old_size

        with self.db.atomic():
            self.db.conn.execute(
                SQL_INSERT_MIGRATED_REGISTRY,
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
            self.db.conn.execute(SQL_UPSERT_PAYLOAD, (new_id, payload_bytes))
            self.db.conn.execute(SQL_DELETE_PAYLOAD, (old_id,))
            affected_table = self._resolve_table(str(category))
            self._insert_event(
                ArtifactEventRecord(
                    file_id=new_id,
                    event_type="RENAMED",
                    event_at=now,
                    path=new_path,
                    content_hash=str(current_hash),
                    previous_status=str(old_status),
                    new_status=str(new_status),
                    reason=f"Migrated identity from {old_path}",
                    affected_table=affected_table,
                    detecting_run_id=self.active_run_id,
                    replay_run_id=None,
                    convergence_result="PENDING",
                )
            )
            self.db.conn.execute(SQL_UPDATE_FILE_REMOVED, (old_path,))

    def migrate_identity(
        self,
        old_rel_path: str,
        new_filepath: str,
        *,
        observed_hash: str | None = None,
        file_size_bytes: int | None = None,
    ) -> bool:
        """Atomically move an artifact's current identity, retaining the old history.

        Parameters
        ----------
        old_rel_path : str
            Existing relative file path in the registry.
        new_filepath : str
            Target destination path for the renamed artifact.
        observed_hash : str, optional
            Precomputed content hash if available.
        file_size_bytes : int, optional
            Precomputed file size in bytes if available.

        Returns
        -------
        bool
            True if migration succeeded; False if source payload is missing.

        Raises
        ------
        ValueError
            If destination path or ID is already registered.
        """
        old_path = normalize_path(old_rel_path)
        new_path = normalize_path(new_filepath)
        if old_path == new_path:
            return True

        row = self.db.conn.execute(SQL_SELECT_FILE_FOR_MIGRATION, (old_path,)).fetchone()
        if not row:
            return False

        old_id = row[0]
        payload_row = self.db.conn.execute(SQL_SELECT_PAYLOAD_BYTES, (old_id,)).fetchone()
        if not payload_row or payload_row[0] is None:
            diagnostics.warning(
                "Artifact registry: Cannot migrate %s because its payload is missing; "
                "destination will be ingested as new.",
                old_path,
            )
            return False

        new_id = generate_file_id(new_path)
        conflict = self.db.conn.execute(
            SQL_CHECK_PATH_OR_ID_CONFLICT,
            (new_path, new_id),
        ).fetchone()
        if conflict:
            raise ValueError(
                f"Cannot migrate artifact to already-registered path or ID: {new_path}"
            )

        self._execute_identity_swap(
            old_id, new_id, old_path, new_path, row, observed_hash, file_size_bytes, payload_row[0]
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
        """Upsert metadata without assuming the persisted ID is path-derived.

        Parameters
        ----------
        filepath : str
            Canonical relative path.
        filename : str
            File basename.
        category : str
            File category.
        file_type : str
            File type string.
        file_hash : str
            SHA-256 digest.
        file_size : int
            File size in bytes.
        now : str
            Current timestamp string.

        Returns
        -------
        tuple[str, str | None]
            (file_id, previous_status).
        """
        path = normalize_path(filepath)
        existing = self.db.conn.execute(SQL_SELECT_FILE_ID_AND_STATUS, (path,)).fetchone()
        if existing:
            file_id, previous_status = existing
            self.db.conn.execute(
                SQL_UPDATE_FILE_REGISTRY_METADATA,
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
            SQL_INSERT_NEW_FILE_REGISTRY,
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

    def _ingest_single_binary(
        self,
        filepath: str,
        category: str,
        file_type: str,
        new_paths: set[str],
        changed_paths: set[str],
    ) -> None:
        """Vault a single binary file payload into the SQLite raw store.

        Parameters
        ----------
        filepath : str
            Physical file path on disk.
        category : str
            Asset category classification.
        file_type : str
            File type string (e.g. 'csv', 'sqlite').
        new_paths : set[str]
            Set of newly discovered file paths.
        changed_paths : set[str]
            Set of modified file paths.
        """
        path = normalize_path(filepath)
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
            self.db.conn.execute(SQL_UPSERT_PAYLOAD, (file_id, raw_bytes))
            if path in new_paths:
                event_type = "DISCOVERED"
            elif path in changed_paths:
                event_type = "CHANGED"
            else:
                event_type = "REINGESTED"

            affected_table = self._resolve_table(category)
            self._insert_event(
                ArtifactEventRecord(
                    file_id=file_id,
                    event_type=event_type,
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=previous_status,
                    new_status="PENDING_BRONZE",
                    reason="Binary payload stored in control-plane vault",
                    affected_table=affected_table,
                    detecting_run_id=self.active_run_id,
                    replay_run_id=self.active_run_id if event_type == "REINGESTED" else None,
                    convergence_result="PENDING",
                )
            )

    def ingest_binaries(
        self,
        actionable_files: dict[str, list[str]],
        new_files: dict[str, list[str]] | None = None,
        changed_files: dict[str, list[str]] | None = None,
    ) -> None:
        """Store payloads and record discovery audit events for actionable files.

        Parameters
        ----------
        actionable_files : dict[str, list[str]]
            Category-mapped files actionable for this run.
        new_files : dict[str, list[str]], optional
            Subset of files that are newly discovered.
        changed_files : dict[str, list[str]], optional
            Subset of files with hash changes.
        """
        new_paths = {normalize_path(path) for paths in (new_files or {}).values() for path in paths}
        changed_paths = {
            normalize_path(path) for paths in (changed_files or {}).values() for path in paths
        }
        total_count = 0
        for category, filepaths in actionable_files.items():
            file_type = FILE_TYPE_MAP.get(category, "csv")
            for filepath in filepaths:
                try:
                    self._ingest_single_binary(
                        filepath, category, file_type, new_paths, changed_paths
                    )
                    total_count += 1
                except Exception:
                    diagnostics.exception("Ingestion: Failed to ingest %s", filepath)
                    raise
        if total_count:
            diagnostics.info(
                "Ingestion: Safely vaulted %d payloads into SQLite Raw Store.", total_count
            )

    def inject_virtual_file(self, filename: str, category: str, raw_bytes: bytes) -> str:
        """Inject an in-memory configuration asset as a virtual:// control plane artifact.

        Parameters
        ----------
        filename : str
            Virtual artifact file name.
        category : str
            Asset category.
        raw_bytes : bytes
            Binary content to vault.

        Returns
        -------
        str
            Virtual file path created.
        """
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
            self.db.conn.execute(SQL_UPSERT_PAYLOAD, (file_id, raw_bytes))
            affected_table = self._resolve_table(category)
            self._insert_event(
                ArtifactEventRecord(
                    file_id=file_id,
                    event_type="VIRTUAL_UPDATED" if previous_status else "VIRTUAL_CREATED",
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=previous_status,
                    new_status="PENDING_BRONZE",
                    reason="Virtual configuration artifact injected",
                    affected_table=affected_table,
                    detecting_run_id=self.active_run_id,
                    replay_run_id=self.active_run_id if previous_status else None,
                    convergence_result="PENDING",
                )
            )
        return path

    def get_file_bytes(self, filepath: str) -> bytes | None:
        """Retrieve stored binary payload for an artifact by canonical path.

        Parameters
        ----------
        filepath : str
            Relative or virtual file path.

        Returns
        -------
        bytes | None
            Stored raw bytes if found, otherwise None.
        """
        path = normalize_path(filepath)
        row = self.db.conn.execute(SQL_SELECT_PAYLOAD_BYTES_BY_PATH, (path,)).fetchone()
        return row[0] if row else None

    def get_pending_files(self) -> dict[str, list[str]]:
        """Return categorized map of all artifacts marked PENDING_BRONZE.

        Returns
        -------
        dict[str, list[str]]
            Category-mapped pending file paths.
        """
        cursor = self.db.conn.execute(SQL_SELECT_PENDING_FILES)
        pending: dict[str, list[str]] = {}
        for category, path in cursor.fetchall():
            pending.setdefault(category, []).append(normalize_path(path))
        return pending

    def get_all_paths_by_category(self) -> dict[str, list[str]]:
        """Return all registered relative paths grouped by file category.

        Returns
        -------
        dict[str, list[str]]
            Category-mapped relative file paths.
        """
        cursor = self.db.conn.execute(SQL_SELECT_ALL_PATHS_BY_CATEGORY)
        result: dict[str, list[str]] = {}
        for category, path in cursor.fetchall():
            result.setdefault(category, []).append(normalize_path(path))
        return result

    def get_all_registry(self) -> dict[str, str]:
        """Return canonical path -> sync_status dictionary.

        Returns
        -------
        dict[str, str]
            Map of path to sync status.
        """
        cursor = self.db.conn.execute(SQL_SELECT_ALL_REGISTRY_STATUS)
        return {normalize_path(path): status for path, status in cursor.fetchall()}

    def mark_synced(self, filepaths: list[str]) -> None:
        """Mark successfully loaded artifacts as SYNCED in the registry and audit log.

        Parameters
        ----------
        filepaths : list[str]
            Filepaths that completed Bronze synchronization.
        """
        if not filepaths:
            return
        now = self._now()
        marked = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    SQL_SELECT_FILE_METADATA_FOR_SYNC,
                    (path,),
                ).fetchone()
                if not row:
                    diagnostics.warning(
                        "Artifact registry: Cannot mark unknown file as SYNCED: %s", path
                    )
                    continue
                file_id, previous_status, last_run, digest, file_cat = row
                if previous_status == "SYNCED" and last_run == self.active_run_id:
                    continue
                affected_table = self._resolve_table(file_cat)
                self._insert_event(
                    ArtifactEventRecord(
                        file_id=file_id,
                        event_type="SYNCED",
                        event_at=now,
                        path=path,
                        content_hash=digest,
                        previous_status=previous_status,
                        new_status="SYNCED",
                        reason="Loaded into DuckDB Bronze lakehouse",
                        affected_table=affected_table,
                        detecting_run_id=self.active_run_id,
                        replay_run_id=self.active_run_id,
                        convergence_result="CONVERGED",
                    )
                )
                self.db.conn.execute(
                    SQL_UPDATE_FILE_SYNCED,
                    (self.active_run_id, now, path),
                )
                marked += 1
        if marked:
            diagnostics.debug("Artifact registry: Marked %d file(s) as SYNCED.", marked)

    def mark_healed(
        self,
        filepaths: list[str],
        *,
        affected_table: str | None = None,
        detecting_run_id: str | None = None,
        replay_run_id: str | None = None,
        convergence_result: str | None = "CONVERGED",
    ) -> None:
        """Restore previously removed artifacts to PENDING_BRONZE.

        Parameters
        ----------
        filepaths : list[str]
            Filepaths that reappeared on disk.
        affected_table : str, optional
            Target lakehouse table.
        detecting_run_id : str, optional
            Run ID detecting the reappearance.
        replay_run_id : str, optional
            Run ID replaying the ingestion.
        convergence_result : str, default='CONVERGED'
            State convergence outcome.
        """
        if not filepaths:
            return
        now = self._now()
        healed = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    SQL_SELECT_FILE_METADATA_FOR_STATUS,
                    (path,),
                ).fetchone()
                if not row or row[1] != "REMOVED":
                    continue
                file_id, previous_status, digest, file_cat = row
                resolved_table = self._resolve_table(affected_table or file_cat)
                self._insert_event(
                    ArtifactEventRecord(
                        file_id=file_id,
                        event_type="HEALED",
                        event_at=now,
                        path=path,
                        content_hash=digest,
                        previous_status=previous_status,
                        new_status="PENDING_BRONZE",
                        reason="File re-appeared after prior removal",
                        affected_table=resolved_table,
                        detecting_run_id=detecting_run_id or self.active_run_id,
                        replay_run_id=replay_run_id or self.active_run_id,
                        convergence_result=convergence_result,
                    )
                )
                self.db.conn.execute(
                    SQL_UPDATE_FILE_HEALED,
                    (self.active_run_id, now, path),
                )
                healed += 1
        if healed:
            diagnostics.info("Artifact registry: Marked %d file(s) as HEALED.", healed)

    def record_healing_event(
        self,
        filepath: str,
        *,
        affected_table: str | None = None,
        detecting_run_id: str | None = None,
        replay_run_id: str | None = None,
        convergence_result: str | None = "CONVERGED",
        reason: str | None = "Inconsistency healed",
    ) -> None:
        """Record an explicit healing lineage event for an artifact.

        Parameters
        ----------
        filepath : str
            Path to the healed file.
        affected_table : str, optional
            Target lakehouse table.
        detecting_run_id : str, optional
            Detecting run ID.
        replay_run_id : str, optional
            Replay run ID.
        convergence_result : str, default='CONVERGED'
            Outcome classification.
        reason : str, default='Inconsistency healed'
            Human-readable explanation.
        """
        path = normalize_path(filepath)
        row = self.db.conn.execute(SQL_SELECT_FILE_METADATA_FOR_STATUS, (path,)).fetchone()
        if not row:
            return
        file_id, status, digest, file_cat = row
        now = self._now()
        resolved_table = self._resolve_table(affected_table or file_cat)
        with self.db.atomic():
            self._insert_event(
                ArtifactEventRecord(
                    file_id=file_id,
                    event_type="HEALED",
                    event_at=now,
                    path=path,
                    content_hash=digest,
                    previous_status=status,
                    new_status=status,
                    reason=reason,
                    affected_table=resolved_table,
                    detecting_run_id=detecting_run_id or self.active_run_id,
                    replay_run_id=replay_run_id or self.active_run_id,
                    convergence_result=convergence_result,
                )
            )

    def mark_removed(self, filepaths: list[str]) -> None:
        """Mark missing files as REMOVED in the registry and log audit tombstone events.

        Parameters
        ----------
        filepaths : list[str]
            Filepaths that are no longer present on disk.
        """
        if not filepaths:
            return
        now = self._now()
        removed = 0
        with self.db.atomic():
            for path in dict.fromkeys(normalize_path(fp) for fp in filepaths):
                row = self.db.conn.execute(
                    SQL_SELECT_FILE_METADATA_FOR_STATUS,
                    (path,),
                ).fetchone()
                if not row or row[1] == "REMOVED":
                    continue
                file_id, previous_status, digest, file_cat = row
                affected_table = self._resolve_table(file_cat)
                self._insert_event(
                    ArtifactEventRecord(
                        file_id=file_id,
                        event_type="REMOVED",
                        event_at=now,
                        path=path,
                        content_hash=digest,
                        previous_status=previous_status,
                        new_status="REMOVED",
                        reason="File no longer present on disk",
                        affected_table=affected_table,
                        detecting_run_id=self.active_run_id,
                        replay_run_id=None,
                        convergence_result="TOMBSTONED",
                    )
                )
                self.db.conn.execute(SQL_UPDATE_FILE_REMOVED, (path,))
                removed += 1
        if removed:
            diagnostics.info("Artifact registry: Marked %d file(s) as REMOVED.", removed)
