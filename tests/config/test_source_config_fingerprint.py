"""Unit tests for deterministic cryptographic SourceConfiguration fingerprinting.

Verifies:
1. Deterministic repeatability: Identical configurations yield byte-stable fingerprints.
2. Unordered collection invariance: Shuffling sources, datasets, column mappings, or enabled
   capabilities produces the exact same fingerprint.
3. Sequential order sensitivity: Reordering normalization rules changes the fingerprint to
   strictly reflect execution pipeline semantics.
4. Semantic sensitivity: Any mutation to sources, selectors, identities, mappings, change-detection
   policies, or capabilities changes the fingerprint.
5. Structural validity: Fingerprint format, content hash digest length, and canonical JSON.
"""

from __future__ import annotations

import copy
import json
import random
from typing import cast

from personal_finance_etl.config.sources import (
    CURRENT_SOURCE_CONFIG_SCHEMA_VERSION,
    CapabilitySelection,
    ColumnMapping,
    SourceConfig,
    SourceConfigFingerprint,
    SourceConfiguration,
    SourceDatasetConfig,
    compute_source_config_fingerprint,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.normalization import (
    NormalizeCaseRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_fingerprint_baseline_structure() -> None:
    """Verify that baseline SourceConfiguration computes a valid, well-formed fingerprint."""
    config = get_shan_baseline_source_configuration()
    fp = compute_source_config_fingerprint(config)

    assert isinstance(fp, SourceConfigFingerprint)
    assert fp.fingerprint.startswith("src_cfg_")
    assert len(fp.fingerprint) == 24  # 'src_cfg_' (8) + 16 hex chars
    assert len(fp.content_hash) == 64
    assert fp.schema_version == CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
    assert fp.content_hash.startswith(fp.fingerprint.removeprefix("src_cfg_"))

    # Canonical payload should be valid, compact JSON
    parsed = json.loads(fp.canonical_payload)
    assert isinstance(parsed, dict)
    assert parsed["schema_version"] == CURRENT_SOURCE_CONFIG_SCHEMA_VERSION
    sources_data = cast(list[object], parsed["sources"])
    datasets_data = cast(list[object], parsed["datasets"])
    assert len(sources_data) == len(config.sources)
    assert len(datasets_data) == len(config.datasets)


def test_fingerprint_deterministic_repeatability() -> None:
    """Verify that repeated fingerprint computations on identical instances produce identical hashes."""
    cfg1 = get_shan_baseline_source_configuration()
    cfg2 = get_shan_baseline_source_configuration()

    fp1 = compute_source_config_fingerprint(cfg1)
    fp2 = compute_source_config_fingerprint(cfg2)

    assert fp1.fingerprint == fp2.fingerprint
    assert fp1.content_hash == fp2.content_hash
    assert fp1.canonical_payload == fp2.canonical_payload


def test_fingerprint_invariance_to_shuffled_sources() -> None:
    """Verify fingerprint is invariant to the ordering of sources."""
    base_cfg = get_shan_baseline_source_configuration()
    fp_base = compute_source_config_fingerprint(base_cfg)

    shuffled_sources = list(base_cfg.sources)
    rng = random.Random(42)
    rng.shuffle(shuffled_sources)

    shuffled_cfg = SourceConfiguration(
        schema_version=base_cfg.schema_version,
        capabilities=base_cfg.capabilities,
        sources=tuple(shuffled_sources),
        datasets=base_cfg.datasets,
    )
    fp_shuffled = compute_source_config_fingerprint(shuffled_cfg)

    assert fp_shuffled.content_hash == fp_base.content_hash
    assert fp_shuffled.fingerprint == fp_base.fingerprint


def test_fingerprint_invariance_to_shuffled_datasets() -> None:
    """Verify fingerprint is invariant to the ordering of datasets."""
    base_cfg = get_shan_baseline_source_configuration()
    fp_base = compute_source_config_fingerprint(base_cfg)

    shuffled_datasets = list(base_cfg.datasets)
    rng = random.Random(123)
    rng.shuffle(shuffled_datasets)

    shuffled_cfg = SourceConfiguration(
        schema_version=base_cfg.schema_version,
        capabilities=base_cfg.capabilities,
        sources=base_cfg.sources,
        datasets=tuple(shuffled_datasets),
    )
    fp_shuffled = compute_source_config_fingerprint(shuffled_cfg)

    assert fp_shuffled.content_hash == fp_base.content_hash
    assert fp_shuffled.fingerprint == fp_base.fingerprint


def test_fingerprint_invariance_to_shuffled_mappings() -> None:
    """Verify fingerprint is invariant to the ordering of column mappings within a dataset."""
    base_cfg = get_shan_baseline_source_configuration()
    fp_base = compute_source_config_fingerprint(base_cfg)

    # Pick a dataset with multiple mappings and reverse the mappings tuple
    datasets_copy = [copy.deepcopy(ds) for ds in base_cfg.datasets]
    target_ds = next(ds for ds in datasets_copy if len(ds.mapping) > 1)
    target_ds.mapping = list(reversed(target_ds.mapping))

    reordered_cfg = SourceConfiguration(
        schema_version=base_cfg.schema_version,
        capabilities=base_cfg.capabilities,
        sources=base_cfg.sources,
        datasets=tuple(datasets_copy),
    )
    fp_reordered = compute_source_config_fingerprint(reordered_cfg)

    assert fp_reordered.content_hash == fp_base.content_hash
    assert fp_reordered.fingerprint == fp_base.fingerprint


def test_fingerprint_invariance_to_shuffled_capabilities() -> None:
    """Verify fingerprint is invariant to the ordering of requested capabilities."""
    base_cfg = get_shan_baseline_source_configuration()
    fp_base = compute_source_config_fingerprint(base_cfg)

    reversed_caps = tuple(reversed(list(CapabilityId)))
    cfg_reversed_caps = SourceConfiguration(
        schema_version=base_cfg.schema_version,
        capabilities=CapabilitySelection(enabled=reversed_caps),
        sources=base_cfg.sources,
        datasets=base_cfg.datasets,
    )
    fp_reversed = compute_source_config_fingerprint(cfg_reversed_caps)

    assert fp_reversed.content_hash == fp_base.content_hash
    assert fp_reversed.fingerprint == fp_base.fingerprint


def test_fingerprint_sensitivity_to_normalization_rule_order() -> None:
    """Verify that reordering sequential normalization rules alters the fingerprint."""
    source = SourceConfig(
        source_id=SourceId("src_test"),
        provider_type=ProviderType.CSV,
        location="test.csv",
    )
    # Dataset with 2 normalization rules in sequence A -> B
    dataset_seq1 = SourceDatasetConfig(
        dataset_id=DatasetId.COMMON_COLUMN_MASTER,
        source_id=SourceId("src_test"),
        selector=CsvSelector(file_pattern="test.csv"),
        normalization=[
            TrimRule(field="col1"),
            NormalizeCaseRule(field="col1", case="lower"),
        ],
    )
    cfg1 = SourceConfiguration(sources=(source,), datasets=(dataset_seq1,))

    # Dataset with swapped normalization rules B -> A
    dataset_seq2 = SourceDatasetConfig(
        dataset_id=DatasetId.COMMON_COLUMN_MASTER,
        source_id=SourceId("src_test"),
        selector=CsvSelector(file_pattern="test.csv"),
        normalization=[
            NormalizeCaseRule(field="col1", case="lower"),
            TrimRule(field="col1"),
        ],
    )
    cfg2 = SourceConfiguration(sources=(source,), datasets=(dataset_seq2,))

    fp1 = compute_source_config_fingerprint(cfg1)
    fp2 = compute_source_config_fingerprint(cfg2)

    assert fp1.content_hash != fp2.content_hash
    assert fp1.fingerprint != fp2.fingerprint


def test_fingerprint_semantic_sensitivity() -> None:
    """Verify that any semantic mutation alters the fingerprint."""
    base_cfg = get_shan_baseline_source_configuration()
    base_fp = compute_source_config_fingerprint(base_cfg)

    # 1. Mutate source location
    sources_mut = [copy.deepcopy(s) for s in base_cfg.sources]
    sources_mut[0].location = sources_mut[0].location + "_modified"
    cfg_mut_source = SourceConfiguration(
        sources=tuple(sources_mut),
        datasets=base_cfg.datasets,
        capabilities=base_cfg.capabilities,
    )
    assert compute_source_config_fingerprint(cfg_mut_source).content_hash != base_fp.content_hash

    # 2. Mutate dataset selector
    datasets_mut_sel = [copy.deepcopy(ds) for ds in base_cfg.datasets]
    target_csv_ds = next(ds for ds in datasets_mut_sel if isinstance(ds.selector, CsvSelector))
    target_csv_ds.selector = CsvSelector(file_pattern="modified_*.csv")
    cfg_mut_sel = SourceConfiguration(
        sources=base_cfg.sources,
        datasets=tuple(datasets_mut_sel),
        capabilities=base_cfg.capabilities,
    )
    assert compute_source_config_fingerprint(cfg_mut_sel).content_hash != base_fp.content_hash

    # 3. Mutate mapping
    datasets_mut_map = [copy.deepcopy(ds) for ds in base_cfg.datasets]
    datasets_mut_map[0].mapping = list(datasets_mut_map[0].mapping) + [
        ColumnMapping(source_field="extra_col", canonical_field="canonical_extra"),
    ]
    cfg_mut_map = SourceConfiguration(
        sources=base_cfg.sources,
        datasets=tuple(datasets_mut_map),
        capabilities=base_cfg.capabilities,
    )
    assert compute_source_config_fingerprint(cfg_mut_map).content_hash != base_fp.content_hash

    # 4. Mutate capabilities
    cfg_mut_caps = SourceConfiguration(
        sources=base_cfg.sources,
        datasets=base_cfg.datasets,
        capabilities=CapabilitySelection(enabled=(CapabilityId.TAX,)),
    )
    assert compute_source_config_fingerprint(cfg_mut_caps).content_hash != base_fp.content_hash
