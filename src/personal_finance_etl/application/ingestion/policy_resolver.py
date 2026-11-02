"""Transitional compatibility resolver for legacy file hashing and synchronization policy.

Owns
----
- resolve_legacy_change_detection_policy: Translates historical v9.5.3 categories, format maps,
  and Settings.FILE_HASH_POLICY into explicit, typed ChangeDetectionPolicy instances.

Does not own
------------
- ChangeDetectionPolicy model definition (owned by config.sources.change_detection).
- FileSyncService execution or database persistence (owned by infrastructure.control_plane).
- Warehouse table upsert execution (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

from personal_finance_etl.config.settings import FileHashPolicy, Settings
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    resolve_change_detection_policy,
)
from personal_finance_etl.contracts.datasets import PROVIDER_GENERATED_DATASETS
from personal_finance_etl.infrastructure.control_plane.hashing import FILE_TYPE_MAP
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)

__all__ = ["resolve_legacy_change_detection_policy"]


def resolve_legacy_change_detection_policy(
    category: str,
    settings: Settings | None = None,
    hash_policy: FileHashPolicy | None = None,
) -> ChangeDetectionPolicy:
    """Resolve an authoritative ChangeDetectionPolicy for a legacy v9.5.3 sync category.

    Parameters
    ----------
    category : str
        Historical sync category name (e.g. 'sqlite_source', 'mf_holdings', 'currency_mapping').
    settings : Settings | None, default None
        Optional application Settings instance containing active FILE_HASH_POLICY.
    hash_policy : FileHashPolicy | None, default None
        Optional explicit FileHashPolicy instance. Takes precedence over settings if provided.

    Returns
    -------
    ChangeDetectionPolicy
        Resolved change-detection and synchronization policy.
    """
    effective_policy: FileHashPolicy
    if hash_policy is not None:
        effective_policy = hash_policy
    elif settings is not None:
        effective_policy = settings.FILE_HASH_POLICY
    else:
        effective_policy = FileHashPolicy()

    # Look up Bronze contracts for this category to determine full-replace behavior
    contracts_for_cat = [
        contract for contract in BRONZE_CONTRACT_REGISTRY if contract.sync_category == category
    ]
    if contracts_for_cat:
        full_replace_flags = {contract.is_full_replace for contract in contracts_for_cat}
        if len(full_replace_flags) > 1:
            raise ValueError(
                f"Conflicting full_replace flags for sync category '{category}': {full_replace_flags}"
            )
        is_full_replace = next(iter(full_replace_flags))
    else:
        is_full_replace = False

    # Detect provider-generated virtual streams (e.g. currency_history, us_stock_market)
    is_provider_generated = False
    if contracts_for_cat and all(
        contract.dataset_id in PROVIDER_GENERATED_DATASETS for contract in contracts_for_cat
    ):
        # Note: benchmark_history is in FILE_TYPE_MAP as 'parquet', whereas virtual
        # API streams like currency_history and us_stock_market have no disk files.
        if category in ("currency_history", "us_stock_market"):
            is_provider_generated = True

    file_type = FILE_TYPE_MAP.get(category, "csv")

    return resolve_change_detection_policy(
        file_type=file_type,
        is_full_replace=is_full_replace,
        hash_policy=effective_policy,
        is_provider_generated=is_provider_generated,
    )
