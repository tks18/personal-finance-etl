"""Parameterized matrix tests for legacy change-detection policy compatibility resolution.

Owns
----
- Parameterized matrix test across all 16 sync categories in BRONZE_CONTRACT_REGISTRY.
- Verification of exact v9.5.3 hash checking, drift, and full/incremental sync semantics.
- Tests for format-level FileHashPolicy dynamic toggling (CSV, Excel, SQLite).
- Explicit tests for provider-generated virtual streams (currency_history, us_stock_market).

Does not own
------------
- FileSyncService disk execution (tested in tests/infrastructure/control_plane).
- Warehouse persistence operations (tested in tests/infrastructure/warehouse).
"""

from __future__ import annotations

import pytest

from personal_finance_etl.application.ingestion.policy_resolver import (
    resolve_legacy_change_detection_policy,
)
from personal_finance_etl.config.settings import FileHashPolicy
from personal_finance_etl.config.sources.change_detection import (
    DriftStrategy,
    FingerprintStrategy,
    RenameStrategy,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)

# Canonical expected matrix for all 16 sync categories under default settings
MATRIX_TEST_CASES = [
    # SQLite Household
    (
        "sqlite_source",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    # Configured CSV Dependencies (Full Replace)
    (
        "mf_isin",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "benchmark_mapping",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "opening_balances",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "benchmark_master",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "macro_parameters",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "column_master",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    (
        "currency_mapping",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.FULL_REPLACE,
    ),
    # Excel Statements (Incremental, Metadata Drift by default)
    (
        "mf_holdings",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    (
        "mf_orders",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    (
        "stock_pl",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    (
        "stock_orders",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    # US Stock Transactions (CSV, Incremental)
    (
        "us_stock_transactions",
        FingerprintStrategy.SHA256,
        DriftStrategy.CONTENT,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    # Provider-Generated Virtual Streams
    (
        "currency_history",
        FingerprintStrategy.NONE,
        DriftStrategy.METADATA,
        RenameStrategy.DISABLED,
        SyncStrategy.INCREMENTAL,
    ),
    (
        "benchmark_history",
        FingerprintStrategy.SHA256,
        DriftStrategy.METADATA,
        RenameStrategy.CONTENT_FINGERPRINT,
        SyncStrategy.INCREMENTAL,
    ),
    (
        "us_stock_market",
        FingerprintStrategy.NONE,
        DriftStrategy.METADATA,
        RenameStrategy.DISABLED,
        SyncStrategy.INCREMENTAL,
    ),
]


def test_every_registry_sync_category_covered_in_matrix() -> None:
    """Verify that every unique sync_category in BRONZE_CONTRACT_REGISTRY is tested."""
    registry_categories = {contract.sync_category for contract in BRONZE_CONTRACT_REGISTRY}
    tested_categories = {case[0] for case in MATRIX_TEST_CASES}
    assert registry_categories == tested_categories
    assert len(registry_categories) == 16


@pytest.mark.parametrize(
    ("category", "expected_fp", "expected_drift", "expected_rename", "expected_sync"),
    MATRIX_TEST_CASES,
)
def test_compatibility_resolver_matrix(
    category: str,
    expected_fp: FingerprintStrategy,
    expected_drift: DriftStrategy,
    expected_rename: RenameStrategy,
    expected_sync: SyncStrategy,
) -> None:
    """Verify that each category resolves to exact v9.5.3 semantics under default settings."""
    policy = resolve_legacy_change_detection_policy(category)
    assert policy.fingerprint_strategy == expected_fp
    assert policy.drift_strategy == expected_drift
    assert policy.rename_strategy == expected_rename
    assert policy.sync_strategy == expected_sync


def test_compatibility_resolver_hash_policy_toggling() -> None:
    """Verify dynamic resolution when FileHashPolicy flags are modified."""
    # When Excel hashing is enabled
    excel_hash_on = FileHashPolicy(csv=True, excel=True, sqlite=False)
    mf_holdings_policy = resolve_legacy_change_detection_policy(
        "mf_holdings", hash_policy=excel_hash_on
    )
    assert mf_holdings_policy.drift_strategy == DriftStrategy.CONTENT
    assert mf_holdings_policy.fingerprint_strategy == FingerprintStrategy.SHA256

    # When CSV hashing is disabled
    csv_hash_off = FileHashPolicy(csv=False, excel=False, sqlite=False)
    mf_isin_policy = resolve_legacy_change_detection_policy("mf_isin", hash_policy=csv_hash_off)
    assert mf_isin_policy.drift_strategy == DriftStrategy.METADATA
    assert mf_isin_policy.fingerprint_strategy == FingerprintStrategy.SHA256

    # When SQLite hashing is enabled
    sqlite_hash_on = FileHashPolicy(csv=True, excel=False, sqlite=True)
    sqlite_policy = resolve_legacy_change_detection_policy(
        "sqlite_source", hash_policy=sqlite_hash_on
    )
    assert sqlite_policy.drift_strategy == DriftStrategy.CONTENT
    assert sqlite_policy.fingerprint_strategy == FingerprintStrategy.SHA256
    assert sqlite_policy.sync_strategy == SyncStrategy.FULL_REPLACE
