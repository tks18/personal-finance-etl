"""Deterministic configuration change classification and replay coordination.

Owns
----
- SourceConfigChangeClassifier: Classifies configuration deltas between prior successful run snapshots and active configurations.
- ReplayCoordinator: Enforces identity policy safety guards and prepares selective layer replay actions.
- Generating authoritative ReplayPlan contracts specifying affected datasets and migration directives.

Does not own
-------------
- Low-level database transaction management (owned by RunLifecycleCoordinator).
- Ingestion execution or data transformations (owned by DatasetIngestionService and PipelineExecutor).
- Snapshot persistence in SQLite control plane (owned by RunRepository).
"""

from __future__ import annotations

import json
from typing import cast

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.fingerprint import canonicalize_source_configuration
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.contracts.recovery import (
    ConfigChangeClass,
    DatasetChangeDetail,
    IdentityPolicyViolationError,
    ReplayAction,
    ReplayPlan,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
)

__all__ = ["ReplayCoordinator", "SourceConfigChangeClassifier"]

diagnostics = get_observability_diagnostics(__name__)


class SourceConfigChangeClassifier:
    """Classifies semantic configuration deltas between prior snapshot and active configuration."""

    @staticmethod
    def classify(
        prior_payload: str | dict[str, object] | None,
        current_config: SourceConfiguration,
    ) -> ReplayPlan:
        """Classify changes and determine the authoritative replay plan.

        Parameters
        ----------
        prior_payload : str | dict[str, object] | None
            Canonical JSON payload string or dict of prior successful run configuration snapshot.
        current_config : SourceConfiguration
            Active, validated source configuration.

        Returns
        -------
        ReplayPlan
            Authoritative replay and migration plan.
        """
        if prior_payload is None:
            return ReplayPlan(overall_action=ReplayAction.NO_REPLAY)

        prior_data: dict[str, object]
        if isinstance(prior_payload, str):
            try:
                loaded = json.loads(prior_payload)
                if not isinstance(loaded, dict):
                    return ReplayPlan(overall_action=ReplayAction.NO_REPLAY)
                prior_data = cast("dict[str, object]", loaded)
            except Exception as e:
                diagnostics.warning("Failed to parse prior source config snapshot JSON: %s", e)
                return ReplayPlan(overall_action=ReplayAction.NO_REPLAY)
        else:
            prior_data = prior_payload

        current_canonical = canonicalize_source_configuration(current_config)

        raw_prior_obj = prior_data.get("datasets", [])
        prior_datasets: dict[str, dict[str, object]] = {}
        if isinstance(raw_prior_obj, list):
            raw_prior_list = cast("list[object]", raw_prior_obj)
            for item in raw_prior_list:
                if isinstance(item, dict) and "dataset_id" in item:
                    ds_dict = cast("dict[str, object]", item)
                    ds_id_str = str(ds_dict.get("dataset_id", ""))
                    prior_datasets[ds_id_str] = ds_dict

        raw_curr_obj = current_canonical.get("datasets", [])
        current_datasets: dict[str, dict[str, object]] = {}
        if isinstance(raw_curr_obj, list):
            raw_curr_list = cast("list[object]", raw_curr_obj)
            for item in raw_curr_list:
                if isinstance(item, dict) and "dataset_id" in item:
                    ds_dict = cast("dict[str, object]", item)
                    ds_id_str = str(ds_dict.get("dataset_id", ""))
                    current_datasets[ds_id_str] = ds_dict

        all_dataset_ids = sorted(set(prior_datasets.keys()) | set(current_datasets.keys()))

        dataset_changes: list[DatasetChangeDetail] = []
        affected_datasets: list[str] = []
        requires_identity_rebuild: bool = False
        blocked_reason: str | None = None

        for ds_id in all_dataset_ids:
            prior_ds = prior_datasets.get(ds_id)
            curr_ds = current_datasets.get(ds_id)

            # 1. Dataset Removed
            if prior_ds is not None and curr_ds is None:
                if bool(prior_ds.get("enabled", True)):
                    dataset_changes.append(
                        DatasetChangeDetail(
                            dataset_id=ds_id,
                            change_class=ConfigChangeClass.DATASET_STATE,
                            action=ReplayAction.PRUNE_DISABLED_DATASETS,
                            details={"reason": "Dataset removed from source configuration"},
                        )
                    )
                continue

            # 2. Dataset Added
            if prior_ds is None and curr_ds is not None:
                continue

            assert prior_ds is not None and curr_ds is not None

            # 3. Dataset Disabled or Re-enabled
            prior_enabled = bool(prior_ds.get("enabled", True))
            curr_enabled = bool(curr_ds.get("enabled", True))

            if prior_enabled and not curr_enabled:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.DATASET_STATE,
                        action=ReplayAction.PRUNE_DISABLED_DATASETS,
                        details={"reason": "Dataset disabled in source configuration"},
                    )
                )
                continue

            if not prior_enabled and curr_enabled:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.DATASET_STATE,
                        action=ReplayAction.REPLAY_AFFECTED_DATASETS,
                        details={"reason": "Dataset re-enabled in source configuration"},
                    )
                )
                affected_datasets.append(ds_id)
                continue

            if not curr_enabled:
                continue

            # 4. Identity Strategy Change (Strict Guard)
            prior_ident = prior_ds.get("identity")
            curr_ident = curr_ds.get("identity")
            if prior_ident != curr_ident:
                requires_identity_rebuild = True
                old_str = json.dumps(prior_ident, sort_keys=True)
                new_str = json.dumps(curr_ident, sort_keys=True)
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.IDENTITY_STRATEGY,
                        action=ReplayAction.REQUIRE_IDENTITY_REBUILD,
                        details={
                            "old_identity": old_str,
                            "new_identity": new_str,
                        },
                    )
                )
                if blocked_reason is None:
                    blocked_reason = (
                        f"Identity strategy changed for dataset '{ds_id}': {old_str} -> {new_str}."
                    )
                continue

            # 5. Mapping Semantic Change
            prior_mapping = prior_ds.get("mapping", [])
            curr_mapping = curr_ds.get("mapping", [])
            if prior_mapping != curr_mapping:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.MAPPING_SEMANTICS,
                        action=ReplayAction.REPLAY_AFFECTED_DATASETS,
                        details={"reason": "Column mapping rules altered"},
                    )
                )
                affected_datasets.append(ds_id)
                continue

            # 6. Normalization Semantic Change
            prior_norm = prior_ds.get("normalization", [])
            curr_norm = curr_ds.get("normalization", [])
            if prior_norm != curr_norm:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.NORMALIZATION_SEMANTICS,
                        action=ReplayAction.REPLAY_AFFECTED_DATASETS,
                        details={"reason": "Field normalization rules altered"},
                    )
                )
                affected_datasets.append(ds_id)
                continue

            # 7. Change Detection Policy Change
            prior_cd = prior_ds.get("change_detection")
            curr_cd = curr_ds.get("change_detection")
            if prior_cd != curr_cd:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.CHANGE_DETECTION,
                        action=ReplayAction.NO_REPLAY,
                        details={"reason": "Change detection policy updated for future syncs"},
                    )
                )
                continue

            # 8. Source Selector / Metadata Change
            prior_sel = prior_ds.get("selector")
            curr_sel = curr_ds.get("selector")
            if prior_sel != curr_sel:
                dataset_changes.append(
                    DatasetChangeDetail(
                        dataset_id=ds_id,
                        change_class=ConfigChangeClass.SOURCE_METADATA,
                        action=ReplayAction.NO_REPLAY,
                        details={"reason": "Selector metadata updated for future discovery"},
                    )
                )

        # 9. Classify compiled topology deltas if prior snapshot contained compiled topology
        prior_topology = prior_data.get("compiled_topology")
        curr_topology = current_canonical.get("compiled_topology")
        if isinstance(prior_topology, dict) and isinstance(curr_topology, dict):
            top_deltas = SourceConfigChangeClassifier.classify_topology_deltas(
                cast("dict[str, object]", prior_topology),
                cast("dict[str, object]", curr_topology),
            )
            existing_dataset_ids = {c.dataset_id for c in dataset_changes}
            for td in top_deltas:
                if td.dataset_id not in existing_dataset_ids:
                    dataset_changes.append(td)

        # Determine overall action
        overall_action = ReplayAction.NO_REPLAY
        if requires_identity_rebuild:
            overall_action = ReplayAction.REQUIRE_IDENTITY_REBUILD
        elif affected_datasets:
            overall_action = ReplayAction.REPLAY_AFFECTED_DATASETS
        elif any(c.action == ReplayAction.PRUNE_DISABLED_DATASETS for c in dataset_changes):
            overall_action = ReplayAction.PRUNE_DISABLED_DATASETS

        return ReplayPlan(
            overall_action=overall_action,
            dataset_changes=dataset_changes,
            affected_dataset_ids=affected_datasets,
            requires_identity_rebuild=requires_identity_rebuild,
            requires_analytical_rebuild=bool(affected_datasets or requires_identity_rebuild),
            blocked_reason=blocked_reason,
        )

    @staticmethod
    def classify_topology_deltas(
        prior_topology: dict[str, object] | None,
        current_topology_dict: dict[str, object],
    ) -> list[DatasetChangeDetail]:
        """Classify semantic deltas in compiled source binding topology.

        Parameters
        ----------
        prior_topology : dict[str, object] | None
            Canonical dictionary of prior compiled topology snapshot.
        current_topology_dict : dict[str, object]
            Canonical dictionary of active compiled topology.

        Returns
        -------
        list[DatasetChangeDetail]
            Classified change details for bindings, routes, and productions.
        """
        if not prior_topology:
            return []

        deltas: list[DatasetChangeDetail] = []

        prior_bindings_raw = prior_topology.get("bindings", [])
        curr_bindings_raw = current_topology_dict.get("bindings", [])

        prior_bindings_list = (
            cast("list[dict[str, object]]", prior_bindings_raw)
            if isinstance(prior_bindings_raw, list)
            else []
        )
        curr_bindings_list = (
            cast("list[dict[str, object]]", curr_bindings_raw)
            if isinstance(curr_bindings_raw, list)
            else []
        )

        prior_bindings = {
            str(b.get("binding_id")): b for b in prior_bindings_list if "binding_id" in b
        }
        curr_bindings = {
            str(b.get("binding_id")): b for b in curr_bindings_list if "binding_id" in b
        }

        for b_id, curr_b in curr_bindings.items():
            prior_b = prior_bindings.get(b_id)
            if prior_b is None:
                continue

            # Check binding metadata: selector, fields, change_detection, enabled
            if (
                prior_b.get("selector") != curr_b.get("selector")
                or prior_b.get("fields") != curr_b.get("fields")
                or prior_b.get("change_detection") != curr_b.get("change_detection")
                or prior_b.get("enabled") != curr_b.get("enabled")
            ):
                deltas.append(
                    DatasetChangeDetail(
                        dataset_id=b_id,
                        change_class=ConfigChangeClass.SOURCE_BINDING,
                        action=ReplayAction.NO_REPLAY,
                        details={"reason": f"Binding '{b_id}' configuration altered"},
                    )
                )

            # Check routes within binding
            prior_r_list = (
                cast("list[dict[str, object]]", prior_b.get("routes", []))
                if isinstance(prior_b.get("routes"), list)
                else []
            )
            curr_r_list = (
                cast("list[dict[str, object]]", curr_b.get("routes", []))
                if isinstance(curr_b.get("routes"), list)
                else []
            )

            prior_routes = {str(r.get("route_id")): r for r in prior_r_list if "route_id" in r}
            curr_routes = {str(r.get("route_id")): r for r in curr_r_list if "route_id" in r}

            for r_id, curr_r in curr_routes.items():
                prior_r = prior_routes.get(r_id)
                if prior_r is None:
                    continue

                if (
                    prior_r.get("mapping") != curr_r.get("mapping")
                    or prior_r.get("normalization") != curr_r.get("normalization")
                    or prior_r.get("identity") != curr_r.get("identity")
                    or prior_r.get("enabled") != curr_r.get("enabled")
                ):
                    target_d_id = str(curr_r.get("target_dataset_id", b_id))
                    deltas.append(
                        DatasetChangeDetail(
                            dataset_id=target_d_id,
                            change_class=ConfigChangeClass.CANONICAL_ROUTE,
                            action=ReplayAction.NO_REPLAY,
                            details={"reason": f"Route '{r_id}' in binding '{b_id}' altered"},
                        )
                    )

        # Check productions
        prior_p_raw = prior_topology.get("productions", [])
        curr_p_raw = current_topology_dict.get("productions", [])

        prior_prods_list = (
            cast("list[dict[str, object]]", prior_p_raw) if isinstance(prior_p_raw, list) else []
        )
        curr_prods_list = (
            cast("list[dict[str, object]]", curr_p_raw) if isinstance(curr_p_raw, list) else []
        )

        prior_prods = {str(p.get("dataset_id")): p for p in prior_prods_list if "dataset_id" in p}
        curr_prods = {str(p.get("dataset_id")): p for p in curr_prods_list if "dataset_id" in p}

        for d_id, curr_p in curr_prods.items():
            prior_p = prior_prods.get(d_id)
            if prior_p is None:
                continue

            if (
                prior_p.get("assembly_mode") != curr_p.get("assembly_mode")
                or prior_p.get("producer_kind") != curr_p.get("producer_kind")
                or prior_p.get("source_routes") != curr_p.get("source_routes")
                or prior_p.get("enabled") != curr_p.get("enabled")
            ):
                deltas.append(
                    DatasetChangeDetail(
                        dataset_id=d_id,
                        change_class=ConfigChangeClass.CANONICAL_PRODUCTION,
                        action=ReplayAction.NO_REPLAY,
                        details={"reason": f"Production rule for dataset '{d_id}' altered"},
                    )
                )

        return deltas


class ReplayCoordinator:
    """Evaluates replay plans, enforces identity guards, and coordinates layer replay."""

    def __init__(
        self,
        settings: Settings,
        source_config: SourceConfiguration,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.settings = settings
        self.source_config = source_config
        self.emitter = emitter or get_global_emitter()

    def evaluate(self, cp: ControlPlane) -> ReplayPlan:
        """Evaluate the active source configuration against prior successful run snapshot.

        Parameters
        ----------
        cp : ControlPlane
            Active ControlPlane instance.

        Returns
        -------
        ReplayPlan
            Evaluated authoritative replay plan.

        Raises
        ------
        IdentityPolicyViolationError
            If an identity policy change is detected and allow_identity_rebuild is False.
        """
        latest_snap_id = cp.runs.get_latest_successful_run_source_config_snapshot_id()
        if not latest_snap_id:
            return ReplayPlan(overall_action=ReplayAction.NO_REPLAY)

        prior_snapshot = cp.runs.get_source_config_snapshot(latest_snap_id)
        if not prior_snapshot:
            return ReplayPlan(overall_action=ReplayAction.NO_REPLAY)

        prior_payload = cast("str | None", prior_snapshot.get("canonical_payload"))
        plan = SourceConfigChangeClassifier.classify(prior_payload, self.source_config)

        if plan.requires_identity_rebuild:
            if not self.settings.ALLOW_IDENTITY_REBUILD:
                first_ident_change = next(
                    (
                        c
                        for c in plan.dataset_changes
                        if c.change_class == ConfigChangeClass.IDENTITY_STRATEGY
                    ),
                    None,
                )
                old_ident = (
                    first_ident_change.details.get("old_identity", "") if first_ident_change else ""
                )
                new_ident = (
                    first_ident_change.details.get("new_identity", "") if first_ident_change else ""
                )
                ds_id = first_ident_change.dataset_id if first_ident_change else "unknown"

                diagnostics.error(
                    "Identity policy change detected for dataset '%s' without explicit authorization. Aborting run.",
                    ds_id,
                )
                self.emitter.emit_event(
                    event_code=EventCode.SYSTEM_CONFIG_FINGERPRINT,
                    message=f"Identity policy violation on dataset '{ds_id}': rebuild not authorized.",
                    presentation_kind=PresentationKind.RECOVERY,
                    severity=DiagnosticSeverity.ERROR,
                )
                raise IdentityPolicyViolationError(
                    dataset_id=ds_id,
                    old_identity=old_ident,
                    new_identity=new_ident,
                )

            # Rebuild is authorized by user
            diagnostics.warning(
                "Identity policy rebuild explicitly authorized by settings (ALLOW_IDENTITY_REBUILD=True)."
            )
            authorized_datasets = list(
                {
                    c.dataset_id
                    for c in plan.dataset_changes
                    if c.change_class == ConfigChangeClass.IDENTITY_STRATEGY
                }
                | set(plan.affected_dataset_ids)
            )
            return ReplayPlan(
                overall_action=ReplayAction.REPLAY_AFFECTED_DATASETS,
                dataset_changes=plan.dataset_changes,
                affected_dataset_ids=authorized_datasets,
                requires_identity_rebuild=True,
                requires_analytical_rebuild=True,
                blocked_reason=None,
            )

        if plan.affected_dataset_ids:
            self.emitter.emit_event(
                event_code=EventCode.SYSTEM_CONFIG_FINGERPRINT,
                message=(
                    f"Configuration replay evaluated: {len(plan.affected_dataset_ids)} dataset(s) "
                    f"scheduled for canonical replay: {plan.affected_dataset_ids}"
                ),
                presentation_kind=PresentationKind.RECOVERY,
                severity=DiagnosticSeverity.INFO,
            )

        return plan

    @staticmethod
    def prepare_dataset_replay(
        db_manager: DuckDBManager,
        dataset_ids: list[str],
    ) -> None:
        """Truncate Pre-Bronze, Bronze, and file registry tables for replayed datasets.

        Parameters
        ----------
        db_manager : DuckDBManager
            Active DuckDB connection manager.
        dataset_ids : list[str]
            List of DatasetId string values scheduled for replay.
        """
        for ds_name in dataset_ids:
            try:
                ds_id = DatasetId(ds_name)
            except ValueError:
                continue

            # Clear all Pre-Bronze tables associated with this dataset
            try:
                pb_tables = [
                    str(r[0])
                    for r in db_manager.conn.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE lower(table_schema) = 'pre_bronze' AND "
                        "(lower(table_name) = ? OR lower(table_name) LIKE ?)",
                        [ds_name.lower(), f"%__{ds_name.lower()}"],
                    ).fetchall()
                ]
                for tbl in pb_tables:
                    db_manager.conn.execute(f"DELETE FROM pre_bronze.{tbl}")
            except Exception:
                pass

            b_contract = get_bronze_contract_by_dataset_id(ds_id)
            if b_contract:
                try:
                    db_manager.conn.execute(f"DELETE FROM {b_contract.physical_table}")
                except Exception:
                    pass
                try:
                    db_manager.conn.execute(
                        "DELETE FROM meta.m_File_Registry WHERE file_category = ?",
                        [b_contract.sync_category],
                    )
                except Exception:
                    pass
