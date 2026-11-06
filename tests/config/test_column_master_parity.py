"""Transition parity guard and equivalence tests between COLUMN_MASTER.csv and Shan topology.

Verifies that 100% of mappings in the legacy COLUMN_MASTER.csv are captured in
the canonical SourceConfiguration topology and yield identical results.
"""

from __future__ import annotations

import csv
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.mapping import mapping_list_to_dict
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.domain.household.transforms.common import get_column_mapping

FIXTURE_PATH = Path("tests/fixtures/COLUMN_MASTER.csv")

# Mapping from COLUMN_MASTER TABLE_NAME to canonical DatasetId
TABLE_TO_DATASET: dict[str, DatasetId] = {
    "CATEGORY": DatasetId.HOUSEHOLD_ZCATEGORY,
    "ASSETGROUP": DatasetId.HOUSEHOLD_ASSET_GROUP,
    "ASSETS": DatasetId.HOUSEHOLD_ASSETS,
    "CURRENCY": DatasetId.HOUSEHOLD_CURRENCY,
    "INOUTCOME": DatasetId.HOUSEHOLD_INOUTCOME,
    "ZOPBAL": DatasetId.HOUSEHOLD_OPENING_BALANCES,
}


def _load_column_master_rows() -> list[dict[str, str]]:
    """Load raw records from the fixture COLUMN_MASTER.csv."""
    assert FIXTURE_PATH.is_file(), f"Fixture file not found: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def test_column_master_parity_guard() -> None:
    """Transition Parity Guard: Guarantee 100% coverage of COLUMN_MASTER.csv in SourceConfiguration."""
    raw_rows = _load_column_master_rows()
    assert len(raw_rows) == 153, (
        f"Expected 153 mappings in COLUMN_MASTER.csv, found {len(raw_rows)}"
    )

    config = get_shan_baseline_source_configuration()
    bindings_by_id = {ds.dataset_id: ds for ds in config.datasets}

    covered_count = 0
    missing: list[tuple[str, str, str]] = []

    for row in raw_rows:
        table_name = row["TABLE_NAME"]
        old_col = row["OLD_COLUMN"]
        new_col = row["NEW_COLUMN"]

        dataset_id = TABLE_TO_DATASET.get(table_name)
        assert dataset_id is not None, f"Unknown TABLE_NAME '{table_name}' in COLUMN_MASTER.csv"

        ds = bindings_by_id.get(dataset_id)
        assert ds is not None, f"Dataset '{dataset_id}' not found in SourceConfiguration bindings"

        mapping_dict = mapping_list_to_dict(ds.mapping)
        if mapping_dict.get(old_col) == new_col:
            covered_count += 1
        else:
            missing.append((table_name, old_col, new_col))

    assert not missing, f"Missing {len(missing)} mappings from SourceConfiguration: {missing}"
    assert covered_count == 153, f"Expected 153 mappings covered, got {covered_count}"


@pytest.mark.parametrize(
    ("table_name", "dataset_id", "expected_count"),
    [
        ("CATEGORY", DatasetId.HOUSEHOLD_ZCATEGORY, 12),
        ("ASSETGROUP", DatasetId.HOUSEHOLD_ASSET_GROUP, 10),
        ("ASSETS", DatasetId.HOUSEHOLD_ASSETS, 25),
        ("CURRENCY", DatasetId.HOUSEHOLD_CURRENCY, 18),
        ("INOUTCOME", DatasetId.HOUSEHOLD_INOUTCOME, 35),
        ("ZOPBAL", DatasetId.HOUSEHOLD_OPENING_BALANCES, 53),
    ],
)
def test_column_master_equivalence_by_table(
    table_name: str,
    dataset_id: DatasetId,
    expected_count: int,
) -> None:
    """Assert exact mapping equivalence between legacy get_column_mapping and SourceDatasetConfig."""
    df_map = pl.read_csv(FIXTURE_PATH)
    legacy_mapping = get_column_mapping(df_map, table_name)
    assert len(legacy_mapping) == expected_count

    config = get_shan_baseline_source_configuration()
    ds = next(d for d in config.datasets if d.dataset_id == dataset_id)
    new_mapping = mapping_list_to_dict(ds.mapping)
    assert len(new_mapping) == expected_count

    assert new_mapping == legacy_mapping, (
        f"Mapping discrepancy detected for {table_name}: "
        f"diff={set(new_mapping.items()) ^ set(legacy_mapping.items())}"
    )
