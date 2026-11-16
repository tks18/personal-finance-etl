"""Canonical Bronze tabular validation schemas.

Owns
----
- CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ZCATEGORY.
- CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ASSET_GROUP.
- CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_ASSETS.
- CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_CURRENCY.
- CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA: Immutable pandera.polars.DataFrameSchema for DatasetId.HOUSEHOLD_INOUTCOME.
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
    "CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA",
    "CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA",
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
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_zcategory",
)

CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "ASSET_GROUP": pa.Column(pl.String, nullable=False, name="ASSET_GROUP"),
        "TYPE": pa.Column(pl.Int64, nullable=False, name="TYPE"),
        "DEVICE_ID": pa.Column(pl.Int64, nullable=True, name="DEVICE_ID"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "USE_TIME": pa.Column(pl.Int64, nullable=True, name="USE_TIME"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_asset_group",
)

CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "ASSET_NAME": pa.Column(pl.String, nullable=False, name="ASSET_NAME"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "CARD_STATEMENT_DATE": pa.Column(pl.String, nullable=True, name="CARD_STATEMENT_DATE"),
        "CARD_PAYMENT_DATE": pa.Column(pl.String, nullable=True, name="CARD_PAYMENT_DATE"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "IS_DEL": pa.Column(pl.String, nullable=True, name="IS_DEL"),
        "ASSET_DESCRIPTION": pa.Column(pl.String, nullable=True, name="ASSET_DESCRIPTION"),
        "NOTES": pa.Column(pl.String, nullable=True, name="NOTES"),
        "TRANSFER_EXPENSE": pa.Column(pl.Int64, nullable=True, name="TRANSFER_EXPENSE"),
        "CARD_AUTOPAY": pa.Column(pl.Int64, nullable=True, name="CARD_AUTOPAY"),
        "APP_PACKAGE": pa.Column(pl.String, nullable=True, name="APP_PACKAGE"),
        "APP_NAME": pa.Column(pl.String, nullable=True, name="APP_NAME"),
        "SMS_TEL": pa.Column(pl.String, nullable=True, name="SMS_TEL"),
        "SMS_STRING": pa.Column(pl.String, nullable=True, name="SMS_STRING"),
        "ADDED_TIME": pa.Column(pl.Int64, nullable=True, name="ADDED_TIME"),
        "CARD_USAGE_HURDLE_TYPE": pa.Column(pl.Int64, nullable=True, name="CARD_USAGE_HURDLE_TYPE"),
        "CARD_USAGE_HURDLE_START_DATE": pa.Column(
            pl.Float64, nullable=True, name="CARD_USAGE_HURDLE_START_DATE"
        ),
        "CARD_USAGE_HURDLE_AMOUNT": pa.Column(
            pl.Float64, nullable=True, name="CARD_USAGE_HURDLE_AMOUNT"
        ),
        "CURRENCY_ID": pa.Column(pl.String, nullable=True, name="CURRENCY_ID"),
        "AUTOPAY_ASSET_ID": pa.Column(pl.String, nullable=True, name="AUTOPAY_ASSET_ID"),
        "ASSET_GROUP_ID": pa.Column(pl.String, nullable=True, name="ASSET_GROUP_ID"),
        "GROUP_ID": pa.Column(pl.String, nullable=True, required=False, name="GROUP_ID"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_assets",
)

CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "CURRENCY_NAME": pa.Column(pl.String, nullable=False, name="CURRENCY_NAME"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "ISO": pa.Column(pl.String, nullable=True, name="ISO"),
        "MAIN_ISO": pa.Column(pl.String, nullable=True, name="MAIN_ISO"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "ORDER_SEQUENCE": pa.Column(pl.Int64, nullable=True, name="ORDER_SEQUENCE"),
        "RATE": pa.Column(pl.Float64, nullable=True, name="RATE"),
        "SYMBOL": pa.Column(pl.String, nullable=True, name="SYMBOL"),
        "INSERT_TYPE": pa.Column(pl.String, nullable=True, name="INSERT_TYPE"),
        "SYMBOL_POSITION": pa.Column(pl.String, nullable=True, name="SYMBOL_POSITION"),
        "IS_MAIN_CURRENCY": pa.Column(pl.Int64, nullable=True, name="IS_MAIN_CURRENCY"),
        "IS_SHOW": pa.Column(pl.Int64, nullable=True, name="IS_SHOW"),
        "MODIFY_DATE": pa.Column(pl.Int64, nullable=True, name="MODIFY_DATE"),
        "DECIMAL_POINT": pa.Column(pl.Int64, nullable=True, name="DECIMAL_POINT"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "CURRENCY_CODE": pa.Column(pl.String, nullable=True, required=False, name="CURRENCY_CODE"),
        "CURRENCY_SYMBOL": pa.Column(
            pl.String, nullable=True, required=False, name="CURRENCY_SYMBOL"
        ),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_currency",
)

CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    columns={
        "UID": pa.Column(pl.String, nullable=False, unique=True, name="UID"),
        "ASSET_ID": pa.Column(pl.String, nullable=False, name="ASSET_ID"),
        "TIMESTAMP": pa.Column(pl.String, nullable=False, name="TIMESTAMP"),
        "TRANSACTION_TYPE": pa.Column(pl.String, nullable=False, name="TRANSACTION_TYPE"),
        "BASE_AMOUNT": pa.Column(pl.String, nullable=False, name="BASE_AMOUNT"),
        "S_NO": pa.Column(pl.Int64, nullable=True, name="S_NO"),
        "CARDDIVIDMONTH": pa.Column(pl.String, nullable=True, name="CARDDIVIDMONTH"),
        "CATEGORY_ID": pa.Column(pl.String, nullable=True, name="CATEGORY_ID"),
        "TO_ASSET_ID": pa.Column(pl.String, nullable=True, name="TO_ASSET_ID"),
        "DESCRIPTION": pa.Column(pl.String, nullable=True, name="DESCRIPTION"),
        "DATE": pa.Column(pl.String, nullable=True, name="DATE"),
        "TIME": pa.Column(pl.String, nullable=True, name="TIME"),
        "PAID": pa.Column(pl.String, nullable=True, name="PAID"),
        "TRANSFER_UID": pa.Column(pl.String, nullable=True, name="TRANSFER_UID"),
        "FEES_NOTES": pa.Column(pl.String, nullable=True, name="FEES_NOTES"),
        "SMS_RDATE": pa.Column(pl.String, nullable=True, name="SMS_RDATE"),
        "LOCAL_AMOUNT": pa.Column(pl.String, nullable=True, name="LOCAL_AMOUNT"),
        "ASSET_NAME": pa.Column(pl.String, nullable=True, name="ASSET_NAME"),
        "CATEGORY_NAME": pa.Column(pl.String, nullable=True, name="CATEGORY_NAME"),
        "CARD_DIVIDE_ID": pa.Column(pl.String, nullable=True, name="CARD_DIVIDE_ID"),
        "CARD_DIVIDE_MONTH_STR": pa.Column(pl.String, nullable=True, name="CARD_DIVIDE_MONTH_STR"),
        "MARK": pa.Column(pl.Int64, nullable=True, name="MARK"),
        "TRANSFER_FEES": pa.Column(pl.String, nullable=True, name="TRANSFER_FEES"),
        "SMS_ORIGIN": pa.Column(pl.String, nullable=True, name="SMS_ORIGIN"),
        "SMS_PARSE_CONTENT": pa.Column(pl.String, nullable=True, name="SMS_PARSE_CONTENT"),
        "IS_DEL": pa.Column(pl.Int64, nullable=True, name="IS_DEL"),
        "UPDATED_TIME": pa.Column(pl.Int64, nullable=True, name="UPDATED_TIME"),
        "CURRENCY_ID": pa.Column(pl.String, nullable=True, name="CURRENCY_ID"),
        "AMOUNT_ACCOUNT": pa.Column(pl.Float64, nullable=True, name="AMOUNT_ACCOUNT"),
        "LAT": pa.Column(pl.Float64, nullable=True, name="LAT"),
        "LONG": pa.Column(pl.Float64, nullable=True, name="LONG"),
        "GSTD": pa.Column(pl.String, nullable=True, name="GSTD"),
        "IS_SYNCED": pa.Column(pl.Int64, nullable=True, name="IS_SYNCED"),
        "SYNC_TIME": pa.Column(pl.Float64, nullable=True, name="SYNC_TIME"),
        "SYNC_VERSION": pa.Column(pl.Int64, nullable=True, name="SYNC_VERSION"),
        "TRANSACTION_DATE": pa.Column(
            pl.String, nullable=True, required=False, name="TRANSACTION_DATE"
        ),
        "AMOUNT": pa.Column(pl.Float64, nullable=True, required=False, name="AMOUNT"),
        "SUB_CATEGORY_ID": pa.Column(
            pl.String, nullable=True, required=False, name="SUB_CATEGORY_ID"
        ),
        "CONTENT": pa.Column(pl.String, nullable=True, required=False, name="CONTENT"),
        "MEMO": pa.Column(pl.String, nullable=True, required=False, name="MEMO"),
        "ORDER_NUM": pa.Column(pl.Int64, nullable=True, required=False, name="ORDER_NUM"),
        "artifact_id": pa.Column(pl.String, nullable=False, required=False, name="artifact_id"),
    },
    strict=False,
    name="canonical_bronze_household_inoutcome",
)

CANONICAL_BRONZE_SCHEMAS: dict[DatasetId, pa.DataFrameSchema] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA,
    DatasetId.HOUSEHOLD_ASSET_GROUP: CANONICAL_BRONZE_HOUSEHOLD_ASSET_GROUP_SCHEMA,
    DatasetId.HOUSEHOLD_ASSETS: CANONICAL_BRONZE_HOUSEHOLD_ASSETS_SCHEMA,
    DatasetId.HOUSEHOLD_CURRENCY: CANONICAL_BRONZE_HOUSEHOLD_CURRENCY_SCHEMA,
    DatasetId.HOUSEHOLD_INOUTCOME: CANONICAL_BRONZE_HOUSEHOLD_INOUTCOME_SCHEMA,
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
