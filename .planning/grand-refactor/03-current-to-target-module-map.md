# Personal Finance ETL — Current → Target Module Map

> **Source:** v8.3.1 production package  
> **Purpose:** make the target architecture executable rather than aspirational.

## 1. Disposition vocabulary

| Disposition | Meaning |
| --- | --- |
| **KEEP** | Concept and location remain essentially valid. |
| **MOVE** | Responsibility is sound; relocate to correct owner. |
| **RENAME** | Responsibility remains but architectural name changes. |
| **SPLIT** | Current module owns multiple responsibilities; divide them. |
| **MERGE** | Several modules represent one target responsibility. |
| **REPLACE** | Preserve behavior through a better boundary/contract/package surface. |
| **RETIRE** | Remove after consumers migrate. |

## 2. Mapping

| Current module | Action | Target | Migration note |
| --- | --- | --- | --- |
| `__init__.py` | **REPLACE** | `__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `backend/__init__.py` | **REPLACE** | `(retire backend package)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/api/__init__.py` | **REPLACE** | `target package init based on migrated modules` | Package docs/public exports rewritten after child modules migrate. |
| `backend/api/engine.py` | **SPLIT** | `application/facade.py + bootstrap/container.py` | Keep PersonalFinanceEngine public façade; move concrete assembly to composition root; remove legacy tuple status compatibility. |
| `backend/config/financial_rules.py` | **SPLIT** | `config/financial_rules/{model,household,investments,tax,fire}.py` | Preserve one composed FinancialRules authority; split source by policy domain and add class documentation. |
| `backend/config/settings.py` | **SPLIT** | `config/settings.py + infrastructure/preferences/repository.py` | Keep Settings/FileHashPolicy in config; move PreferencesManager filesystem persistence to infrastructure. |
| `backend/engines/__init__.py` | **REPLACE** | `target package init based on migrated modules` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/__init__.py` | **REPLACE** | `domain/investments or application/investments package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/context.py` | **MOVE** | `application/investments/context.py` | Run-scoped analytics coordination context; remove UI-status concerns from domain. |
| `backend/engines/analytics/core/__init__.py` | **REPLACE** | `domain/investments or application/investments package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/core/fifo.py` | **MOVE** | `domain/investments/lots/fifo.py` | Preserve stateful domain object and behavior. |
| `backend/engines/analytics/core/math.py` | **SPLIT** | `domain/investments/performance/{returns,xirr}.py` | Keep pure calculations; move result types close to owning domain/common calculation primitives. |
| `backend/engines/analytics/engine.py` | **MOVE** | `application/investments/quant_service.py` | Application service coordinating investment-domain calculations. |
| `backend/engines/analytics/io/loader.py` | **REPLACE** | `application/investments/input_adapter.py / infrastructure warehouse reader` | Remove duplicate cleaning helpers; typed input adapter reads canonical warehouse outputs. |
| `backend/engines/analytics/isin_pipeline.py` | **SPLIT** | `application/investments/isin_service.py + contracts/application.py` | Decompose multiprocessing/orchestration and replace anonymous result dictionaries with named contracts. |
| `backend/engines/analytics/pipeline/__init__.py` | **REPLACE** | `domain/investments or application/investments package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/pipeline/context.py` | **SPLIT** | `domain/market/fx.py + application/investments/context.py` | Separate FX rate lookup/domain semantics from run context. |
| `backend/engines/analytics/pipeline/postprocessor/__init__.py` | **REPLACE** | `domain/investments or application/investments package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/pipeline/postprocessor/analytics.py` | **MOVE** | `domain/investments/portfolio/analytics.py` | Portfolio analytics calculations. |
| `backend/engines/analytics/pipeline/postprocessor/coordinator.py` | **SPLIT** | `application/investments/aggregation_service.py + domain/investments/portfolio/*` | Decompose 453-line coordinator into application sequence plus domain calculators. |
| `backend/engines/analytics/pipeline/postprocessor/gains.py` | **MOVE** | `domain/investments/performance/attribution.py` | Realized gains aggregation. |
| `backend/engines/analytics/pipeline/postprocessor/group_processor.py` | **MOVE** | `domain/investments/portfolio/aggregation.py` | Group aggregation by class/subtype/geography/etc. |
| `backend/engines/analytics/pipeline/postprocessor/harvest.py` | **MOVE** | `domain/investments/portfolio/analytics.py` | Tax-harvest analytical output; preserve current semantics. |
| `backend/engines/analytics/pipeline/postprocessor/weights.py` | **MOVE** | `domain/investments/portfolio/aggregation.py` | Portfolio weights calculation. |
| `backend/engines/analytics/pipeline/postprocessor/xirr.py` | **MOVE** | `domain/investments/performance/xirr.py` | Portfolio/group XIRR aggregation. |
| `backend/engines/analytics/pipeline/processor/__init__.py` | **REPLACE** | `domain/investments or application/investments package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/analytics/pipeline/processor/benchmark.py` | **MOVE** | `domain/investments/valuation/benchmark.py` | Benchmark valuation capability. |
| `backend/engines/analytics/pipeline/processor/extractor.py` | **MOVE** | `application/investments/input_adapter.py` | Adapts canonical tables into typed per-ISIN task inputs. |
| `backend/engines/analytics/pipeline/processor/fx_gate.py` | **MOVE** | `domain/investments/valuation/fx.py` | FX evidence validation/valuation policy; use typed domain errors. |
| `backend/engines/analytics/pipeline/processor/isin_processor.py` | **SPLIT** | `domain/investments/{lots,valuation,reconciliation,performance} + application/investments/isin_service.py` | Largest hotspot: extract cohesive financial steps while application service owns sequence. |
| `backend/engines/analytics/pipeline/processor/snapshot.py` | **MOVE** | `domain/investments/portfolio/snapshots.py` | Portfolio snapshot construction; decompose only if behaviorally useful. |
| `backend/engines/analytics/post_pipeline.py` | **MOVE** | `application/investments/aggregation_service.py` | Application coordination for post-ISIN portfolio aggregation. |
| `backend/engines/analytics/rules/macro.py` | **SPLIT** | `domain/market/macro.py + domain/tax/classification.py` | Macro table lookup remains market/reference domain; LTCG threshold policy belongs to Tax/investment tax classification. |
| `backend/engines/presentation/__init__.py` | **REPLACE** | `domain/{household,wealth,fire} or application/wealth package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/presentation/core/__init__.py` | **REPLACE** | `domain/{household,wealth,fire} or application/wealth package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/presentation/core/inflation_builder.py` | **MOVE** | `domain/fire/inflation.py` | Inflation planning calculation. |
| `backend/engines/presentation/core/ledger_builder.py` | **MOVE** | `domain/household/ledger.py` | Canonical household ledger modelling. |
| `backend/engines/presentation/core/net_worth_builder.py` | **SPLIT** | `domain/wealth/net_worth.py + domain/wealth/analytics.py` | Decompose 442-line builder into net-worth construction and derived analytics. |
| `backend/engines/presentation/helpers/fire_mc_sim.py` | **MOVE** | `domain/fire/simulation.py` | Preserve Numba kernel as documented complexity/performance exception. |
| `backend/engines/presentation/helpers/forecasting.py` | **MOVE** | `domain/fire/forecasting.py` | Current deterministic planning forecast helper; future ML remains separate post-refactor. |
| `backend/engines/presentation/helpers/scoring.py` | **MOVE** | `domain/wealth/scoring.py` | Deterministic financial health scoring. |
| `backend/engines/presentation/modules/budget_forecast.py` | **MOVE** | `domain/household/budget.py` | Current deterministic budget forecast. |
| `backend/engines/presentation/modules/cashflow_statement_builder.py` | **MOVE** | `domain/household/cashflow.py` | Merge cohesive cash-flow statement logic with cashflow domain module. |
| `backend/engines/presentation/modules/income_streams.py` | **MOVE** | `domain/household/income.py` | Income stream analytics. |
| `backend/engines/presentation/modules/investment_analytics.py` | **MOVE** | `domain/wealth/analytics.py` | Decision-facing investment contribution within household wealth context; consume investment public contracts. |
| `backend/engines/presentation/modules/monthly_cashflow_summary.py` | **MOVE** | `domain/household/cashflow.py` | Monthly cash-flow domain output. |
| `backend/engines/presentation/modules/spend_analytics.py` | **MOVE** | `domain/household/budget.py` | Spending analytics. |
| `backend/engines/presentation/modules/wealth_risk_analytics.py` | **SPLIT** | `domain/wealth/analytics.py + domain/fire/deterministic.py` | Separate current wealth/risk analytics from FI planning semantics. |
| `backend/engines/presentation/wealth_engine.py` | **MOVE** | `application/wealth/wealth_service.py` | Rename away from presentation; application service coordinates wealth/fire domain builders. |
| `backend/engines/tax/__init__.py` | **REPLACE** | `domain/tax or application/tax package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/tax/core/__init__.py` | **REPLACE** | `domain/tax or application/tax package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/tax/core/base_events.py` | **SPLIT** | `domain/tax/{events,classification,estimates}.py` | Separate event normalization, classification, estimates while preserving canonical TaxEvent semantics. |
| `backend/engines/tax/core/gold_formatter.py` | **SPLIT** | `domain/tax/reconciliation.py + application/tax/tax_service.py` | Domain reconciliation/calculation separate from publication-shaped formatting. |
| `backend/engines/tax/tax_engine.py` | **MOVE** | `application/tax/tax_service.py` | Application orchestration; domain Tax calculations move beneath it. |
| `backend/engines/tax/utils/__init__.py` | **REPLACE** | `domain/tax or application/tax package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/engines/tax/utils/date_utils.py` | **MOVE** | `domain/common/dates.py` | Generic financial-year/date helper. |
| `backend/extract/benchmark_extractor.py` | **SPLIT** | `infrastructure/providers/market/benchmark.py + application/ingestion/market_sync.py` | Provider acquisition in infrastructure; provenance/publication coordination in application. |
| `backend/extract/csv_extractor.py` | **SPLIT** | `infrastructure/providers/files/csv.py` | File-format parsing adapter; source-specific semantic mapping should remain outside infrastructure where applicable. |
| `backend/extract/currency_extractor.py` | **SPLIT** | `infrastructure/providers/market/currency.py + application/ingestion/market_sync.py` | Provider acquisition in infrastructure; Control Plane/publication coordination in application. |
| `backend/extract/excel_extractor.py` | **SPLIT** | `infrastructure/providers/files/excel.py` | Excel parsing adapter; retain strict source validation boundary. |
| `backend/extract/sqlite_extractor.py` | **MOVE** | `infrastructure/providers/files/sqlite.py` | External household SQLite source adapter. |
| `backend/extract/statement_locator.py` | **MOVE** | `infrastructure/providers/files/locator.py` | Filesystem/source discovery adapter. |
| `backend/extract/us_market_extractor.py` | **SPLIT** | `infrastructure/providers/market/us_market.py + application/ingestion/market_sync.py` | Provider acquisition in infrastructure; provenance/publication coordination in application. |
| `backend/load/backup.py` | **SPLIT** | `infrastructure/recovery/backup.py + contracts/recovery.py + application/recovery/snapshot_service.py` | Concrete archive mechanics in infrastructure; typed outcomes in contracts; use case coordination in application. |
| `backend/load/bronze.py` | **MOVE** | `infrastructure/warehouse/bronze.py` | Concrete Bronze persistence. |
| `backend/load/control_plane/__init__.py` | **REPLACE** | `infrastructure/control_plane/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `backend/load/control_plane/artifact_repo.py` | **MOVE** | `infrastructure/control_plane/artifact_repository.py` | Preserve repository ownership; improve docs/types. |
| `backend/load/control_plane/connection.py` | **MOVE** | `infrastructure/control_plane/connection.py` | Concrete SQLite manager. |
| `backend/load/control_plane/file_sync.py` | **MOVE** | `infrastructure/control_plane/file_sync.py` | Preserve synchronization service; expose narrow application capability. |
| `backend/load/control_plane/orchestrator.py` | **RENAME** | `infrastructure/control_plane/facade.py` | Current ControlPlane is an infrastructure façade, not application orchestrator. |
| `backend/load/control_plane/run_repo.py` | **MOVE** | `infrastructure/control_plane/run_repository.py` | Preserve repository ownership; improve docs/types. |
| `backend/load/control_plane/utils.py` | **SPLIT** | `infrastructure/control_plane/hashing.py + infrastructure/filesystem/paths.py` | Separate artifact hashing/ID support from generic path normalization. |
| `backend/load/database.py` | **MOVE** | `infrastructure/warehouse/connection.py` | Concrete DuckDB manager. |
| `backend/load/gold.py` | **MOVE** | `infrastructure/warehouse/gold.py` | Concrete Gold persistence. |
| `backend/load/metadata.py` | **MOVE** | `infrastructure/warehouse/meta.py` | Current analytical Meta projection. |
| `backend/load/registry.py` | **MOVE** | `infrastructure/warehouse/registry.py` | Warehouse physical publication contract registry. |
| `backend/load/schema/__init__.py` | **REPLACE** | `infrastructure/warehouse/schema/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `backend/load/schema/bronze.py` | **MOVE** | `infrastructure/warehouse/schema/bronze.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/schema/control_plane.py` | **MOVE** | `infrastructure/warehouse/schema/control_plane.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/schema/gold.py` | **MOVE** | `infrastructure/warehouse/schema/gold.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/schema/meta.py` | **MOVE** | `infrastructure/warehouse/schema/meta.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/schema/pragmas.py` | **MOVE** | `infrastructure/warehouse/schema/pragmas.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/schema/silver.py` | **MOVE** | `infrastructure/warehouse/schema/silver.py` | Declarative schema catalog; preserve as complexity exception and improve package docs. |
| `backend/load/silver.py` | **MOVE** | `infrastructure/warehouse/silver.py` | Concrete Silver persistence. |
| `backend/pipeline/benchmark_pipeline.py` | **MERGE** | `application/ingestion/market_sync.py` | Merge market evidence synchronization use cases behind one typed coordinator. |
| `backend/pipeline/core/extractor.py` | **SPLIT** | `application/ingestion/coordinator.py + infrastructure/providers/files/*` | Separate acquisition adapters from ingestion coordination. |
| `backend/pipeline/core/transformer.py` | **SPLIT** | `application/pipeline/execution.py + domain/*/transforms` | Transformation DAG coordination in application; semantic transforms remain in owning domains. |
| `backend/pipeline/currency_pipeline.py` | **MERGE** | `application/ingestion/market_sync.py` | Merge market evidence synchronization use cases behind one typed coordinator. |
| `backend/pipeline/etl_pipeline.py` | **SPLIT** | `application/pipeline/{orchestrator,execution,lifecycle,worker}.py` | Primary orchestration decomposition target; preserve commit/recovery state machine exactly. |
| `backend/pipeline/strategies.py` | **MOVE** | `application/ingestion/asset_strategies.py` | Asset-specific ingestion strategy coordination. |
| `backend/pipeline/us_market_pipeline.py` | **MERGE** | `application/ingestion/market_sync.py` | Merge market evidence synchronization use cases behind one typed coordinator. |
| `backend/transform/benchmark_transformer.py` | **MOVE** | `domain/market/benchmarks.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/calendar.py` | **MOVE** | `domain/household/transforms/calendar.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/currency_transformer.py` | **MOVE** | `domain/market/fx.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/dimensions.py` | **MOVE** | `domain/household/transforms/dimensions.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/facts.py` | **MOVE** | `domain/household/transforms/transactions.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/helpers.py` | **MOVE** | `domain/household/transforms/common.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/investments.py` | **MOVE** | `domain/investments/transforms/common.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/mutual_funds.py` | **MOVE** | `domain/investments/transforms/mutual_funds.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/stocks.py` | **MOVE** | `domain/investments/transforms/indian_equity.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/us_stocks.py` | **MOVE** | `domain/investments/transforms/us_equity.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/transform/us_stocks_transformer.py` | **MOVE** | `domain/investments/valuation/market_state.py` | Preserve functional Polars style; split only where source adaptation and financial semantics are currently mixed. |
| `backend/types/__init__.py` | **REPLACE** | `contracts/domain package init(s)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/types/analytics.py` | **SPLIT** | `domain/investments/contracts.py` | Finish replacing Any/dict seams with investment-domain records. |
| `backend/types/batch_result.py` | **MOVE** | `contracts/extraction.py` | Cross-boundary extraction outcomes. |
| `backend/types/calculation.py` | **SPLIT** | `domain/common/calculation.py + domain/investments/performance/contracts.py` | Shared status primitive plus domain-specific calculation results. |
| `backend/types/failure.py` | **MOVE** | `contracts/lifecycle.py` | Operational failure taxonomy. |
| `backend/types/fx.py` | **MOVE** | `domain/market/fx.py` | FX domain records. |
| `backend/types/pipeline.py` | **SPLIT** | `contracts/lifecycle.py + contracts/application.py + domain/investments/contracts.py` | CommitState is lifecycle; task/results split into application and investment-domain contracts. |
| `backend/types/presentation.py` | **RETIRE** | `application/wealth/wealth_service.py typed request/result contracts` | Empty placeholder config should be replaced by real typed service inputs or removed. |
| `backend/types/validation.py` | **MOVE** | `domain/common/validation.py` | Financial source validation error/semantics. |
| `backend/utils/__init__.py` | **REPLACE** | `(retire utils package; exports redistributed)` | Package docs/public exports rewritten after child modules migrate. |
| `backend/utils/helpers.py` | **SPLIT** | `domain/common/validation.py + infrastructure/filesystem/paths.py + domain/common/dates.py` | Separate strict financial parsing/date semantics from resource/cache filesystem helpers. |
| `backend/utils/identity.py` | **MOVE** | `domain/common/identity.py` | Deterministic identity is a domain-wide primitive; preserve serialization/version semantics exactly. |
| `backend/utils/interfaces.py` | **REPLACE** | `application/ports (consumer-owned narrow protocols)` | Replace ILogger/IDatabaseLoader broad legacy interfaces with narrow capabilities extracted from consumers. |
| `backend/utils/logger.py` | **MOVE** | `infrastructure/logging/setup.py` | Concrete logging/process handler infrastructure. |
| `backend/utils/models.py` | **SPLIT** | `contracts/{application,extraction}.py + domain/investments/lots/models.py + presentation contracts` | Move EngineStatus/LogLevel to cross-boundary contracts; TaxLot to investment domain; extraction results to application/extraction contracts; UI-only enums to presentation. |
| `backend/utils/ordering.py` | **MOVE** | `domain/investments/lots/ordering.py` | Purchase/sale chronological ordering is investment-domain policy. |
| `backend/utils/polars_expressions.py` | **MOVE** | `domain/common/polars.py` | Pure reusable analytical expressions; keep functional. |
| `backend/utils/reproducibility.py` | **SPLIT** | `domain/fire/reproducibility.py + infrastructure/warehouse/fingerprints.py` | Simulation replay belongs with FIRE; registry fingerprinting belongs with warehouse contracts. |
| `backend/utils/theme.py` | **MOVE** | `presentation/desktop/theme.py` | UI theme/log-tag presentation concern. |
| `frontend/__init__.py` | **REPLACE** | `presentation/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `frontend/cli/__init__.py` | **REPLACE** | `presentation/cli/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `frontend/cli/app.py` | **MOVE** | `presentation/cli/app.py` | CLI consumes application façade only. |
| `frontend/commons/__init__.py` | **REPLACE** | `(retire commons package)` | Package docs/public exports rewritten after child modules migrate. |
| `frontend/commons/docs/__init__.py` | **REPLACE** | `presentation/docs/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `frontend/commons/docs/guides_window.py` | **MOVE** | `presentation/docs/guides_window.py` | Packaged documentation UI belongs to presentation. |
| `frontend/commons/docs/manifest.py` | **MOVE** | `presentation/docs/manifest.py` | Packaged documentation UI belongs to presentation. |
| `frontend/commons/docs/renderer.py` | **MOVE** | `presentation/docs/renderer.py` | Packaged documentation UI belongs to presentation. |
| `frontend/desktop/__init__.py` | **REPLACE** | `presentation/desktop/__init__.py` | Package docs/public exports rewritten after child modules migrate. |
| `frontend/desktop/app.py` | **MOVE** | `presentation/desktop/app.py` | Desktop consumes typed application façade/status contracts. |
| `frontend/desktop/base_tab.py` | **MOVE** | `presentation/desktop/base_tab.py` | Desktop UI base abstraction. |
| `frontend/launcher.py` | **MOVE** | `presentation/launcher.py` | Human-facing entry point. |

## 3. Highest-risk migrations

### ETL orchestration

`backend/pipeline/etl_pipeline.py` is split only after typed lifecycle/repository capabilities exist. Preserve the v8.3.1 commit/recovery state machine exactly.

### Investment analytics

`isin_pipeline.py`, `IsinProcessor`, and `PostProcessor` are migrated contract-first. Existing named records are expanded until anonymous dictionaries disappear; only then are workflow responsibilities moved.

### Wealth builders

Large `build()` methods are decomposed by financial responsibility, not arbitrary line count. Gold outputs remain byte/semantic compatible at the contract level.

### Tax

Preserve the v8.3.1 FinancialRules → income-subcategory semantics, multiple exempt/residual categories, Tax credit separation, Quant realization ownership, and estimate-completeness semantics.

### Control Plane

Mostly move/polish rather than redesign. Repository behavior and operational authority remain intact.

## 4. Migration rule

> **A module is not considered migrated when its import path changes. It is migrated when ownership, contracts, dependencies, documentation, and behavior satisfy the Engineering Constitution.**
