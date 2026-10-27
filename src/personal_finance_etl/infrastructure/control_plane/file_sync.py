"""Filesystem synchronization and delta detection for control plane artifacts.

Owns
----
- Reconciling physical filesystem scan results against control plane registry state.
- Delta identification (new, changed, renamed, removed, healed, skipped files).
- Exact file rename detection using content hash heuristics.
- Coordinating binary payload vaulting for new and modified artifacts.

Does not own
-------------
- Physical file searching or pattern discovery (owned by infrastructure.providers.files.locator).
- Low-level artifact payload persistence (owned by artifact_repository).
- Run lifecycle state management (owned by run_repository).
"""

from __future__ import annotations

import os

from personal_finance_etl.application.observability.diagnostics import get_observability_diagnostics
from personal_finance_etl.config.settings import FileHashPolicy
from personal_finance_etl.infrastructure.control_plane.artifact_repository import ArtifactRepository
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    compute_file_hash,
    normalize_path,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.control_plane.file_sync")


class FileSyncService:
    """Service synchronizing physical statement discoveries with the control plane registry.

    Parameters
    ----------
    artifact_repo : ArtifactRepository
        Durable artifact repository instance.
    """

    def __init__(self, artifact_repo: ArtifactRepository) -> None:
        self.artifact_repo = artifact_repo
        self._active_run_id: str | None = None

    @property
    def active_run_id(self) -> str | None:
        """Currently active pipeline run identifier."""
        return self._active_run_id

    @active_run_id.setter
    def active_run_id(self, value: str | None) -> None:
        """Set the active run identifier and propagate it to the artifact repository."""
        self._active_run_id = value
        self.artifact_repo.active_run_id = value

    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:
        """Synchronize the scan as one atomic control-plane operation.

        Parameters
        ----------
        discovered_files : dict[str, list[str]]
            Category-mapped list of discovered filesystem paths.
        hash_policy : FileHashPolicy
            Policy determining which file types require SHA-256 drift checks.
        full_replace_categories : list[str]
            Categories that replace full datasets upon each discovery.

        Returns
        -------
        tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]
            A 4-tuple containing:
            - new_files: dict mapping category to new filepaths.
            - changed_files: dict mapping category to modified filepaths.
            - files_skipped: int count of unchanged files.
            - renames: list of (old_path, new_path, category) tuples.
        """
        with self.artifact_repo.db.atomic():
            return self._sync_with_disk(discovered_files, hash_policy, full_replace_categories)

    def _normalize_discovered_files(
        self,
        discovered_files: dict[str, list[str]],
    ) -> tuple[dict[str, list[str]], int]:
        """Normalize discovered filepaths and validate uniqueness across categories.

        Parameters
        ----------
        discovered_files : dict[str, list[str]]
            Discovered paths per category.

        Returns
        -------
        tuple[dict[str, list[str]], int]
            (normalized_paths_by_category, unique_count).
        """
        seen_path_categories: dict[str, str] = {}
        normalized_by_category: dict[str, list[str]] = {}
        unique_input_count = 0

        for category, filepaths in discovered_files.items():
            normalized_paths: list[str] = []
            category_seen: set[str] = set()
            for filepath in filepaths:
                path = normalize_path(filepath)
                prior_category = seen_path_categories.get(path)
                if prior_category is not None and prior_category != category:
                    raise ValueError(
                        f"Discovered path {path!r} appears in both {prior_category!r} and {category!r}."
                    )
                seen_path_categories[path] = category
                if path not in category_seen:
                    normalized_paths.append(path)
                    category_seen.add(path)
            normalized_by_category[category] = normalized_paths
            unique_input_count += len(normalized_paths)

        return normalized_by_category, unique_input_count

    def _try_migrate_rename(
        self,
        path: str,
        category: str,
        active_paths: set[str],
        hash_to_paths: dict[str, dict[str, list[str]]],
        registry: dict[str, tuple[str, str]],
    ) -> tuple[str, str, str] | None:
        """Attempt to migrate registered artifact identity when a single unambiguous same-hash candidate exists."""
        disk_hash = compute_file_hash(path)
        if not disk_hash:
            raise FileNotFoundError(
                f"Discovered file disappeared or could not be read during sync: {path}"
            )
        cat_hashes = hash_to_paths.get(category, {})
        candidates = [p for p in cat_hashes.get(disk_hash, []) if p not in active_paths]
        if len(candidates) == 1:
            old_path = candidates[0]
            try:
                file_size = os.path.getsize(path)
            except OSError:
                file_size = None
            migrated = self.artifact_repo.migrate_identity(
                old_path, path, observed_hash=disk_hash, file_size_bytes=file_size
            )
            cat_hashes[disk_hash] = [p for p in cat_hashes[disk_hash] if p != old_path]
            if migrated:
                registry[path] = (disk_hash, category)
                registry.pop(old_path, None)
                diagnostics.debug("File sync: Migrated identity from '%s' to '%s'.", old_path, path)
                return (old_path, path, category)
            diagnostics.warning(
                "File sync: Source identity %s has no payload; ingesting %s as new.",
                old_path,
                path,
            )
        elif len(candidates) > 1:
            diagnostics.warning(
                "File sync: Ambiguous rename for %s: %d same-hash candidates. Treating as new.",
                path,
                len(candidates),
            )
        return None

    def _prune_removed_paths(
        self,
        registry_with_status: dict[str, tuple[str, str, str]],
        discovered_categories: set[str],
        all_active_paths: set[str],
        renamed_old_paths: set[str],
    ) -> list[str]:
        """Detect and mark registered artifacts that no longer exist on disk as REMOVED."""
        removed_paths: list[str] = [
            registered_path
            for registered_path, (_digest, category, status) in registry_with_status.items()
            if (
                category in discovered_categories
                and status != "REMOVED"
                and registered_path not in all_active_paths
                and registered_path not in renamed_old_paths
            )
        ]
        if removed_paths:
            diagnostics.info("File sync: %d file(s) no longer present on disk.", len(removed_paths))
            self.artifact_repo.mark_removed(removed_paths)
        return removed_paths

    def _evaluate_file_status(
        self,
        path: str,
        category: str,
        active_paths: set[str],
        hash_to_paths: dict[str, dict[str, list[str]]],
        registry: dict[str, tuple[str, str]],
        registry_with_status: dict[str, tuple[str, str, str]],
        should_check_hash: bool,
    ) -> tuple[str, tuple[str, str, str] | None]:
        """Classify a single file into 'HEALED', 'RENAME', 'NEW', 'CHANGED', or 'UNCHANGED'.

        Parameters
        ----------
        path : str
            Candidate file path.
        category : str
            Category name.
        active_paths : set[str]
            Active paths discovered for this category.
        hash_to_paths : dict[str, dict[str, list[str]]]
            Precomputed hash lookup map.
        registry : dict[str, tuple[str, str]]
            Registry map.
        registry_with_status : dict[str, tuple[str, str, str]]
            Registry with status map.
        should_check_hash : bool
            Whether hash drift checking is enabled for this file type.

        Returns
        -------
        tuple[str, tuple[str, str, str] | None]
            (action_kind, rename_tuple_if_applicable).
        """
        current = registry_with_status.get(path)
        previous_status = current[2] if current else None

        if previous_status == "REMOVED":
            diagnostics.info("File sync: %s re-appeared after prior removal.", path)
            self.artifact_repo.mark_healed([path], affected_table=category)
            return "NEW", None

        if current is None:
            rename = self._try_migrate_rename(path, category, active_paths, hash_to_paths, registry)
            if rename:
                return "RENAME", rename
            return "NEW", None

        if not self.artifact_repo.has_payload(path):
            diagnostics.warning("File sync: Registered artifact has no payload: %s", path)
            return "NEW", None

        if should_check_hash:
            disk_hash = compute_file_hash(path)
            if not disk_hash:
                raise FileNotFoundError(
                    f"Registered file disappeared or could not be read during sync: {path}"
                )
            registered_hash = registry[path][0]
            if disk_hash != registered_hash:
                diagnostics.info(
                    "File sync: %s changed (registry=%s, disk=%s).",
                    path,
                    registered_hash,
                    disk_hash,
                )
                return "CHANGED", None

        return "UNCHANGED", None

    def _sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:
        registry_with_status = self.artifact_repo.get_registry_with_status()
        registry: dict[str, tuple[str, str]] = {
            path: (digest, category)
            for path, (digest, category, _status) in registry_with_status.items()
        }

        hash_to_paths: dict[str, dict[str, list[str]]] = {}
        for path, (digest, category, status) in registry_with_status.items():
            if status != "REMOVED" and digest:
                hash_to_paths.setdefault(category, {}).setdefault(digest, []).append(path)

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}
        renames: list[tuple[str, str, str]] = []
        renamed_old_paths: set[str] = set()
        all_active_paths: set[str] = set()
        full_replace = set(full_replace_categories)

        normalized_by_category, unique_input_count = self._normalize_discovered_files(
            discovered_files
        )

        for category, filepaths in normalized_by_category.items():
            new_files[category] = []
            changed_files[category] = []
            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = bool(getattr(hash_policy, file_type, False))
            active_paths = set(filepaths)
            all_active_paths.update(active_paths)

            for path in filepaths:
                kind, rename_item = self._evaluate_file_status(
                    path,
                    category,
                    active_paths,
                    hash_to_paths,
                    registry,
                    registry_with_status,
                    should_check_hash,
                )
                if kind == "NEW":
                    new_files[category].append(path)
                elif kind == "CHANGED":
                    changed_files[category].append(path)
                elif kind == "RENAME" and rename_item:
                    renamed_old_paths.add(rename_item[0])
                    renames.append(rename_item)

            if category in full_replace:
                self.artifact_repo.prune_category(category, filepaths)

        discovered_categories = set(normalized_by_category)
        removed_paths = self._prune_removed_paths(
            registry_with_status, discovered_categories, all_active_paths, renamed_old_paths
        )

        actionable_count = (
            sum(len(paths) for paths in new_files.values())
            + sum(len(paths) for paths in changed_files.values())
            + len(renames)
        )
        files_skipped = max(0, unique_input_count - actionable_count)
        actionable_files: dict[str, list[str]] = {}
        for category in normalized_by_category:
            merged = list(dict.fromkeys(new_files[category] + changed_files[category]))
            if merged:
                actionable_files[category] = merged
        self.artifact_repo.ingest_binaries(
            actionable_files, new_files=new_files, changed_files=changed_files
        )

        new_count = sum(len(paths) for paths in new_files.values())
        changed_count = sum(len(paths) for paths in changed_files.values())
        rename_count = len(renames)
        rename_str = f" | {rename_count} Renamed" if rename_count else ""
        removed_str = f" | {len(removed_paths)} Removed" if removed_paths else ""
        diagnostics.info(
            "File sync: Delta identified: %d New | %d Changed%s%s | %d Skipped",
            new_count,
            changed_count,
            rename_str,
            removed_str,
            files_skipped,
        )
        return new_files, changed_files, files_skipped, renames
