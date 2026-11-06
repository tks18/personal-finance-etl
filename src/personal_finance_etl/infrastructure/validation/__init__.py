"""Tabular schema and contract validation subsystem.

Owns
----
- Pandera integration for Polars DataFrame and LazyFrame validation.
- Pandera error parsing, grouping, and bounded failure generation.
- Execution of data and schema validation under appropriate depth configurations.
- Mapping between internal Pandera exceptions and pure cross-boundary validation contracts.
- Compilation of declarative SourceDatasetConfig models into Pre-Bronze DataFrameSchemas.
- Authoritative canonical Bronze validation schemas and registry.

Does not own
-------------
- Validation contracts, context, and result models (owned by contracts.validation).
- Source configuration or dataset schemas (owned by config.sources).
- Downstream Medallion persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA,
    CANONICAL_BRONZE_SCHEMAS,
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.validation.compiler import (
    POLARS_TYPE_MAP,
    compile_source_schema,
)
from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)

__all__ = [
    "CANONICAL_BRONZE_HOUSEHOLD_ZCATEGORY_SCHEMA",
    "CANONICAL_BRONZE_SCHEMAS",
    "POLARS_TYPE_MAP",
    "PanderaDataFrameValidator",
    "compile_source_schema",
    "get_canonical_bronze_schema",
    "has_canonical_bronze_schema",
]
