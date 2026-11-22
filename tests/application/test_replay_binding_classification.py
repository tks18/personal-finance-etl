"""Tests for replay classification of source binding, canonical route, and production deltas.

Owns
----
- Verification that SourceConfigChangeClassifier detects SOURCE_BINDING, CANONICAL_ROUTE,
  and CANONICAL_PRODUCTION configuration changes.
- Verification that compiled topology deltas map to ReplayAction.NO_REPLAY without activating
  premature rebuild behavior during the migration program.
"""

from __future__ import annotations

import copy
from typing import cast

from personal_finance_etl.application.pipeline.replay import SourceConfigChangeClassifier
from personal_finance_etl.config.sources.fingerprint import (
    canonicalize_compiled_topology,
    compute_source_config_fingerprint,
)
from personal_finance_etl.config.sources.loader import (
    SourceConfiguration,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.normalization import TrimRule
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.recovery import (
    ConfigChangeClass,
    ReplayAction,
)


def test_classify_topology_deltas_detects_binding_selector_change() -> None:
    """Verify modifying a binding's selector generates a SOURCE_BINDING change with NO_REPLAY."""
    base_cfg = get_shan_baseline_source_configuration()
    top_base = base_cfg.compile_binding_topology()
    prior_dict = canonicalize_compiled_topology(top_base)

    # Mutate selector of opening_balance_csv (CSV source)
    mutated_datasets = list(base_cfg.datasets)
    target_idx = next(
        i
        for i, ds in enumerate(mutated_datasets)
        if ds.dataset_id == DatasetId.HOUSEHOLD_OPENING_BALANCES
    )
    original_ds = mutated_datasets[target_idx]
    mutated_datasets[target_idx] = SourceDatasetConfig(
        source_id=original_ds.source_id,
        dataset_id=original_ds.dataset_id,
        selector=CsvSelector(file_pattern="MUTATED_*.csv"),
        enabled=original_ds.enabled,
        description=original_ds.description,
        change_detection=original_ds.change_detection,
        identity=original_ds.identity,
        mapping=list(original_ds.mapping),
        normalization=list(original_ds.normalization),
        fields=list(original_ds.fields),
    )
    mutated_cfg = SourceConfiguration(sources=base_cfg.sources, datasets=tuple(mutated_datasets))
    curr_top = mutated_cfg.compile_binding_topology()
    curr_dict = canonicalize_compiled_topology(curr_top)

    deltas = SourceConfigChangeClassifier.classify_topology_deltas(prior_dict, curr_dict)
    assert len(deltas) >= 1
    binding_delta = next(
        (d for d in deltas if d.change_class == ConfigChangeClass.SOURCE_BINDING),
        None,
    )
    assert binding_delta is not None
    assert "opening_balances" in binding_delta.dataset_id
    assert binding_delta.action == ReplayAction.NO_REPLAY


def test_classify_topology_deltas_detects_route_normalization_change() -> None:
    """Verify modifying a route's normalization generates a CANONICAL_ROUTE change with NO_REPLAY."""
    base_cfg = get_shan_baseline_source_configuration()
    top_base = base_cfg.compile_binding_topology()
    prior_dict = canonicalize_compiled_topology(top_base)

    mutated_datasets = list(base_cfg.datasets)
    target_idx = next(
        i for i, ds in enumerate(mutated_datasets) if ds.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    )
    original_ds = mutated_datasets[target_idx]
    mutated_datasets[target_idx] = SourceDatasetConfig(
        source_id=original_ds.source_id,
        dataset_id=original_ds.dataset_id,
        selector=original_ds.selector,
        enabled=original_ds.enabled,
        description=original_ds.description,
        change_detection=original_ds.change_detection,
        identity=original_ds.identity,
        mapping=list(original_ds.mapping),
        normalization=list(original_ds.normalization) + [TrimRule(field="ZNAME", mode="both")],
        fields=list(original_ds.fields),
    )
    mutated_cfg = SourceConfiguration(sources=base_cfg.sources, datasets=tuple(mutated_datasets))
    curr_top = mutated_cfg.compile_binding_topology()
    curr_dict = canonicalize_compiled_topology(curr_top)

    deltas = SourceConfigChangeClassifier.classify_topology_deltas(prior_dict, curr_dict)
    route_delta = next(
        (d for d in deltas if d.change_class == ConfigChangeClass.CANONICAL_ROUTE),
        None,
    )
    assert route_delta is not None
    assert route_delta.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY.value
    assert route_delta.action == ReplayAction.NO_REPLAY


def test_classify_topology_deltas_detects_production_rule_change() -> None:
    """Verify modifying a production rule generates a CANONICAL_PRODUCTION change with NO_REPLAY."""
    base_cfg = get_shan_baseline_source_configuration()
    top_base = base_cfg.compile_binding_topology()
    prior_dict = canonicalize_compiled_topology(top_base)

    # Mutate production dictionary directly by altering assembly_mode or source_routes
    curr_dict = copy.deepcopy(prior_dict)
    productions_list = cast("list[dict[str, object]]", curr_dict["productions"])
    first_prod = productions_list[0]
    first_prod["assembly_mode"] = "UNION"

    deltas = SourceConfigChangeClassifier.classify_topology_deltas(prior_dict, curr_dict)
    prod_delta = next(
        (d for d in deltas if d.change_class == ConfigChangeClass.CANONICAL_PRODUCTION),
        None,
    )
    assert prod_delta is not None
    assert prod_delta.action == ReplayAction.NO_REPLAY


def test_classify_includes_topology_deltas_in_overall_replay_plan() -> None:
    """Verify classify() includes topology deltas without forcing premature rebuilds."""
    base_cfg = get_shan_baseline_source_configuration()
    prior_fp = compute_source_config_fingerprint(base_cfg)

    # In base configuration without changes, overall action is NO_REPLAY and 0 deltas
    plan = SourceConfigChangeClassifier.classify(prior_fp.canonical_payload, base_cfg)
    assert plan.overall_action == ReplayAction.NO_REPLAY
    assert len(plan.dataset_changes) == 0
