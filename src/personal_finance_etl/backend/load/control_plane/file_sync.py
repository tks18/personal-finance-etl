import os

from personal_finance_etl.backend.config.settings import FileHashPolicy
from personal_finance_etl.backend.load.control_plane.artifact_repo import ArtifactRepository
from personal_finance_etl.backend.load.control_plane.utils import FILE_TYPE_MAP, compute_file_hash


class FileSyncService:
    def __init__(self, artifact_repo: ArtifactRepository):
        self.artifact_repo = artifact_repo

    def sync_with_disk(
        self,
        discovered_files: dict[str, list[str]],
        hash_policy: FileHashPolicy,
        full_replace_categories: list[str],
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:

        registry = self.artifact_repo.get_registry()
        # Build hash index for detecting renames
        hash_to_paths: dict[str, list[str]] = {}
        for p, h in registry.items():
            hash_to_paths.setdefault(h, []).append(p)

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}

        for category, filepaths in discovered_files.items():
            new_files[category] = []
            changed_files[category] = []

            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = getattr(hash_policy, file_type, False)

            # Pre-calculate active paths to know which old paths are missing
            active_rel_paths = {f.replace("\\", "/") for f in filepaths}

            for filepath in filepaths:
                rel_path = filepath.replace("\\", "/")
                if rel_path not in registry:
                    disk_hash = compute_file_hash(filepath)
                    # Check if this is a rename: same hash exists in registry, but the old path is no longer on disk
                    is_rename = False
                    if disk_hash in hash_to_paths:
                        for old_path in hash_to_paths[disk_hash]:
                            # If the old path is not active on disk anymore, treat it as a rename
                            if old_path not in active_rel_paths:
                                # We update the registry to point to the new path
                                self.artifact_repo.db.conn.execute(
                                    "UPDATE cp_file_registry SET relative_path = ?, file_name = ? WHERE relative_path = ?",
                                    (rel_path, os.path.basename(filepath), old_path),
                                )
                                # Update our local registry copy so we don't treat it as new
                                registry[rel_path] = disk_hash
                                del registry[old_path]
                                # No need to ingest binary, it's just a rename
                                is_rename = True
                                break

                    if not is_rename:
                        new_files[category].append(filepath)
                elif should_check_hash:
                    disk_hash = compute_file_hash(filepath)
                    if disk_hash != registry[rel_path]:
                        changed_files[category].append(filepath)

            if category in full_replace_categories:
                self.artifact_repo.prune_category(category, filepaths)

        files_skipped = sum(len(f) for f in discovered_files.values()) - (
            sum(len(f) for f in new_files.values()) + sum(len(f) for f in changed_files.values())
        )

        actionable_files: dict[str, list[str]] = {}
        for cat in set(new_files.keys()).union(changed_files.keys()):
            merged = new_files.get(cat, []) + changed_files.get(cat, [])
            if merged:
                actionable_files[cat] = merged

        self.artifact_repo.ingest_binaries(actionable_files)

        return new_files, changed_files, files_skipped
