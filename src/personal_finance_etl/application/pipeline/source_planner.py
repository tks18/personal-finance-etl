"""Application source planner and deterministic execution plan compiler.

Owns
----
- SourcePlanningError: Dedicated exception for source configuration planning failures.
- DatasetPlan: Immutable compiled execution plan for an individual dataset.
- SourcePlan: Immutable compiled execution plan for an evidence source and its child datasets.
- CompiledSourcePlan: Complete immutable compiled source topology plan.
- SourcePlanner: Non-I/O application compiler transforming SourceConfiguration + ExecutionPlan
  into deterministic DatasetPlan and SourcePlan objects.

Does not own
-------------
- Source configuration models or TOML parsing (owned by config.sources).
- Physical file access or provider extraction (owned by infrastructure.providers).
- Capability graph or execution planning (owned by contracts.capabilities and application.pipeline.planner).
"""

from __future__ import annotations

from dataclasses import dataclass

from personal_finance_etl.config.settings import FileHashPolicy
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    resolve_change_detection_policy,
)
from personal_finance_etl.config.sources.identity import BronzeIdentityStrategy
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.selectors import DatasetSelector
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    DatasetId,
    DatasetOrigin,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.sources import ProviderType, SourceId

__all__ = [
    "CompiledSourcePlan",
    "DatasetPlan",
    "SourcePlan",
    "SourcePlanner",
    "SourcePlanningError",
]


class SourcePlanningError(Exception):
    """Raised when source planning or dataset satisfiability fails."""


@dataclass(frozen=True, slots=True)
class DatasetPlan:
    """Immutable compiled execution plan for an individual canonical dataset.

    Parameters
    ----------
    source_id : SourceId
        Logical identifier of the physical evidence source supplying this dataset.
    dataset_id : DatasetId
        Canonical dataset identifier.
    provider_type : ProviderType
        Physical extractor provider type.
    location : str
        Configured filesystem location or URI.
    selector : DatasetSelector
        Provider-specific typed selector.
    change_detection : ChangeDetectionPolicy
        Resolved change-detection and synchronization policy.
    origin : DatasetOrigin
        Authoritative dataset origin classification.
    is_required : bool
        Whether this dataset is mandatory under the active ExecutionPlan.
    is_enabled : bool
        Whether this dataset is actively enabled for execution.
    mapping_plan : object | None, default None
        Mapping and normalization plan (unresolved placeholder until Phase 018).
    identity_strategy : BronzeIdentityStrategy | None, default None
        Bronze row identity strategy reference where configured.
    """

    source_id: SourceId
    dataset_id: DatasetId
    provider_type: ProviderType
    location: str
    selector: DatasetSelector
    change_detection: ChangeDetectionPolicy
    origin: DatasetOrigin
    is_required: bool
    is_enabled: bool
    mapping_plan: object | None = None
    identity_strategy: BronzeIdentityStrategy | None = None


@dataclass(frozen=True, slots=True)
class SourcePlan:
    """Immutable compiled execution plan for an evidence source and its child datasets.

    Parameters
    ----------
    source_id : SourceId
        Logical identifier of the physical evidence source.
    provider_type : ProviderType
        Physical extractor provider type.
    location : str
        Configured filesystem location or URI.
    enabled : bool
        Whether the source is operationally enabled.
    dataset_plans : tuple[DatasetPlan, ...]
        Compiled plans for datasets bound to this source.
    """

    source_id: SourceId
    provider_type: ProviderType
    location: str
    enabled: bool
    dataset_plans: tuple[DatasetPlan, ...]


@dataclass(frozen=True, slots=True)
class CompiledSourcePlan:
    """Complete immutable compiled source topology plan.

    Parameters
    ----------
    source_plans : tuple[SourcePlan, ...]
        All compiled source plans.
    dataset_plans : tuple[DatasetPlan, ...]
        All compiled dataset plans in deterministic order.
    """

    source_plans: tuple[SourcePlan, ...]
    dataset_plans: tuple[DatasetPlan, ...]

    def get_dataset_plan(self, dataset_id: DatasetId | str) -> DatasetPlan | None:
        """Find a dataset plan by canonical DatasetId.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Target canonical dataset identifier.

        Returns
        -------
        DatasetPlan | None
            Matching DatasetPlan if compiled, else None.
        """
        target = str(dataset_id)
        for dp in self.dataset_plans:
            if str(dp.dataset_id) == target:
                return dp
        return None

    def get_source_plan(self, source_id: SourceId | str) -> SourcePlan | None:
        """Find a source plan by logical SourceId.

        Parameters
        ----------
        source_id : SourceId | str
            Target logical source identifier.

        Returns
        -------
        SourcePlan | None
            Matching SourcePlan if compiled, else None.
        """
        target = str(source_id)
        for sp in self.source_plans:
            if str(sp.source_id) == target:
                return sp
        return None

    def is_dataset_enabled(self, dataset_id: DatasetId | str) -> bool:
        """Return True if dataset has a compiled plan and is actively enabled.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Target canonical dataset identifier.

        Returns
        -------
        bool
            True if the dataset plan exists and is enabled, else False.
        """
        dp = self.get_dataset_plan(dataset_id)
        return dp.is_enabled if dp is not None else False


class SourcePlanner:
    """Compiles validated SourceConfiguration and ExecutionPlan into immutable plans without I/O.

    Parameters
    ----------
    source_config : SourceConfiguration
        Validated user source configuration.
    execution_plan : ExecutionPlan
        Authoritative resolved execution plan.
    """

    def __init__(
        self,
        source_config: SourceConfiguration,
        execution_plan: ExecutionPlan,
    ) -> None:
        self.source_config = source_config
        self.execution_plan = execution_plan

    def compile_plan(self) -> CompiledSourcePlan:
        """Compile source configuration and execution plan into deterministic plans.

        Returns
        -------
        CompiledSourcePlan
            Immutable compiled source plan.

        Raises
        ------
        SourcePlanningError
            If an enabled/required dataset cannot be satisfied by the configured sources.
        """
        sources_by_id = {s.source_id: s for s in self.source_config.sources}

        dataset_plans_list: list[DatasetPlan] = []
        satisfied_datasets: set[DatasetId] = set()

        for binding in self.source_config.datasets:
            source = sources_by_id.get(binding.source_id)
            if source is None:
                raise SourcePlanningError(
                    f"Dataset binding '{binding.dataset_id.value}' references unknown source '{binding.source_id}'."
                )

            origin = BRONZE_DATASET_ORIGIN_MAP.get(
                binding.dataset_id, DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE
            )

            # Resolve change detection policy
            policy = binding.change_detection or resolve_change_detection_policy(
                file_type=source.provider_type.value,
                is_full_replace=False,
                hash_policy=FileHashPolicy(),
                is_provider_generated=(origin == DatasetOrigin.PROVIDER_GENERATED),
            )

            # Check required & enabled against execution_plan
            is_required = self.execution_plan.is_dataset_required(binding.dataset_id)
            is_active_in_plan = self.execution_plan.is_bronze_dataset_active(binding.dataset_id)
            is_enabled = binding.enabled and source.enabled and is_active_in_plan

            dp = DatasetPlan(
                source_id=binding.source_id,
                dataset_id=binding.dataset_id,
                provider_type=source.provider_type,
                location=source.location,
                selector=binding.selector,
                change_detection=policy,
                origin=origin,
                is_required=is_required,
                is_enabled=is_enabled,
                mapping_plan=None,
                identity_strategy=binding.identity,
            )
            dataset_plans_list.append(dp)
            if is_enabled:
                satisfied_datasets.add(binding.dataset_id)

        # Invariant check: All required Bronze datasets with EXTERNAL_CONFIGURED_SOURCE origin
        # must be configured in the source configuration bindings
        configured_datasets = {binding.dataset_id for binding in self.source_config.datasets}
        for req_id in self.execution_plan.required_bronze_datasets:
            origin = BRONZE_DATASET_ORIGIN_MAP.get(req_id, DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE)
            if origin == DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE:
                if req_id not in configured_datasets:
                    raise SourcePlanningError(
                        f"Required Bronze dataset '{req_id.value}' cannot be satisfied by configured source bindings. "
                        f"Ensure a valid source binding exists for '{req_id.value}'."
                    )

        # Assemble SourcePlans grouped by source_id
        ds_by_source: dict[SourceId, list[DatasetPlan]] = {}
        for dp in dataset_plans_list:
            ds_by_source.setdefault(dp.source_id, []).append(dp)

        source_plans_list: list[SourcePlan] = []
        for src in self.source_config.sources:
            sp = SourcePlan(
                source_id=src.source_id,
                provider_type=src.provider_type,
                location=src.location,
                enabled=src.enabled,
                dataset_plans=tuple(ds_by_source.get(src.source_id, [])),
            )
            source_plans_list.append(sp)

        return CompiledSourcePlan(
            source_plans=tuple(source_plans_list),
            dataset_plans=tuple(dataset_plans_list),
        )
