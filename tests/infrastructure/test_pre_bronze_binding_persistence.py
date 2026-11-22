"""Unit and integration tests for binding-keyed Pre-Bronze persistence.

Validates that Pre-Bronze lakehouse persistence is keyed by SourceBindingId rather than
canonical DatasetId, proving that distinct physical streams targeting the same canonical
target dataset persist into independent physical tables without collisions or data loss.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceBindingId, SourceId
from personal_finance_etl.contracts.validation import (
    ValidationCheckFailure,
    ValidationContext,
    ValidationError,
    ValidationResult,
    ValidationStage,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_BINDING_ID,
    PRE_BRONZE_SOURCE_ID,
    PreBronzeDataContract,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer


@pytest.fixture
def pre_bronze_env(tmp_path: Path) -> tuple[DuckDBManager, PreBronzeLayer]:
    """Fixture providing an isolated DuckDB warehouse connection and PreBronzeLayer."""
    db_path = str(tmp_path / "test_pb_persistence.duckdb")
    db_mgr = DuckDBManager(db_path)
    db_mgr.open()
    db_mgr.conn.execute("CREATE SCHEMA IF NOT EXISTS pre_bronze")
    pb_layer = PreBronzeLayer(db_mgr)
    return db_mgr, pb_layer


def test_multi_binding_collision_free_persistence(
    pre_bronze_env: tuple[DuckDBManager, PreBronzeLayer],
) -> None:
    """Verify that multiple bindings targeting the same DatasetId persist without collision."""
    _db_mgr, pb_layer = pre_bronze_env

    # Two distinct bindings targeting the same transitional DatasetId
    binding_a = SourceBindingId("zerodha_broker__stock_orders")
    binding_b = SourceBindingId("groww_broker__stock_orders")

    contract_a = PreBronzeDataContract(
        binding_id=binding_a,
        physical_table=f"pre_bronze.{binding_a}",
        sync_strategy=SyncStrategy.INCREMENTAL,
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
    )
    contract_b = PreBronzeDataContract(
        binding_id=binding_b,
        physical_table=f"pre_bronze.{binding_b}",
        sync_strategy=SyncStrategy.INCREMENTAL,
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
    )

    df_a = pl.DataFrame({"order_id": ["ZA1", "ZA2"], "amount": [100.0, 200.0]})
    df_b = pl.DataFrame({"order_id": ["GB1", "GB2", "GB3"], "amount": [300.0, 400.0, 500.0]})

    # Persist binding A
    pb_layer.write_incremental(
        contract=contract_a,
        df=df_a,
        artifact_id="art_zerodha_01",
        source_id=SourceId("zerodha_broker"),
    )

    # Persist binding B
    pb_layer.write_incremental(
        contract=contract_b,
        df=df_b,
        artifact_id="art_groww_01",
        source_id=SourceId("groww_broker"),
    )

    # Read back each binding independently
    read_a = pb_layer.read(binding_a, include_provenance=True)
    read_b = pb_layer.read(binding_b, include_provenance=True)

    assert read_a.height == 2
    assert read_b.height == 3

    assert PRE_BRONZE_BINDING_ID in read_a.columns
    assert PRE_BRONZE_SOURCE_ID in read_a.columns
    assert read_a[PRE_BRONZE_BINDING_ID].to_list() == [str(binding_a), str(binding_a)]
    assert read_b[PRE_BRONZE_BINDING_ID].to_list() == [
        str(binding_b),
        str(binding_b),
        str(binding_b),
    ]

    # Assert mutual isolation: data from A does not exist in B and vice versa
    assert set(read_a["order_id"].to_list()) == {"ZA1", "ZA2"}
    assert set(read_b["order_id"].to_list()) == {"GB1", "GB2", "GB3"}


def test_gate_one_validation_context_includes_binding_id() -> None:
    """Verify that Gate 1 validation reporting captures binding_id in context and error."""
    binding_id = SourceBindingId("custom_source__special_stream")
    source_id = SourceId("custom_source")

    ctx = ValidationContext(
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        source_id=source_id,
        contract_id=f"pre_bronze_{binding_id}",
        binding_id=binding_id,
    )
    assert ctx.binding_id == binding_id

    res = ValidationResult(
        is_valid=False,
        stage=ValidationStage.PRE_BRONZE,
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        source_id=source_id,
        binding_id=binding_id,
        contract_id=f"pre_bronze_{binding_id}",
        contract_version="1.0.0",
        affected_row_count=1,
        failures=(
            ValidationCheckFailure(
                column="order_id",
                check="not_nullable",
                error_message="Nulls found",
                failure_count=1,
                examples=(),
            ),
        ),
    )
    error = ValidationError(result=res)
    error_str = str(error)
    assert f"source '{source_id}'" in error_str
    assert f"binding '{binding_id}'" in error_str
