"""Physical evidence source configuration package.

Owns
----
- SourceConfig: Declarative validated evidence source configuration model.
- SourceDatasetConfig: Declarative binding of a physical source to a canonical dataset.
- CsvSelector, ExcelSelector, SqliteSelector: Discriminated physical dataset selectors.
- DatasetSelector: Discriminated union of supported dataset selectors.
- TopologyCoverageReport: Diagnostic report summarizing Bronze dataset coverage.
- evaluate_bronze_topology_coverage: Evaluator comparing configured bindings against Bronze contracts.
- validate_source_dataset_bindings: Aggregate validation helper for sources and dataset bindings.
- validate_source_selector_compatibility: Cross-model provider compatibility validator.

Does not own
------------
- SourceId, ProviderType, and DatasetId contract definitions (owned by contracts).
- Root settings or runtime operational environment flags (owned by config.settings).
- Physical provider extraction mechanics (owned by infrastructure.providers).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    DatasetSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.config.sources.topology import (
    TopologyCoverageReport,
    evaluate_bronze_topology_coverage,
)
from personal_finance_etl.config.sources.validation import (
    validate_source_dataset_bindings,
    validate_source_selector_compatibility,
)

__all__ = [
    "CsvSelector",
    "DatasetSelector",
    "ExcelSelector",
    "SourceConfig",
    "SourceDatasetConfig",
    "SqliteSelector",
    "TopologyCoverageReport",
    "evaluate_bronze_topology_coverage",
    "validate_source_dataset_bindings",
    "validate_source_selector_compatibility",
]
