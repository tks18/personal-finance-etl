# Design Decisions

This document records the reasoning behind major architectural choices in Personal Finance ETL.

I want these decisions documented because architecture is not just a diagram of what exists. The useful question is:

> **Why does it exist this way, what problem does it solve, and what trade-off did I accept?**

These are not immutable laws. They are the decisions that best fit the current v6 workload and constraints.

When the workload changes, a decision can change too. But I want that change to be deliberate.

---

## Decision summary

| Decision | Chosen direction | Primary reason |
| --- | --- | --- |
| Local-first architecture | Local storage and compute | Privacy, control, personal workload |
| SQLite + DuckDB | Separate raw/control and analytical roles | Workload-specific persistence |
| Raw BLOB persistence | Preserve source artifacts | Provenance and recovery |
| Incremental Bronze | Synchronize changed source state | Efficient source-history maintenance |
| Rebuild Silver/Gold | Deterministic derived state | Simpler correctness |
| Polars + DuckDB | Separate compute from serving persistence | Vectorized analytics + SQL/BI storage |
| Canonical financial contracts | Resolve source semantics upstream | Stable downstream engines |
| FinancialRules separate from Settings | Separate policy from operations | Explicit financial semantics |
| Asset pipelines | Strategy boundary for investment types | Extensibility without engine conditionals |
| Broker-authoritative reconciliation | Anchor current investment truth | Real-world source imperfections |
| Shadow benchmarks | Match capital deployment | Better benchmark-relative context |
| Multi-grain Gold marts | Model questions at correct grain | BI correctness |
| Curated serving metrics | Publish decision-useful analytics | Reduce analytical noise |
| Process-isolated pipeline | Keep frontends responsive | Failure and execution isolation |
| Application-coordinated transactions | Coordinate two local stores | Practical rollback semantics |
| Configuration + strategies | Parameters vs behaviour | Avoid configuration-as-code |

---

## ADR-001 · Keep the platform local-first

## Context

The system processes highly personal financial data and is used primarily by one local user.

The workload does not require multi-user cloud serving, elastic distributed compute, or remote collaboration.

## Decision

I keep the core platform local-first.

Financial data, raw artifacts, analytical databases, transformations, simulations, and BI-serving state are designed to live on the local machine.

## Why

This gives me:

- direct control over financial data,
- simple deployment,
- low infrastructure overhead,
- predictable local access,
- and freedom to use embedded analytical technologies such as DuckDB and SQLite.

## Trade-offs

I accept:

- local backup responsibility,
- no built-in multi-user concurrency model,
- no automatic remote disaster recovery,
- and local machine resource limits.

## Revisit when

This decision should be revisited if the project becomes a true multi-user product or requires remote/mobile synchronization.

---

## ADR-002 · Use SQLite and DuckDB for different jobs

## Context

The system needs both:

- transactional registry/BLOB state,
- and columnar analytical persistence.

Using one database for everything would reduce technology count but force one engine into a workload it is not primarily chosen for.

## Decision

I use:

**SQLite** for the Raw/control plane.

**DuckDB** for the analytical warehouse.

## Why

SQLite is a strong fit for:

- local metadata,
- registry updates,
- BLOB persistence,
- synchronization state,
- and transactional control-plane operations.

DuckDB is a strong fit for:

- analytical tables,
- columnar execution,
- warehouse schemas,
- SQL exploration,
- and BI-serving workloads.

## Trade-offs

I accept:

- two local database files,
- transaction coordination at the application layer,
- and more operational concepts to understand.

## Rejected alternative

### One DuckDB database for everything

Simpler technology footprint, but weaker conceptual separation between raw evidence/control state and analytical state.

### One SQLite database for everything

Strong transactional simplicity, but less aligned with the analytical/BI workload.

---

## ADR-003 · Persist raw source bytes

## Context

A file-based ETL pipeline can easily treat the source folder as permanent truth.

That creates problems when files change, move, disappear, or external data is fetched dynamically.

## Decision

I persist actionable raw source bytes in the SQLite Raw Document Store.

## Why

This provides:

- provenance,
- replayability,
- source evidence independent of filesystem state,
- recovery after analytical warehouse loss,
- and a consistent model for physical and virtual artifacts.

## Trade-offs

I accept:

- additional local storage,
- BLOB-management complexity,
- and the need to distinguish source evidence from analytical state.

## Rejected alternative

### Store only paths and hashes

Smaller Raw database, but the system would still depend on the original external file remaining available for reconstruction.

---

## ADR-004 · Make source synchronization explicit

## Context

Seeing a file does not prove that Bronze contains its latest representation.

## Decision

I model Raw-to-Bronze synchronization using explicit states such as:

```text
PENDING_BRONZE
SYNCED
```

## Why

This makes ingestion state observable and supports reconstruction when warehouse registry state is missing.

## Trade-offs

A small state machine must be maintained correctly.

That is preferable to implicit assumptions about synchronization.

---

## ADR-005 · Use asymmetric Bronze loading

## Context

Reference sources and historical event sources do not have the same semantics.

## Decision

I use:

- full replacement for appropriate reference/current-state datasets,
- file-aware replacement for historical/event datasets.

## Why

This matches persistence behaviour to source meaning.

## Trade-offs

The Bronze loader has more than one strategy.

I consider that better than a simpler loader with less accurate data semantics.

---

## ADR-006 · Rebuild Silver and Gold deterministically

## Context

Making every derived dataset incremental would require dependency-aware invalidation across canonical facts, rolling measures, portfolio aggregation, tax state, and FIRE.

## Decision

Bronze remains persistent and incrementally synchronized.

Silver and Gold are rebuilt from complete current upstream state.

## Why

This simplifies correctness.

The derived state becomes a deterministic function of:

```text
Bronze evidence
+ current rules
+ current configuration
+ current analytical code
```

## Trade-offs

I accept more compute per run.

For the current local workload, that is preferable to complex stale-state management.

## Revisit when

If data volume grows enough that full reconstruction becomes the dominant operational constraint, incremental derived-state strategies may become worthwhile.

---

## ADR-007 · Use Polars for computation and DuckDB for persistence

## Context

The platform needs both expressive dataframe transformations and durable analytical SQL storage.

## Decision

I use Polars as the primary transformation/analytical compute layer and DuckDB as the persistent analytical warehouse.

## Why

Polars provides:

- lazy execution,
- vectorized transformations,
- streaming collection,
- and efficient dataframe composition.

DuckDB provides:

- durable analytical tables,
- SQL access,
- schema organization,
- and BI-friendly local serving.

## Trade-offs

Some logic crosses dataframe and SQL boundaries.

That requires clear ownership of where transformations belong.

---

## ADR-008 · Establish canonical financial contracts

## Context

Source-specific layouts vary.

If analytical engines depend directly on broker columns, worksheet names, or bank-specific schemas, every new source contaminates the entire application.

## Decision

I resolve source-specific structure upstream and expose canonical financial concepts downstream.

## Why

This lets analytical engines reason about:

- income,
- expenses,
- transfers,
- assets,
- purchases,
- sales,
- market data,
- benchmarks,
- and tax lots

without understanding every source format.

## Trade-offs

The transformation boundary becomes more important and must be designed carefully.

## Long-term significance

This is probably the most important seam for making the platform more reusable.

---

## ADR-009 · Separate Settings from FinancialRules

## Context

A file path and a tax rate are both configuration values, but they represent completely different concerns.

## Decision

I separate operational settings from financial semantic policy.

## Why

Operational configuration answers:

> Where and how does the application run?

Financial rules answer:

> How should the system interpret financial meaning?

This makes policy visible and validated rather than burying it inside transformations.

## Trade-offs

Users/developers must understand two configuration concepts instead of one giant settings object.

That is a good trade.

---

## ADR-010 · Use asset pipelines as an investment extension seam

## Context

Stocks and mutual funds can have different upstream source structures.

The downstream investment engine should not need branches everywhere for every asset type.

## Decision

I use asset-specific pipelines behind a common result contract.

## Why

This keeps source/asset-specific behaviour upstream while preserving common downstream investment semantics.

## Trade-offs

A new asset type must satisfy the canonical contract rather than simply dumping arbitrary columns into the engine.

That constraint is intentional.

---

## ADR-011 · Reconcile to broker-reported current state

## Context

Historical transaction data can be imperfect because of:

- missing history,
- opening positions,
- corporate actions,
- broker corrections,
- and source limitations.

## Decision

I reconstruct history from transactions but allow broker-reported current quantity/cost state to anchor the analytical position when the two disagree.

## Why

The system is used operationally.

A theoretically pure reconstruction that disagrees with the actual broker position is less useful for current planning.

## Trade-offs

Reconciliation adjustments can complicate lot-level interpretation.

The policy must therefore remain explicit.

## Alternative

Fail every time transaction-derived state differs from broker state.

That would maximize purity but make the system brittle against real financial data.

---

## ADR-012 · Model a shadow benchmark portfolio

## Context

Comparing an investment CAGR with an index CAGR ignores when capital was actually deployed.

## Decision

Investment purchases create cash-equivalent benchmark exposure.

Shadow benchmark inventory evolves alongside real inventory.

## Why

This gives benchmark-relative analysis a closer relationship to actual cash deployment.

## Trade-offs

The engine must maintain another stateful position model and benchmark-history dependency.

I accept that complexity because benchmark comparison is a real investment decision input.

---

## ADR-013 · Keep investment and household analytics connected

## Context

It would be easy to build an investment dashboard and household finance dashboard as independent systems.

That would create multiple financial truths.

## Decision

Investment market/tax state flows into household wealth and long-range planning.

## Why

My FIRE model should not use a manually entered portfolio value when the investment engine already knows the current market and tax-aware state.

This creates one financial lineage.

## Trade-offs

The engines have meaningful dependency relationships that must be kept explicit.

---

## ADR-014 · Publish multiple Gold grains

## Context

Household wealth, expense composition, tax lots, security performance, allocation drift, and portfolio performance are different analytical questions.

## Decision

Gold publishes domain marts at the grain appropriate to each question.

## Why

Trying to force everything into one fact table creates:

- duplicated values,
- ambiguous aggregation,
- difficult BI semantics,
- and misleading measures.

## Trade-offs

The serving layer contains more physical marts.

That is preferable to one oversized ambiguous model.

---

## ADR-015 · Treat grain as part of the contract

## Context

A metric name without grain can be misleading.

For example:

```text
lot return
instrument XIRR
portfolio XIRR
```

are not interchangeable.

## Decision

Every important published dataset should have an explicit grain.

## Why

Grain determines:

- row meaning,
- valid joins,
- aggregation methodology,
- and measure interpretation.

This is fundamental BI engineering, not documentation decoration.

---

## ADR-016 · Compute richly, publish selectively

## Context

Earlier versions accumulated more quantitative metrics than I found useful in the real workflow.

Some older risk machinery can still exist internally even when it no longer belongs in Gold.

## Decision

The serving model exposes a curated analytical surface.

## Why

More metrics do not automatically produce better decisions.

The current investment serving contract focuses on measures such as:

- XIRR,
- after-tax XIRR,
- benchmark XIRR,
- active return,
- max drawdown,
- tax state,
- position,
- and allocation.

## Trade-offs

Some technically valid calculations are intentionally absent from BI.

That is a feature, not a deficiency.

---

## ADR-017 · Keep financial logic out of Power BI where possible

## Context

Power BI can calculate almost anything, but report-specific business logic can fragment financial semantics.

## Decision

Important reusable financial state is calculated upstream and published through Silver/Gold contracts.

## Why

This gives:

- consistent methodology,
- reusable semantics,
- easier testing/reconciliation,
- and less dashboard-specific logic.

Power BI remains the exploration and presentation layer.

---

## ADR-018 · Isolate heavy execution from the frontend

## Context

Polars, DuckDB, investment processing, and Monte Carlo workloads can be long-running.

Running them directly inside the desktop event loop would couple UI responsiveness to analytical execution.

## Decision

The backend facade launches pipeline execution in a child process and communicates status back to the frontend.

## Why

This improves:

- responsiveness,
- failure isolation,
- and separation of concerns.

## Trade-offs

Inter-process communication and execution-state management add complexity.

---

## ADR-019 · Coordinate local transactions at the application layer

## Context

The system writes to both DuckDB and SQLite during a run.

## Decision

The orchestrator begins, commits, and rolls back local transactions in a coordinated lifecycle.

## Why

This provides practical rollback semantics across the two local persistence roles.

## Trade-offs

It is not distributed two-phase commit.

A narrow sequential-commit failure window remains.

The documentation therefore deliberately avoids claiming a stronger guarantee.

---

## ADR-020 · Preserve failed-run telemetry

## Context

If run telemetry were part of the same rollback scope as all analytical state, failure could erase the evidence that the run happened.

## Decision

Operational run logging has a lifecycle that allows failed execution to remain visible.

## Why

A failed run is operational information.

Observability should not require successful Gold publication.

---

## ADR-021 · Use Monte Carlo as scenario analysis, not prediction

## Context

FIRE planning involves uncertain returns, inflation, employment, withdrawal behaviour, and sequence risk.

## Decision

I model distributions of outcomes under explicit assumptions rather than claim one predicted future.

## Why

This is a more honest use of stochastic modelling.

## Trade-offs

Outputs such as probability of success are conditional on the configured model.

They should never be interpreted as unconditional real-world probabilities.

---

## ADR-022 · Use configuration for parameters, strategies for behaviour

## Context

The long-term platform needs to become more reusable.

A tempting approach is to move every difference into YAML/TOML.

## Decision

I distinguish between:

**parameters**, which belong in validated configuration,

and

**materially different behaviour**, which belongs behind adapters or strategies.

## Why

Tax regimes, broker parsing, and asset-specific behaviour can contain logic, dates, exceptions, and branching that become unreadable when encoded as giant configuration files.

## Trade-offs

Some extension scenarios will require Python code.

That is preferable to configuration becoming a programming language with worse tooling.

---

## ADR-023 · Generalize by extraction, not rewrite

## Context

The current system already produces results I rely on.

A full generic rewrite would discard a valuable working specification.

## Decision

I generalize incrementally.

```text
working behaviour
      ↓
identify embedded assumption
      ↓
extract parameter / strategy
      ↓
run existing environment
      ↓
reconcile outputs
```

## Why

The current production results become the behavioural contract for refactoring.

## Trade-offs

Generalization is slower than starting a clean framework.

It is also much safer.

---

## ADR-024 · Keep documentation version-controlled with the code

## Context

The project has a CLI, desktop application, GitHub repository, package distribution, and future Wiki.

Maintaining separate documentation copies would invite drift.

## Decision

The Markdown under `docs/` becomes the authoritative technical documentation.

Other surfaces should consume or derive from it.

## Why

One maintained source is easier to keep aligned with the production implementation.

## Future direction

The CLI and desktop documentation browser can eventually derive navigation from the same documentation hierarchy or manifest.

---

## Decisions I intentionally have not made yet

Some architecture questions should remain open until the workload justifies them.

## Universal source plugin framework

The seams are becoming clear, but I do not need to build a marketplace-style plugin system before multiple real source environments demand it.

## Distributed/cloud warehouse

The current workload does not justify replacing the local architecture merely for scale theatre.

## Generic jurisdiction engine

Tax strategy boundaries are a likely future direction, but only real multi-jurisdiction requirements should determine the final abstraction.

## Fully incremental Silver/Gold

This should be considered only if deterministic rebuild cost becomes materially problematic.

## Automatic contract generation

A shared data-contract registry is attractive, but the physical/reference documentation should stabilize before code is reorganized around it.

---

## Decision-making principles

Across these ADRs, several recurring principles appear.

### Solve the real workload first

I prefer a working vertical system over a speculative universal framework.

### Preserve evidence

Derived state can be rebuilt; lost source evidence cannot.

### Make semantics explicit

Financial meaning should live in canonical contracts and validated policy rather than report-specific transformations.

### Use asymmetry deliberately

Different workloads deserve different persistence, computation, and modelling strategies.

### Respect grain

BI correctness begins with row meaning.

### Be precise about guarantees

I would rather document a modest guarantee accurately than advertise a stronger architecture that does not exist.

### Prefer decision usefulness

The goal is not maximum metric count.

### Generalize without breaking behaviour

A reusable platform should emerge from the working system, not replace it blindly.

---

## Related documentation

Continue with:

- [System Architecture](system-architecture.md) — complete component view.
- [Data Lifecycle](data-lifecycle.md) — state transitions and data movement.
- [Warehouse Architecture](warehouse-architecture.md) — persistence model.
- [Data Model](data-model.md) — canonical contracts and grains.
- [Reliability & Recovery](reliability-and-recovery.md) — failure and reconstruction behaviour.
- [Project Roadmap](../about/roadmap.md) — future generalization direction.

[← Architecture Home](README.md) · [← Documentation Home](../README.md)
