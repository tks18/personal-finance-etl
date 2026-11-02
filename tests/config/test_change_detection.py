"""Unit tests for change-detection and synchronization policy models.

Owns
----
- Invariant tests for ChangeDetectionPolicy and strategy enums.
- Cross-strategy dependency validation (content drift/rename requiring fingerprint).
- Serialization round-trip tests for ChangeDetectionPolicy.
- Tests for pure resolution function resolve_change_detection_policy.
- Explicit policy override tests on SourceDatasetConfig.

Does not own
------------
- FileSyncService execution or database operations (tested in tests/infrastructure/control_plane).
- Legacy category translation logic (tested in tests/application/test_policy_resolver.py).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.settings import FileHashPolicy
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    DriftStrategy,
    FingerprintStrategy,
    RenameStrategy,
    SyncStrategy,
    resolve_change_detection_policy,
)
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId


def test_policy_defaults_and_roundtrip() -> None:
    """Verify ChangeDetectionPolicy defaults, dictionary, and JSON round-trip serialization."""
    policy = ChangeDetectionPolicy()
    assert policy.fingerprint_strategy == FingerprintStrategy.SHA256
    assert policy.drift_strategy == DriftStrategy.CONTENT
    assert policy.rename_strategy == RenameStrategy.CONTENT_FINGERPRINT
    assert policy.sync_strategy == SyncStrategy.INCREMENTAL

    # Dict round-trip
    dumped = policy.model_dump()
    assert dumped == {
        "fingerprint_strategy": "sha256",
        "drift_strategy": "content",
        "rename_strategy": "content_fingerprint",
        "sync_strategy": "incremental",
    }
    reconstructed_dict = ChangeDetectionPolicy.model_validate(dumped)
    assert reconstructed_dict == policy

    # JSON round-trip
    json_str = policy.model_dump_json()
    reconstructed_json = ChangeDetectionPolicy.model_validate_json(json_str)
    assert reconstructed_json == policy


def test_invariant_content_drift_requires_fingerprint() -> None:
    """Verify that DriftStrategy.CONTENT strictly requires a content fingerprint strategy."""
    with pytest.raises(
        ValidationError, match="DriftStrategy.CONTENT requires a content fingerprint"
    ):
        ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.NONE,
            drift_strategy=DriftStrategy.CONTENT,
            rename_strategy=RenameStrategy.DISABLED,
        )


def test_invariant_content_rename_requires_fingerprint() -> None:
    """Verify that RenameStrategy.CONTENT_FINGERPRINT strictly requires a content fingerprint strategy."""
    with pytest.raises(
        ValidationError, match="RenameStrategy.CONTENT_FINGERPRINT requires a content fingerprint"
    ):
        ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.NONE,
            drift_strategy=DriftStrategy.METADATA,
            rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
        )


def test_valid_metadata_drift_without_fingerprint() -> None:
    """Verify that metadata drift with disabled rename is valid when no fingerprint is produced."""
    policy = ChangeDetectionPolicy(
        fingerprint_strategy=FingerprintStrategy.NONE,
        drift_strategy=DriftStrategy.METADATA,
        rename_strategy=RenameStrategy.DISABLED,
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    assert policy.fingerprint_strategy == FingerprintStrategy.NONE
    assert policy.drift_strategy == DriftStrategy.METADATA
    assert policy.rename_strategy == RenameStrategy.DISABLED
    assert policy.sync_strategy == SyncStrategy.INCREMENTAL


def test_pure_resolver_independent_of_provider_type() -> None:
    """Verify that resolve_change_detection_policy resolves policies independently of provider type."""
    hash_policy = FileHashPolicy(csv=True, excel=False, sqlite=False)

    # Full-replace CSV (e.g. mapping dependency)
    csv_full = resolve_change_detection_policy(
        file_type="csv",
        is_full_replace=True,
        hash_policy=hash_policy,
    )
    assert csv_full.sync_strategy == SyncStrategy.FULL_REPLACE
    assert csv_full.drift_strategy == DriftStrategy.CONTENT
    assert csv_full.rename_strategy == RenameStrategy.CONTENT_FINGERPRINT

    # Incremental CSV (e.g. US stock transaction ledger)
    csv_inc = resolve_change_detection_policy(
        file_type="csv",
        is_full_replace=False,
        hash_policy=hash_policy,
    )
    assert csv_inc.sync_strategy == SyncStrategy.INCREMENTAL
    assert csv_inc.drift_strategy == DriftStrategy.CONTENT
    assert csv_inc.rename_strategy == RenameStrategy.CONTENT_FINGERPRINT

    # Provider-generated virtual stream
    provider_policy = resolve_change_detection_policy(
        file_type="parquet",
        is_full_replace=False,
        hash_policy=hash_policy,
        is_provider_generated=True,
    )
    assert provider_policy.fingerprint_strategy == FingerprintStrategy.NONE
    assert provider_policy.drift_strategy == DriftStrategy.METADATA
    assert provider_policy.rename_strategy == RenameStrategy.DISABLED
    assert provider_policy.sync_strategy == SyncStrategy.INCREMENTAL


def test_source_dataset_config_explicit_policy_attachment() -> None:
    """Verify that SourceDatasetConfig supports optional explicit change_detection policies."""
    custom_policy = ChangeDetectionPolicy(
        fingerprint_strategy=FingerprintStrategy.SHA256,
        drift_strategy=DriftStrategy.METADATA,
        rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
        sync_strategy=SyncStrategy.FULL_REPLACE,
    )

    binding = SourceDatasetConfig(
        source_id=SourceId("custom_csv"),
        dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        selector=CsvSelector(),
        change_detection=custom_policy,
    )

    assert binding.change_detection == custom_policy

    # Serialization round-trip
    dumped = binding.model_dump()
    assert dumped["change_detection"] == custom_policy.model_dump()

    reconstructed = SourceDatasetConfig.model_validate_json(binding.model_dump_json())
    assert reconstructed.change_detection == custom_policy
