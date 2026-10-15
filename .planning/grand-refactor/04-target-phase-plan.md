# Personal Finance ETL --- Grand Refactor Implementation Plan

> **Purpose:** phase-by-phase implementation guide for the Grand
> Refactor\
> **Governing documents:** Engineering Constitution, Target Package
> Architecture, Target Dependency Model, Current-to-Target Module Map\
> **Primary rule:** structural creativity is unlimited; financial
> behavior is frozen.

------------------------------------------------------------------------

# 1. Refactor objective

The Grand Refactor should preserve the complete behavior of v8.3.1 while
taking the internal engineering standard to a substantially higher
level.

The target is:

``` text
same financial truth
same outputs
same functionality
        ↓
clear package ownership
typed contracts
smaller workflows
explicit dependencies
strong OOP where state exists
functional transforms where appropriate
documented public APIs
intentional Polars boundaries
clean application orchestration
```

This is not a feature release.

Do not add finance features, ML, AI, new financial formulas, or
unrelated optimizations during the refactor.

If an output changes, stop and determine why before continuing.

------------------------------------------------------------------------

# 2. Golden behavioral rule

At the end of every phase ask:

``` text
Does the application still represent
the same financial state as v8.3.1?

YES → continue
NO  → stop and investigate
```

The following are frozen unless changed through a separately approved
functional change:

-   deterministic identities;
-   source validation;
-   Bronze synchronization;
-   canonical transformations;
-   FIFO;
-   realized events;
-   reconciliation;
-   XIRR / CAGR semantics;
-   benchmarks;
-   FX;
-   Tax;
-   household finance;
-   cash flow;
-   wealth;
-   FIRE / Monte Carlo;
-   warehouse contract meaning and grain;
-   Control Plane lifecycle;
-   recovery;
-   CLI/Desktop behavior.

------------------------------------------------------------------------

# 3. Overall implementation order

``` text
PHASE 0   Prepare the architecture
    ↓
PHASE 1   Typed contracts
    ↓
PHASE 2   Configuration + common primitives
    ↓
PHASE 3   Infrastructure
    ↓
PHASE 4   Extraction / ingestion
    ↓
PHASE 5   Canonical financial domains
    ↓
PHASE 6   Investment / Quant
    ↓
PHASE 7   Tax
    ↓
PHASE 8   Household analytics / Wealth / FIRE
    ↓
PHASE 9   Application orchestration + bootstrap
    ↓
PHASE 10  CLI / Desktop / Docs
    ↓
PHASE 11  Remove legacy architecture
    ↓
PHASE 12  Final architecture certification
```

Commit after meaningful sub-phases rather than waiting for one enormous
phase to finish.

------------------------------------------------------------------------

# 4. Phase 0 --- Prepare the architecture

## Goal

Create the target architectural skeleton without moving production
financial logic.

## Target packages

``` text
personal_finance_etl/
├── application/
├── bootstrap/
├── config/
├── contracts/
├── domain/
│   ├── common/
│   ├── household/
│   ├── market/
│   ├── investments/
│   ├── tax/
│   ├── wealth/
│   └── fire/
├── infrastructure/
│   ├── control_plane/
│   ├── warehouse/
│   ├── providers/
│   ├── recovery/
│   ├── preferences/
│   ├── logging/
│   └── filesystem/
└── presentation/
    ├── cli/
    ├── desktop/
    └── docs/
```

## Work

-   create packages;
-   document ownership in each meaningful `__init__.py`;
-   establish architecture-boundary checks;
-   create an architecture-exception register;
-   reserve the composition root;
-   keep existing production execution unchanged.

## Do not

-   move finance algorithms;
-   change imports simply for appearance;
-   change CLI/Desktop behavior;
-   create a second working bootstrap.

## Exit gate

-   package structure exists;
-   ownership documentation exists;
-   architecture rules are enforceable;
-   existing application behavior is unchanged.

------------------------------------------------------------------------

# 5. Phase 1 --- Typed contracts

## Goal

Make major boundaries understandable before moving implementations.

This phase should substantially reduce anonymous dictionaries, tuples,
and unexplained `Any`.

## 1A --- Operational contracts

Formalize/move:

``` text
EngineStatus
ExtractionBatchResult
ExtractorEntityResult
ExtractorEntityStatus
CommitState
FailureDomain
SnapshotResult
RestoreResult
SnapshotOutcome
RestoreOutcome
```

Cross-process messages must become named contracts.

Remove the final architecture's dependence on:

``` python
tuple[str, Any | None, float | None]
```

Do not infer state from message text.

## 1B --- Investment contracts

Formalize:

``` text
CashflowRecord
TerminalValueRecord
RealizedEventRecord
ReconciliationEventRecord
SnapshotRecord
ISINProcessResult
PipelineExecutionResult
```

Replace stable structures such as:

``` python
dict[str, Any]
list[dict[str, Any]]
dict[str, list[dict[str, Any]]]
```

where their shape is already known.

## Important

Do not refactor Quant algorithms yet.

First make their boundaries explicit.

## Exit gate

Major application and Quant boundaries can be understood from type
definitions without reverse-engineering dictionary keys.

------------------------------------------------------------------------

# 6. Phase 2 --- Configuration and common primitives

## Goal

Clean the foundations used by many domains.

## 2A --- FinancialRules

Split the large policy module by domain:

``` text
config/financial_rules/
├── household.py
├── investments.py
├── tax.py
├── fire.py
└── model.py
```

Keep `FinancialRules` as the composed authoritative policy model.

Preserve every:

-   field;
-   default;
-   validator;
-   serialization behavior;
-   Tax sub-head;
-   exempt category;
-   residual-income category.

## 2B --- Runtime settings

Keep runtime configuration in `config/settings.py`.

Move preference persistence out of configuration.

## 2C --- Common domain primitives

Move concepts such as:

-   deterministic identity;
-   financial source validation;
-   truly cross-domain calculation semantics;
-   genuinely shared domain expressions;

into deliberate homes.

## Rule

Do not replace `utils` with `domain/common/everything.py`.

An item belongs in common only when multiple real domains legitimately
own/use the abstraction.

## Exit gate

-   FinancialRules behavior unchanged;
-   fingerprints/serialization unchanged;
-   deterministic IDs unchanged;
-   validation unchanged;
-   major domain primitives no longer depend on the old utility gravity
    well.

------------------------------------------------------------------------

# 7. Phase 3 --- Infrastructure

## Goal

Give persistence, providers, recovery, filesystem, logging, and
preferences explicit ownership.

## 3A --- Control Plane

Move the existing architecture largely intact:

``` text
RunRepository
ArtifactRepository
FileSyncService
ControlPlane
SQLiteManager
```

into:

``` text
infrastructure/control_plane/
```

Improve typing, documentation, and dependency boundaries.

Do not redesign healthy behavior simply because the files moved.

## 3B --- Warehouse

Move:

``` text
database
bronze
silver
gold
metadata
registry
schema/*
```

under:

``` text
infrastructure/warehouse/
```

Keep schema catalogs declarative.

Split only when ownership/discoverability improves.

## 3C --- Recovery

Move:

``` text
snapshot
restore
backup
locking
```

under:

``` text
infrastructure/recovery/
```

## 3D --- Supporting infrastructure

Move genuine concerns into:

``` text
infrastructure/logging/
infrastructure/filesystem/
infrastructure/preferences/
```

## Exit gate

-   SQLite Control Plane behavior unchanged;
-   DuckDB contracts unchanged;
-   snapshot/restore unchanged;
-   domain code does not know concrete persistence implementations.

------------------------------------------------------------------------

# 8. Phase 4 --- Extraction and ingestion

## Goal

Separate evidence acquisition from application policy.

Ask two different questions:

``` text
HOW is evidence fetched?
```

and:

``` text
WHAT should the application do with it?
```

## Provider layer

External/file-specific mechanics belong under infrastructure providers.

Examples:

``` text
files
currency
benchmark
US market
```

Providers return typed extraction outcomes.

## Application ingestion

Application services own:

``` text
request provider
    ↓
evaluate completeness
    ↓
record provenance
    ↓
construct/inject evidence
    ↓
synchronize Bronze
```

## Preserve

-   retries;
-   caching;
-   completeness;
-   virtual artifacts;
-   hashes;
-   rename/removal behavior;
-   provider provenance.

## Exit gate

The same evidence becomes actionable and reaches Bronze as under v8.3.1.

------------------------------------------------------------------------

# 9. Phase 5 --- Canonical financial domains

## Goal

Move the healthiest functional transformations into proper financial
ownership before touching Quant.

## Household

Move canonical semantics for:

-   income;
-   expenses;
-   transfers;
-   household ledger;
-   assets;
-   liabilities;
-   cash-flow classification.

## Market

Move canonical semantics for:

-   currency;
-   FX;
-   benchmarks;
-   market/reference state.

## Investments

Move source-independent canonical investment transforms where
appropriate.

## Important rule

Do not OOP-ify good Polars transforms.

If a transformation is naturally:

``` text
LazyFrame → deterministic financial transformation → LazyFrame
```

a function is probably the correct abstraction.

## Exit gate

Canonical outputs and deterministic identities remain unchanged.

------------------------------------------------------------------------

# 10. Phase 6 --- Investment / Quant

> **Highest financial-risk phase. Do not implement as one giant
> rewrite.**

Treat each sub-phase as a separate refactor milestone.

------------------------------------------------------------------------

## Phase 6A --- Finish investment contracts

Remove remaining anonymous stable financial structures from major Quant
boundaries.

Target named concepts:

``` text
AcquisitionLot
Purchase
Sale
RealizedEvent
ReconciliationEvent
CashflowRecord
TerminalValueRecord
SnapshotRecord
ISINProcessResult
PortfolioResult
```

------------------------------------------------------------------------

## Phase 6B --- FIFO / lot accounting

Move:

``` text
FIFOPortfolio
TaxLot / acquisition-lot models
purchase/sale lot behavior
```

into:

``` text
domain/investments/lots/
```

### Rule

Do not improve FIFO while moving it.

Move it, type it, document it, prove it.

------------------------------------------------------------------------

## Phase 6C --- Valuation and market context

Extract from the giant ISIN workflow:

-   historical market state;
-   prices;
-   benchmark context;
-   FX context;
-   valuation state.

Give each cohesive responsibility a clear home.

------------------------------------------------------------------------

## Phase 6D --- Performance

Separate:

``` text
XIRR
CAGR
returns
benchmark comparison
FX attribution
portfolio/group performance
```

into explicit performance modules.

Preserve calculation validity semantics.

------------------------------------------------------------------------

## Phase 6E --- Reconciliation

Move:

``` text
quantity reconciliation
basis reconciliation
reconciliation events
```

into:

``` text
domain/investments/reconciliation/
```

Observed and reconstructed evidence must remain separately traceable.

------------------------------------------------------------------------

## Phase 6F --- Decompose `IsinProcessor.process()`

Only attack the current \~673-line workflow after the domain
responsibilities above have somewhere to go.

Target shape:

``` text
prepare instrument
      ↓
build lot state
      ↓
construct valuation
      ↓
reconcile
      ↓
calculate performance
      ↓
return typed ISINProcessResult
```

The application service owns **sequence**.

The domain owns **financial behavior**.

------------------------------------------------------------------------

## Phase 6G --- Portfolio aggregation

Finally decompose:

``` text
IsinPipeline.process_all()
PostProcessor.run()
```

around typed results and explicit aggregation responsibilities.

## Phase 6 exit gate

Compare directly with v8.3.1:

-   deterministic IDs;
-   lots;
-   realized events;
-   reconciliation events;
-   snapshots;
-   XIRR;
-   CAGR;
-   benchmark results;
-   FX attribution;
-   portfolio/group aggregates.

Do not proceed if Quant differs unexpectedly.

------------------------------------------------------------------------

# 11. Phase 7 --- Tax

## Goal

Give Tax explicit domain/application ownership while preserving v8.3.1
semantics exactly.

Possible target:

``` text
domain/tax/
├── contracts.py
├── events.py
├── classification.py
├── estimates.py
└── reconciliation.py

application/tax/
└── tax_service.py
```

## Preserve

``` text
FinancialRules
      ↓
Income Subcategory Master
      ↓
ledger Tax classification
```

and:

``` text
Quant realized events
      ↓
TaxEvents
```

Preserve:

-   Tax sub-head semantics;
-   multiple exempt categories;
-   residual income;
-   Tax credits;
-   `CHECK_REQUIRED`;
-   estimate completeness;
-   Tax event identities.

## Rule

Tax consumes Quant realization.

Tax never reaches into FIFO internals to recreate it.

## Exit gate

TaxEvents, estimates, classifications, reconciliation, and Gold Tax
outputs match the behavioral baseline.

------------------------------------------------------------------------

# 12. Phase 8 --- Household analytics, Wealth and FIRE

## Goal

Decompose the giant analytical builders by actual financial
responsibility.

Review:

``` text
NetWorthBuilder
CashflowStatementBuilder
MonthlyCashflowSummaryBuilder
IncomeStreamsBuilder
SpendAnalyticsBuilder
BudgetForecastBuilder
InvestmentAnalyticsBuilder
WealthRiskAnalyticsBuilder
```

Do not split by line count alone.

Look for:

``` text
input preparation
calculation
aggregation
reconciliation
output construction
```

and separate only genuinely independent responsibilities.

## FIRE

Separate:

``` text
deterministic FI
simulation inputs
simulation orchestration
Monte Carlo kernel
simulation outputs
provenance/reproducibility
```

## Numba exception

If `_run_mc_simulations_numba()` needs to remain large for
compilation/performance/mathematical readability, keep it large.

Document why.

Do not manufacture abstractions around a hot numerical kernel merely to
satisfy a line-count guideline.

## Exit gate

Preserve:

-   net worth;
-   cash flow;
-   budget;
-   income/spend analytics;
-   deterministic FI;
-   stochastic outputs under documented replay semantics.

------------------------------------------------------------------------

# 13. Phase 9 --- Application orchestration and bootstrap

## Goal

Only after the lower layers are stable, refactor the whole-system
workflow.

## Decompose `ETLOrchestrator.run()`

Separate responsibilities such as:

``` text
high-level orchestration
execution
run lifecycle
commit/recovery lifecycle
publication
worker coordination
```

The orchestrator should become readable because the actual work has
already moved behind cohesive capabilities.

## Composition root

Implement:

``` text
bootstrap/container.py
```

as the one place where concrete dependencies are assembled.

Conceptually:

``` text
Settings / FinancialRules
        ↓
SQLite / DuckDB
providers
repositories
domain/application services
        ↓
PersonalFinanceEngine
```

## Application façade

Keep `PersonalFinanceEngine` as the stable presentation-facing façade.

## Exit gate

-   same pipeline order where behavior depends on it;
-   same transaction/commit/recovery behavior;
-   one composition root;
-   no uncontrolled concrete dependency fan-out from orchestration.

------------------------------------------------------------------------

# 14. Phase 10 --- CLI, Desktop and Docs

## Goal

Move presentation only after the application façade is stable.

Target:

``` text
presentation/
├── cli/
├── desktop/
└── docs/
```

## Remove legacy process contracts

Delete support for anonymous status tuples and display-text inference.

Presentation should consume:

``` text
EngineStatus
PipelineResult
SnapshotResult
RestoreResult
```

directly.

## Snapshot/restore

This is the right phase to expose detailed backend snapshot/restore
outcomes in CLI/Desktop.

## Docs renderer

Move/refactor docs rendering without changing user-visible behavior.

The giant renderer can be decomposed structurally, but documentation
rendering is not allowed to become a domain concern.

## Exit gate

Preserve:

-   commands;
-   Desktop workflows;
-   configuration/rules selection;
-   unattended/cron behavior;
-   docs access;
-   user-visible functional behavior.

------------------------------------------------------------------------

# 15. Phase 11 --- Remove legacy architecture

> **The satisfying demolition phase.**

Search for:

``` text
backend.
frontend.
old utils
legacy
compat
deprecated
```

Remove:

-   old import paths;
-   re-export shims;
-   compatibility adapters;
-   duplicate types;
-   duplicate interfaces;
-   dead helpers;
-   legacy process tuples.

The goal is to remove the old `backend/` / `frontend/` architecture
completely unless a deliberate external compatibility requirement
justifies a tiny shell.

The old utility gravity well should disappear.

No migration scaffolding survives merely because deleting it feels
scary.

------------------------------------------------------------------------

# 16. Phase 12 --- Architecture certification

Stop implementing.

Audit the final codebase against the Engineering Constitution.

## Typing

Search:

``` text
Any
dict[str, Any]
type: ignore
object
anonymous tuples
```

Every survivor needs a documented reason.

## Complexity

Re-run:

-   function length;
-   cyclomatic complexity;
-   nesting;
-   parameter counts;
-   class responsibility review.

Do not chase arbitrary zeroes.

Review remaining exceptions intelligently.

## Dependencies

Verify all forbidden arrows.

## Documentation

Check every:

``` text
package
module
public class
non-trivial public callable
```

for compliance.

## Polars

Audit:

``` text
collect()
collect_schema()
to_dicts()
rows()
iter_rows()
to_pandas()
```

Classify every meaningful materialization boundary.

## Behavioral comparison

Compare against v8.3.1:

``` text
Bronze
Silver
Gold
Meta
deterministic IDs
lots
realized events
reconciliation
Tax
wealth
cash flow
FIRE
```

No unexplained difference is acceptable.

------------------------------------------------------------------------

# 17. Suggested personal implementation rhythm

A rough ten-day rhythm, **not a deadline**:

  Day    Suggested focus
  ------ ----------------------------------------------------------
  1      Phase 0 + Phase 1
  2      Phase 2 + Phase 3
  3      Phase 4 + Phase 5
  4--6   Phase 6 --- Investment / Quant
  7      Phase 7 --- Tax
  8      Phase 8 --- Wealth / FIRE
  9      Phase 9 --- Orchestration / bootstrap
  10     Phase 10--12 --- Presentation, demolition, certification

If Quant needs four or five days, let it.

Understanding and correctness matter more than finishing inside an
arbitrary calendar window.

------------------------------------------------------------------------

# 18. Commit strategy

Prefer small coherent commits.

Examples:

``` text
refactor(contracts): introduce typed application messages
refactor(config): split FinancialRules by domain
refactor(control-plane): migrate persistence package
refactor(ingestion): separate provider acquisition from orchestration
```

For Quant:

``` text
refactor(quant): finalize typed result contracts
refactor(quant): migrate FIFO lot domain
refactor(quant): extract valuation responsibilities
refactor(quant): extract performance domain
refactor(quant): extract reconciliation domain
refactor(quant): decompose ISIN workflow
refactor(quant): migrate portfolio aggregation
```

Do not hide five architectural changes inside one heroic commit.

------------------------------------------------------------------------

# 19. Stop conditions

Stop the current phase immediately if:

-   financial outputs change unexpectedly;
-   deterministic IDs change;
-   warehouse grain changes;
-   reconciliation changes;
-   Tax classification changes;
-   FIRE behavior changes;
-   recovery semantics change;
-   a compatibility layer creates two authoritative implementations;
-   typing requires guessing a domain shape;
-   a proposed abstraction has no clear current responsibility.

Investigate before continuing.

------------------------------------------------------------------------

# 20. Things explicitly forbidden during the refactor

Do not add:

-   new finance features;
-   ML;
-   AI;
-   derivative engines --- yes, this rule is unfortunately necessary 😂;
-   new financial ratios just because a module is open;
-   Tax scope changes;
-   new FIRE assumptions;
-   unrelated performance experiments;
-   warehouse redesigns for convenience.

Write good ideas down for later.

The refactor already has enough surface area.

------------------------------------------------------------------------

# 21. Final target

The final repository should make these questions easy to answer:

``` text
What does this package own?
What does this module own?
What state does this class own?
Why is this a class?
What shape crosses this boundary?
Where does this dependency point?
What can fail?
Where does this LazyFrame materialize?
Where does this state become durable?
Which component owns this financial truth?
```

And the final flow should feel like:

``` text
Evidence
   ↓
Infrastructure adapters
   ↓
Application ingestion
   ↓
Canonical financial domains
   ↓
Investment / Tax / Wealth / FIRE
   ↓
Application orchestration
   ↓
Warehouse publication
   ↓
Application façade
   ↓
CLI / Desktop
```

with operational provenance and recovery remaining explicit throughout.

------------------------------------------------------------------------

# 22. Completion condition

The Grand Refactor is complete only when:

``` text
same financial truth       ✅
same user functionality    ✅
same contract meaning      ✅

clear package ownership    ✅
typed boundaries           ✅
intentional dependencies   ✅
smaller workflows          ✅
documented source          ✅
intentional materialization✅
legacy architecture gone   ✅
```

At that point the application is ready for the next era:

``` text
Grand Refactor
      🔒
       ↓
Deterministic finance features
       ↓
Personal-finance ML
       ↓
AI explanation layer — much later
```

> **Build the architecture once so future features have somewhere
> correct to live.**
