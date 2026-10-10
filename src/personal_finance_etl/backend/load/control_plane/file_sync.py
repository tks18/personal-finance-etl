from __future__ import annotations

import os

from personal_finance_etl.backend.config.settings import FileHashPolicy
from personal_finance_etl.backend.load.control_plane.artifact_repo import ArtifactRepository
from personal_finance_etl.backend.load.control_plane.utils import (
    FILE_TYPE_MAP,
    compute_file_hash,
    normalize_path,
)
from personal_finance_etl.backend.utils.logger import logger


class FileSyncService:
    def __init__(self, artifact_repo: ArtifactRepository):
        self.artifact_repo = artifact_repo
        self._active_run_id: str | None = None

    @property
    def active_run_id(self) -> str | None:
        return self._active_run_id

    @active_run_id.setter
    def active_run_id(self, value: str | None) -> None:
        self._active_run_id = value
        # One authoritative run ID for file sync and all artifact events.
        self.artifact_repo.active_run_id = value

    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:
        """Synchronize the scan as one atomic control-plane operation."""
        with self.artifact_repo.db.atomic():
            return self._sync_with_disk(discovered_files, hash_policy, full_replace_categories)

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
        seen_path_categories: dict[str, str] = {}
        unique_input_count = 0
        full_replace = set(full_replace_categories)

        # Canonicalize/deduplicate before any destructive pruning. A path assigned to
        # multiple categories is a contract error and must not silently change identity.
        normalized_by_category: dict[str, list[str]] = {}
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

        for category, filepaths in normalized_by_category.items():
            new_files[category] = []
            changed_files[category] = []
            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = bool(getattr(hash_policy, file_type, False))
            active_paths = set(filepaths)
            all_active_paths.update(active_paths)

            for path in filepaths:
                current = registry_with_status.get(path)
                previous_status = current[2] if current else None

                if previous_status == "REMOVED":
                    logger.info("[SYNC:HEALED] %s re-appeared after prior removal.", path)
                    self.artifact_repo.mark_healed([path])
                    new_files[category].append(path)
                    continue

                if current is None:
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
                        # Consume the old candidate regardless of whether migration succeeded,
                        # so it cannot be reused for another same-content destination.
                        cat_hashes[disk_hash] = [p for p in cat_hashes[disk_hash] if p != old_path]
                        if migrated:
                            registry[path] = (disk_hash, category)
                            registry.pop(old_path, None)
                            renamed_old_paths.add(old_path)
                            renames.append((old_path, path, category))
                            logger.debug(
                                "[SYNC:RENAME] Migrated identity from '%s' to '%s'.", old_path, path
                            )
                            continue
                        logger.warning(
                            "[SYNC:RENAME] Source identity %s has no payload; ingesting %s as new.",
                            old_path,
                            path,
                        )
                    elif len(candidates) > 1:
                        logger.warning(
                            "[SYNC:RENAME] Ambiguous rename for %s: %d same-hash candidates. "
                            "Treating as new.",
                            path,
                            len(candidates),
                        )
                    new_files[category].append(path)
                    continue

                # Registry entries whose payload disappeared unexpectedly must be repaired,
                # even when hash checking is disabled for that file type.
                if not self.artifact_repo.has_payload(path):
                    logger.warning("[SYNC:REPAIR] Registered artifact has no payload: %s", path)
                    new_files[category].append(path)
                    continue

                if should_check_hash:
                    disk_hash = compute_file_hash(path)
                    if not disk_hash:
                        raise FileNotFoundError(
                            f"Registered file disappeared or could not be read during sync: {path}"
                        )
                    registered_hash = registry[path][0]
                    if disk_hash != registered_hash:
                        logger.info(
                            "[SYNC:DRIFT] %s changed (registry=%s, disk=%s).",
                            path,
                            registered_hash,
                            disk_hash,
                        )
                        changed_files[category].append(path)

            # This operation is safe only for categories that the caller positively
            # confirms were scanned. An absent category is intentionally not pruned.
            if category in full_replace:
                self.artifact_repo.prune_category(category, filepaths)

        removed_paths: list[str] = []
        discovered_categories = set(normalized_by_category)
        for registered_path, (_digest, category, status) in registry_with_status.items():
            if (
                category in discovered_categories
                and status != "REMOVED"
                and registered_path not in all_active_paths
                and registered_path not in renamed_old_paths
            ):
                removed_paths.append(registered_path)
        if removed_paths:
            logger.info("[SYNC:REMOVED] %d file(s) no longer present on disk.", len(removed_paths))
            self.artifact_repo.mark_removed(removed_paths)

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
        logger.info(
            "[SYNC] Delta identified: %d New | %d Changed%s%s | %d Skipped",
            new_count,
            changed_count,
            rename_str,
            removed_str,
            files_skipped,
        )
        return new_files, changed_files, files_skipped, renames
