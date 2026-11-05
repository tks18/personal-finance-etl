"""Immutable execution plan contract governing pipeline execution and plan-scoped completeness.

Owns
----
- ExecutionPlan: Immutable contract specifying active capabilities, required/optional Bronze
  datasets, active Silver/Gold presentation contracts, external enrichments, and engine stages.
- plan_fingerprint: Cryptographic hash prefix for deterministic plan identity and provenance.
- Analytical contract query helpers (active_analytical_datasets, is_capability_active, is_dataset_active).

Does not own
-------------
- Capability topological sort and planning logic (owned by application.pipeline.planner).
- Physical execution or stage orchestration (owned by application.pipeline.execution).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    ContributionDescriptor,
    ContributionScope,
    ExternalEnrichmentId,
)
from personal_finance_etl.contracts.datasets import DatasetId

__all__ = ["ExecutionPlan"]


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Immutable execution plan governing pipeline execution and plan-scoped completeness.

    Parameters
    ----------
    plan_fingerprint : str
        Cryptographic SHA-256 fingerprint prefix uniquely identifying the plan configuration.
    requested_capabilities : tuple[CapabilityId, ...]
        Capabilities explicitly requested by configuration or orchestrator.
    resolved_capabilities : tuple[CapabilityId, ...]
        Topologically sorted list of all active capabilities including transitive dependencies.
    required_bronze_datasets : tuple[DatasetId, ...]
        Mandatory canonical Bronze datasets required for execution.
    optional_bronze_datasets : tuple[DatasetId, ...]
        Optional Bronze datasets consumed if present.
    active_silver_datasets : tuple[DatasetId, ...]
        Canonical Silver datasets produced and expected to be persisted.
    active_gold_datasets : tuple[DatasetId, ...]
        Decision-ready Gold analytical datasets produced and expected to be persisted.
    required_external_enrichments : tuple[ExternalEnrichmentId, ...]
        External provider market data feeds required by the active plan.
    ordered_engine_stages : tuple[EngineStage, ...]
        High-level pipeline execution stages governed by this plan.
    active_contributions : tuple[ContributionDescriptor, ...], default=()
        Active cross-capability financial contributions between active capabilities.
    """

    plan_fingerprint: str
    requested_capabilities: tuple[CapabilityId, ...]
    resolved_capabilities: tuple[CapabilityId, ...]
    required_bronze_datasets: tuple[DatasetId, ...]
    optional_bronze_datasets: tuple[DatasetId, ...]
    active_silver_datasets: tuple[DatasetId, ...]
    active_gold_datasets: tuple[DatasetId, ...]
    required_external_enrichments: tuple[ExternalEnrichmentId, ...]
    ordered_engine_stages: tuple[EngineStage, ...]
    active_contributions: tuple[ContributionDescriptor, ...] = ()

    @property
    def active_capabilities(self) -> tuple[CapabilityId, ...]:
        """Alias for resolved active capabilities in topological order.

        Returns
        -------
        tuple[CapabilityId, ...]
            Topologically sorted list of active capabilities.
        """
        return self.resolved_capabilities

    @property
    def active_stages(self) -> tuple[EngineStage, ...]:
        """Alias for ordered engine stages governed by this execution plan.

        Returns
        -------
        tuple[EngineStage, ...]
            Execution stages for this plan.
        """
        return self.ordered_engine_stages

    @property
    def active_bronze_datasets(self) -> frozenset[DatasetId]:
        """Combined set of all required and optional Bronze datasets in this plan.

        Returns
        -------
        frozenset[DatasetId]
            Active Bronze datasets.
        """
        return frozenset(self.required_bronze_datasets + self.optional_bronze_datasets)

    @property
    def active_capability_count(self) -> int:
        """Count of active capabilities in this plan.

        Returns
        -------
        int
            Active capability count.
        """
        return len(self.resolved_capabilities)

    @property
    def active_bronze_dataset_count(self) -> int:
        """Count of active Bronze datasets in this plan.

        Returns
        -------
        int
            Active Bronze dataset count.
        """
        return len(self.active_bronze_datasets)

    @property
    def active_analytical_dataset_count(self) -> int:
        """Count of active analytical Silver and Gold datasets in this plan.

        Returns
        -------
        int
            Active analytical dataset count.
        """
        return len(self.active_analytical_datasets)

    @property
    def active_analytical_datasets(self) -> frozenset[DatasetId]:
        """Set of all active Silver and Gold analytical datasets expected to be produced.

        Returns
        -------
        frozenset[DatasetId]
            Combined set of active Silver and Gold analytical datasets.
        """
        return frozenset(self.active_silver_datasets + self.active_gold_datasets)

    def is_capability_active(self, capability_id: CapabilityId | str) -> bool:
        """Check whether a specific capability is active in this execution plan.

        Parameters
        ----------
        capability_id : CapabilityId | str
            Authoritative capability identifier to check.

        Returns
        -------
        bool
            True if active, False otherwise.
        """
        val = (
            capability_id.value
            if isinstance(capability_id, CapabilityId)
            else str(capability_id).lower()
        )
        return any(c.value == val for c in self.resolved_capabilities)

    def is_dataset_active(self, dataset_id: DatasetId | str) -> bool:
        """Check whether a specific Silver or Gold dataset is active in this execution plan.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Canonical dataset identifier to check.

        Returns
        -------
        bool
            True if active in either Silver or Gold layer, False otherwise.
        """
        val = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id).lower()
        return any(d.value == val for d in self.active_analytical_datasets)

    def is_bronze_dataset_active(self, dataset_id: DatasetId | str) -> bool:
        """Check whether a specific Bronze dataset is active (required or optional) in this execution plan.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Canonical Bronze dataset identifier to check.

        Returns
        -------
        bool
            True if active (required or optional), False otherwise.
        """
        val = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id).lower()
        return any(d.value == val for d in self.active_bronze_datasets)

    def is_dataset_required(self, dataset_id: DatasetId | str) -> bool:
        """Check whether a specific Bronze dataset is required by this execution plan.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Canonical Bronze dataset identifier to check.

        Returns
        -------
        bool
            True if required for execution, False otherwise.
        """
        val = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id).lower()
        return any(d.value == val for d in self.required_bronze_datasets)

    def to_dict(self) -> dict[str, object]:
        """Convert the execution plan to a deterministic JSON-serializable dictionary.

        Returns
        -------
        dict[str, object]
            JSON-serializable representation of the execution plan.
        """
        return {
            "plan_fingerprint": self.plan_fingerprint,
            "requested_capabilities": [c.value for c in self.requested_capabilities],
            "resolved_capabilities": [c.value for c in self.resolved_capabilities],
            "required_bronze_datasets": [d.value for d in self.required_bronze_datasets],
            "optional_bronze_datasets": [d.value for d in self.optional_bronze_datasets],
            "active_silver_datasets": [d.value for d in self.active_silver_datasets],
            "active_gold_datasets": [d.value for d in self.active_gold_datasets],
            "required_external_enrichments": [e.value for e in self.required_external_enrichments],
            "ordered_engine_stages": [s.value for s in self.ordered_engine_stages],
            "active_contributions": [
                {
                    "target_capability": c.target_capability.value,
                    "scope": c.scope.value,
                    "description": c.description,
                }
                for c in self.active_contributions
            ],
        }

    def to_canonical_json(self) -> str:
        """Serialize execution plan to sorted, compact canonical JSON format.

        Returns
        -------
        str
            Deterministic compact JSON string without whitespace variations.
        """
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ExecutionPlan:
        """Construct an ExecutionPlan from a serialized dictionary.

        Parameters
        ----------
        data : Mapping[str, object]
            Serialized key-value mapping representing execution plan fields.

        Returns
        -------
        ExecutionPlan
            Reconstructed execution plan instance.
        """
        raw_req_caps = data.get("requested_capabilities")
        req_caps: list[CapabilityId] = []
        if isinstance(raw_req_caps, list):
            for c in cast(list[object], raw_req_caps):
                if isinstance(c, (str, CapabilityId)):
                    req_caps.append(CapabilityId(str(c)))

        raw_res_caps = data.get("resolved_capabilities")
        res_caps: list[CapabilityId] = []
        if isinstance(raw_res_caps, list):
            for c in cast(list[object], raw_res_caps):
                if isinstance(c, (str, CapabilityId)):
                    res_caps.append(CapabilityId(str(c)))

        raw_req_br = data.get("required_bronze_datasets")
        req_br: list[DatasetId] = []
        if isinstance(raw_req_br, list):
            for d in cast(list[object], raw_req_br):
                if isinstance(d, (str, DatasetId)):
                    req_br.append(DatasetId(str(d)))

        raw_opt_br = data.get("optional_bronze_datasets")
        opt_br: list[DatasetId] = []
        if isinstance(raw_opt_br, list):
            for d in cast(list[object], raw_opt_br):
                if isinstance(d, (str, DatasetId)):
                    opt_br.append(DatasetId(str(d)))

        raw_sil = data.get("active_silver_datasets")
        act_sil: list[DatasetId] = []
        if isinstance(raw_sil, list):
            for d in cast(list[object], raw_sil):
                if isinstance(d, (str, DatasetId)):
                    act_sil.append(DatasetId(str(d)))

        raw_gold = data.get("active_gold_datasets")
        act_gold: list[DatasetId] = []
        if isinstance(raw_gold, list):
            for d in cast(list[object], raw_gold):
                if isinstance(d, (str, DatasetId)):
                    act_gold.append(DatasetId(str(d)))

        raw_enr = data.get("required_external_enrichments")
        req_enr: list[ExternalEnrichmentId] = []
        if isinstance(raw_enr, list):
            for e in cast(list[object], raw_enr):
                if isinstance(e, (str, ExternalEnrichmentId)):
                    req_enr.append(ExternalEnrichmentId(str(e)))

        raw_stg = data.get("ordered_engine_stages")
        ord_stg: list[EngineStage] = []
        if isinstance(raw_stg, list):
            for s in cast(list[object], raw_stg):
                if isinstance(s, (str, EngineStage)):
                    ord_stg.append(EngineStage(str(s)))

        raw_contrib = data.get("active_contributions")
        contributions: list[ContributionDescriptor] = []
        if isinstance(raw_contrib, list):
            for item in cast(list[object], raw_contrib):
                if isinstance(item, dict):
                    typed_dict = cast(dict[object, object], item)
                    raw_target = typed_dict.get("target_capability")
                    raw_scope = typed_dict.get("scope")
                    raw_desc = typed_dict.get("description")
                    if isinstance(raw_target, (str, CapabilityId)) and isinstance(
                        raw_scope, (str, ContributionScope)
                    ):
                        contributions.append(
                            ContributionDescriptor(
                                target_capability=CapabilityId(str(raw_target)),
                                scope=ContributionScope(str(raw_scope)),
                                description=str(raw_desc) if raw_desc is not None else "",
                            )
                        )

        return cls(
            plan_fingerprint=str(data.get("plan_fingerprint", "")),
            requested_capabilities=tuple(req_caps),
            resolved_capabilities=tuple(res_caps),
            required_bronze_datasets=tuple(req_br),
            optional_bronze_datasets=tuple(opt_br),
            active_silver_datasets=tuple(act_sil),
            active_gold_datasets=tuple(act_gold),
            required_external_enrichments=tuple(req_enr),
            ordered_engine_stages=tuple(ord_stg),
            active_contributions=tuple(contributions),
        )
