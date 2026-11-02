"""Unit and architectural tests for policy-driven FileSyncService execution.

Owns
----
- Verification of FileSyncService consuming ChangeDetectionPolicy maps.
- Drift detection semantics (content vs metadata drift).
- Pruning semantics (full-replace vs incremental sync).
- Rename heuristics (content fingerprint vs disabled, ambiguous duplicate resolution).
- Policy completeness validation (missing category raises KeyError before mutations).
- Transaction atomicity and rollback on error.
- Architectural boundary checks (no FileHashPolicy or FILE_TYPE_MAP in file_sync,
  no FILE_HASH_POLICY in MetaLayer.register_file).
"""

from __future__ import annotations

import ast
from collections.abc import Generator
from pathlib import Path

import pytest

from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    DriftStrategy,
    FingerprintStrategy,
    RenameStrategy,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.control_plane.artifact_repository import (
    ArtifactRepository,
)
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.file_sync import (
    FileSyncService,
)


@pytest.fixture
def sync_env(tmp_path: Path) -> Generator[tuple[FileSyncService, SQLiteManager, Path]]:
    """Provide an initialized FileSyncService backed by a clean SQLite Control Plane."""
    db_dir = tmp_path / "control_plane"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite_mgr = SQLiteManager(str(db_dir), "test_cp.sqlite")
    sqlite_mgr.open()
    sqlite_mgr.ensure_schema()
    artifact_repo = ArtifactRepository(sqlite_mgr)
    sync_service = FileSyncService(artifact_repo)

    try:
        yield sync_service, sqlite_mgr, tmp_path
    finally:
        sqlite_mgr.close()


def test_sync_with_disk_policy_completeness_missing_category(
    sync_env: tuple[FileSyncService, SQLiteManager, Path],
) -> None:
    """Verify that a discovered category missing a ChangeDetectionPolicy raises KeyError before mutations."""
    sync_service, sqlite_mgr, tmp_path = sync_env
    test_file = tmp_path / "data.csv"
    test_file.write_text("col1,col2\n1,2\n", encoding="utf-8")

    discovered = {"unconfigured_cat": [str(test_file)]}
    policies: dict[str, ChangeDetectionPolicy] = {}

    with pytest.raises(KeyError, match="No ChangeDetectionPolicy resolved for discovered category"):
        sync_service.sync_with_disk(discovered, policies)

    # Assert that no registry row was written
    cursor = sqlite_mgr.conn.execute("SELECT count(*) FROM cp_file_registry")
    count = cursor.fetchone()[0]
    assert count == 0


def test_sync_with_disk_content_drift_vs_metadata_drift(
    sync_env: tuple[FileSyncService, SQLiteManager, Path],
) -> None:
    """Verify that DriftStrategy.CONTENT detects modified file contents while DriftStrategy.METADATA skips them."""
    sync_service, _sqlite_mgr, tmp_path = sync_env

    content_file = tmp_path / "content_drift.csv"
    content_file.write_text("initial,content\n1,2\n", encoding="utf-8")

    metadata_file = tmp_path / "metadata_drift.csv"
    metadata_file.write_text("initial,content\n3,4\n", encoding="utf-8")

    policies = {
        "cat_content": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
            sync_strategy=SyncStrategy.INCREMENTAL,
        ),
        "cat_metadata": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.METADATA,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
            sync_strategy=SyncStrategy.INCREMENTAL,
        ),
    }

    discovered = {
        "cat_content": [str(content_file)],
        "cat_metadata": [str(metadata_file)],
    }

    # Pass 1: Both are NEW
    new_files, changed_files, skipped, renames = sync_service.sync_with_disk(discovered, policies)
    assert len(new_files["cat_content"]) == 1
    assert len(new_files["cat_metadata"]) == 1
    assert len(changed_files["cat_content"]) == 0
    assert len(changed_files["cat_metadata"]) == 0
    assert skipped == 0
    assert len(renames) == 0

    # Modify both files on disk
    content_file.write_text("modified,content\n99,100\n", encoding="utf-8")
    metadata_file.write_text("modified,content\n99,100\n", encoding="utf-8")

    # Pass 2: cat_content should be CHANGED, cat_metadata should be UNCHANGED (skipped)
    new_files, changed_files, skipped, renames = sync_service.sync_with_disk(discovered, policies)
    assert len(new_files["cat_content"]) == 0
    assert len(new_files["cat_metadata"]) == 0
    assert len(changed_files["cat_content"]) == 1
    assert len(changed_files["cat_metadata"]) == 0
    assert skipped == 1
    assert len(renames) == 0


def test_sync_with_disk_full_replace_vs_incremental_pruning(
    sync_env: tuple[FileSyncService, SQLiteManager, Path],
) -> None:
    """Verify that SyncStrategy.FULL_REPLACE prunes category artifacts whereas INCREMENTAL retains them as REMOVED."""
    sync_service, sqlite_mgr, tmp_path = sync_env

    file_full_1 = tmp_path / "full_1.csv"
    file_full_1.write_text("a,b\n1,2\n", encoding="utf-8")
    file_full_2 = tmp_path / "full_2.csv"
    file_full_2.write_text("a,b\n3,4\n", encoding="utf-8")

    file_inc_1 = tmp_path / "inc_1.csv"
    file_inc_1.write_text("c,d\n5,6\n", encoding="utf-8")
    file_inc_2 = tmp_path / "inc_2.csv"
    file_inc_2.write_text("c,d\n7,8\n", encoding="utf-8")

    policies = {
        "cat_full": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
            sync_strategy=SyncStrategy.FULL_REPLACE,
        ),
        "cat_inc": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
            sync_strategy=SyncStrategy.INCREMENTAL,
        ),
    }

    discovered = {
        "cat_full": [str(file_full_1), str(file_full_2)],
        "cat_inc": [str(file_inc_1), str(file_inc_2)],
    }

    # Pass 1: Ingest both categories
    sync_service.sync_with_disk(discovered, policies)

    # Pass 2: Discover only 1 file in each category (full_2 and inc_2 removed from discovery and disk)
    file_full_2.unlink()
    file_inc_2.unlink()

    discovered_pass2 = {
        "cat_full": [str(file_full_1)],
        "cat_inc": [str(file_inc_1)],
    }
    sync_service.sync_with_disk(discovered_pass2, policies)

    # For cat_full: prune_category deletes payloads for obsolete files from SQLite vault
    assert not sync_service.artifact_repo.has_payload(str(file_full_2))
    assert sync_service.artifact_repo.has_payload(str(file_full_1))

    # For cat_inc: payloads are retained even when file is unlinked / missing from scan
    assert sync_service.artifact_repo.has_payload(str(file_inc_2))
    assert sync_service.artifact_repo.has_payload(str(file_inc_1))

    # Both categories mark the missing file as REMOVED in the registry
    rows_full = sqlite_mgr.conn.execute(
        "SELECT relative_path, sync_status FROM cp_file_registry WHERE file_category = 'cat_full'"
    ).fetchall()
    status_full = {r[0]: r[1] for r in rows_full}
    assert status_full[str(file_full_2).replace("\\", "/")] == "REMOVED"

    rows_inc = sqlite_mgr.conn.execute(
        "SELECT relative_path, sync_status FROM cp_file_registry WHERE file_category = 'cat_inc'"
    ).fetchall()
    status_inc = {r[0]: r[1] for r in rows_inc}
    assert status_inc[str(file_inc_2).replace("\\", "/")] == "REMOVED"


def test_sync_with_disk_rename_detection_enabled_and_disabled(
    sync_env: tuple[FileSyncService, SQLiteManager, Path],
) -> None:
    """Verify that RenameStrategy.CONTENT_FINGERPRINT detects renames while RenameStrategy.DISABLED treats them as NEW and REMOVED."""
    sync_service, _sqlite_mgr, tmp_path = sync_env

    # Setup files with distinct contents
    file_ren_a = tmp_path / "order_2023.csv"
    file_ren_a.write_text("order_id,amount\n101,500.0\n", encoding="utf-8")

    file_no_ren_a = tmp_path / "feed_old.csv"
    file_no_ren_a.write_text("feed_id,value\n201,1000.0\n", encoding="utf-8")

    policies = {
        "cat_rename_enabled": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
            sync_strategy=SyncStrategy.INCREMENTAL,
        ),
        "cat_rename_disabled": ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.SHA256,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.DISABLED,
            sync_strategy=SyncStrategy.INCREMENTAL,
        ),
    }

    discovered = {
        "cat_rename_enabled": [str(file_ren_a)],
        "cat_rename_disabled": [str(file_no_ren_a)],
    }

    # Pass 1: Ingest
    sync_service.sync_with_disk(discovered, policies)

    # Rename on disk
    file_ren_b = tmp_path / "order_2023_renamed.csv"
    file_ren_a.rename(file_ren_b)

    file_no_ren_b = tmp_path / "feed_new.csv"
    file_no_ren_a.rename(file_no_ren_b)

    discovered_pass2 = {
        "cat_rename_enabled": [str(file_ren_b)],
        "cat_rename_disabled": [str(file_no_ren_b)],
    }

    # Pass 2: Rename detection evaluation
    new_files, changed_files, _skipped, renames = sync_service.sync_with_disk(
        discovered_pass2, policies
    )

    # cat_rename_enabled detected the rename
    assert len(renames) == 1
    assert renames[0][0] == str(file_ren_a).replace("\\", "/")
    assert renames[0][1] == str(file_ren_b).replace("\\", "/")
    assert renames[0][2] == "cat_rename_enabled"
    assert len(new_files["cat_rename_enabled"]) == 0

    # cat_rename_disabled did NOT detect the rename; reported feed_new as NEW
    assert len(new_files["cat_rename_disabled"]) == 1
    assert len(changed_files["cat_rename_disabled"]) == 0


def test_sync_with_disk_ambiguous_rename_candidates(
    sync_env: tuple[FileSyncService, SQLiteManager, Path],
) -> None:
    """Verify that multiple registered candidates with identical SHA-256 hashes result in NEW classification rather than erroneous migration."""
    sync_service, _sqlite_mgr, tmp_path = sync_env

    # Create two different files with identical content
    identical_content = "same,content\n1,1\n"
    file_orig_1 = tmp_path / "dup_1.csv"
    file_orig_1.write_text(identical_content, encoding="utf-8")
    file_orig_2 = tmp_path / "dup_2.csv"
    file_orig_2.write_text(identical_content, encoding="utf-8")

    policy = ChangeDetectionPolicy(
        fingerprint_strategy=FingerprintStrategy.SHA256,
        drift_strategy=DriftStrategy.CONTENT,
        rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    policies = {"cat_dup": policy}

    # Pass 1: Ingest both duplicates
    sync_service.sync_with_disk({"cat_dup": [str(file_orig_1), str(file_orig_2)]}, policies)

    # Remove both originals and introduce a third candidate with the same content
    file_orig_1.unlink()
    file_orig_2.unlink()
    file_candidate = tmp_path / "dup_candidate.csv"
    file_candidate.write_text(identical_content, encoding="utf-8")

    # Pass 2: Because 2 missing files share the exact same hash, it is ambiguous
    new_files, _changed_files, _skipped, renames = sync_service.sync_with_disk(
        {"cat_dup": [str(file_candidate)]}, policies
    )

    # Must treat candidate as NEW, and must NOT guess a rename
    assert len(renames) == 0
    assert len(new_files["cat_dup"]) == 1
    assert new_files["cat_dup"][0] == str(file_candidate).replace("\\", "/")


def test_sync_with_disk_transaction_atomicity_rollback(
    sync_env: tuple[FileSyncService, SQLiteManager, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that an unhandled failure during file synchronization triggers an atomic rollback."""
    sync_service, sqlite_mgr, tmp_path = sync_env

    file_ok = tmp_path / "valid.csv"
    file_ok.write_text("a,b\n1,2\n", encoding="utf-8")

    policy = ChangeDetectionPolicy(
        fingerprint_strategy=FingerprintStrategy.SHA256,
        drift_strategy=DriftStrategy.CONTENT,
        rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    policies = {"cat_test": policy}

    def _exploding_evaluate(*args: object, **kwargs: object) -> tuple[str, None]:
        raise RuntimeError("Simulated transient disk/database fault during sync evaluation")

    monkeypatch.setattr(sync_service, "_evaluate_file_status", _exploding_evaluate)

    with pytest.raises(RuntimeError, match="Simulated transient disk/database fault"):
        sync_service.sync_with_disk({"cat_test": [str(file_ok)]}, policies)

    # Verify atomic rollback: zero rows persisted in SQLite registry
    cursor = sqlite_mgr.conn.execute("SELECT count(*) FROM cp_file_registry")
    assert cursor.fetchone()[0] == 0


def test_file_sync_architectural_boundaries() -> None:
    """Verify architectural boundaries: FileSyncService does not import FileHashPolicy or FILE_TYPE_MAP; MetaLayer does not inspect FILE_HASH_POLICY."""
    repo_root = Path(__file__).resolve().parents[2]

    # 1. Inspect file_sync.py
    file_sync_path = (
        repo_root
        / "src"
        / "personal_finance_etl"
        / "infrastructure"
        / "control_plane"
        / "file_sync.py"
    )
    file_sync_content = file_sync_path.read_text(encoding="utf-8")
    file_sync_tree = ast.parse(file_sync_content, filename=str(file_sync_path))

    imported_names: list[str] = []
    for node in ast.walk(file_sync_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.append(alias.name)

    assert "FileHashPolicy" not in imported_names, (
        "FileSyncService must not import FileHashPolicy; it must consume ChangeDetectionPolicy."
    )
    assert "FILE_TYPE_MAP" not in imported_names, (
        "FileSyncService must not import FILE_TYPE_MAP; policy is passed in resolved."
    )

    # 2. Inspect meta/layer.py
    meta_layer_path = (
        repo_root
        / "src"
        / "personal_finance_etl"
        / "infrastructure"
        / "warehouse"
        / "meta"
        / "layer.py"
    )
    meta_layer_content = meta_layer_path.read_text(encoding="utf-8")
    assert "FILE_HASH_POLICY" not in meta_layer_content, (
        "MetaLayer must not inspect FILE_HASH_POLICY; Control Plane owns the artifact fingerprint."
    )
