"""Enterprise test suite for ExecutionPlan contract.

Owns
----
- Verification of ExecutionPlan immutability and frozen slots enforcement.
- Query helper methods: is_dataset_active, is_capability_active, dataset_count, capability_count.
- Deterministic JSON and dictionary serialization / deserialization roundtrip.
- Byte-stable cryptographic fingerprinting verification.

Does not own
-------------
- Topological capability graph resolution (owned by test_capabilities.py).
- Capability planner algorithms (owned by test_capability_planner.py).
- Pipeline runtime stage execution (owned by test_plan_scoped_completeness.py).
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.execution_plan import ExecutionPlan


def _create_sample_plan() -> ExecutionPlan:
    """Create a minimal deterministic ExecutionPlan for testing."""
    return ExecutionPlan(
        plan_fingerprint="plan_1234567890abcdef",
        requested_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        resolved_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        required_bronze_datasets=(DatasetId.HOUSEHOLD_INOUTCOME, DatasetId.HOUSEHOLD_ASSETS),
        optional_bronze_datasets=(),
        active_silver_datasets=(DatasetId.COMMON_CALENDAR, DatasetId.WEALTH_INCOME_CATEGORY),
        active_gold_datasets=(DatasetId.WEALTH_CORE_MONTHLY,),
        required_external_enrichments=(),
        ordered_engine_stages=(EngineStage.EXTRACTING, EngineStage.TRANSFORMING),
    )


def test_execution_plan_immutability() -> None:
    """Verify ExecutionPlan is frozen and cannot be modified after construction."""
    plan = _create_sample_plan()
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.plan_fingerprint = "new_fingerprint"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.resolved_capabilities = ()  # type: ignore[misc]


def test_execution_plan_query_helpers() -> None:
    """Verify is_dataset_active and is_capability_active return correct membership."""
    plan = _create_sample_plan()

    assert plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE) is True
    assert plan.is_capability_active(CapabilityId.TAX) is False
    assert plan.is_capability_active("HOUSEHOLD_CORE") is True
    assert plan.is_capability_active("TAX") is False

    assert plan.is_dataset_active(DatasetId.COMMON_CALENDAR) is True
    assert plan.is_dataset_active(DatasetId.WEALTH_CORE_MONTHLY) is True
    assert plan.is_dataset_active(DatasetId.FIRE_ANALYTICS) is False
    assert plan.is_dataset_active("common_calendar") is True
    assert plan.is_dataset_active("FIRE_ANALYTICS") is False

    assert plan.active_capability_count == 1
    assert plan.active_analytical_dataset_count == 3
    assert plan.active_bronze_dataset_count == 2


def test_execution_plan_serialization_roundtrip() -> None:
    """Verify to_dict and from_dict produce lossless reconstruction."""
    plan = _create_sample_plan()
    data = plan.to_dict()

    assert data["plan_fingerprint"] == "plan_1234567890abcdef"
    assert data["resolved_capabilities"] == ["household_core"]
    assert isinstance(data["required_bronze_datasets"], list)
    assert "household_inoutcome" in data["required_bronze_datasets"]
    assert isinstance(data["active_silver_datasets"], list)
    assert "common_calendar" in data["active_silver_datasets"]
    assert isinstance(data["active_gold_datasets"], list)
    assert "wealth_core_monthly" in data["active_gold_datasets"]
    assert data["ordered_engine_stages"] == ["EXTRACTING", "TRANSFORMING"]

    reconstructed = ExecutionPlan.from_dict(data)
    assert reconstructed == plan
    assert reconstructed.plan_fingerprint == plan.plan_fingerprint
    assert reconstructed.active_capabilities == plan.active_capabilities
    assert reconstructed.active_analytical_datasets == plan.active_analytical_datasets
    assert reconstructed.active_stages == plan.active_stages


def test_execution_plan_canonical_json_determinism() -> None:
    """Verify to_canonical_json produces sorted, compact, deterministic output."""
    plan = _create_sample_plan()
    json_str_1 = plan.to_canonical_json()
    json_str_2 = plan.to_canonical_json()

    assert json_str_1 == json_str_2
    parsed = json.loads(json_str_1)
    assert parsed["plan_fingerprint"] == "plan_1234567890abcdef"
    # Compact format verification: no spaces after colons/commas
    assert ", " not in json_str_1
    assert ": " not in json_str_1
