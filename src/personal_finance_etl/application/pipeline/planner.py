"""Financial capability execution planner.

Owns
----
- CapabilityPlanner: Resolves requested capabilities into an immutable, deterministically fingerprinted ExecutionPlan.
- Default full-system capability plan creation.
- Canonical JSON hashing for plan fingerprint generation.

Does not own
-------------
- Capability dependency graph definitions (owned by contracts.capabilities).
- Stage execution and pipeline orchestration (owned by application.pipeline.execution).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import (
    CapabilityGraph,
    CapabilityId,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan

__all__ = ["CapabilityPlanner", "DEFAULT_ENGINE_STAGES"]

DEFAULT_ENGINE_STAGES: tuple[EngineStage, ...] = (
    EngineStage.INITIALIZING,
    EngineStage.DISCOVERING,
    EngineStage.EXTRACTING,
    EngineStage.TRANSFORMING,
    EngineStage.ANALYZING,
    EngineStage.PUBLISHING,
)


class CapabilityPlanner:
    """Constructs immutable, validated ExecutionPlan instances from capability selections.

    Parameters
    ----------
    graph : CapabilityGraph | None, optional
        Underlying capability graph. Defaults to authoritative CapabilityGraph instance.
    """

    def __init__(self, graph: CapabilityGraph | None = None) -> None:
        self.graph = graph or CapabilityGraph()

    def create_plan(
        self,
        requested_capabilities: Iterable[CapabilityId] | None = None,
        ordered_engine_stages: tuple[EngineStage, ...] | None = None,
    ) -> ExecutionPlan:
        """Resolve requested capabilities into an immutable ExecutionPlan.

        Parameters
        ----------
        requested_capabilities : Iterable[CapabilityId] | None, optional
            Capabilities requested to execute. If None, defaults to the full current capability set.
        ordered_engine_stages : tuple[EngineStage, ...] | None, optional
            Engine execution stages for the plan. Defaults to DEFAULT_ENGINE_STAGES.

        Returns
        -------
        ExecutionPlan
            Immutable, deterministic execution plan with computed cryptographic fingerprint.
        """
        resolved = self.graph.resolve(requested_capabilities)

        stages = ordered_engine_stages or DEFAULT_ENGINE_STAGES

        # Deterministic sorting for canonical JSON fingerprint calculation
        sorted_req_bronze = tuple(sorted(resolved.required_bronze_datasets, key=lambda d: d.value))
        sorted_opt_bronze = tuple(sorted(resolved.optional_bronze_datasets, key=lambda d: d.value))
        sorted_silver = tuple(sorted(resolved.produced_silver_datasets, key=lambda d: d.value))
        sorted_gold = tuple(sorted(resolved.produced_gold_datasets, key=lambda d: d.value))
        sorted_enrichments = tuple(
            sorted(resolved.required_external_enrichments, key=lambda e: e.value)
        )

        canonical_payload = {
            "capabilities": [c.value for c in resolved.active_capabilities],
            "enrichments": [e.value for e in sorted_enrichments],
            "gold_datasets": [d.value for d in sorted_gold],
            "optional_bronze": [d.value for d in sorted_opt_bronze],
            "required_bronze": [d.value for d in sorted_req_bronze],
            "silver_datasets": [d.value for d in sorted_silver],
            "stages": [s.value for s in stages],
        }

        serialized = json.dumps(canonical_payload, separators=(",", ":"), sort_keys=True)
        hash_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        plan_fingerprint = f"plan_{hash_digest}"

        return ExecutionPlan(
            plan_fingerprint=plan_fingerprint,
            requested_capabilities=resolved.requested_capabilities,
            resolved_capabilities=resolved.active_capabilities,
            required_bronze_datasets=sorted_req_bronze,
            optional_bronze_datasets=sorted_opt_bronze,
            active_silver_datasets=sorted_silver,
            active_gold_datasets=sorted_gold,
            required_external_enrichments=sorted_enrichments,
            ordered_engine_stages=stages,
            active_contributions=resolved.active_contributions,
        )
