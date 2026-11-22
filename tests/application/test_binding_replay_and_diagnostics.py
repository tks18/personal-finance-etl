"""Unit and integration tests for binding replay truncation and diagnostics dry run.

Validates that ReplayCoordinator truncates binding-keyed Pre-Bronze tables for replayed
datasets, and that DiagnosticsService checks sources using binding plans without mutating
production Pre-Bronze or Control Plane state.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.application.diagnostics.service import DiagnosticService
from personal_finance_etl.application.pipeline.replay import ReplayCoordinator
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceBindingId, SourceId
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PreBronzeDataContract,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer


@pytest.fixture
def replay_warehouse(tmp_path: Path) -> tuple[DuckDBManager, PreBronzeLayer]:
    """Fixture providing an isolated DuckDB manager and PreBronzeLayer."""
    db_path = str(tmp_path / "test_replay.duckdb")
    db_mgr = DuckDBManager(db_path)
    db_mgr.open()
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS pre_bronze")
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS meta")
    db_mgr.conn.execute(
        "CREATE TABLE meta.m_File_Registry (file_id VARCHAR, file_category VARCHAR)"
    )
    pb_layer = PreBronzeLayer(db_mgr)
    return db_mgr, pb_layer


def test_replay_truncates_binding_keyed_pre_bronze_tables(
    replay_warehouse: tuple[DuckDBManager, PreBronzeLayer],
) -> None:
    """Verify that ReplayCoordinator truncates binding Pre-Bronze tables for affected datasets."""
    db_mgr, pb_layer = replay_warehouse
    binding_id = SourceBindingId("sqlite_source__household_zcategory")
    contract = PreBronzeDataContract(
        binding_id=binding_id,
        physical_table=f"pre_bronze.{binding_id}",
        sync_strategy=SyncStrategy.FULL_REPLACE,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
    )

    # Populate Pre-Bronze and Bronze tables
    pb_layer.write_full_replace(
        contract,
        pl.DataFrame({"cat_id": [1, 2], "name": ["Groceries", "Utilities"]}),
        artifact_id="art_rep_1",
        source_id=SourceId("sqlite_source"),
    )
    db_mgr.conn.execute(
        "CREATE TABLE bronze.household_zcategory AS SELECT 1 AS cat_id, 'Groceries' AS name"
    )

    assert pb_layer.read(binding_id).height == 2
    res_b = db_mgr.conn.execute("SELECT count(*) FROM bronze.household_zcategory").fetchone()
    assert res_b is not None and res_b[0] == 1

    # Execute replay preparation for the affected dataset
    ReplayCoordinator.prepare_dataset_replay(db_mgr, ["household_zcategory"])

    # Both binding-keyed Pre-Bronze and Bronze tables must be truncated
    assert pb_layer.read(binding_id).height == 0
    res_b_after = db_mgr.conn.execute("SELECT count(*) FROM bronze.household_zcategory").fetchone()
    assert res_b_after is not None and res_b_after[0] == 0


def test_diagnostics_service_checks_sources_without_warehouse_mutation(
    tmp_path: Path,
) -> None:
    """Verify that DiagnosticsService.check_sources reads bindings without warehouse mutation."""
    data_dir = tmp_path / "csv_data"
    data_dir.mkdir()
    sample_csv = data_dir / "sample_orders.csv"
    sample_csv.write_text("order_id,amount\n1,100\n2,200\n", encoding="utf-8")

    src = SourceConfig(
        source_id=SourceId("diag_source"),
        provider_type=ProviderType.CSV,
        location=str(data_dir),
        enabled=True,
    )
    ds = SourceDatasetConfig(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        source_id=SourceId("diag_source"),
        selector=CsvSelector(file_pattern="sample_orders.csv"),
        mapping=[],
        normalization=[],
        identity=None,
        fields=[],
    )
    cfg = SourceConfiguration(sources=(src,), datasets=(ds,))

    diag_service = DiagnosticService()
    result = diag_service.check_sources(source_config=cfg)

    assert result.is_all_reachable is True
    assert len(result.sources) == 1
    assert result.sources[0].source_id == SourceId("diag_source")
    assert result.sources[0].status.value == "REACHABLE"
    assert len(result.sources[0].dataset_selectors) == 1
    assert result.sources[0].dataset_selectors[0].is_valid is True
