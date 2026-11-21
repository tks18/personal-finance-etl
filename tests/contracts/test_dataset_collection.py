"""Comprehensive test suite for typed DatasetCollection transport.

Owns
----
- Invariant tests for DatasetCollection immutability, type enforcement, and accessors.
- Bounded operational metadata tests for DatasetRuntimeMetadata.
- Authoritative transport verification for DatasetCollection across Bronze lakehouse.
- BronzeLayer.get_dataset_collection lakehouse reconstruction tests.
- Eager-free lazy evaluation preservation assertions.

Does not own
------------
- Full pipeline execution tests (owned by tests/application).
- Source configuration parsing tests (owned by tests/config).
- Downstream financial transformation tests (owned by tests/domain).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.dataset_collection import (
    DatasetCollection,
    DatasetRuntimeMetadata,
    MissingDatasetError,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.provenance import ProvenanceRef
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import get_global_emitter
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer


def test_dataset_collection_empty() -> None:
    """Verify empty DatasetCollection factory and empty state invariants."""
    collection = DatasetCollection.empty()
    assert len(collection) == 0
    assert len(collection.dataset_ids()) == 0
    assert len(list(collection)) == 0
    assert collection.get(DatasetId.HOUSEHOLD_ZCATEGORY) is None
    assert DatasetId.HOUSEHOLD_ZCATEGORY not in collection
    assert "DatasetCollection" in repr(collection)


def test_dataset_collection_instantiation_and_immutability() -> None:
    """Verify type enforcement, defensive copying, and immutability."""
    lf = pl.LazyFrame({"a": [1, 2, 3]})
    df = pl.DataFrame({"b": ["x", "y"]})
    initial_frames: dict[DatasetId, pl.LazyFrame | pl.DataFrame] = {
        DatasetId.HOUSEHOLD_ZCATEGORY: lf,
        DatasetId.HOUSEHOLD_ASSETS: df,
    }

    collection = DatasetCollection(frames=initial_frames)
    assert len(collection) == 2
    assert DatasetId.HOUSEHOLD_ZCATEGORY in collection
    assert DatasetId.HOUSEHOLD_ASSETS in collection

    # Mutating original input dictionary does not mutate collection
    initial_frames[DatasetId.HOUSEHOLD_CURRENCY] = pl.LazyFrame()
    assert DatasetId.HOUSEHOLD_CURRENCY not in collection
    assert len(collection) == 2

    # Reject non-DatasetId key
    bad_keys: dict[object, object] = {"not_a_dataset_id": lf}
    with pytest.raises(TypeError, match="DatasetCollection keys must be DatasetId instances"):
        DatasetCollection(frames=bad_keys)  # type: ignore[arg-type]

    # Reject non-Polars frame
    bad_values: dict[object, object] = {DatasetId.HOUSEHOLD_ZCATEGORY: [1, 2, 3]}
    with pytest.raises(
        TypeError, match="DatasetCollection frames must be Polars LazyFrame or DataFrame"
    ):
        DatasetCollection(frames=bad_values)  # type: ignore[arg-type]


def test_dataset_collection_require_and_require_lazy() -> None:
    """Verify require() and require_lazy() semantics and missing error details."""
    lf = pl.LazyFrame({"id": [1, 2]})
    df = pl.DataFrame({"val": [10.5, 20.5]})
    collection = DatasetCollection(
        frames={
            DatasetId.HOUSEHOLD_ZCATEGORY: lf,
            DatasetId.HOUSEHOLD_ASSETS: df,
        }
    )

    # require returns exact frame
    assert collection.require(DatasetId.HOUSEHOLD_ZCATEGORY) is lf
    assert collection.require(DatasetId.HOUSEHOLD_ASSETS) is df
    assert collection[DatasetId.HOUSEHOLD_ZCATEGORY] is lf

    # require_lazy ensures LazyFrame
    res_lf = collection.require_lazy(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert isinstance(res_lf, pl.LazyFrame)

    res_from_df = collection.require_lazy(DatasetId.HOUSEHOLD_ASSETS)
    assert isinstance(res_from_df, pl.LazyFrame)
    assert res_from_df.collect().equals(df)

    # Missing dataset raises MissingDatasetError
    with pytest.raises(MissingDatasetError) as exc_info:
        collection.require(DatasetId.HOUSEHOLD_CURRENCY)
    assert exc_info.value.dataset_id == DatasetId.HOUSEHOLD_CURRENCY
    assert "household_currency" in str(exc_info.value)

    # Missing dataset with capability context
    with pytest.raises(MissingDatasetError) as exc_info2:
        collection.require(DatasetId.HOUSEHOLD_CURRENCY, capability_context="household_facts")
    assert exc_info2.value.capability_context == "household_facts"
    assert "required by capability: 'household_facts'" in str(exc_info2.value)


def test_dataset_collection_optional_lookups() -> None:
    """Verify get(), get_lazy(), contains(), and iteration."""
    lf = pl.LazyFrame({"col": [1]})
    df = pl.DataFrame({"col": [2]})
    collection = DatasetCollection(
        frames={
            DatasetId.HOUSEHOLD_ZCATEGORY: lf,
            DatasetId.COMMON_COLUMN_MASTER: df,
        }
    )

    # Present lookups
    assert collection.get(DatasetId.HOUSEHOLD_ZCATEGORY) is lf
    assert collection.get_lazy(DatasetId.HOUSEHOLD_ZCATEGORY) is lf
    assert isinstance(collection.get_lazy(DatasetId.COMMON_COLUMN_MASTER), pl.LazyFrame)
    assert collection.contains(DatasetId.HOUSEHOLD_ZCATEGORY) is True
    assert DatasetId.HOUSEHOLD_ZCATEGORY in collection

    # Absent lookups
    assert collection.get(DatasetId.HOUSEHOLD_ASSET_GROUP) is None
    default_frame = pl.DataFrame()
    assert collection.get(DatasetId.HOUSEHOLD_ASSET_GROUP, default=default_frame) is default_frame
    assert collection.get_lazy(DatasetId.HOUSEHOLD_ASSET_GROUP) is None
    assert collection.contains(DatasetId.HOUSEHOLD_ASSET_GROUP) is False
    assert DatasetId.HOUSEHOLD_ASSET_GROUP not in collection

    # Iteration & enumeration
    ids = collection.dataset_ids()
    assert set(ids) == {DatasetId.HOUSEHOLD_ZCATEGORY, DatasetId.COMMON_COLUMN_MASTER}

    items = collection.items()
    assert len(items) == 2
    assert set(k for k, _ in items) == {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.COMMON_COLUMN_MASTER,
    }


def test_dataset_collection_functional_updates() -> None:
    """Verify with_dataset and merge return new immutable collections."""
    lf1 = pl.LazyFrame({"x": [1]})
    lf2 = pl.LazyFrame({"y": [2]})
    lf3 = pl.LazyFrame({"z": [3]})

    col1 = DatasetCollection(frames={DatasetId.HOUSEHOLD_ZCATEGORY: lf1})
    col2 = col1.with_dataset(DatasetId.HOUSEHOLD_ASSETS, lf2)

    # col1 is unchanged
    assert len(col1) == 1
    assert DatasetId.HOUSEHOLD_ASSETS not in col1

    # col2 has both
    assert len(col2) == 2
    assert DatasetId.HOUSEHOLD_ZCATEGORY in col2
    assert DatasetId.HOUSEHOLD_ASSETS in col2

    # Merge
    col3 = DatasetCollection(
        frames={
            DatasetId.HOUSEHOLD_CURRENCY: lf3,
            DatasetId.HOUSEHOLD_ZCATEGORY: lf2,  # Overwrite lf1
        }
    )
    merged = col1.merge(col3)
    assert len(merged) == 2
    assert merged.require(DatasetId.HOUSEHOLD_ZCATEGORY) is lf2
    assert merged.require(DatasetId.HOUSEHOLD_CURRENCY) is lf3


def test_dataset_runtime_metadata() -> None:
    """Verify DatasetRuntimeMetadata attachment and validation."""
    meta = DatasetRuntimeMetadata(
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_id=SourceId("household_db"),
        provenance=(ProvenanceRef(artifact_id="abc12345"),),
        config_fingerprint="fp_v1",
    )
    lf = pl.LazyFrame({"x": [1]})

    collection = DatasetCollection(
        frames={DatasetId.HOUSEHOLD_ZCATEGORY: lf},
        metadata={DatasetId.HOUSEHOLD_ZCATEGORY: meta},
    )

    retrieved = collection.get_metadata(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert retrieved is not None
    assert retrieved.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert retrieved.source_id == SourceId("household_db")
    assert len(retrieved.provenance) == 1
    assert retrieved.provenance[0].artifact_id == "abc12345"
    assert retrieved.config_fingerprint == "fp_v1"

    # Absent metadata returns None
    assert collection.get_metadata(DatasetId.HOUSEHOLD_ASSETS) is None

    # Mismatched metadata key raises ValueError
    bad_meta = DatasetRuntimeMetadata(dataset_id=DatasetId.HOUSEHOLD_ASSETS)
    with pytest.raises(ValueError, match="does not match key"):
        DatasetCollection(
            frames={DatasetId.HOUSEHOLD_ZCATEGORY: lf},
            metadata={DatasetId.HOUSEHOLD_ZCATEGORY: bad_meta},
        )

    # Metadata for absent frame raises ValueError
    orphan_meta = DatasetRuntimeMetadata(dataset_id=DatasetId.HOUSEHOLD_ASSETS)
    with pytest.raises(ValueError, match="which does not exist in frames"):
        DatasetCollection(
            frames={DatasetId.HOUSEHOLD_ZCATEGORY: lf},
            metadata={DatasetId.HOUSEHOLD_ASSETS: orphan_meta},
        )


def test_dataset_collection_canonical_registry_coverage() -> None:
    """Verify DatasetCollection can represent all canonical DatasetIds without data loss."""
    frames = {ds_id: pl.LazyFrame({"id": [idx]}) for idx, ds_id in enumerate(DatasetId)}
    collection = DatasetCollection(frames=frames)
    assert len(collection) == len(DatasetId)
    for ds_id in DatasetId:
        assert ds_id in collection
        assert collection.require_lazy(ds_id).collect().height == 1


def test_bronze_layer_get_dataset_collection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    tmp_path: Path,
) -> None:
    """Verify BronzeLayer.get_dataset_collection() reconstructs lakehouse into DatasetCollection."""
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    # Populate a subset of Bronze tables with test data
    zcat_df = pl.DataFrame(
        {
            "ID": [1, 2],
            "NAME": ["Salary", "Groceries"],
            "TYPE": [0, 1],
            "UID": ["CAT_1", "CAT_2"],
        }
    )
    isolated_duckdb_manager.conn.register("temp_zcat_df", zcat_df)
    isolated_duckdb_manager.conn.execute(
        "CREATE OR REPLACE TABLE bronze.household_zcategory AS SELECT * FROM temp_zcat_df"
    )

    cm_df = pl.DataFrame(
        {
            "physical_table": ["bronze.household_zcategory"],
            "source_column": ["NAME"],
            "canonical_column": ["NAME"],
        }
    )
    isolated_duckdb_manager.conn.register("temp_cm_df", cm_df)
    isolated_duckdb_manager.conn.execute(
        "CREATE OR REPLACE TABLE bronze.common_column_master AS SELECT * FROM temp_cm_df"
    )

    emitter = get_global_emitter()
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, None)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    # 1. Read as DatasetCollection
    collection = bronze.get_dataset_collection()
    assert isinstance(collection, DatasetCollection)
    assert len(collection) == len(BRONZE_CONTRACT_REGISTRY)  # All 20 contracts represented

    # Existing populated tables contain data
    zcat_read = collection.require(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert isinstance(zcat_read, pl.LazyFrame)
    assert zcat_read.collect().height == 2

    cm_read = collection.require(DatasetId.COMMON_COLUMN_MASTER)
    assert isinstance(cm_read, pl.DataFrame)
    assert cm_read.height == 1

    # Unpopulated tables return empty LazyFrames without crashing
    assets_read = collection.require(DatasetId.HOUSEHOLD_ASSETS)
    assert isinstance(assets_read, pl.LazyFrame)
    assert assets_read.collect().is_empty()
