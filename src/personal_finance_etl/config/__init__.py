"""Configuration and financial policy package.

Owns
----
- Validated runtime environment settings (Settings).
- Financial policy and rule definitions (FinancialRules).
- Declarative physical evidence source configuration (SourceConfig, SourceDatasetConfig).
- Physical dataset selectors (CsvSelector, ExcelSelector, SqliteSelector).
- Change-detection and synchronization policy (ChangeDetectionPolicy, FingerprintStrategy, etc.).
- Topology coverage evaluation (TopologyCoverageReport, evaluate_bronze_topology_coverage).
- Validation of TOML configuration files.

Does not own
-------------
- Filesystem persistence of preferences (owned by infrastructure.preferences).
- Domain calculations or execution workflows (owned by domain and application).
- UI configuration forms (owned by presentation).
"""

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import FileHashPolicy, Settings
from personal_finance_etl.config.sources import (
    BronzeIdentityStrategy,
    ChangeDetectionPolicy,
    CompositeIdentity,
    CsvSelector,
    DatasetSelector,
    DerivedDeterministicIdentity,
    DriftStrategy,
    ExcelSelector,
    FingerprintStrategy,
    RenameStrategy,
    SourceConfig,
    SourceDatasetConfig,
    SourceFieldIdentity,
    SqliteSelector,
    SyncStrategy,
    TopologyCoverageReport,
    evaluate_bronze_topology_coverage,
    resolve_change_detection_policy,
)

__all__ = [
    "BronzeIdentityStrategy",
    "ChangeDetectionPolicy",
    "CompositeIdentity",
    "CsvSelector",
    "DatasetSelector",
    "DerivedDeterministicIdentity",
    "DriftStrategy",
    "ExcelSelector",
    "FileHashPolicy",
    "FinancialRules",
    "FingerprintStrategy",
    "RenameStrategy",
    "Settings",
    "SourceConfig",
    "SourceDatasetConfig",
    "SourceFieldIdentity",
    "SqliteSelector",
    "SyncStrategy",
    "TopologyCoverageReport",
    "evaluate_bronze_topology_coverage",
    "resolve_change_detection_policy",
]
