"""Canonical Bronze tabular validation schemas.

Owns
----
- CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ZCATEGORY.
- CANONICAL_BRONZE_SCHEMAS: Registry mapping DatasetIds to authoritative canonical Bronze schemas.
- get_canonical_bronze_schema: Safe accessor for retrieving the canonical Bronze schema for a given DatasetId.
- has_canonical_bronze_schema: Inspection predicate determining whether a DatasetId has a registered canonical schema.

Does not own
-------------
- Source schema compilation (owned by infrastructure.validation.compiler).
- Validation execution or telemetry emission (owned by PanderaDataFrameValidator).
- Downstream Medallion persistence or schema management (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA",
    "CANONICAL_BRONZE_SCHEMAS",
    "get_canonical_bronze_schema",
    "has_canonical_bronze_schema",
]

CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "CATEGORY_NAME": pa.Column(pl.String, nullable=False, name="CATEGORY_NAME"),
        "TYPE": pa.Column(pl.Int64, nullable=False, name="TYPE"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "MODIFY_DATE": pa.Column(pl.Int64, nullable=True, name="MODIFY_DATE"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "STATUS": pa.Column(pl.Int64, nullable=True, name="STATUS"),
        "CATEGORY_ID": pa.Column(pl.String, nullable=True, name="CATEGORY_ID"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Int64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_zcategory",
)

CANONICAL_BRONZE_SCHEMAS: dict[DatasetId, pa.DataFrameSchema] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA,
}


def get_canonical_bronze_schema(dataset_id: DatasetId) -> pa.DataFrameSchema:
    """Retrieve the authoritative canonical Bronze Pandera schema for a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Target canonical dataset identifier.

    Returns
    -------
    pa.DataFrameSchema
        Authoritative Pandera DataFrameSchema for the dataset.

    Raises
    ------
    KeyError
        If no canonical Bronze schema is registered for the specified DatasetId.
    """
    if dataset_id not in CANONICAL_BRONZE_SCHEMAS:
        registered = sorted(d.value for d in CANONICAL_BRONZE_SCHEMAS)
        raise KeyError(
            f"No canonical Bronze validation schema registered for dataset '{dataset_id}'. "
            f"Registered datasets: {registered}."
        )
    return CANONICAL_BRONZE_SCHEMAS[dataset_id]


def has_canonical_bronze_schema(dataset_id: DatasetId) -> bool:
    """Check whether an authoritative canonical Bronze Pandera schema exists for a dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Target canonical dataset identifier.

    Returns
    -------
    bool
        True if a canonical Bronze schema is registered, False otherwise.
    """
    return dataset_id in CANONICAL_BRONZE_SCHEMAS
