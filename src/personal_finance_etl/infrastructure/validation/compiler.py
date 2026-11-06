"""Source tabular contract compiler.

Owns
----
- POLARS_TYPE_MAP: Authoritative mapping of declarative type names to Polars DataFrame dtypes.
- compile_source_schema: Compiles a SourceDatasetConfig into an authoritative pandera.polars.DataFrameSchema for Pre-Bronze validation.

Does not own
-------------
- Validation execution or telemetry emission (owned by PanderaDataFrameValidator).
- Source configuration models or declarations (owned by config.sources).
- Downstream Medallion persistence or schema management (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from personal_finance_etl.config.sources.model import SourceDatasetConfig

__all__ = [
    "POLARS_TYPE_MAP",
    "compile_source_schema",
]

POLARS_TYPE_MAP: dict[str, type[pl.DataType] | pl.DataType] = {
    "string": pl.String,
    "str": pl.String,
    "int64": pl.Int64,
    "i64": pl.Int64,
    "int": pl.Int64,
    "int32": pl.Int32,
    "i32": pl.Int32,
    "float64": pl.Float64,
    "f64": pl.Float64,
    "float": pl.Float64,
    "float32": pl.Float32,
    "f32": pl.Float32,
    "boolean": pl.Boolean,
    "bool": pl.Boolean,
    "date": pl.Date,
    "datetime": pl.Datetime,
}


def compile_source_schema(config: SourceDatasetConfig) -> pa.DataFrameSchema:
    """Compile a declarative SourceDatasetConfig into a Pandera Polars DataFrameSchema.

    Parameters
    ----------
    config : SourceDatasetConfig
        Configured dataset binding containing declared source fields.

    Returns
    -------
    pa.DataFrameSchema
        Authoritative Pandera DataFrameSchema representing expected source tabular structure.

    Raises
    ------
    ValueError
        If config.fields is empty, contains duplicate field names, or references
        an unknown/unsupported data type.
    """
    if not config.fields:
        raise ValueError(
            f"Cannot compile source schema for dataset '{config.dataset_id}': "
            "config.fields is empty. Declare at least one SourceFieldDeclaration."
        )

    columns: dict[str, pa.Column] = {}
    for field in config.fields:
        if field.name in columns:
            raise ValueError(
                f"Duplicate source field declaration '{field.name}' in dataset '{config.dataset_id}'."
            )

        norm_type = field.data_type.strip().lower()
        if norm_type not in POLARS_TYPE_MAP:
            supported = sorted(set(POLARS_TYPE_MAP.keys()))
            raise ValueError(
                f"Unsupported or unknown data type '{field.data_type}' for source field '{field.name}' "
                f"in dataset '{config.dataset_id}'. Supported types: {supported}."
            )

        dtype = POLARS_TYPE_MAP[norm_type]
        columns[field.name] = pa.Column(
            dtype=dtype,
            nullable=field.nullable,
            unique=field.unique,
            name=field.name,
        )

    return pa.DataFrameSchema(
        columns=columns,
        strict=False,
        name=f"pre_bronze_{config.dataset_id.value}",
    )
