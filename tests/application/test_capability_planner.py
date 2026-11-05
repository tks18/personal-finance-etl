"""Enterprise test suite for CapabilityPlanner.

Owns
----
- Verification of default full execution plan generation and 100% contract parity.
- Verification of 46 analytical datasets and 20 Bronze datasets matching active plan.
- Deterministic SHA-256 fingerprint verification across plan instantiations.
- Partial capability plan scoping and transitive dependency resolution.
- Error handling on unknown requested capabilities.

Does not own
-------------
- Physical warehouse persistence (owned by infrastructure.warehouse).
- Runtime pipeline stage execution (owned by test_plan_scoped_completeness.py).
"""

from __future__ import annotations

import pytest

from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import (
    CapabilityGraphError,
    CapabilityId,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)


def test_default_full_plan_generation() -> None:
    """Verify CapabilityPlanner creates a full-system execution plan by default."""
    planner = CapabilityPlanner()
    plan = planner.create_plan()

    assert plan.plan_fingerprint.startswith("plan_")
    assert len(plan.plan_fingerprint) == 21  # 'plan_' (5) + 16 hex chars

    # Full system parity checks
    assert plan.active_capability_count == len(CapabilityId)
    assert plan.active_bronze_dataset_count == 20
    assert plan.active_analytical_dataset_count == 46

    # Verify every analytical contract in DATA_CONTRACT_REGISTRY is in plan
    registry_analytical_datasets = {c.dataset_id for c in DATA_CONTRACT_REGISTRY}
    assert set(plan.active_analytical_datasets) == registry_analytical_datasets

    # Verify every Bronze contract in BRONZE_CONTRACT_REGISTRY is in plan
    registry_bronze_datasets = {c.dataset_id for c in BRONZE_CONTRACT_REGISTRY}
    assert set(plan.active_bronze_datasets) == registry_bronze_datasets

    # Active stages verification
    expected_stages = (
        EngineStage.INITIALIZING,
        EngineStage.DISCOVERING,
        EngineStage.EXTRACTING,
        EngineStage.TRANSFORMING,
        EngineStage.ANALYZING,
        EngineStage.PUBLISHING,
    )
    assert plan.active_stages == expected_stages


def test_plan_fingerprint_determinism() -> None:
    """Verify identical capability selections generate byte-identical fingerprints."""
    planner = CapabilityPlanner()
    plan1 = planner.create_plan()
    plan2 = planner.create_plan()

    assert plan1.plan_fingerprint == plan2.plan_fingerprint
    assert plan1.to_canonical_json() == plan2.to_canonical_json()


def test_partial_capability_plan() -> None:
    """Verify partial execution plans scope active datasets and produce distinct fingerprints."""
    planner = CapabilityPlanner()
    partial_plan = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])

    assert partial_plan.is_capability_active(CapabilityId.HOUSEHOLD_CORE)
    assert not partial_plan.is_capability_active(CapabilityId.TAX)

    full_plan = planner.create_plan()
    assert partial_plan.plan_fingerprint != full_plan.plan_fingerprint
    assert partial_plan.active_capability_count < full_plan.active_capability_count
    assert partial_plan.active_analytical_dataset_count < full_plan.active_analytical_dataset_count

    # Repeat partial plan generation is deterministic
    partial_plan_2 = planner.create_plan(requested_capabilities=[CapabilityId.HOUSEHOLD_CORE])
    assert partial_plan.plan_fingerprint == partial_plan_2.plan_fingerprint


def test_unknown_capability_rejected() -> None:
    """Verify planner rejects invalid capability identifiers."""
    planner = CapabilityPlanner()
    with pytest.raises((CapabilityGraphError, ValueError)):
        planner.create_plan(requested_capabilities=["NON_EXISTENT_CAPABILITY"])  # type: ignore[list-item]
