from personal_finance_etl.backend.config.settings import FileHashPolicy
from personal_finance_etl.backend.load.control_plane.artifact_repo import ArtifactRepository
from personal_finance_etl.backend.load.control_plane.utils import FILE_TYPE_MAP, compute_file_hash
from personal_finance_etl.backend.utils.logger import logger


class FileSyncService:
    def __init__(self, artifact_repo: ArtifactRepository):
        self.artifact_repo = artifact_repo
        self.active_run_id: str | None = None

    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:

        # Use the richer registry that includes sync_status so we can detect
        # HEALED (previously REMOVED files that re-appeared on disk) and
        # REMOVED (registered files no longer present on disk).
        registry_with_status = self.artifact_repo.get_registry_with_status()

        # Build the plain-hash registry view expected by the rename-detection logic below.
        registry: dict[str, tuple[str, str]] = {
            p: (h, cat) for p, (h, cat, _status) in registry_with_status.items()
        }

        # Build hash index for detecting renames, scoped by category
        hash_to_paths: dict[str, dict[str, list[str]]] = {}
        for p, (h, cat) in registry.items():
            hash_to_paths.setdefault(cat, {}).setdefault(h, []).append(p)

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}
        renames: list[tuple[str, str, str]] = []

        # Collect all active paths across categories for REMOVED detection.
        all_active_rel_paths: set[str] = set()

        for category, filepaths in discovered_files.items():
            new_files[category] = []
            changed_files[category] = []

            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = getattr(hash_policy, file_type, False)

            # Pre-calculate active paths to know which old paths are missing
            active_rel_paths = {f.replace("\\", "/") for f in filepaths}
            all_active_rel_paths.update(active_rel_paths)

            for filepath in filepaths:
                rel_path = filepath.replace("\\", "/")

                # HEALED detection: file was previously REMOVED but is back on disk.
                prev_status = registry_with_status.get(rel_path, (None, None, None))[2]
                if prev_status == "REMOVED":
                    logger.info(f"[SYNC:HEALED] {rel_path} re-appeared after prior removal.")
                    self.artifact_repo.mark_healed([rel_path])
                    # Treat as new so it gets re-ingested.
                    new_files[category].append(rel_path)
                    continue

                if rel_path not in registry:
                    disk_hash = compute_file_hash(filepath)
                    # Check if this is a rename: same hash exists in registry, but the old path is no longer on disk
                    is_rename = False
                    cat_hashes = hash_to_paths.get(category, {})
                    if disk_hash in cat_hashes:
                        for old_path in cat_hashes[disk_hash]:
                            # If the old path is not active on disk anymore, treat it as a rename
                            if old_path not in active_rel_paths:
                                # We update the registry and payloads to point to the new path properly
                                self.artifact_repo.migrate_identity(old_path, filepath)

                                # Update our local registry copy so we don't treat it as new
                                registry[rel_path] = (disk_hash, category)
                                del registry[old_path]
                                # No need to ingest binary, it's just a rename
                                is_rename = True
                                renames.append((old_path, filepath, category))
                                logger.debug(
                                    f"[SYNC:RENAME] Migrating identity from '{old_path}' to '{filepath}'."
                                )
                                break

                    if not is_rename:
                        logger.debug(f"[SYNC:NEW] {rel_path} discovered (Hash: {disk_hash}).")
                        new_files[category].append(rel_path)
                elif should_check_hash:
                    disk_hash = compute_file_hash(filepath)
                    registry_hash = registry[rel_path][0]
                    if disk_hash != registry_hash:
                        logger.debug(
                            f"[SYNC:DRIFT] {rel_path} changed! Disk: {disk_hash} | Registry: {registry_hash}"
                        )
                        changed_files[category].append(rel_path)

            if category in full_replace_categories:
                self.artifact_repo.prune_category(category, filepaths)

        # REMOVED detection: registry paths (not REMOVED already) that are no longer on disk.
        discovered_categories = set(discovered_files.keys())
        removed_paths: list[str] = []
        for reg_path, (_, reg_cat, reg_status) in registry_with_status.items():
            if (
                reg_cat in discovered_categories
                and reg_status != "REMOVED"
                and reg_path not in all_active_rel_paths
            ):
                removed_paths.append(reg_path)

        if removed_paths:
            logger.info(f"[SYNC:REMOVED] {len(removed_paths)} file(s) no longer present on disk.")
            self.artifact_repo.mark_removed(removed_paths)

        files_skipped = sum(len(f) for f in discovered_files.values()) - (
            sum(len(f) for f in new_files.values())
            + sum(len(f) for f in changed_files.values())
            + len(renames)
        )

        actionable_files: dict[str, list[str]] = {}
        for cat in set(new_files.keys()).union(changed_files.keys()):
            merged = new_files.get(cat, []) + changed_files.get(cat, [])
            if merged:
                actionable_files[cat] = merged

        self.artifact_repo.ingest_binaries(
            actionable_files, new_files=new_files, changed_files=changed_files
        )

        new_count = sum(len(f) for f in new_files.values())
        changed_count = sum(len(f) for f in changed_files.values())
        rename_count = len(renames)

        rename_str = f" | {rename_count} Renamed" if rename_count > 0 else ""
        removed_str = f" | {len(removed_paths)} Removed" if removed_paths else ""

        logger.info(
            f"[SYNC] Delta identified: {new_count} New | {changed_count} Changed{rename_str}{removed_str} | {files_skipped} Skipped"
        )

        return new_files, changed_files, files_skipped, renames
