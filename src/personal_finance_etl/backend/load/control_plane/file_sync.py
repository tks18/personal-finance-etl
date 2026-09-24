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

        new_files: dict[str, list[str]] = {}
        changed_files: dict[str, list[str]] = {}

        for category, filepaths in discovered_files.items():
            new_files[category] = []
            changed_files[category] = []

            file_type = FILE_TYPE_MAP.get(category, "csv")
            should_check_hash = getattr(hash_policy, file_type, False)

            for filepath in filepaths:
                rel_path = filepath.replace("\\", "/")

                if rel_path not in registry:
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
