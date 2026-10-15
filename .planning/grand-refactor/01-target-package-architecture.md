# Personal Finance ETL — Target Package Architecture

> **Status:** Grand Refactor target design  
> **Behavioral reference:** v8.3.1  
> **Governing standard:** `personal_finance_etl_ENGINEERING_CONSTITUTION.md`

## 1. Design intent

The target architecture makes existing ownership explicit. It is **not** a textbook Clean Architecture transplant and it does not change financial behavior.

The current `backend/` umbrella is retired because it contains domain logic, application orchestration, contracts, infrastructure, persistence, and utilities. The target promotes those responsibilities into first-class packages.

```text
personal_finance_etl/
├── application/       # use cases, orchestration, façade, lifecycle coordination
├── bootstrap/         # composition root: concrete dependency assembly
├── config/            # validated runtime settings + financial policy
├── contracts/         # true cross-boundary commands/results/messages only
├── domain/            # financial meaning, algorithms, canonical semantic transforms
├── infrastructure/    # providers, SQLite/DuckDB, filesystem, logging, recovery
└── presentation/      # CLI, Desktop, packaged-doc UI
```

The rule is simple:

> **Domain says what the finance means. Application says what the system does. Infrastructure says how external state is acquired or persisted. Presentation says how a human invokes it.**

## 2. Proposed package tree

```text
src/personal_finance_etl/
├── __init__.py
│
├── application/
│   ├── __init__.py
│   ├── facade.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── execution.py
│   │   ├── lifecycle.py
│   │   └── worker.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── coordinator.py
│   │   ├── discovery.py
│   │   ├── asset_strategies.py
│   │   └── market_sync.py
│   ├── investments/
│   │   ├── __init__.py
│   │   ├── quant_service.py
│   │   ├── isin_service.py
│   │   └── aggregation_service.py
│   ├── tax/
│   │   ├── __init__.py
│   │   └── tax_service.py
│   ├── wealth/
│   │   ├── __init__.py
│   │   └── wealth_service.py
│   └── recovery/
│       ├── __init__.py
│       ├── recovery_service.py
│       └── snapshot_service.py
│
├── bootstrap/
│   ├── __init__.py
│   └── container.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── financial_rules/
│       ├── __init__.py
│       ├── model.py
│       ├── household.py
│       ├── investments.py
│       ├── tax.py
│       └── fire.py
│
├── contracts/
│   ├── __init__.py
│   ├── application.py
│   ├── extraction.py
│   ├── lifecycle.py
│   ├── recovery.py
│   └── logging.py
│
├── domain/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── calculation.py
│   │   ├── identity.py
│   │   ├── ordering.py
│   │   ├── validation.py
│   │   └── polars.py
│   ├── household/
│   │   ├── __init__.py
│   │   ├── transforms/
│   │   │   ├── calendar.py
│   │   │   ├── dimensions.py
│   │   │   └── transactions.py
│   │   ├── ledger.py
│   │   ├── cashflow.py
│   │   ├── budget.py
│   │   └── income.py
│   ├── market/
│   │   ├── __init__.py
│   │   ├── fx.py
│   │   ├── benchmarks.py
│   │   └── macro.py
│   ├── investments/
│   │   ├── __init__.py
│   │   ├── contracts.py
│   │   ├── transforms/
│   │   │   ├── common.py
│   │   │   ├── mutual_funds.py
│   │   │   ├── indian_equity.py
│   │   │   └── us_equity.py
│   │   ├── lots/
│   │   │   ├── fifo.py
│   │   │   └── models.py
│   │   ├── valuation/
│   │   │   ├── market_state.py
│   │   │   ├── benchmark.py
│   │   │   └── fx.py
│   │   ├── performance/
│   │   │   ├── returns.py
│   │   │   ├── xirr.py
│   │   │   └── attribution.py
│   │   ├── reconciliation/
│   │   │   ├── engine.py
│   │   │   └── models.py
│   │   └── portfolio/
│   │       ├── snapshots.py
│   │       ├── aggregation.py
│   │       └── analytics.py
│   ├── tax/
│   │   ├── __init__.py
│   │   ├── contracts.py
│   │   ├── events.py
│   │   ├── classification.py
│   │   ├── estimates.py
│   │   └── reconciliation.py
│   ├── wealth/
│   │   ├── __init__.py
│   │   ├── net_worth.py
│   │   ├── analytics.py
│   │   └── scoring.py
│   └── fire/
│       ├── __init__.py
│       ├── deterministic.py
│       ├── simulation.py
│       ├── inflation.py
│       └── forecasting.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── control_plane/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── run_repository.py
│   │   ├── artifact_repository.py
│   │   ├── file_sync.py
│   │   └── facade.py
│   ├── warehouse/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── registry.py
│   │   ├── bronze.py
│   │   ├── silver.py
│   │   ├── gold.py
│   │   ├── meta.py
│   │   └── schema/
│   │       ├── bronze.py
│   │       ├── silver.py
│   │       ├── gold.py
│   │       ├── meta.py
│   │       ├── control_plane.py
│   │       └── pragmas.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── files/
│   │   │   ├── csv.py
│   │   │   ├── excel.py
│   │   │   ├── sqlite.py
│   │   │   └── locator.py
│   │   └── market/
│   │       ├── currency.py
│   │       ├── benchmark.py
│   │       └── us_market.py
│   ├── recovery/
│   │   ├── __init__.py
│   │   └── backup.py
│   ├── preferences/
│   │   ├── __init__.py
│   │   └── repository.py
│   ├── logging/
│   │   ├── __init__.py
│   │   └── setup.py
│   └── filesystem/
│       ├── __init__.py
│       └── paths.py
│
└── presentation/
    ├── __init__.py
    ├── launcher.py
    ├── cli/
    │   └── app.py
    ├── desktop/
    │   ├── app.py
    │   ├── base_tab.py
    │   └── theme.py
    └── docs/
        ├── manifest.py
        ├── renderer.py
        └── guides_window.py
```

This is a **target ownership model**, not a demand to create empty files before behavior moves into them. Files appear only when a migrated responsibility earns them.

## 3. Package ownership

### `domain/`

Owns financial meaning and deterministic financial algorithms. It MUST NOT know SQLite, DuckDB, Tkinter, filesystem paths, provider SDKs, or CLI rendering.

Domain subpackages are financial concepts, not technical layers. This is where future finance features attach.

### `application/`

Owns use cases and coordination: run the ETL, synchronize evidence, execute Quant, build Tax/wealth outputs, coordinate recovery, and expose a stable façade. It does not own storage implementations or financial formulas.

### `infrastructure/`

Owns concrete external state: Control Plane SQLite, DuckDB warehouse, files, market providers, snapshots, preferences, logging, and filesystem behavior.

### `contracts/`

Owns only messages/results that genuinely cross architectural boundaries: application status, extraction batch outcomes, commit/recovery state, snapshot/restore outcomes, logging messages. Domain-native records do **not** migrate here merely because they are typed.

### `config/`

Owns validated runtime configuration and financial policy. `FinancialRules` remains authoritative, but its current monolithic source file is split by policy domain while preserving one composed `FinancialRules` model.

### `presentation/`

Reserved exclusively for human-facing surfaces. The current `backend.engines.presentation` name disappears; those modules are financial domains, not UI presentation.

### `bootstrap/`

Owns concrete dependency assembly. It is the composition root where protocols meet SQLite/DuckDB/provider implementations. Domain/application code does not instantiate concrete infrastructure deep inside workflows.

## 4. Important public surfaces

The target should expose a small number of stable package surfaces:

```text
personal_finance_etl.application.PersonalFinanceEngine
personal_finance_etl.config.Settings
personal_finance_etl.config.FinancialRules
personal_finance_etl.domain.investments   # intentional domain exports
personal_finance_etl.domain.tax
personal_finance_etl.domain.wealth
personal_finance_etl.domain.fire
```

Infrastructure internals are not public product API merely because Python can import them.

## 5. Current strengths deliberately preserved

- Functional Polars transforms remain functional.
- `FIFOPortfolio` remains an invariant-rich stateful object.
- Control Plane repository/service decomposition is retained.
- Warehouse registry remains the publication authority.
- Numba Monte Carlo remains a specialized numerical kernel.
- `PersonalFinanceEngine` remains conceptually the presentation-facing façade.
- FinancialRules remains the policy authority.

## 6. Major structural changes

1. Retire the `backend/` umbrella.
2. Reserve `presentation/` for actual UI.
3. Break the `utils` gravity well by ownership.
4. Split provider adapters from ingestion/application coordination.
5. Move DuckDB/SQLite persistence into explicit infrastructure packages.
6. Move financial engines/builders into financial domains.
7. Finish typed investment contracts instead of anonymous dictionaries.
8. Introduce a composition root rather than constructing concrete dependencies inside orchestration.
9. Split the FinancialRules source by policy domain without splitting policy authority.
10. Decompose giant workflow methods without changing outputs.

## 7. Future finance / ML attachment points

The target intentionally leaves clean extension seams:

```text
Cash / spending ML      → domain.household + future application analytics use cases
Goal planning           → domain.wealth / domain.fire
Portfolio risk ML       → consume domain.investments portfolio/performance contracts
Tax cash forecasting    → consume domain.tax canonical outputs
FIRE ML                 → consume domain.fire scenario/simulation contracts
AI explanation          → application read-only query layer over canonical outputs
```

ML MUST NOT import persistence internals or mutate canonical finance. Future model infrastructure can be introduced later under a dedicated infrastructure/modeling adapter if a real need emerges; no empty `ml/` package is created during this refactor.

## 8. Non-goals

The target architecture does not:

- change financial behavior;
- introduce cloud infrastructure;
- create repositories/interfaces for every function;
- convert pure transforms into classes;
- split numerical kernels for line-count aesthetics;
- add future finance/ML features during migration;
- create empty architecture folders simply to match the diagram.

## 9. Target outcome

The package tree should make this question answerable from the path alone:

> **Is this financial meaning, application coordination, external infrastructure, cross-boundary contract, configuration policy, or human presentation?**

If the path cannot answer that, the architecture has not finished its job.
