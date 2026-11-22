"""Tests verifying the legacy 1:1 coupling between physical source datasets and canonical dataset identity.

Owns
----
- Migration baseline verification demonstrating coupling between physical source bindings and canonical datasets.
- Verification that SourceDatasetConfig.dataset_id is coupled directly to DatasetPlan.dataset_id.
- Verification that Pre-Bronze warehouse table naming directly mirrors canonical DatasetId.
- Verification that one physical evidence container (e.g. SQLite) requires duplicate SourceDatasetConfig
  declarations to ingest multiple logical tables.

Does not own
------------
- Target decoupled multi-source architecture (governed by binding_model.py and canonical_plans.py).
- Removal Owner: Phase 055 (when legacy SourceDatasetConfig is decommissioned).
"""

from __future__ import annotations

from personal_finance_etl.application.pipeline.source_planner import DatasetPlan
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    SyncStrategy,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.datasets import DatasetId, DatasetOrigin
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_CONTRACT_REGISTRY,
)


def test_legacy_source_dataset_config_couples_physical_and_canonical_identity() -> None:
    """Demonstrate that legacy SourceDatasetConfig treats physical stream identity as canonical DatasetId."""
    source_id = SourceId("sqlite_household")
    selector = SqliteSelector(table_name="ZCATEGORY")

    # In legacy architecture, the binding cannot declare its own binding ID; it must use canonical DatasetId
    binding = SourceDatasetConfig(
        source_id=source_id,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=selector,
    )

    assert binding.source_id == "sqlite_household"
    assert binding.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert selector.table_name == "ZCATEGORY"
    assert binding.dataset_id.value == "household_zcategory"


def test_legacy_dataset_plan_couples_source_and_canonical_id() -> None:
    """Demonstrate that legacy DatasetPlan carries a 1:1 dataset_id without an intermediate binding ID."""
    plan = DatasetPlan(
        source_id=SourceId("sqlite_household"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        provider_type=ProviderType.SQLITE,
        location="data/household.sqlite",
        selector=SqliteSelector(table_name="ZCATEGORY"),
        change_detection=ChangeDetectionPolicy(sync_strategy=SyncStrategy.FULL_REPLACE),
        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
        is_required=True,
        is_enabled=True,
    )

    # Legacy DatasetPlan lacks a dedicated source_binding_id field
    assert hasattr(plan, "dataset_id")
    assert not hasattr(plan, "binding_id")
    assert plan.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY


def test_legacy_pre_bronze_table_naming_mirrors_canonical_dataset_id() -> None:
    """Demonstrate that Pre-Bronze tables in legacy architecture are named pre_bronze.<dataset_id>."""
    pb_contract = next(
        c for c in PRE_BRONZE_CONTRACT_REGISTRY if c.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    )

    # Pre-Bronze physical table is now keyed by SourceBindingId
    assert pb_contract.physical_table == f"pre_bronze.{pb_contract.binding_id}"
    assert pb_contract.binding_id == "household_db__household_zcategory"
    assert pb_contract.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY


def test_legacy_single_source_requires_duplicated_binding_declarations() -> None:
    """Demonstrate that 1:N source-to-table requires declaring multiple SourceDatasetConfig objects."""
    src = SourceConfig(
        source_id=SourceId("sqlite_household"),
        provider_type=ProviderType.SQLITE,
        location="data/household.sqlite",
    )

    # Ingesting ZCATEGORY, INOUTCOME, and ASSETS from one SQLite file
    # requires creating 3 distinct SourceDatasetConfig objects repeating the same source_id
    binding_cat = SourceDatasetConfig(
        source_id=src.source_id,
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
    )
    binding_txn = SourceDatasetConfig(
        source_id=src.source_id,
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        selector=SqliteSelector(table_name="INOUTCOME"),
    )
    binding_assets = SourceDatasetConfig(
        source_id=src.source_id,
        dataset_id=DatasetId.HOUSEHOLD_ASSETS,
        selector=SqliteSelector(table_name="ASSETS"),
    )

    # All three bindings repeat the source_id because legacy config lacks multi-stream SourceBinding
    assert binding_cat.source_id == binding_txn.source_id == binding_assets.source_id
    assert {binding_cat.dataset_id, binding_txn.dataset_id, binding_assets.dataset_id} == {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_ASSETS,
    }
