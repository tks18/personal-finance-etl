"""Authoritative change-detection and synchronization policy models.

Owns
----
- FingerprintStrategy: Cryptographic fingerprinting options for evidence files.
- DriftStrategy: Determination mechanisms for on-disk file modifications.
- RenameStrategy: Mechanisms for detecting and migrating renamed/moved files.
- SyncStrategy: Warehouse synchronization modes (full-replace vs incremental).
- ChangeDetectionPolicy: Validated configuration model binding all four policy dimensions.
- resolve_change_detection_policy: Pure resolution function building policy from format and flags.

Does not own
------------
- Physical hash computation or file reading (owned by infrastructure.control_plane.hashing).
- FileSyncService execution loop (owned by infrastructure.control_plane.file_sync).
- Legacy category mapping resolution (owned by application.ingestion.policy_resolver).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from personal_finance_etl.config.settings import FileHashPolicy

__all__ = [
    "ChangeDetectionPolicy",
    "DriftStrategy",
    "FingerprintStrategy",
    "RenameStrategy",
    "SyncStrategy",
    "resolve_change_detection_policy",
]


class FingerprintStrategy(StrEnum):
    """Cryptographic fingerprinting strategy for ingested evidence artifacts."""

    NONE = "none"
    SHA256 = "sha256"


class DriftStrategy(StrEnum):
    """Strategy for detecting modifications or drift in previously seen files."""

    METADATA = "metadata"
    CONTENT = "content"


class RenameStrategy(StrEnum):
    """Strategy for detecting and migrating artifact identity across file renames."""

    DISABLED = "disabled"
    CONTENT_FINGERPRINT = "content_fingerprint"


class SyncStrategy(StrEnum):
    """Warehouse Bronze synchronization strategy."""

    FULL_REPLACE = "full_replace"
    INCREMENTAL = "incremental"


class ChangeDetectionPolicy(BaseModel):
    """Decoupled, typed policy governing change detection and synchronization.

    Parameters
    ----------
    fingerprint_strategy : FingerprintStrategy, default FingerprintStrategy.SHA256
        Strategy used to generate unique content digests for artifacts.
    drift_strategy : DriftStrategy, default DriftStrategy.CONTENT
        Mechanism used to evaluate if an existing file has changed on disk.
    rename_strategy : RenameStrategy, default RenameStrategy.CONTENT_FINGERPRINT
        Mechanism used to detect and migrate artifact identity when files are renamed.
    sync_strategy : SyncStrategy, default SyncStrategy.INCREMENTAL
        Warehouse synchronization mode (full table replacement or incremental append).
    """

    fingerprint_strategy: FingerprintStrategy = FingerprintStrategy.SHA256
    drift_strategy: DriftStrategy = DriftStrategy.CONTENT
    rename_strategy: RenameStrategy = RenameStrategy.CONTENT_FINGERPRINT
    sync_strategy: SyncStrategy = SyncStrategy.INCREMENTAL

    @model_validator(mode="after")
    def validate_fingerprint_dependencies(self) -> Self:
        """Validate that content-based drift and rename strategies require a content fingerprint.

        Returns
        -------
        Self
            Validated ChangeDetectionPolicy instance.

        Raises
        ------
        ValueError
            If content drift or content rename is requested without a fingerprint strategy.
        """
        if (
            self.drift_strategy == DriftStrategy.CONTENT
            and self.fingerprint_strategy == FingerprintStrategy.NONE
        ):
            raise ValueError(
                "DriftStrategy.CONTENT requires a content fingerprint strategy (got FingerprintStrategy.NONE)."
            )

        if (
            self.rename_strategy == RenameStrategy.CONTENT_FINGERPRINT
            and self.fingerprint_strategy == FingerprintStrategy.NONE
        ):
            raise ValueError(
                "RenameStrategy.CONTENT_FINGERPRINT requires a content fingerprint strategy (got FingerprintStrategy.NONE)."
            )

        return self


def resolve_change_detection_policy(
    *,
    file_type: str,
    is_full_replace: bool,
    hash_policy: FileHashPolicy,
    is_provider_generated: bool = False,
) -> ChangeDetectionPolicy:
    """Resolve a typed ChangeDetectionPolicy from raw format, hash policy, and replacement flags.

    Parameters
    ----------
    file_type : str
        Source file format identifier (e.g. 'csv', 'excel', 'sqlite', 'parquet').
    is_full_replace : bool
        Whether the target dataset synchronizes via full replacement.
    hash_policy : FileHashPolicy
        Active file hash policy configuration specifying format-level hash checking.
    is_provider_generated : bool, default False
        Whether the dataset is generated dynamically by provider services without disk files.

    Returns
    -------
    ChangeDetectionPolicy
        Resolved change-detection and synchronization policy.
    """
    if is_provider_generated:
        return ChangeDetectionPolicy(
            fingerprint_strategy=FingerprintStrategy.NONE,
            drift_strategy=DriftStrategy.METADATA,
            rename_strategy=RenameStrategy.DISABLED,
            sync_strategy=SyncStrategy.INCREMENTAL,
        )

    # In v9.5.3, all file-backed artifacts vaulted to Control Plane receive SHA-256 digests
    # and participate in rename detection via content fingerprinting.
    should_check_hash = bool(getattr(hash_policy, file_type, False))
    drift = DriftStrategy.CONTENT if should_check_hash else DriftStrategy.METADATA
    sync = SyncStrategy.FULL_REPLACE if is_full_replace else SyncStrategy.INCREMENTAL

    return ChangeDetectionPolicy(
        fingerprint_strategy=FingerprintStrategy.SHA256,
        drift_strategy=drift,
        rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
        sync_strategy=sync,
    )
