"""Automated Git Commit Tool adhering to Commitlint and Conventional Commits.

Owns
----
- Automatic generation of Conventional Commit messages within 72-80 character limit.
- Individual file staging and granular committing for refactoring workflows.
- Dry-run preview of commit headers and scopes.
- Reusable across all refactoring phases (Phase 0 through Phase 8).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Explicit commit overrides for known files during the refactoring phases
KNOWN_COMMIT_MESSAGES: dict[str, str] = {
    # Phase 0 Architecture
    "tests/test_architecture_boundaries.py": "test(architecture): add AST layer boundary enforcement test",
    # Phase 1 Contracts
    "src/personal_finance_etl/contracts/__init__.py": "refactor(contracts): declare lifecycle and extraction exports",
    "src/personal_finance_etl/contracts/lifecycle.py": "refactor(contracts): define CommitState and FailureDomain contracts",
    "src/personal_finance_etl/contracts/logging.py": "refactor(contracts): add NullStatusQueue to logging protocol",
    "src/personal_finance_etl/contracts/extraction.py": "refactor(contracts): define extraction result and error contracts",
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): define snapshot and restore result contracts",
    "src/personal_finance_etl/contracts/application.py": "refactor(contracts): define engine execution and status contracts",
    "src/personal_finance_etl/domain/common/calculation.py": "refactor(domain/common): define financial calculation results",
    "src/personal_finance_etl/domain/common/validation.py": "refactor(domain/common): define validation exceptions and parsing",
    "tests/test_phase1_contracts.py": "test(contracts): add Phase 1 contracts and re-export tests",
    # Phase 1 Legacy Deactivations
    "src/personal_finance_etl/backend/types/calculation.py": "refactor(legacy): deactivate types/calculation and delegate",
    "src/personal_finance_etl/backend/types/validation.py": "refactor(legacy): deactivate types/validation and delegate",
    "src/personal_finance_etl/backend/types/fx.py": "refactor(legacy): deactivate types/fx and delegate",
    "src/personal_finance_etl/backend/types/failure.py": "refactor(legacy): deactivate types/failure and delegate",
    "src/personal_finance_etl/backend/types/batch_result.py": "refactor(legacy): deactivate types/batch_result and delegate",
    "src/personal_finance_etl/backend/types/pipeline.py": "refactor(legacy): deactivate types/pipeline and delegate",
    "src/personal_finance_etl/backend/types/analytics.py": "refactor(legacy): deactivate types/analytics and delegate",
    "src/personal_finance_etl/backend/utils/models.py": "refactor(legacy): deactivate models LogLevel and TaxLot",
    # Phase 2 Config & Common Primitives
    "src/personal_finance_etl/config/financial_rules/household.py": "refactor(config): implement household policy and budget rules",
    "src/personal_finance_etl/config/financial_rules/investments.py": "refactor(config): implement investment and portfolio rules",
    "src/personal_finance_etl/config/financial_rules/tax.py": "refactor(config): implement tax assumptions and rates policy",
    "src/personal_finance_etl/config/financial_rules/fire.py": "refactor(config): implement FIRE, CMA and Monte Carlo policy",
    "src/personal_finance_etl/config/financial_rules/model.py": "refactor(config): implement root FinancialRules composed model",
    "src/personal_finance_etl/config/financial_rules/__init__.py": "refactor(config): export financial rules policy models",
    "src/personal_finance_etl/config/settings.py": "refactor(config): import PreferencesManager at top level",
    "src/personal_finance_etl/config/__init__.py": "refactor(config): export Settings and FinancialRules",
    "src/personal_finance_etl/infrastructure/preferences/repository.py": "refactor(infrastructure): implement PreferencesManager store",
    "src/personal_finance_etl/infrastructure/preferences/__init__.py": "refactor(infrastructure): export PreferencesManager repository",
    "src/personal_finance_etl/infrastructure/filesystem/paths.py": "refactor(infrastructure): implement path and cache utilities",
    "src/personal_finance_etl/infrastructure/filesystem/__init__.py": "refactor(infrastructure): export filesystem path helpers",
    "src/personal_finance_etl/domain/common/identity.py": "refactor(domain/common): add deterministic entity identity v2",
    "src/personal_finance_etl/domain/common/dates.py": "refactor(domain/common): implement Indian fiscal year and dates",
    "src/personal_finance_etl/domain/common/polars.py": "refactor(domain/common): implement reusable analytical expressions",
    "src/personal_finance_etl/domain/common/__init__.py": "refactor(domain/common): export common domain primitives",
    "tests/test_phase2_config_and_primitives.py": "test(config): add Phase 2 configuration and primitives tests",
    # Phase 2 Legacy Deactivations
    "src/personal_finance_etl/backend/config/financial_rules.py": "refactor(legacy): deactivate config/financial_rules and delegate",
    "src/personal_finance_etl/backend/config/settings.py": "refactor(legacy): deactivate config/settings and delegate",
    "src/personal_finance_etl/backend/utils/helpers.py": "refactor(legacy): deactivate utils/helpers and delegate",
    "src/personal_finance_etl/backend/utils/identity.py": "refactor(legacy): deactivate utils/identity and delegate",
    "src/personal_finance_etl/backend/utils/polars_expressions.py": "refactor(legacy): deactivate utils/polars_expressions and delegate",
    "src/personal_finance_etl/backend/engines/tax/utils/date_utils.py": "refactor(legacy): deactivate engines/tax date_utils and delegate",
    # Phase 3 Control Plane
    "src/personal_finance_etl/infrastructure/control_plane/__init__.py": "refactor(infrastructure): export control plane repositories",
    "src/personal_finance_etl/infrastructure/control_plane/schema.py": "refactor(control_plane): define canonical SQLite RAW_DDL schema",
    "src/personal_finance_etl/infrastructure/control_plane/connection.py": "refactor(control_plane): import RAW_DDL from local schema",
    "src/personal_finance_etl/infrastructure/control_plane/hashing.py": "refactor(infrastructure): implement hashing and file identity",
    "src/personal_finance_etl/infrastructure/control_plane/run_repository.py": "refactor(infrastructure): implement RunRepository lifecycle",
    "src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py": "refactor(infrastructure): implement ArtifactRepository store",
    "src/personal_finance_etl/infrastructure/control_plane/file_sync.py": "refactor(infrastructure): implement FileSyncService sync",
    "src/personal_finance_etl/infrastructure/control_plane/facade.py": "refactor(infrastructure): implement ControlPlane facade",
    # Phase 3 Warehouse Schemas
    "src/personal_finance_etl/infrastructure/warehouse/schema/__init__.py": "refactor(warehouse): export schema DDL statements and pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/pragmas.py": "refactor(warehouse): define SQLite and DuckDB pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/control_plane.py": "refactor(warehouse): re-export RAW_DDL from control_plane schema",
    "src/personal_finance_etl/infrastructure/warehouse/schema/bronze.py": "refactor(warehouse): define bronze lakehouse DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/silver.py": "refactor(warehouse): define silver layer DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/gold.py": "refactor(warehouse): define gold presentation DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/meta.py": "refactor(warehouse): define meta telemetry DDL schemas",
    # Phase 3 Warehouse & Storage
    "src/personal_finance_etl/infrastructure/warehouse/__init__.py": "refactor(warehouse): decouple layer modules from warehouse init",
    "src/personal_finance_etl/infrastructure/warehouse/connection.py": "refactor(warehouse): implement DuckDBManager connection",
    "src/personal_finance_etl/infrastructure/warehouse/registry.py": "refactor(warehouse): implement data contract registries",
    "src/personal_finance_etl/infrastructure/warehouse/fingerprints.py": "refactor(warehouse): implement contract registry fingerprinting",
    "src/personal_finance_etl/infrastructure/warehouse/bronze.py": "refactor(warehouse): remove TYPE_CHECKING and import ControlPlane",
    "src/personal_finance_etl/infrastructure/warehouse/silver.py": "refactor(warehouse): implement SilverLayer table persistence",
    "src/personal_finance_etl/infrastructure/warehouse/gold.py": "refactor(warehouse): implement GoldLayer analytical tables",
    "src/personal_finance_etl/infrastructure/warehouse/meta.py": "refactor(warehouse): remove TYPE_CHECKING and import ControlPlane",
    # Phase 3 Recovery & Logging
    "src/personal_finance_etl/infrastructure/recovery/__init__.py": "refactor(infrastructure): export SystemBackupManager",
    "src/personal_finance_etl/infrastructure/recovery/backup.py": "refactor(infrastructure): implement SystemBackupManager",
    "src/personal_finance_etl/infrastructure/logging/__init__.py": "refactor(infrastructure): export setup_logger and handlers",
    "src/personal_finance_etl/infrastructure/logging/setup.py": "refactor(infrastructure): implement multi-process logging",
    # Phase 3 Tests
    "tests/test_phase3_infrastructure.py": "test(infrastructure): add Phase 3 infrastructure test suite",
    # Phase 3 Legacy Deactivations
    "src/personal_finance_etl/backend/load/control_plane/__init__.py": "refactor(legacy): deactivate backend control plane init",
    "src/personal_finance_etl/backend/load/control_plane/connection.py": "refactor(legacy): deactivate load control plane connection",
    "src/personal_finance_etl/backend/load/control_plane/utils.py": "refactor(legacy): deactivate load control plane utils",
    "src/personal_finance_etl/backend/load/control_plane/run_repo.py": "refactor(legacy): deactivate load control plane run_repo",
    "src/personal_finance_etl/backend/load/control_plane/artifact_repo.py": "refactor(legacy): deactivate load control plane artifact_repo",
    "src/personal_finance_etl/backend/load/control_plane/file_sync.py": "refactor(legacy): deactivate load control plane file_sync",
    "src/personal_finance_etl/backend/load/control_plane/orchestrator.py": "refactor(legacy): deactivate control plane orchestrator",
    "src/personal_finance_etl/backend/load/schema/__init__.py": "refactor(legacy): deactivate backend load schema init",
    "src/personal_finance_etl/backend/load/schema/pragmas.py": "refactor(legacy): deactivate backend load schema pragmas",
    "src/personal_finance_etl/backend/load/schema/control_plane.py": "refactor(legacy): deactivate load schema control_plane",
    "src/personal_finance_etl/backend/load/schema/bronze.py": "refactor(legacy): deactivate backend load schema bronze",
    "src/personal_finance_etl/backend/load/schema/silver.py": "refactor(legacy): deactivate backend load schema silver",
    "src/personal_finance_etl/backend/load/schema/gold.py": "refactor(legacy): deactivate backend load schema gold",
    "src/personal_finance_etl/backend/load/schema/meta.py": "refactor(legacy): deactivate backend load schema meta",
    "src/personal_finance_etl/backend/load/database.py": "refactor(legacy): deactivate load database manager",
    "src/personal_finance_etl/backend/load/registry.py": "refactor(legacy): deactivate load contract registry",
    "src/personal_finance_etl/backend/load/bronze.py": "refactor(legacy): deactivate load bronze layer",
    "src/personal_finance_etl/backend/load/silver.py": "refactor(legacy): deactivate load silver layer",
    "src/personal_finance_etl/backend/load/gold.py": "refactor(legacy): deactivate load gold layer",
    "src/personal_finance_etl/backend/load/metadata.py": "refactor(legacy): deactivate load metadata layer",
    "src/personal_finance_etl/backend/load/backup.py": "refactor(legacy): deactivate load backup manager",
    "src/personal_finance_etl/backend/utils/logger.py": "refactor(legacy): deactivate utils logger setup",
    "src/personal_finance_etl/backend/utils/reproducibility.py": "refactor(legacy): deactivate utils reproducibility",
    # Phase 4 File Providers
    "src/personal_finance_etl/infrastructure/providers/files/__init__.py": "refactor(providers): export statement and file adapters",
    "src/personal_finance_etl/infrastructure/providers/files/locator.py": "refactor(providers): implement statement locator adapter",
    "src/personal_finance_etl/infrastructure/providers/files/csv.py": "refactor(providers): implement CSV evidence extraction adapters",
    "src/personal_finance_etl/infrastructure/providers/files/excel.py": "refactor(providers): implement Excel evidence parsing adapters",
    "src/personal_finance_etl/infrastructure/providers/files/sqlite.py": "refactor(providers): implement SQLite external source adapter",
    # Phase 4 Market Providers
    "src/personal_finance_etl/infrastructure/providers/market/__init__.py": "refactor(providers): export market series provider adapters",
    "src/personal_finance_etl/infrastructure/providers/market/currency.py": "refactor(providers): implement CurrencyExtractor provider",
    "src/personal_finance_etl/infrastructure/providers/market/benchmark.py": "refactor(providers): implement BenchmarkExtractor provider",
    "src/personal_finance_etl/infrastructure/providers/market/us_market.py": "refactor(providers): implement USMarketExtractor provider",
    # Phase 4 Application Ingestion
    "src/personal_finance_etl/application/ingestion/__init__.py": "refactor(ingestion): export ingestion coordinators and strategies",
    "src/personal_finance_etl/application/ingestion/asset_strategies.py": "refactor(ingestion): implement asset-specific ingestion pipelines",
    "src/personal_finance_etl/application/ingestion/coordinator.py": "refactor(ingestion): implement DataExtractor coordinator",
    "src/personal_finance_etl/application/ingestion/market_sync.py": "refactor(ingestion): implement MarketSyncService and pipelines",
    # Phase 4 Tests
    "tests/test_phase4_extraction_and_ingestion.py": "test(ingestion): add Phase 4 extraction and ingestion test suite",
    # Phase 4 Legacy Deactivations
    "src/personal_finance_etl/backend/extract/statement_locator.py": "refactor(legacy): deactivate statement_locator and delegate",
    "src/personal_finance_etl/backend/extract/csv_extractor.py": "refactor(legacy): deactivate csv_extractor and delegate",
    "src/personal_finance_etl/backend/extract/excel_extractor.py": "refactor(legacy): deactivate excel_extractor and delegate",
    "src/personal_finance_etl/backend/extract/sqlite_extractor.py": "refactor(legacy): deactivate sqlite_extractor and delegate",
    "src/personal_finance_etl/backend/extract/currency_extractor.py": "refactor(legacy): deactivate currency_extractor and delegate",
    "src/personal_finance_etl/backend/extract/benchmark_extractor.py": "refactor(legacy): deactivate benchmark_extractor and delegate",
    "src/personal_finance_etl/backend/extract/us_market_extractor.py": "refactor(legacy): deactivate us_market_extractor and delegate",
    "src/personal_finance_etl/backend/pipeline/strategies.py": "refactor(legacy): deactivate pipeline strategies and delegate",
    "src/personal_finance_etl/backend/pipeline/core/extractor.py": "refactor(legacy): deactivate DataExtractor and delegate",
    "src/personal_finance_etl/backend/pipeline/currency_pipeline.py": "refactor(legacy): deactivate CurrencyPipeline and delegate",
    "src/personal_finance_etl/backend/pipeline/benchmark_pipeline.py": "refactor(legacy): deactivate BenchmarkPipeline and delegate",
    "src/personal_finance_etl/backend/pipeline/us_market_pipeline.py": "refactor(legacy): deactivate USMarketPipeline and delegate",
    # Phase 5: Canonical Financial Domains (Household)
    "src/personal_finance_etl/domain/household/transforms/calendar.py": "feat(domain): implement calendar time intelligence transform",
    "src/personal_finance_etl/domain/household/transforms/common.py": "feat(domain): implement household mapping helpers",
    "src/personal_finance_etl/domain/household/transforms/dimensions.py": "feat(domain): implement household dimension transformations",
    "src/personal_finance_etl/domain/household/transforms/transactions.py": "feat(domain): implement transaction facts transformations",
    "src/personal_finance_etl/domain/household/transforms/__init__.py": "refactor(domain): export canonical household transformations",
    # Phase 5: Canonical Financial Domains (Market)
    "src/personal_finance_etl/domain/market/benchmarks.py": "feat(domain): implement benchmark returns and staleness policy",
    "src/personal_finance_etl/domain/market/fx.py": "feat(domain): implement FXRateProvider and daily FX series",
    "src/personal_finance_etl/domain/market/macro.py": "feat(domain): implement FYMacroParametersTable and holding rules",
    "src/personal_finance_etl/domain/market/__init__.py": "refactor(domain): export canonical market domain models",
    # Phase 5: Canonical Financial Domains (Investments)
    "src/personal_finance_etl/domain/investments/lots/ordering.py": "feat(domain): implement CanonicalOrderPolicy lot sorting",
    "src/personal_finance_etl/domain/investments/transforms/common.py": "feat(domain): implement investment reference transformations",
    "src/personal_finance_etl/domain/investments/transforms/indian_equity.py": "feat(domain): implement Indian equity trade transformations",
    "src/personal_finance_etl/domain/investments/transforms/mutual_funds.py": "feat(domain): implement mutual fund trade transformations",
    "src/personal_finance_etl/domain/investments/transforms/us_equity.py": "feat(domain): implement US equity trade transformations",
    "src/personal_finance_etl/domain/investments/valuation/market_state.py": "feat(domain): implement US stock FIFO market valuation spine",
    "src/personal_finance_etl/domain/investments/transforms/__init__.py": "refactor(domain): export canonical investment transformations",
    # Phase 5: Legacy Deactivations
    "src/personal_finance_etl/backend/transform/calendar.py": "refactor(legacy): deactivate transform calendar and delegate",
    "src/personal_finance_etl/backend/transform/helpers.py": "refactor(legacy): deactivate transform helpers and delegate",
    "src/personal_finance_etl/backend/transform/dimensions.py": "refactor(legacy): deactivate transform dimensions and delegate",
    "src/personal_finance_etl/backend/transform/facts.py": "refactor(legacy): deactivate transform facts and delegate",
    "src/personal_finance_etl/backend/transform/benchmark_transformer.py": "refactor(legacy): deactivate benchmark transformer and delegate",
    "src/personal_finance_etl/backend/transform/currency_transformer.py": "refactor(legacy): deactivate currency transformer and delegate",
    "src/personal_finance_etl/backend/engines/analytics/rules/macro.py": "refactor(legacy): deactivate macro parameters and delegate",
    "src/personal_finance_etl/backend/utils/ordering.py": "refactor(legacy): deactivate ordering policy and delegate",
    "src/personal_finance_etl/backend/transform/investments.py": "refactor(legacy): deactivate transform investments and delegate",
    "src/personal_finance_etl/backend/transform/mutual_funds.py": "refactor(legacy): deactivate transform mutual funds and delegate",
    "src/personal_finance_etl/backend/transform/stocks.py": "refactor(legacy): deactivate transform stocks and delegate",
    "src/personal_finance_etl/backend/transform/us_stocks.py": "refactor(legacy): deactivate transform US stocks and delegate",
    "src/personal_finance_etl/backend/transform/us_stocks_transformer.py": "refactor(legacy): deactivate US stocks transformer and delegate",
    # Phase 5: Verification Suite
    "tests/test_phase5_canonical_domains.py": "test(domain): add Phase 5 canonical domain test suite",
    # Phase 6A: Investment Contracts & Typed Models
    "src/personal_finance_etl/domain/investments/contracts.py": "refactor(investments): define investment contracts and typed models",
    "src/personal_finance_etl/domain/investments/lots/models.py": "feat(investments): define TaxLot AcquisitionLot and LotAction",
    "src/personal_finance_etl/domain/investments/reconciliation/models.py": "feat(investments): define ReconciliationEvent typed model",
    "src/personal_finance_etl/domain/investments/reconciliation/__init__.py": "refactor(investments): export reconciliation models",
    "src/personal_finance_etl/domain/investments/__init__.py": "refactor(investments): export investment models and services",
    # Phase 6B: FIFO & Lot Accounting
    "src/personal_finance_etl/domain/investments/lots/fifo.py": "feat(investments): implement FIFOPortfolio queue and shadow units",
    "src/personal_finance_etl/backend/engines/analytics/core/fifo.py": "refactor(legacy): deactivate analytics fifo and delegate",
    "src/personal_finance_etl/domain/investments/lots/__init__.py": "refactor(investments): export FIFOPortfolio and lot models",
    # Phase 6C: Valuation, FX & Benchmark Context
    "src/personal_finance_etl/domain/investments/valuation/fx.py": "feat(investments): implement FXValidationGate and error types",
    "src/personal_finance_etl/domain/investments/valuation/benchmark.py": "feat(investments): implement BenchmarkPriceProvider with fallback",
    "src/personal_finance_etl/domain/investments/valuation/__init__.py": "refactor(investments): export valuation gates and benchmark provider",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/processor/fx_gate.py": "refactor(legacy): deactivate fx_gate and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/processor/benchmark.py": "refactor(legacy): deactivate benchmark provider and delegate",
    # Phase 6D: Performance & Mathematics
    "src/personal_finance_etl/domain/investments/performance/returns.py": "feat(investments): implement calculate_cagr with typed status",
    "src/personal_finance_etl/domain/investments/performance/xirr.py": "feat(investments): implement calculate_xirr and portfolio solver",
    "src/personal_finance_etl/domain/investments/performance/attribution.py": "feat(investments): implement RealizedGainsCalculator",
    "src/personal_finance_etl/domain/investments/performance/__init__.py": "refactor(investments): export performance and attribution metrics",
    "src/personal_finance_etl/backend/engines/analytics/core/math.py": "refactor(legacy): deactivate analytics math and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/xirr.py": "refactor(legacy): deactivate postprocessor xirr and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/gains.py": "refactor(legacy): deactivate postprocessor gains and delegate",
    # Phase 6E: Reconciliation Engine
    "src/personal_finance_etl/domain/investments/reconciliation/engine.py": "feat(investments): implement ReconciliationEngine with tolerances",
    # Phase 6F: Portfolio Snapshots & Aggregation
    "src/personal_finance_etl/domain/investments/portfolio/snapshots.py": "feat(investments): implement SnapshotGenerator lot snapshots",
    "src/personal_finance_etl/domain/investments/portfolio/analytics.py": "feat(investments): implement AdvancedAnalyticsCalculator",
    "src/personal_finance_etl/domain/investments/portfolio/aggregation.py": "feat(investments): implement GroupProcessor and portfolio weights",
    "src/personal_finance_etl/domain/investments/portfolio/__init__.py": "refactor(investments): export portfolio snapshots and aggregators",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/processor/snapshot.py": "refactor(legacy): deactivate snapshot generator and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/group_processor.py": "refactor(legacy): deactivate group_processor and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/weights.py": "refactor(legacy): deactivate portfolio weights and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/analytics.py": "refactor(legacy): deactivate postprocessor analytics and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/harvest.py": "refactor(legacy): deactivate harvest calculator and delegate",
    # Phase 6G: Application ISIN & Quant Orchestration Services
    "src/personal_finance_etl/application/investments/input_adapter.py": "feat(investments): implement TaxDataLoader and IsinDataExtractor",
    "src/personal_finance_etl/application/investments/context.py": "refactor(investments): use top-level EngineStatusMessage in context",
    "src/personal_finance_etl/application/investments/isin_service.py": "refactor(investments): use top-level EngineStatusMessage in isin",
    "src/personal_finance_etl/application/investments/aggregation_service.py": "refactor(investments): use top-level EngineStatusMessage",
    "src/personal_finance_etl/application/investments/quant_service.py": "refactor(investments): use top-level EngineStatusMessage in quant",
    "src/personal_finance_etl/application/investments/__init__.py": "refactor(investments): export investment application services",
    "src/personal_finance_etl/backend/engines/analytics/context.py": "refactor(legacy): deactivate analytics context and delegate",
    "src/personal_finance_etl/backend/engines/analytics/engine.py": "refactor(legacy): deactivate quant engine and delegate",
    "src/personal_finance_etl/backend/engines/analytics/isin_pipeline.py": "refactor(legacy): deactivate isin_pipeline and delegate",
    "src/personal_finance_etl/backend/engines/analytics/post_pipeline.py": "refactor(legacy): deactivate post_pipeline and delegate",
    "src/personal_finance_etl/backend/engines/analytics/io/loader.py": "refactor(legacy): deactivate analytics loader and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/context.py": "refactor(legacy): deactivate pipeline context and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/processor/extractor.py": "refactor(legacy): deactivate data extractor and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/processor/isin_processor.py": "refactor(legacy): deactivate isin_processor and delegate",
    "src/personal_finance_etl/backend/engines/analytics/pipeline/postprocessor/coordinator.py": "refactor(legacy): deactivate postprocessor coordinator and delegate",
    # Phase 6H: Verification Suite
    "tests/test_phase6_investments_and_quant.py": "test(investments): add Phase 6 investment and quant test suite",
    # Phase 7: Tax Domain & Application Service
    "src/personal_finance_etl/domain/tax/classification.py": "feat(domain/tax): add TaxClassifier for income heads and sub-heads",
    "src/personal_finance_etl/domain/tax/estimates.py": "feat(domain/tax): add TaxEstimator for rate resolution and bounding",
    "src/personal_finance_etl/domain/tax/events.py": "feat(domain/tax): add BaseEventsBuilder and canonical event schema",
    "src/personal_finance_etl/domain/tax/reconciliation.py": "feat(domain/tax): add TaxGoldFormatter and audit reconciliation marts",
    "src/personal_finance_etl/domain/tax/__init__.py": "feat(domain/tax): export canonical tax domain symbols",
    "src/personal_finance_etl/application/tax/tax_service.py": "feat(application/tax): add TaxService application engine",
    "src/personal_finance_etl/application/tax/__init__.py": "feat(application/tax): export TaxService and TaxEngine symbols",
    "src/personal_finance_etl/backend/engines/tax/core/base_events.py": "refactor(backend/tax): shim base_events to domain.tax.events",
    "src/personal_finance_etl/backend/engines/tax/core/gold_formatter.py": "refactor(backend/tax): shim gold_formatter to domain.tax.reconciliation",
    "src/personal_finance_etl/backend/engines/tax/tax_engine.py": "refactor(backend/tax): shim tax_engine to application.tax.tax_service",
    "src/personal_finance_etl/backend/engines/tax/core/__init__.py": "refactor(backend/tax): re-export canonical domain tax symbols in core",
    "src/personal_finance_etl/backend/engines/tax/__init__.py": "refactor(backend/tax): re-export TaxEngine in backend tax init",
    "tests/test_phase7_tax_domain.py": "test(domain/tax): add Phase 7 tax domain and service test suite",
    # Phase 8: Household Analytics, Wealth, and FIRE
    "src/personal_finance_etl/domain/household/ledger.py": "feat(domain/household): add LedgerBuilder for monthly balances",
    "src/personal_finance_etl/domain/household/cashflow.py": "feat(domain/household): add cashflow statement builders",
    "src/personal_finance_etl/domain/household/budget.py": "feat(domain/household): add budget forecast and spend analytics",
    "src/personal_finance_etl/domain/household/income.py": "feat(domain/household): add IncomeStreamsBuilder for yield",
    "src/personal_finance_etl/domain/household/__init__.py": "feat(domain/household): export canonical household builders",
    "src/personal_finance_etl/domain/wealth/net_worth.py": "feat(domain/wealth): add NetWorthBuilder for mark-to-market NW",
    "src/personal_finance_etl/domain/wealth/scoring.py": "feat(domain/wealth): add HealthScorer and budget health scoring",
    "src/personal_finance_etl/domain/wealth/analytics.py": "feat(domain/wealth): add InvestmentAnalyticsBuilder for drift",
    "src/personal_finance_etl/domain/wealth/__init__.py": "feat(domain/wealth): export canonical wealth domain symbols",
    "src/personal_finance_etl/domain/fire/inflation.py": "feat(domain/fire): add InflationBuilder for continuous CPI series",
    "src/personal_finance_etl/domain/fire/forecasting.py": "feat(domain/fire): add forward budget forecast helper",
    "src/personal_finance_etl/domain/fire/simulation.py": "feat(domain/fire): add Monte Carlo simulation kernel and batch",
    "src/personal_finance_etl/domain/fire/deterministic.py": "feat(domain/fire): add WealthRiskAnalyticsBuilder for FIRE",
    "src/personal_finance_etl/domain/fire/reproducibility.py": "feat(domain/fire): add deterministic simulation seed helpers",
    "src/personal_finance_etl/domain/fire/__init__.py": "feat(domain/fire): export canonical FIRE domain symbols",
    "src/personal_finance_etl/application/wealth/wealth_service.py": "feat(application/wealth): add WealthService presentation DAG",
    "src/personal_finance_etl/application/wealth/__init__.py": "feat(application/wealth): export WealthService and engine",
    "src/personal_finance_etl/backend/engines/presentation/core/ledger_builder.py": "refactor(backend/presentation): shim ledger_builder to domain",
    "src/personal_finance_etl/backend/engines/presentation/core/net_worth_builder.py": "refactor(backend/presentation): shim net_worth_builder to domain",
    "src/personal_finance_etl/backend/engines/presentation/core/inflation_builder.py": "refactor(backend/presentation): shim inflation_builder to domain",
    "src/personal_finance_etl/backend/engines/presentation/core/__init__.py": "refactor(backend/presentation): re-export core builders in core init",
    "src/personal_finance_etl/backend/engines/presentation/helpers/scoring.py": "refactor(backend/presentation): shim scoring to domain wealth",
    "src/personal_finance_etl/backend/engines/presentation/helpers/forecasting.py": "refactor(backend/presentation): shim forecasting to domain fire",
    "src/personal_finance_etl/backend/engines/presentation/helpers/fire_mc_sim.py": "refactor(backend/presentation): shim fire_mc_sim to domain fire",
    "src/personal_finance_etl/backend/engines/presentation/modules/cashflow_statement_builder.py": "refactor(backend/presentation): shim cashflow statement to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/monthly_cashflow_summary.py": "refactor(backend/presentation): shim monthly cashflow to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/spend_analytics.py": "refactor(backend/presentation): shim spend_analytics to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/budget_forecast.py": "refactor(backend/presentation): shim budget_forecast to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/income_streams.py": "refactor(backend/presentation): shim income_streams to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/investment_analytics.py": "refactor(backend/presentation): shim investment_analytics to domain",
    "src/personal_finance_etl/backend/engines/presentation/modules/wealth_risk_analytics.py": "refactor(backend/presentation): shim wealth_risk_analytics to domain",
    "src/personal_finance_etl/backend/engines/presentation/wealth_engine.py": "refactor(backend/presentation): shim wealth_engine to application",
    "src/personal_finance_etl/backend/engines/presentation/__init__.py": "refactor(backend/presentation): deprecate and re-export WealthService",
    "src/personal_finance_etl/backend/pipeline/etl_pipeline.py": "refactor(legacy/pipeline): shim etl_pipeline to application",
    "tests/test_phase8_household_wealth_fire.py": "test(presentation): add Phase 8 household wealth and fire tests",
    # Phase 9: Application Orchestration & Bootstrap Composition Root
    "src/personal_finance_etl/application/pipeline/lifecycle.py": "feat(application/pipeline): implement RunLifecycleCoordinator",
    "src/personal_finance_etl/application/pipeline/execution.py": "refactor(application): deduplicate engine progress log events",
    "src/personal_finance_etl/application/pipeline/orchestrator.py": "refactor(application): deduplicate orchestrator status messages",
    "src/personal_finance_etl/application/pipeline/worker.py": "feat(application/pipeline): implement WorkerPoolCoordinator",
    "src/personal_finance_etl/application/pipeline/__init__.py": "refactor(application/pipeline): export pipeline orchestration symbols",
    "src/personal_finance_etl/bootstrap/container.py": "feat(bootstrap): implement ServiceContainer composition root",
    "src/personal_finance_etl/bootstrap/__init__.py": "refactor(bootstrap): export ServiceContainer composition root",
    "src/personal_finance_etl/application/facade.py": "refactor(application): remove TYPE_CHECKING and inline container",
    "src/personal_finance_etl/application/__init__.py": "refactor(application): export PersonalFinanceEngine facade",
    "src/personal_finance_etl/backend/api/engine.py": "refactor(legacy/api): shim PersonalFinanceEngine to application facade",
    "tests/test_phase9_orchestration_and_bootstrap.py": "test(application): use top-level DuckDBManager import",
    # Phase 10: Presentation (CLI, Desktop GUI, Docs)
    "src/personal_finance_etl/presentation/docs/assets/mermaid/LICENSE": "chore(presentation): add mermaid license",
    "src/personal_finance_etl/presentation/docs/assets/mermaid/VERSION": "chore(presentation): add mermaid version",
    "src/personal_finance_etl/presentation/docs/assets/mermaid/mermaid.min.js": "feat(presentation): add bundled mermaid runtime",
    "src/personal_finance_etl/presentation/docs/assets/svg-pan-zoom/LICENSE": "chore(presentation): add svg-pan-zoom license",
    "src/personal_finance_etl/presentation/docs/assets/svg-pan-zoom/VERSION": "chore(presentation): add svg-pan-zoom version",
    "src/personal_finance_etl/presentation/docs/assets/svg-pan-zoom/svg-pan-zoom.min.js": "feat(presentation): add svg-pan-zoom runtime",
    ".gitattributes": "chore(repo): update gitattributes for presentation docs assets",
    "src/personal_finance_etl/presentation/desktop/theme.py": "feat(presentation): implement canonical desktop theme tokens",
    "src/personal_finance_etl/backend/utils/theme.py": "refactor(legacy): shim backend theme to presentation desktop theme",
    "src/personal_finance_etl/presentation/desktop/base_tab.py": "feat(presentation): implement BaseEngineTab desktop component",
    "src/personal_finance_etl/frontend/desktop/base_tab.py": "refactor(legacy): shim frontend base_tab to presentation base_tab",
    "src/personal_finance_etl/presentation/docs/manifest.py": "feat(presentation): implement DocsCatalog and DocEntry manifest",
    "src/personal_finance_etl/frontend/commons/docs/manifest.py": "refactor(legacy): shim frontend docs manifest to presentation",
    "src/personal_finance_etl/presentation/docs/renderer.py": "feat(presentation): implement DocsRenderer markdown web compiler",
    "src/personal_finance_etl/frontend/commons/docs/renderer.py": "refactor(legacy): shim frontend docs renderer to presentation",
    "src/personal_finance_etl/presentation/docs/guides_window.py": "feat(presentation): implement show_guides_window pywebview viewer",
    "src/personal_finance_etl/frontend/commons/docs/guides_window.py": "refactor(legacy): shim frontend guides_window to presentation",
    "src/personal_finance_etl/presentation/docs/__init__.py": "refactor(presentation): export canonical docs models and viewer",
    "src/personal_finance_etl/frontend/commons/docs/__init__.py": "refactor(legacy): shim frontend docs package to presentation",
    "src/personal_finance_etl/presentation/desktop/app.py": "feat(presentation): implement DesktopApp and UnifiedETLTab",
    "src/personal_finance_etl/frontend/desktop/app.py": "refactor(legacy): shim frontend desktop app to presentation app",
    "src/personal_finance_etl/presentation/desktop/__init__.py": "refactor(presentation): export canonical desktop app and theme",
    "src/personal_finance_etl/frontend/desktop/__init__.py": "refactor(legacy): shim frontend desktop package to presentation",
    "src/personal_finance_etl/presentation/cli/app.py": "feat(presentation): implement terminal CLI app with Rich progress",
    "src/personal_finance_etl/frontend/cli/app.py": "refactor(legacy): shim frontend cli app to presentation cli app",
    "src/personal_finance_etl/presentation/cli/__init__.py": "refactor(presentation): export canonical CLI app entrypoints",
    "src/personal_finance_etl/frontend/cli/__init__.py": "refactor(legacy): shim frontend cli package to presentation cli",
    "src/personal_finance_etl/presentation/launcher.py": "feat(presentation): implement dual-mode CLI and GUI launcher",
    "src/personal_finance_etl/frontend/launcher.py": "refactor(legacy): shim frontend launcher to presentation launcher",
    "src/personal_finance_etl/presentation/__init__.py": "refactor(presentation): export main launcher in root presentation",
    "src/personal_finance_etl/frontend/__init__.py": "refactor(legacy): shim frontend root package to presentation",
    "pyproject.toml": "chore(config): ignore presentation desktop in pyright",
    "tests/test_phase10_presentation.py": "test(presentation): add Phase 10 presentation test suite",
}

# Phase 11 Demolition and Clean Architecture Completion
PHASE11_COMMIT_MESSAGES: dict[str, str] = {
    "scripts/auto_commit.py": "chore(scripts): add Phase 11 commit messages mapping",
    "src/personal_finance_etl/application/pipeline/transformer.py": "refactor(application): canonicalize TransformationDAG pipeline",
    "src/personal_finance_etl/application/pipeline/__init__.py": "refactor(application): export canonical TransformationDAG",
    "src/personal_finance_etl/application/pipeline/execution.py": "refactor(application): import TransformationDAG canonically",
    "src/personal_finance_etl/presentation/docs/renderer.py": "refactor(presentation): remove legacy doc assets fallbacks",
    "src/personal_finance_etl/__init__.py": "refactor(root): declare canonical clean architecture facade exports",
    "pyproject.toml": "chore(build): route CLI and GUI entry points to presentation",
    ".gitattributes": "chore(git): remove obsolete frontend asset attributes",
    "tests/run_headless.py": "test(headless): use canonical settings and orchestrator imports",
    "tests/test_architecture_boundaries.py": "test(architecture): enforce legacy demolition boundary checks",
    "tests/test_phase1_contracts.py": "test(contracts): remove obsolete legacy shim identity tests",
    "tests/test_phase2_config_and_primitives.py": "test(config): remove obsolete legacy shim identity tests",
    "tests/test_phase3_infrastructure.py": "test(infrastructure): remove obsolete legacy shim identity tests",
    "tests/test_phase4_extraction_and_ingestion.py": "test(ingestion): remove obsolete legacy shim identity tests",
    "tests/test_phase5_canonical_domains.py": "test(domains): remove obsolete legacy shim identity tests",
    "tests/test_phase6_investments_and_quant.py": "test(investments): remove obsolete legacy shim identity tests",
    "tests/test_phase7_tax_domain.py": "test(tax): remove obsolete legacy shim identity tests",
    "tests/test_phase8_household_wealth_fire.py": "test(wealth): remove obsolete legacy shim identity tests",
    "tests/test_phase9_orchestration_and_bootstrap.py": "test(bootstrap): remove obsolete legacy shim identity tests",
    "tests/test_phase10_presentation.py": "test(presentation): remove obsolete legacy shim identity tests",
    "tests/test_phase11_legacy_demolition.py": "test(demolition): add Phase 11 legacy demolition test suite",
}

# Phase 12 Constitutional Certification & Audit
PHASE12_COMMIT_MESSAGES: dict[str, str] = {
    "src/personal_finance_etl/__init__.py": "docs(root): add NumPy Owns and Does not own package docstrings",
    "src/personal_finance_etl/application/investments/isin_service.py": "refactor(application): type partition dicts and eliminate type ignores",
    "src/personal_finance_etl/domain/fire/simulation.py": "refactor(domain): specify explicit codes for numba prange ignore",
    "src/personal_finance_etl/domain/tax/reconciliation.py": "refactor(domain): specify explicit code on schema cast ignore",
    "src/personal_finance_etl/presentation/desktop/app.py": "refactor(presentation): specify misc code on DesktopApp ignore",
    "tests/test_phase12_constitutional_certification.py": "test(certification): add Phase 12 constitutional audit test suite",
}

# Dedicated v9.1.0 Semantic Hardening Commit Messages
V910_COMMIT_MESSAGES: dict[str, str] = {
    # v9.1.0 Phase 1 Semantic Baseline
    ".planning/refactor_v910_v920/v9.1.0/05-any-remediation-map.csv": "docs(v9.1.0): classify 277 any remediation inventory items",
    # v9.1.0 Phase 2 Investment & Application Contracts
    "src/personal_finance_etl/domain/investments/contracts.py": "docs(domain): document RealizedEventRecord property accessors",
    "src/personal_finance_etl/application/investments/input_adapter.py": "docs(application): document TaxDataLoader and IsinDataExtractor",
    "src/personal_finance_etl/application/investments/isin_service.py": "docs(application): document IsinProcessor and IsinPipeline",
    "src/personal_finance_etl/domain/investments/lots/fifo.py": "docs(domain): document FIFOPortfolio valuation and balance methods",
    "src/personal_finance_etl/domain/investments/lots/ordering.py": "refactor(investments): type CanonicalOrderPolicy with TradeRecord",
    "src/personal_finance_etl/domain/investments/portfolio/analytics.py": "docs(domain): document analytics and harvest recommendation calculators",
    "src/personal_finance_etl/domain/investments/portfolio/snapshots.py": "docs(domain): document SnapshotGenerator.generate method",
    "src/personal_finance_etl/domain/investments/performance/attribution.py": "docs(domain): document RealizedGainsCalculator.calculate method",
    "src/personal_finance_etl/domain/investments/performance/xirr.py": "docs(domain): document PortfolioXIRRCalculator.calculate method",
    "src/personal_finance_etl/domain/investments/__init__.py": "refactor(investments): export typed investment contracts",
    "src/personal_finance_etl/domain/investments/valuation/fx.py": "refactor(investments): bind FXValidationGate to typed contracts",
    "src/personal_finance_etl/domain/investments/valuation/market_state.py": "refactor(investments): type US stock market spine records",
    "src/personal_finance_etl/domain/investments/reconciliation/engine.py": "refactor(investments): type reconciliation engine output events",
    "src/personal_finance_etl/domain/investments/portfolio/aggregation.py": "docs(domain): document PortfolioWeightsCalculator.calculate",
    "src/personal_finance_etl/application/investments/context.py": "docs(application): document RunContext and context manager methods",
    # v9.1.0 Phase 3 Domain & Application Hardening
    "src/personal_finance_etl/contracts/extraction.py": "refactor(contracts): define ExtractionProviderRequest typed contract",
    "src/personal_finance_etl/contracts/logging.py": "refactor(contracts): define structural StatusQueue protocol",
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): narrow archive paths to Path or str",
    "src/personal_finance_etl/bootstrap/container.py": "docs(bootstrap): document _NullLoggerQueue.put method",
    "src/personal_finance_etl/config/financial_rules/model.py": "docs(config): document FinancialRules root model",
    "src/personal_finance_etl/config/settings.py": "docs(config): document FileHashPolicy and Settings models",
    "src/personal_finance_etl/domain/common/dates.py": "refactor(domain/common): narrow parse_flexible_date inputs to object",
    "src/personal_finance_etl/domain/common/identity.py": "refactor(domain/common): type deterministic row with Mapping",
    "src/personal_finance_etl/domain/common/validation.py": "refactor(domain/common): narrow validation records to object",
    "src/personal_finance_etl/domain/tax/classification.py": "refactor(domain/tax): type quant sub head with RealizedEventDict",
    "src/personal_finance_etl/domain/household/budget.py": "refactor(domain/household): type budget builder LazyFrame frames",
    "src/personal_finance_etl/domain/household/cashflow.py": "refactor(domain/household): type cashflow builder LazyFrame frames",
    "src/personal_finance_etl/domain/household/income.py": "refactor(domain/household): type income stream builder LazyFrames",
    "src/personal_finance_etl/domain/household/ledger.py": "refactor(domain/household): type ledger builder base frames",
    "src/personal_finance_etl/domain/wealth/analytics.py": "refactor(domain/wealth): type investment analytics LazyFrames",
    "src/personal_finance_etl/domain/wealth/net_worth.py": "refactor(domain/wealth): type NetWorthBuilder with InflationResult",
    "src/personal_finance_etl/domain/fire/deterministic.py": "refactor(domain/fire): type WealthRiskAnalyticsBuilder LazyFrames",
    "src/personal_finance_etl/domain/fire/inflation.py": "refactor(domain/fire): define InflationCalendarResult TypedDict",
    "src/personal_finance_etl/domain/market/benchmarks.py": "refactor(domain/market): type benchmark generator StatusQueue",
    "src/personal_finance_etl/domain/market/macro.py": "refactor(domain/market): define MacroClassificationContext TypedDict",
    "src/personal_finance_etl/domain/investments/transforms/common.py": "refactor(investments): narrow transform rows to Mapping[str, object]",
    "src/personal_finance_etl/application/investments/aggregation_service.py": "refactor(investments): type aggregation service status queue",
    "src/personal_finance_etl/application/investments/quant_service.py": "refactor(investments): type quant service status queue with protocol",
    "src/personal_finance_etl/application/pipeline/execution.py": "refactor(application): eliminate cast Any in pipeline execution",
    "src/personal_finance_etl/application/pipeline/lifecycle.py": "refactor(application): type engine status message queue streams",
    "src/personal_finance_etl/application/pipeline/orchestrator.py": "docs(application): document ETLOrchestrator.dfs property setter",
    "src/personal_finance_etl/application/pipeline/worker.py": "docs(application): document QueueStream write and flush methods",
    "src/personal_finance_etl/application/wealth/wealth_service.py": "refactor(application): type LazyFrame nodes in wealth service",
    "src/personal_finance_etl/application/facade.py": "docs(application): document ContainerProtocol.create_orchestrator",
    # v9.1.0 Phase 4 Infrastructure & External Typing Boundaries
    "src/personal_finance_etl/contracts/lifecycle.py": "refactor(contracts): define SyncSummaryRecord for run metrics",
    "src/personal_finance_etl/contracts/__init__.py": "refactor(contracts): export SyncSummaryRecord contract",
    "src/personal_finance_etl/domain/fire/simulation.py": "docs(fire): document TYP-001 Numba simulation kernel exceptions",
    "src/personal_finance_etl/domain/tax/estimates.py": "refactor(tax): narrow float conversion and eliminate type ignore",
    "src/personal_finance_etl/domain/tax/events.py": "refactor(tax): narrow amount conversion and eliminate type ignore",
    "src/personal_finance_etl/domain/tax/reconciliation.py": "refactor(tax): type schema with pl.Schema and eliminate type ignores",
    "src/personal_finance_etl/infrastructure/control_plane/facade.py": "docs(control_plane): document active_run_id setter in facade",
    "src/personal_finance_etl/infrastructure/control_plane/run_repository.py": "refactor(control_plane): type simulation and sync summaries",
    "src/personal_finance_etl/infrastructure/logging/setup.py": "docs(logging): document QueueHandler.emit and ContextFilter.filter",
    "src/personal_finance_etl/infrastructure/preferences/repository.py": "refactor(preferences): narrow JSON preferences to object mappings",
    "src/personal_finance_etl/infrastructure/providers/market/benchmark.py": "docs(providers): document BenchmarkExtractor.extract_benchmark_delta",
    "src/personal_finance_etl/infrastructure/providers/market/currency.py": "docs(providers): document CurrencyExtractor.extract_currency_delta",
    "src/personal_finance_etl/infrastructure/providers/market/us_market.py": "docs(providers): document USMarketExtractor.extract_us_market_delta",
    "src/personal_finance_etl/infrastructure/warehouse/fingerprints.py": "refactor(warehouse): type tables metadata with Sequence and Mapping",
    "src/personal_finance_etl/presentation/cli/app.py": "style(presentation): professionalize CLI banner and bootloader",
    "src/personal_finance_etl/presentation/desktop/app.py": "style(presentation): align app header and description with readme",
    "src/personal_finance_etl/presentation/desktop/base_tab.py": "refactor(presentation): type desktop status handlers with contract",
    "src/personal_finance_etl/presentation/docs/guides_window.py": "docs(presentation): document TYP-005 pywebview window exception",
    "src/personal_finance_etl/presentation/docs/renderer.py": "docs(presentation): document TYP-004 markdown library exception",
    "src/personal_finance_etl/presentation/launcher.py": "docs(presentation): document TYP-003 app mainloop exception",
    ".planning/refactor_v910_v920/v9.1.0/04-typing-exception-register.md": "docs(v9.1.0): update typing exception register with survivors",
    ".planning/refactor_v910_v920/v9.1.0/06-v9.1.0-phase-tracker.md": "docs(v9.1.0): mark Phase 5 and Phase 6 as completed",
    "scripts/auto_commit.py": "chore(scripts): update auto_commit for presentation aesthetic updates",
    # v9.1.0 Phase 5 Documentation Protocol & Phase 6 Certification
    ".planning/refactor_v910_v920/v9.1.0/02-typing-documentation-evidence.md": "docs(v9.1.0): record complete typing and docstring metrics",
    "src/personal_finance_etl/application/ingestion/asset_strategies.py": "docs(application): document asset ingestion pipelines",
    "src/personal_finance_etl/application/ingestion/coordinator.py": "docs(application): document DataExtractor.run method",
    "src/personal_finance_etl/application/ingestion/market_sync.py": "docs(application): document BenchmarkPipeline.process method",
    "src/personal_finance_etl/application/recovery/__init__.py": "refactor(application): add explicit __all__ export to recovery",
    "src/personal_finance_etl/config/financial_rules/fire.py": "docs(config): document stochastic and FIRE assumption models",
    "src/personal_finance_etl/config/financial_rules/household.py": "docs(config): document household financial rule models",
    "src/personal_finance_etl/config/financial_rules/investments.py": "docs(config): document investment and portfolio rule models",
    "src/personal_finance_etl/config/financial_rules/tax.py": "docs(config): document tax configuration models and validators",
    "src/personal_finance_etl/domain/__init__.py": "refactor(domain): add explicit __all__ export to domain root",
    "src/personal_finance_etl/domain/investments/valuation/benchmark.py": "docs(domain): document BenchmarkPriceProvider.get_bm_price method",
    "src/personal_finance_etl/infrastructure/__init__.py": "refactor(infrastructure): add explicit __all__ export to root",
    "src/personal_finance_etl/infrastructure/control_plane/file_sync.py": "docs(control_plane): document active_run_id setter in file sync",
    "src/personal_finance_etl/infrastructure/providers/__init__.py": "refactor(providers): add explicit __all__ export to providers root",
    "src/personal_finance_etl/infrastructure/providers/files/excel.py": "docs(providers): document Excel transaction extraction functions",
}

# Dedicated v9.2.0 Implementation Hardening Commit Messages
V920_COMMIT_MESSAGES: dict[str, str] = {
    # v9.2.0 Release Documentation, CI Quality & Badges
    "README.md": "docs(readme): add Codacy, CodeFactor, and CodeRabbit badges",
    ".codacy.yml": "ci(codacy): configure static analysis and quality engines",
    ".coderabbit.yaml": "ci(coderabbit): configure AI code review and path rules",
    ".flake8": "ci(codefactor): configure flake8 linter rules and exclusions",
    ".planning/refactor_v910_v920/RELEASE_NOTES_AND_PR_v9.1.0_v9.2.0.md": "docs(releases): add PR templates and release notes for v9.1 and v9.2",
    ".planning/refactor_v910_v920/00-HARDENING-PROGRAM-OVERVIEW.md": "docs(planning): update hardening program overview with release links",
    # Standalone Tool Configurations & Orchestration
    "pyproject.toml": "chore(build): configure standalone linters and audit tasks",
    "package.json": "chore(package): add audit and quality gate npm scripts",
    "uv.lock": "chore(deps): update uv lockfile for pylint and dev dependencies",
    "ruff.toml": "ci(ruff): configure standalone ruff with numpy docstring standards",
    "mypy.ini": "ci(mypy): configure standalone strict mypy type checking",
    "pyrightconfig.json": "ci(pyright): configure standalone pyright strict mode",
    "pyrefly.toml": "ci(pyrefly): configure standalone pyrefly type checker",
    "uv.toml": "ci(uv): configure standalone astral uv package manager",
    ".pylintrc": "ci(pylint): configure standalone pylint with 10/10 standard",
    "scripts/tasks.py": "chore(tasks): add audit tasks for two-tier quality gate",
    "scripts/create_releases.py": "fix(scripts): support utf-8 stdout encoding on windows",
    "poe_tasks.toml": "ci(poe): configure standalone poe tasks runner config",
    "scripts/quality_gate.py": "feat(ci): implement unified two-tier quality gate orchestrator",
    "scripts/install_hooks.py": "chore(scripts): add git pre-commit and pre-push hook installer",
    ".githooks/pre-commit": "ci(hooks): add fast tier pre-commit git hook",
    ".githooks/pre-push": "ci(hooks): add full tier pre-push git hook",
    "scripts/auto_commit.py": "chore(scripts): map v9.2.0 quality gate and audit files",
    # NumPy Docstrings & Strict Compliance Fixes
    "src/personal_finance_etl/application/investments/context.py": "docs(investments): add post-init docstring to investment context",
    "src/personal_finance_etl/application/pipeline/execution.py": "refactor(pipeline): fix iteration unpacking and date parsing",
    "src/personal_finance_etl/application/pipeline/lifecycle.py": "refactor(pipeline): type cast multiprocessing queue safely",
    "src/personal_finance_etl/contracts/logging.py": "docs(logging): standardize NullStatusQueue numpy docstring",
    "src/personal_finance_etl/contracts/recovery.py": "docs(contracts): standardize recovery contracts and magic docstrings",
    "src/personal_finance_etl/domain/common/dates.py": "refactor(dates): bound split count on date string parsing",
    "src/personal_finance_etl/domain/fire/simulation.py": "docs(fire): add numba simulation docstrings",
    "src/personal_finance_etl/domain/household/transforms/calendar.py": "docs(household): standardize calendar transforms to numpy docstrings",
    "src/personal_finance_etl/domain/household/transforms/common.py": "docs(household): standardize common transforms to numpy docstrings",
    "src/personal_finance_etl/domain/household/transforms/dimensions.py": "docs(household): standardize dimension transforms to numpy docstrings",
    "src/personal_finance_etl/domain/household/transforms/transactions.py": "docs(household): standardize transaction transforms to numpy docstrings",
    "src/personal_finance_etl/domain/investments/contracts.py": "docs(investments): standardize investment contract docstrings",
    "src/personal_finance_etl/domain/investments/lots/fifo.py": "docs(investments): standardize fifo lot portfolio docstrings",
    "src/personal_finance_etl/domain/investments/portfolio/aggregation.py": "docs(investments): standardize portfolio aggregation docstrings",
    "src/personal_finance_etl/domain/investments/transforms/common.py": "docs(investments): standardize common investment transform docstrings",
    "src/personal_finance_etl/domain/investments/transforms/indian_equity.py": "docs(investments): standardize indian equity transform docstrings",
    "src/personal_finance_etl/domain/investments/transforms/mutual_funds.py": "docs(investments): standardize mutual fund transform docstrings",
    "src/personal_finance_etl/domain/investments/transforms/us_equity.py": "docs(investments): standardize us equity transform docstrings",
    "src/personal_finance_etl/domain/investments/valuation/market_state.py": "docs(investments): standardize market state valuation docstrings",
    "src/personal_finance_etl/domain/market/benchmarks.py": "docs(market): standardize benchmark transform docstrings",
    "src/personal_finance_etl/domain/market/fx.py": "docs(market): standardize currency fx transform docstrings",
    "src/personal_finance_etl/domain/market/macro.py": "docs(market): standardize macro tax parameter docstrings",
    "src/personal_finance_etl/domain/tax/classification.py": "fix(tax): type annotate acquisition date in tax classifier",
    "src/personal_finance_etl/domain/tax/events.py": "docs(tax): standardize tax event builder docstrings",
    "src/personal_finance_etl/infrastructure/control_plane/run_repository.py": "docs(control_plane): standardize run repository docstrings",
    "src/personal_finance_etl/infrastructure/providers/files/excel.py": "docs(providers): standardize excel raw extraction docstrings",
    "src/personal_finance_etl/infrastructure/providers/files/locator.py": "docs(providers): standardize statement locator docstring",
    "src/personal_finance_etl/presentation/cli/app.py": "docs(cli): standardize rich terminal cli app docstrings",
    "src/personal_finance_etl/presentation/desktop/base_tab.py": "docs(desktop): standardize base tab helper docstrings",
    "src/personal_finance_etl/presentation/docs/guides_window.py": "docs(docs): standardize webview guides window docstrings",
}


def _infer_commit_message(filepath: str, status: str) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = filepath.replace("\\", "/")
    if norm in V920_COMMIT_MESSAGES:
        return V920_COMMIT_MESSAGES[norm]
    if norm in V910_COMMIT_MESSAGES:
        return V910_COMMIT_MESSAGES[norm]
    if norm in PHASE12_COMMIT_MESSAGES:
        return PHASE12_COMMIT_MESSAGES[norm]
    if norm in PHASE11_COMMIT_MESSAGES:
        return PHASE11_COMMIT_MESSAGES[norm]
    if norm in KNOWN_COMMIT_MESSAGES:
        return KNOWN_COMMIT_MESSAGES[norm]

    # Package __init__.py skeleton declaration
    if norm.endswith("__init__.py"):
        pkg_parts = norm.split("/")
        pkg_name = pkg_parts[-2] if len(pkg_parts) >= 2 else "root"
        return f"refactor(arch): initialize {pkg_name} package boundary"

    # Test files
    if norm.startswith("tests/"):
        stem = Path(norm).stem.replace("test_", "")
        return f"test({stem[:15]}): update test suite"

    # Legacy backend deactivations
    if "backend/" in norm:
        stem = Path(norm).stem
        return f"refactor(legacy): deactivate {stem} and delegate"

    # Target architectural packages
    if norm.startswith("src/personal_finance_etl/"):
        rel = norm.replace("src/personal_finance_etl/", "")
        parts = rel.split("/")
        layer = parts[0]
        name = Path(norm).stem
        msg = f"refactor({layer}): implement {name}"
        if len(msg) > 72:
            msg = msg[:72]
        return msg

    # Documentation
    if norm.endswith(".md"):
        stem = Path(norm).stem
        return f"docs: update {stem[:30]} documentation"

    # Generic fallback
    stem = Path(norm).stem
    action = "add" if "?" in status or "A" in status else "update"
    return f"chore: {action} {stem[:40]}"


def get_changed_files() -> list[tuple[str, str]]:
    """Return list of (status, filepath) for all uncommitted files."""
    proc = subprocess.run(
        ["git", "status", "-s", "-uall"],
        capture_output=True,
        text=True,
        check=True,
    )
    results: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        status_part = line[:2].strip()
        file_part = line[2:].strip().strip('"')
        results.append((status_part, file_part))
    return results


def run_git_commit(filepath: str, message: str, dry_run: bool = False) -> bool:
    """Stage a single file and create a git commit."""
    # Commitlint enforcement: header must be <= 72 characters, lowercase
    if len(message) > 72:
        print(f"ERROR: Commit message exceeds 72 characters ({len(message)} chars): '{message}'")
        return False

    norm_path = filepath.replace("/", "\\") if sys.platform == "win32" else filepath

    if dry_run:
        print(f"[DRY-RUN] git add {norm_path}")
        print(f'[DRY-RUN] git commit -m "{message}" (len: {len(message)})')
        return True

    # 1. git add
    add_proc = subprocess.run(["git", "add", norm_path], capture_output=True, text=True)
    if add_proc.returncode != 0:
        print(f"FAILED git add {norm_path}: {add_proc.stderr}")
        return False

    # 2. git commit
    commit_proc = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    if commit_proc.returncode != 0:
        print(f"FAILED git commit for {norm_path}: {commit_proc.stderr}")
        return False

    print(f'[OK] Committed {norm_path}: "{message}"')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit changes file-by-file following Commitlint standards."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview commits without executing git commands."
    )
    parser.add_argument("--run", action="store_true", help="Execute the commits immediately.")
    parser.add_argument("--file", type=str, help="Commit only a single specific file.")
    args = parser.parse_args()

    # Default to dry-run if neither --run nor --dry-run is passed
    is_dry_run = not args.run

    if args.file:
        files = [("M", args.file)]
    else:
        files = get_changed_files()

    if not files:
        print("Working tree is completely clean. Nothing to commit.")
        return 0

    mode_label = "DRY-RUN PREVIEW" if is_dry_run else "EXECUTING COMMITS"
    print(f"\n--- {mode_label} ({len(files)} files found) ---\n")

    success_count = 0
    fail_count = 0

    for status, filepath in files:
        message = _infer_commit_message(filepath, status)
        ok = run_git_commit(filepath, message, dry_run=is_dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\nDone: {success_count} succeeded, {fail_count} failed.")
    if is_dry_run:
        print("To execute these commits, run: uv run python scripts/auto_commit.py --run")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
