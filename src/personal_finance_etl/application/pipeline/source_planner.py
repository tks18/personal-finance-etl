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
from personal_finance_etl.config.sources.compiler import derive_source_binding_id
from personal_finance_etl.config.sources.identity import BronzeIdentityStrategy
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.selectors import (
    DatasetSelector,
    MarketProviderSelector,
)
from personal_finance_etl.contracts.canonical_plans import SourceBindingPlan
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    DatasetId,
    DatasetOrigin,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    ProviderType,
    SourceBindingId,
    SourceId,
)

__all__ = [
    "CompiledSourcePlan",
    "DatasetPlan",
    "SourceBindingPlan",
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
        Mapping and normalization plan descriptor where configured.
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
    """Immutable compiled execution plan for an evidence source and its child bindings.

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
    binding_plans : tuple[SourceBindingPlan, ...], default ()
        Compiled physical source binding plans owned by this source.
    dataset_plans : tuple[DatasetPlan, ...], default ()
        Transitional compiled plans for datasets bound to this source.
    """

    source_id: SourceId
    provider_type: ProviderType
    location: str
    enabled: bool
    binding_plans: tuple[SourceBindingPlan, ...] = ()
    dataset_plans: tuple[DatasetPlan, ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledSourcePlan:
    """Complete immutable compiled source topology plan.

    Parameters
    ----------
    source_plans : tuple[SourcePlan, ...]
        All compiled source plans.
    binding_plans : tuple[SourceBindingPlan, ...], default ()
        All compiled source binding plans in deterministic order.
    dataset_plans : tuple[DatasetPlan, ...], default ()
        Transitional compiled dataset plans in deterministic order.
    """

    source_plans: tuple[SourcePlan, ...]
    binding_plans: tuple[SourceBindingPlan, ...] = ()
    dataset_plans: tuple[DatasetPlan, ...] = ()

    def get_binding_plan(self, binding_id: SourceBindingId | str) -> SourceBindingPlan | None:
        """Find a source binding plan by logical SourceBindingId.

        Parameters
        ----------
        binding_id : SourceBindingId | str
            Target source binding identifier.

        Returns
        -------
        SourceBindingPlan | None
            Matching SourceBindingPlan if compiled, else None.
        """
        target = str(binding_id)
        for bp in self.binding_plans:
            if str(bp.binding_id) == target:
                return bp
        return None

    def is_binding_enabled(self, binding_id: SourceBindingId | str) -> bool:
        """Return True if binding has a compiled plan and is actively enabled.

        Parameters
        ----------
        binding_id : SourceBindingId | str
            Target source binding identifier.

        Returns
        -------
        bool
            True if the binding plan exists and is enabled, else False.
        """
        bp = self.get_binding_plan(binding_id)
        return bp.enabled if bp is not None else False

    def get_dataset_plan(self, dataset_id: DatasetId | str) -> DatasetPlan | None:
        """Find a dataset plan by canonical DatasetId.

        Removal Owner
        -------------
        Phase 055 (decommissioning transitional DatasetPlan lookups).

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

        Removal Owner
        -------------
        Phase 055 (decommissioning transitional dataset enablement check).

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

        # Compile physical source binding plans from decoupled topology
        topology = self.source_config.compile_binding_topology()
        legacy_ds_by_binding_id = {
            derive_source_binding_id(ds.source_id, ds.dataset_id): ds
            for ds in self.source_config.datasets
        }
        binding_plans_list: list[SourceBindingPlan] = []
        for b_cfg in topology.bindings:
            src = sources_by_id.get(b_cfg.source_id)
            if src is None:
                raise SourcePlanningError(
                    f"Binding '{b_cfg.binding_id}' references unknown source '{b_cfg.source_id}'."
                )

            is_active = any(
                self.execution_plan.is_bronze_dataset_active(r.target_dataset_id)
                for r in b_cfg.routes
            )
            is_b_enabled = b_cfg.enabled and src.enabled and is_active

            policy = b_cfg.change_detection or resolve_change_detection_policy(
                file_type=src.provider_type.value,
                is_full_replace=False,
                hash_policy=FileHashPolicy(),
                is_provider_generated=False,
            )

            legacy_ds = legacy_ds_by_binding_id.get(b_cfg.binding_id)
            target_ds_id = (
                legacy_ds.dataset_id
                if legacy_ds is not None
                else (b_cfg.routes[0].target_dataset_id if b_cfg.routes else None)
            )

            bp = SourceBindingPlan(
                binding_id=b_cfg.binding_id,
                source_id=b_cfg.source_id,
                provider_type=src.provider_type,
                location=src.location,
                enabled=is_b_enabled,
                selector=b_cfg.selector,
                change_detection=policy,
                route_ids=tuple(r.route_id for r in b_cfg.routes),
                binding_config=b_cfg,
                legacy_dataset_config=legacy_ds,
                target_dataset_id=target_ds_id,
            )
            binding_plans_list.append(bp)

        # Compile provider-generated dataset plans dynamically based on ExecutionPlan
        provider_dataset_plans: list[DatasetPlan] = []
        provider_binding_plans: list[SourceBindingPlan] = []
        for provider_ds_id in (
            DatasetId.MARKET_CURRENCY_FX_RATES,
            DatasetId.MARKET_BENCHMARK_HISTORY,
            DatasetId.MARKET_US_STOCK_PRICES,
        ):
            is_req = self.execution_plan.is_dataset_required(provider_ds_id)
            is_act = self.execution_plan.is_bronze_dataset_active(provider_ds_id)
            prov_plan = DatasetPlan(
                source_id=SourceId("provider_market_data"),
                dataset_id=provider_ds_id,
                provider_type=ProviderType.MARKET_DATA,
                location="provider://market_data",
                selector=MarketProviderSelector(feed_name="yahoo_finance"),
                change_detection=resolve_change_detection_policy(
                    file_type="market_data",
                    is_full_replace=False,
                    hash_policy=FileHashPolicy(),
                    is_provider_generated=True,
                ),
                origin=DatasetOrigin.PROVIDER_GENERATED,
                is_required=is_req,
                is_enabled=is_act,
                mapping_plan=None,
                identity_strategy=None,
            )
            provider_dataset_plans.append(prov_plan)
            dataset_plans_list.append(prov_plan)

            prov_bp = SourceBindingPlan(
                binding_id=derive_source_binding_id(
                    SourceId("provider_market_data"), provider_ds_id
                ),
                source_id=SourceId("provider_market_data"),
                provider_type=ProviderType.MARKET_DATA,
                location="provider://market_data",
                enabled=is_act,
                selector=MarketProviderSelector(feed_name="yahoo_finance"),
                change_detection=resolve_change_detection_policy(
                    file_type="market_data",
                    is_full_replace=False,
                    hash_policy=FileHashPolicy(),
                    is_provider_generated=True,
                ),
                route_ids=(CanonicalRouteId("direct"),),
                target_dataset_id=provider_ds_id,
            )
            provider_binding_plans.append(prov_bp)
            binding_plans_list.append(prov_bp)

            if is_act:
                satisfied_datasets.add(provider_ds_id)

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

        bindings_by_source: dict[SourceId, list[SourceBindingPlan]] = {}
        for bp in binding_plans_list:
            bindings_by_source.setdefault(bp.source_id, []).append(bp)

        source_plans_list: list[SourcePlan] = []
        for src in self.source_config.sources:
            sp = SourcePlan(
                source_id=src.source_id,
                provider_type=src.provider_type,
                location=src.location,
                enabled=src.enabled,
                binding_plans=tuple(bindings_by_source.get(src.source_id, [])),
                dataset_plans=tuple(ds_by_source.get(src.source_id, [])),
            )
            source_plans_list.append(sp)

        # Append synthesized provider market source plan
        prov_source_id = SourceId("provider_market_data")
        source_plans_list.append(
            SourcePlan(
                source_id=prov_source_id,
                provider_type=ProviderType.MARKET_DATA,
                location="provider://market_data",
                enabled=any(dp.is_enabled for dp in provider_dataset_plans),
                binding_plans=tuple(provider_binding_plans),
                dataset_plans=tuple(provider_dataset_plans),
            )
        )

        return CompiledSourcePlan(
            source_plans=tuple(source_plans_list),
            binding_plans=tuple(binding_plans_list),
            dataset_plans=tuple(dataset_plans_list),
        )
