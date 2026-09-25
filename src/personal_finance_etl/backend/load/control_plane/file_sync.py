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
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], int, list[tuple[str, str, str]]]:

        registry = self.artifact_repo.get_registry()
        # Build hash index for detecting renames, scoped by category
        hash_to_paths: dict[str, dict[str, list[str]]] = {}
        for p, (h, cat) in registry.items():
            hash_to_paths.setdefault(cat, {}).setdefault(h, []).append(p)

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}
        renames: list[tuple[str, str, str]] = []

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
                                break

                    if not is_rename:
                        new_files[category].append(filepath)
                elif should_check_hash:
                    disk_hash = compute_file_hash(filepath)
                    if disk_hash != registry[rel_path][0]:
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

        return new_files, changed_files, files_skipped, renames
