"""Tests for generic source-plan file discovery service.

Owns
----
- Verification of discover_source_plan_files across directory selectors.
- Verification of discover_source_plan_files across exact file selectors.
- Verification of discover_source_plan_files across glob patterns in source location.
- Verification of discover_source_plan_files across SQLite selectors.
- Verification of graceful handling of missing directories and non-matching patterns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personal_finance_etl.application.ingestion.file_discovery import (
    discover_source_plan_files,
)
from personal_finance_etl.application.pipeline.source_planner import (
    DatasetPlan,
    SourcePlan,
)
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    DriftStrategy,
    FingerprintStrategy,
    RenameStrategy,
    SyncStrategy,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.datasets import DatasetId, DatasetOrigin
from personal_finance_etl.contracts.sources import ProviderType, SourceId

DEFAULT_POLICY = ChangeDetectionPolicy(
    fingerprint_strategy=FingerprintStrategy.SHA256,
    drift_strategy=DriftStrategy.CONTENT,
    rename_strategy=RenameStrategy.CONTENT_FINGERPRINT,
    sync_strategy=SyncStrategy.INCREMENTAL,
)


def test_discover_exact_csv_file(tmp_path: Path) -> None:
    """Verify discovery of exact CSV file."""
    file_a = tmp_path / "exact_a.csv"
    file_a.write_text("col1,col2\n1,2\n")
    norm_file = str(file_a).replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_csv"),
        dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        provider_type=ProviderType.CSV,
        location=norm_file,
        selector=CsvSelector(),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_csv"),
        provider_type=ProviderType.CSV,
        location=norm_file,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    assert DatasetId.INVESTMENT_MF_ISIN_MAPPING.value in discovered
    paths = discovered[DatasetId.INVESTMENT_MF_ISIN_MAPPING.value]
    assert len(paths) == 1
    assert paths[0] == norm_file


def test_discover_excel_directory_with_pattern(tmp_path: Path) -> None:
    """Verify Excel directory discovery filtered by file_pattern."""
    dir_path = tmp_path / "holdings"
    dir_path.mkdir(parents=True)
    f1 = dir_path / "MF_Holdings_2026.xlsx"
    f1.write_bytes(b"dummy")
    f2 = dir_path / "Stock_Holdings_2026.xlsx"
    f2.write_bytes(b"dummy")
    f_lock = dir_path / "~$MF_Holdings_2026.xlsx"
    f_lock.write_bytes(b"dummy_lock")

    norm_dir = str(dir_path).replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_excel"),
        dataset_id=DatasetId.MARKET_MF_HOLDINGS,
        provider_type=ProviderType.EXCEL,
        location=norm_dir,
        selector=ExcelSelector(
            sheet_name="Holdings",
            file_pattern="*MF_Holdings*.xlsx",
        ),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_excel"),
        provider_type=ProviderType.EXCEL,
        location=norm_dir,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    paths = discovered[DatasetId.MARKET_MF_HOLDINGS.value]
    assert len(paths) == 1
    assert paths[0].endswith("MF_Holdings_2026.xlsx")
    assert not any("~$" in p for p in paths)


def test_discover_location_glob_pattern(tmp_path: Path) -> None:
    """Verify glob pattern directly in source location."""
    base = tmp_path / "orders"
    (base / "2025").mkdir(parents=True)
    (base / "2026").mkdir(parents=True)
    (base / "2025" / "orders_q1.csv").write_text("a,b\n")
    (base / "2026" / "orders_q1.csv").write_text("a,b\n")
    (base / "2026" / "notes.txt").write_text("ignore")

    glob_location = str(base / "**" / "*.csv").replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_glob"),
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        provider_type=ProviderType.CSV,
        location=glob_location,
        selector=CsvSelector(),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_glob"),
        provider_type=ProviderType.CSV,
        location=glob_location,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    paths = discovered[DatasetId.INVESTMENT_STOCK_ORDERS.value]
    assert len(paths) == 2
    assert all(p.endswith(".csv") for p in paths)


def test_discover_sqlite_backup_directory(tmp_path: Path) -> None:
    """Verify discovery of latest SQLite database backup from directory."""
    db1 = tmp_path / "backup_2026-01-01.sqlite"
    db2 = tmp_path / "backup_2026-02-01.sqlite"
    with sqlite3.connect(db1) as conn:
        conn.execute("CREATE TABLE t1 (id int)")
    with sqlite3.connect(db2) as conn:
        conn.execute("CREATE TABLE t1 (id int)")

    norm_dir = str(tmp_path).replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_sqlite"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        provider_type=ProviderType.SQLITE,
        location=norm_dir,
        selector=SqliteSelector(table_name="t1"),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_sqlite"),
        provider_type=ProviderType.SQLITE,
        location=norm_dir,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    paths = discovered[DatasetId.HOUSEHOLD_ZCATEGORY.value]
    assert len(paths) == 1
    assert paths[0].endswith("backup_2026-02-01.sqlite")


def test_discover_excel_directory_recursive_subfolders(tmp_path: Path) -> None:
    """Verify Excel directory discovery finds files in nested subfolders."""
    base_dir = tmp_path / "orders"
    sub_dir = base_dir / "2025-2026"
    sub_dir.mkdir(parents=True)
    f1 = sub_dir / "MF_Orders_2025.xlsx"
    f1.write_bytes(b"dummy")

    norm_dir = str(base_dir).replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_excel_nested"),
        dataset_id=DatasetId.INVESTMENT_MF_ORDERS,
        provider_type=ProviderType.EXCEL,
        location=norm_dir,
        selector=ExcelSelector(sheet_name="Transactions"),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_excel_nested"),
        provider_type=ProviderType.EXCEL,
        location=norm_dir,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    paths = discovered[DatasetId.INVESTMENT_MF_ORDERS.value]
    assert len(paths) == 1
    assert paths[0].endswith("MF_Orders_2025.xlsx")


def test_get_shan_baseline_sources_with_settings(tmp_path: Path) -> None:
    """Verify that get_shan_baseline_sources overrides locations when settings are supplied."""
    from personal_finance_etl.config.settings import Settings
    from personal_finance_etl.config.sources.loader import get_shan_baseline_sources

    db_dir = tmp_path / "mm_backup"
    db_dir.mkdir()
    stmt_dir = tmp_path / "statements"
    stmt_dir.mkdir()
    groww_holdings = stmt_dir / "Investments" / "Groww" / "Mutual Funds - Holdings"
    groww_holdings.mkdir(parents=True)

    csv_file = tmp_path / "custom_isin.csv"
    csv_file.write_text("ISIN,Name\n")

    settings = Settings(
        SOURCE_DB_FOLDER=str(db_dir),
        STATEMENTS_FOLDER=str(stmt_dir),
        MF_ISIN_CSV_PATH=str(csv_file),
    )

    sources = get_shan_baseline_sources(settings=settings)
    src_map = {str(s.source_id): s.location for s in sources}

    assert src_map["household_db"] == str(db_dir)
    assert src_map["mf_isin_csv"] == str(csv_file)
    assert src_map["mf_holdings_excel"] == str(groww_holdings)


def test_discover_missing_directory_gracefully(tmp_path: Path) -> None:
    """Verify missing directory yields empty list without raising exception."""
    missing_dir = str(tmp_path / "non_existent_folder").replace("\\", "/")

    dp = DatasetPlan(
        source_id=SourceId("src_missing"),
        dataset_id=DatasetId.MARKET_STOCK_HOLDINGS,
        provider_type=ProviderType.EXCEL,
        location=missing_dir,
        selector=ExcelSelector(sheet_name="Holdings"),
        change_detection=DEFAULT_POLICY,
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )
    sp = SourcePlan(
        source_id=SourceId("src_missing"),
        provider_type=ProviderType.EXCEL,
        location=missing_dir,
        enabled=True,
        dataset_plans=(dp,),
    )

    discovered = discover_source_plan_files([sp])
    assert discovered.get(DatasetId.MARKET_STOCK_HOLDINGS.value, []) == []
