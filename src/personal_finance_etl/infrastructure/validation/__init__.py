"""Tabular schema and contract validation subsystem.

Owns
----
- Pandera integration for Polars DataFrame and LazyFrame validation.
- Pandera error parsing, grouping, and bounded failure generation.
- Execution of data and schema validation under appropriate depth configurations.
- Mapping between internal Pandera exceptions and pure cross-boundary validation contracts.

Does not own
-------------
- Validation contracts, context, and result models (owned by contracts.validation).
- Source configuration or dataset schemas (owned by config.sources).
- Downstream Medallion persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)

__all__ = [
    "PanderaDataFrameValidator",
]
