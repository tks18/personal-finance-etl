---
name: pfetl-v11-implementation
description: Execute, review, or continue the PFETL v11 Shan-first implementation program phase by phase. Use when implementing a v11 phase, reviewing whether a phase is complete, diagnosing a phase regression, updating a phase completion record, or deciding whether a requested PFETL change belongs in the current v11 program. Enforce the Shan-first product philosophy, current repository authority, 2-3 hour atomic phase boundaries, financial-equivalence protections, observability/recovery invariants, conservative Bronze/Silver/Gold migration rules, and repository-native quality/commit workflows.
---

# PFETL v11 Implementation

## Purpose

Execute the authoritative PFETL v11 Shan-first program safely, one phase at a time. Preserve the sophisticated financial and reliability systems that directly benefit the primary user while preventing a return to generic-platform overengineering.

Treat the repository code as implementation authority and the v11 planning package as target-state authority. Reconcile both before changing code.

## Authority order

Before implementation, read the smallest set of repository authorities needed for the requested phase:

1. root `AGENTS.md` and any nested `AGENTS.md` governing touched paths;
2. the authoritative v11 program `README.md`;
3. `DECISION-LEDGER.md`;
4. `ARCHITECTURE.md`;
5. `MIGRATION-STRATEGY.md` when the phase changes config, reference data, warehouse names, persistence, CLI, or GUI;
6. the exact phase file being implemented;
7. current source, tests, config, DDL, and consumers named by the phase.

The authoritative v11 program is expected under the repository planning area. If filenames above exist in more than one planning package, identify the active Shan-first v11 package from repository history/context before editing. Do not use archived Grand Refactor plans as target authority.

## Core constitution

Preserve these decisions unless the user explicitly amends the authoritative program:

- PFETL is Shan-first and local-first.
- Configuration locates known evidence; it does not describe arbitrary source systems.
- `Settings` and `FinancialRules` remain separate responsibilities.
- Raw Store, Control Plane, recovery, backup/restore, deterministic identities, and the single-emitter observability architecture are protected systems.
- Bronze remains source-oriented evidence with semantic table names and useful provenance.
- Existing Silver table topology is preserved; cleanup is naming, consumer-proven dead-column removal, and specifically approved enrichment only.
- Existing Gold table topology is preserved initially; structural reduction requires an explicit evidence-backed case.
- DuckDB is rebuildable derived state; Control Plane and Raw Store are durable operational/evidence history.
- Financial methodology does not change during schema/naming migration phases.
- Power BI remains a supported consumer.
- PFETL Core owns financial truth; future Analytics Studio is read-only initially and owns exploration/visualization.
- Do not recreate Config Studio, a contracts repository, a separate organization, generic source-binding architecture, plugin frameworks, schema DSLs, or public compatibility machinery.

Read `references/invariants.md` when the phase touches financial outputs, warehouse schemas, migration, observability, recovery, or presentation boundaries.

## Phase execution workflow

### 1. Establish the exact phase contract

Extract from the phase file:

- outcome;
- inherited state;
- current code anchors;
- exact target state;
- implementation sequence;
- files/symbols in scope;
- tests and verification;
- explicit non-goals;
- completion checklist;
- next-phase handoff.

Do not begin with a repository-wide refactor. The phase outcome is the boundary.

### 2. Archaeologize before editing

Inspect the actual current implementation around every named anchor. Verify:

- symbols still exist where the plan expects;
- ownership has not moved;
- downstream consumers are understood before renaming/removing fields;
- tests reflect current behavior;
- no prior local change already completed part of the phase.

If current code contradicts the phase materially, stop implementation and report the contradiction. Propose the smallest plan amendment needed. Do not silently redesign the phase while coding.

### 3. Define the regression oracle

Before changing runtime behavior, identify what must remain identical.

For schema/naming/config migrations this normally includes, as applicable:

- Bronze row/content equivalence;
- household totals and balances;
- investment quantities and valuations;
- protected deterministic IDs;
- realized/reconciliation/Tax events;
- XIRR/CAGR, asset P&L and FX P&L;
- wealth and FIRE outputs;
- Control Plane continuity;
- recovery behavior;
- observability lineage.

If the phase intentionally adds a new analytical output, existing outputs still form the regression oracle.

### 4. Implement only phase-owned changes

Prefer direct, explicit code over generalized frameworks.

Good examples:

- rename a known table and migrate its known consumers;
- move hash ownership to the known source config model;
- replace one obsolete reference file with `instrument_master.csv`;
- add one operator read service consumed by CLI and GUI;
- add a small shared helper for genuinely repeated schema fragments.

Bad examples unless explicitly required by the phase:

- generic source registries or routing DSLs;
- dynamic schema/config compilers;
- abstract factories for a small fixed set of known objects;
- compatibility layers for a one-time local migration;
- table merges/splits for aesthetic normalization;
- new public APIs for hypothetical users;
- new finance methodology hidden inside cleanup work.

### 5. Respect migration boundaries

For one-time breaking migrations:

- preserve Raw Store and Control Plane unless the phase explicitly changes them;
- snapshot/backup before destructive migration work;
- rebuild DuckDB rather than maintaining old warehouse aliases when the phase says to cut over;
- update all known consumers, including Power BI-facing names where relevant;
- never use a compatibility view merely to avoid updating the primary user's own consumer once.

Do not mix naming/schema migration with new financial methodology unless the phase explicitly owns both.

### 6. Verify in layers

Run the narrowest checks first, then broaden.

Typical order:

1. formatter/linter/type checks for touched code;
2. focused unit/contract tests;
3. affected architecture tests;
4. affected financial regression tests;
5. persistence/recovery tests when storage changes;
6. observability tests when events/context change;
7. full affected subsystem suite;
8. full quality gate when required by the phase/release boundary;
9. real Shan-data run when runtime/financial behavior changes.

A phase is not complete because unit tests pass if its completion checklist requires real-data, recovery, Power BI, packaging, or UI verification.

### 7. Treat failures as evidence

If verification exposes a defect:

- determine whether it is introduced by the phase, pre-existing, or a planning gap;
- fix only phase-owned regressions immediately;
- do not opportunistically sweep unrelated debt into the phase;
- record a newly discovered prerequisite instead of stretching the phase into a multi-day branch.

### 8. Close the phase deliberately

Only after every exit assertion is green:

- update the phase completion checklist/record with concrete evidence;
- record compatibility/deletion state where the template asks for it;
- ensure the next phase's handoff is actually true in the repository;
- leave the repository green.

Do not mark a future phase complete or partially implement its work.

## Commit discipline

Do not prescribe one giant commit or one file per commit.

Use the repository's `pfetl-conventional-commits` skill/workflow for preview, semantic grouping, staging, overrides, and Commitlint-compliant messages. Group files by coherent implementation concern. The phase file defines the semantic outcome; the commit skill defines the clean commit mechanics.

## Financial protections

Never change a financial formula merely to make a schema rename easier.

Treat these identities as protected wherever they exist in the current implementation:

- purchase IDs;
- sale IDs;
- lot IDs;
- realized-event IDs;
- reconciliation group/event IDs;
- tax-event IDs;
- other deterministic financial identifiers explicitly protected by tests/current code.

Table/column names may change. Financial identity semantics must not change unless an explicit approved finance phase says so.

When a numerical difference appears during a migration phase, assume regression until proven otherwise.

## Warehouse rules

### Bronze

Keep source-oriented contents. Rename physical tables semantically. Keep provenance needed for sync/debugging. Do not turn Bronze into a universal canonical-finance layer.

### Silver

Keep the current proven table boundaries and grains. Rename tables/columns clearly. Remove source/provenance columns only after consumer archaeology proves them unnecessary. When uncertain, keep the column.

### Gold

Keep current analytical surfaces initially. Standardize names and proven-dead columns conservatively. Do not reduce table count merely because metrics overlap. Power BI usability is a valid reason for a separate Gold surface.

## Approved Core analytics

Only these new analytical themes are currently approved by the v11 decision freeze:

- net-worth change attribution;
- lifestyle / inflation-adjusted expense growth;
- income resilience;
- portfolio concentration;
- LTCG maturity ladder;
- indicative tax-exposure summary.

Do not add rebalancing trade recommendations, generic volatility engines, arbitrary slicing frameworks, or AI/ML financial truth as part of this program unless the authoritative plan is amended.

Prefer adding approved metrics to an existing suitable Gold surface. Create a new table only when the required grain is genuinely distinct.

## CLI and GUI rules

The product identity is `pfetl`.

The target CLI remains compact and operator-focused. Do not grow it into an administration framework.

The PySide6 application is an operations console, not Analytics Studio. Keep financial dashboard creep out of Core GUI. Use application services for actions and dedicated read/query services for inspection. Do not write finance/persistence logic inside Qt presentation code.

Adapt the existing observability projection to Qt. Do not create a parallel Qt logging architecture.

## Stop conditions

Stop and report rather than continue if the phase begins to require any of the following without explicit authority:

- a new generic platform abstraction;
- arbitrary user-defined source/schema behavior;
- a Silver table merge/split;
- broad Gold topology redesign;
- protected identity changes;
- financial formula changes during migration/cleanup;
- redesign of observability, Raw Store, Control Plane, or recovery;
- long-lived compatibility infrastructure for a one-time local migration;
- scope that clearly exceeds the intended 2-3 hour atomic sprint;
- implementation of the next phase to make the current phase "complete".

In these cases, preserve the green state, explain the dependency or contradiction, and amend planning before proceeding.

## Review mode

When asked to review an implemented phase rather than code it:

1. read the exact phase exit checklist;
2. inspect the actual diff/current repository state;
3. verify each exit assertion with code/tests/runtime evidence;
4. classify each assertion as PASS, PARTIAL, GAP, or NOT TESTED;
5. distinguish implementation defects from missing evidence;
6. do not mark completion merely because the intended files changed;
7. state whether the next phase may safely begin.

## Completion standard

The program is succeeding when PFETL becomes easier for its primary user to operate and maintain while retaining sophisticated, deterministic financial truth.

A technically impressive abstraction that increases daily friction is not a success criterion.
