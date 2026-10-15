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
    "src/personal_finance_etl/contracts/logging.py": "refactor(contracts): define LogLevel enum contract",
    "src/personal_finance_etl/contracts/extraction.py": "refactor(contracts): define extraction result and error contracts",
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): define snapshot and restore result contracts",
    "src/personal_finance_etl/contracts/application.py": "refactor(contracts): define engine execution and status contracts",
    "src/personal_finance_etl/domain/common/calculation.py": "refactor(domain/common): define financial calculation results",
    "src/personal_finance_etl/domain/common/validation.py": "refactor(domain/common): define validation exceptions and parsing",
    "src/personal_finance_etl/domain/market/fx.py": "refactor(domain/market): define FXObservation data contract",
    "src/personal_finance_etl/domain/investments/contracts.py": "refactor(domain/investments): define tax lot and realized records",
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
    "src/personal_finance_etl/config/settings.py": "refactor(config): implement Settings and FileHashPolicy models",
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
    # Phase 3 Infrastructure Contracts
    "src/personal_finance_etl/contracts/recovery.py": "refactor(contracts): update backup and restore result contracts",
    # Phase 3 Control Plane
    "src/personal_finance_etl/infrastructure/control_plane/__init__.py": "refactor(infrastructure): export control plane repositories",
    "src/personal_finance_etl/infrastructure/control_plane/connection.py": "refactor(infrastructure): implement SQLiteManager connection",
    "src/personal_finance_etl/infrastructure/control_plane/hashing.py": "refactor(infrastructure): implement hashing and file identity",
    "src/personal_finance_etl/infrastructure/control_plane/run_repository.py": "refactor(infrastructure): implement RunRepository lifecycle",
    "src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py": "refactor(infrastructure): implement ArtifactRepository store",
    "src/personal_finance_etl/infrastructure/control_plane/file_sync.py": "refactor(infrastructure): implement FileSyncService sync",
    "src/personal_finance_etl/infrastructure/control_plane/facade.py": "refactor(infrastructure): implement ControlPlane facade",
    # Phase 3 Warehouse Schemas
    "src/personal_finance_etl/infrastructure/warehouse/schema/__init__.py": "refactor(warehouse): export schema DDL statements and pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/pragmas.py": "refactor(warehouse): define SQLite and DuckDB pragmas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/control_plane.py": "refactor(warehouse): define raw control plane DDL",
    "src/personal_finance_etl/infrastructure/warehouse/schema/bronze.py": "refactor(warehouse): define bronze lakehouse DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/silver.py": "refactor(warehouse): define silver layer DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/gold.py": "refactor(warehouse): define gold presentation DDL schemas",
    "src/personal_finance_etl/infrastructure/warehouse/schema/meta.py": "refactor(warehouse): define meta telemetry DDL schemas",
    # Phase 3 Warehouse & Storage
    "src/personal_finance_etl/infrastructure/warehouse/__init__.py": "refactor(warehouse): export warehouse layers and registry",
    "src/personal_finance_etl/infrastructure/warehouse/connection.py": "refactor(warehouse): implement DuckDBManager connection",
    "src/personal_finance_etl/infrastructure/warehouse/registry.py": "refactor(warehouse): implement data contract registries",
    "src/personal_finance_etl/infrastructure/warehouse/fingerprints.py": "refactor(warehouse): implement contract registry fingerprinting",
    "src/personal_finance_etl/infrastructure/warehouse/bronze.py": "refactor(warehouse): implement BronzeLayer delta upserts",
    "src/personal_finance_etl/infrastructure/warehouse/silver.py": "refactor(warehouse): implement SilverLayer table persistence",
    "src/personal_finance_etl/infrastructure/warehouse/gold.py": "refactor(warehouse): implement GoldLayer analytical tables",
    "src/personal_finance_etl/infrastructure/warehouse/meta.py": "refactor(warehouse): implement MetaLayer telemetry and healing",
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
    # Phase 4 Ingestion Contracts
    "src/personal_finance_etl/contracts/logging.py": "refactor(contracts): define StatusQueue cross-process protocol",
    "src/personal_finance_etl/contracts/__init__.py": "refactor(contracts): export StatusQueue protocol",
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
    "src/personal_finance_etl/domain/investments/lots/__init__.py": "refactor(domain): export investments lot ordering policy",
    "src/personal_finance_etl/domain/investments/transforms/common.py": "feat(domain): implement investment reference transformations",
    "src/personal_finance_etl/domain/investments/transforms/indian_equity.py": "feat(domain): implement Indian equity trade transformations",
    "src/personal_finance_etl/domain/investments/transforms/mutual_funds.py": "feat(domain): implement mutual fund trade transformations",
    "src/personal_finance_etl/domain/investments/transforms/us_equity.py": "feat(domain): implement US equity trade transformations",
    "src/personal_finance_etl/domain/investments/valuation/market_state.py": "feat(domain): implement US stock FIFO market valuation spine",
    "src/personal_finance_etl/domain/investments/transforms/__init__.py": "refactor(domain): export canonical investment transformations",
    "src/personal_finance_etl/domain/investments/valuation/__init__.py": "refactor(domain): export investment valuation models",
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
    # Phase 5: Application Ingestion Updates
    "src/personal_finance_etl/application/ingestion/coordinator.py": "refactor(application): import helpers from canonical domain",
    "src/personal_finance_etl/application/ingestion/asset_strategies.py": "refactor(application): import strategies from canonical domain",
    "src/personal_finance_etl/application/ingestion/market_sync.py": "refactor(application): import market sync from canonical domain",
    # Phase 5: Verification Suite
    "tests/test_phase5_canonical_domains.py": "test(domain): add Phase 5 canonical domain test suite",
    # Phase 6A: Investment Contracts & Typed Models
    "src/personal_finance_etl/domain/investments/contracts.py": "refactor(investments): define investment contracts and typed models",
    "src/personal_finance_etl/domain/investments/lots/models.py": "feat(investments): define TaxLot AcquisitionLot and LotAction",
    "src/personal_finance_etl/domain/investments/reconciliation/models.py": "feat(investments): define ReconciliationEvent typed model",
    "src/personal_finance_etl/domain/investments/reconciliation/__init__.py": "refactor(investments): export reconciliation models",
    "src/personal_finance_etl/domain/investments/__init__.py": "refactor(investments): export investment models and services",
    "src/personal_finance_etl/backend/types/analytics.py": "refactor(legacy): deactivate analytics types and delegate",
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
    "src/personal_finance_etl/application/investments/context.py": "feat(investments): implement RunContext and AnalyticsContextManager",
    "src/personal_finance_etl/application/investments/isin_service.py": "feat(investments): implement IsinProcessor and IsinPipeline",
    "src/personal_finance_etl/application/investments/aggregation_service.py": "feat(investments): implement PostProcessor and PostProcessingPipeline",
    "src/personal_finance_etl/application/investments/quant_service.py": "feat(investments): implement InvestmentQuantEngine and QuantService",
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
    "src/personal_finance_etl/backend/pipeline/etl_pipeline.py": "refactor(backend/pipeline): update TaxEngine import to application",
    "tests/test_phase7_tax_domain.py": "test(domain/tax): add Phase 7 tax domain and service test suite",
    # Scripts & Tooling
    "scripts/auto_commit.py": "chore(scripts): update auto_commit tool with Phase 7 mappings",
}


def _infer_commit_message(filepath: str, status: str) -> str:
    """Infer a Commitlint-compliant message (max 72 chars) based on path heuristics."""
    norm = filepath.replace("\\", "/")
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
        print(f"[DRY-RUN] git commit -m \"{message}\" (len: {len(message)})")
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

    print(f"[OK] Committed {norm_path}: \"{message}\"")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit changes file-by-file following Commitlint standards.")
    parser.add_argument("--dry-run", action="store_true", help="Preview commits without executing git commands.")
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

