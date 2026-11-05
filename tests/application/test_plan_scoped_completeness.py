# pyright: reportPrivateUsage=false
"""Enterprise test suite for plan-scoped completeness and plan snapshot persistence.

Owns
----
- PipelineExecutor plan injection and default plan assignment verification.
- Plan-scoped completeness validation in _run_analytics_phase:
  - 100% full plan parity validation.
  - Unexpected / inactive table detection and failure reporting with plan fingerprint.
  - Missing active table detection and failure reporting with plan fingerprint.
  - Synthetic partial plan execution passing with scoped subsets.
- Control Plane plan snapshot persistence (cp_plan_snapshots) and run linking.

Does not own
-------------
- Capability graph topological resolution (owned by test_capabilities.py).
- CapabilityPlanner resolution algorithms (owned by test_capability_planner.py).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Fixture providing initialized Settings pointing to temporary directory."""
    return Settings(
        TARGET_DB_BASE_PATH=str(tmp_path),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        STATEMENTS_FOLDER=str(tmp_path / "statements"),
    )


def test_pipeline_executor_plan_injection(test_settings: Settings) -> None:
    """Verify PipelineExecutor accepts injected plan and falls back to default full plan."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()

    # 1. Default fallback
    default_executor = PipelineExecutor(test_settings, queue, db_manager)
    assert default_executor.plan is not None
    assert default_executor.plan.active_analytical_dataset_count == 46

    # 2. Injected plan
    custom_plan = CapabilityPlanner().create_plan(
        requested_capabilities=[CapabilityId.HOUSEHOLD_CORE]
    )
    injected_executor = PipelineExecutor(test_settings, queue, db_manager, plan=custom_plan)
    assert injected_executor.plan is custom_plan
    assert injected_executor.plan.plan_fingerprint == custom_plan.plan_fingerprint


def test_plan_scoped_completeness_full_plan_success(test_settings: Settings) -> None:
    """Verify _run_analytics_phase succeeds when all plan-scoped analytical tables are produced."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()
    executor = PipelineExecutor(test_settings, queue, db_manager)

    # Mock engine execution to skip heavy domain calculations
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate dfs with all 46 registered contracts
    for contract in DATA_CONTRACT_REGISTRY:
        executor.dfs[contract.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    # Must succeed without error
    executor._run_analytics_phase(cp, "run_test_001")


def test_plan_scoped_completeness_unexpected_table_rejected(test_settings: Settings) -> None:
    """Verify _run_analytics_phase rejects tables not declared in active plan."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()

    # Create partial plan only containing HOUSEHOLD_CORE
    planner = CapabilityPlanner()
    partial_plan = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])
    executor = PipelineExecutor(test_settings, queue, db_manager, plan=partial_plan)
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate only active datasets
    contract_by_dataset = {c.dataset_id: c for c in DATA_CONTRACT_REGISTRY}
    for ds_id in partial_plan.active_analytical_datasets:
        if ds_id in contract_by_dataset:
            executor.dfs[contract_by_dataset[ds_id].contract_id] = pl.DataFrame({"id": [1]})

    # Now add an analytical table that is in DATA_CONTRACT_REGISTRY but NOT active in partial plan
    unexpected_contract = contract_by_dataset[DatasetId.TAX_YEAR_SUMMARY]
    executor.dfs[unexpected_contract.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    with pytest.raises(RuntimeError) as exc_info:
        executor._run_analytics_phase(cp, "run_test_002")

    msg = str(exc_info.value)
    assert f"unexpected analytical table '{unexpected_contract.contract_id}'" in msg
    assert f"dataset_id='{unexpected_contract.dataset_id.value}'" in msg
    assert f"execution plan '{partial_plan.plan_fingerprint}'" in msg


def test_plan_scoped_completeness_missing_table_rejected(test_settings: Settings) -> None:
    """Verify _run_analytics_phase rejects runs missing required plan analytical tables."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()
    executor = PipelineExecutor(test_settings, queue, db_manager)
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate all 46 except the first contract
    target_contract = DATA_CONTRACT_REGISTRY[0]
    for contract in DATA_CONTRACT_REGISTRY:
        if contract != target_contract:
            executor.dfs[contract.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    with pytest.raises(RuntimeError) as exc_info:
        executor._run_analytics_phase(cp, "run_test_003")

    msg = str(exc_info.value)
    assert "Engine failed to produce required plan analytical datasets" in msg
    assert target_contract.dataset_id.value in msg
    assert executor.plan.plan_fingerprint in msg


def test_synthetic_partial_plan_scoped_completeness(test_settings: Settings) -> None:
    """Verify a synthetic partial plan passes completeness with exactly its active tables."""
    c1 = DATA_CONTRACT_REGISTRY[0]
    c2 = DATA_CONTRACT_REGISTRY[1]
    synthetic_plan = ExecutionPlan(
        plan_fingerprint="plan_synthetic001",
        requested_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        resolved_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        required_bronze_datasets=(DatasetId.HOUSEHOLD_INOUTCOME,),
        optional_bronze_datasets=(),
        active_silver_datasets=(c1.dataset_id,),
        active_gold_datasets=(c2.dataset_id,),
        required_external_enrichments=(),
        ordered_engine_stages=(
            EngineStage.EXTRACTING,
            EngineStage.TRANSFORMING,
            EngineStage.ANALYZING,
        ),
    )

    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()
    executor = PipelineExecutor(test_settings, queue, db_manager, plan=synthetic_plan)
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate only the 2 active analytical tables
    executor.dfs[c1.contract_id] = pl.DataFrame({"id": [1]})
    executor.dfs[c2.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    # Must succeed without error
    executor._run_analytics_phase(cp, "run_test_004")


def test_control_plane_plan_snapshot_lifecycle(tmp_path: Path) -> None:
    """Verify ControlPlane records plan snapshot and links plan_snapshot_id to run metadata."""
    cp = ControlPlane(str(tmp_path), "test_cp.sqlite")
    cp.open()
    cp.ensure_schema()

    planner = CapabilityPlanner()
    plan = planner.create_plan()

    # Start run with plan
    run_id = cp.runs.start_run(
        cfg_json='{"test": 1}',
        rules_json='{"rules": 1}',
        plan=plan,
    )

    # Verify run metadata links plan_snapshot_id
    meta = cp.runs.get_run_metadata(run_id)
    assert meta["plan_snapshot_id"] == plan.plan_fingerprint

    # Verify plan snapshot table has content
    cursor = cp.db.conn.cursor()
    cursor.execute(
        "SELECT snapshot_id, content_hash, canonical_payload FROM cp_plan_snapshots WHERE snapshot_id = ?",
        (plan.plan_fingerprint,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == plan.plan_fingerprint
    assert row[1] == plan.plan_fingerprint.removeprefix("plan_")
    assert "capabilities" in row[2]

    # Verify idempotent logging does not fail
    cp.runs.log_plan_snapshot(run_id, plan)
    cp.close()
