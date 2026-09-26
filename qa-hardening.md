# Personal Finance ETL --- Test & QA Master Plan

> **Baseline:** v6.5.3 (unreleased)
>
> **Purpose:** build a complete, maintainable automated test system
> around the entire application --- financial correctness, Control Plane
> behavior, data-layer contracts, failure recovery, snapshot/restore,
> logging, docs rendering, and public execution surfaces.
>
> **Goal:** the test suite becomes the executable safety net that lets
> future development move quickly without relying on the production
> portfolio as the only proof of correctness.

------------------------------------------------------------------------

# 1. Why This Test Sprint Matters

The application already works on a large real-world dataset.

That is valuable evidence.

It is not enough.

Real production data proves:

> "This particular portfolio currently works."

A deterministic automated suite proves:

> "The intended behaviors remain correct when code changes."

The final testing model should have four complementary sources of
confidence:

```text
Small deterministic unit tests
        +
component tests with temporary SQLite / DuckDB
        +
integration / failure-recovery tests
        +
real-production regression
```

Do not replace the real-data regression.

Do not use the real portfolio as the unit-test fixture.

------------------------------------------------------------------------

# 2. Test Philosophy

## Rule 1 --- Test contracts, not implementation trivia

Prefer:

```text
PENDING_BRONZE artifact replays exactly once
```

over:

```text
private helper X was called twice
```

Prefer:

```text
failed worker cannot publish partial portfolio
```

over asserting internal executor implementation.

This keeps tests useful through refactors.

## Rule 2 --- Pure financial logic gets the smallest tests

FIFO, holding-period classification, set-off, XIRR semantics, and
reconciliation math should be testable without:

```text
GUI
filesystem
real broker files
full ETL
```

## Rule 3 --- State boundaries get real databases

Control Plane and DuckDB behavior should be tested with temporary real
SQLite/DuckDB databases whenever practical.

Do not mock SQL semantics you are specifically trying to verify.

## Rule 4 --- Mock external/environmental boundaries

Good mocking targets:

```text
broker/provider API
clock/time where needed
filesystem failure injection
process-worker failure
webview
GUI file dialogs
OS open-browser calls
```

Avoid mocking:

```text
FIFO math
SQLite transaction behavior
DuckDB publication
DataContract validation
```

when those are the actual subjects under test.

## Rule 5 --- Every production bug becomes a regression test

Examples from the hardening era:

```text
empty actionable source leaves stale Bronze
PENDING_BRONZE not replayed
rename breaks path-derived identity
restore rollback produces mixed DB pair
stale WAL survives restore
unknown XIRR becomes 0%
taxable interest omitted
```

Once fixed:

> **never allow the same bug class to return silently.**

------------------------------------------------------------------------

# 3. Recommended Test Pyramid

Use approximate proportions, not rigid quotas.

```text
                   ┌───────────────┐
                   │   E2E / UI    │   few
                   └───────┬───────┘
                       ┌───▼────┐
                       │Integration│   moderate
                       └────┬────┘
                    ┌───────▼───────┐
                    │ Component / DB │   many
                    └───────┬───────┘
                 ┌──────────▼──────────┐
                 │ Unit / Domain / Pure │   most
                 └─────────────────────┘
```

Recommended emphasis:

```text
Unit/domain                ~50%
Component/database         ~25%
Integration/recovery       ~20%
E2E/UI smoke               ~5%
```

The percentages are guidance only.

------------------------------------------------------------------------

# 4. Recommended Test Directory

Conceptually:

```text
tests/
├── unit/
│   ├── finance/
│   ├── domain/
│   ├── control_plane/
│   ├── contracts/
│   ├── docs/
│   └── utils/
│
├── component/
│   ├── sqlite/
│   ├── duckdb/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   ├── backup/
│   └── logging/
│
├── integration/
│   ├── pipeline/
│   ├── recovery/
│   ├── snapshots/
│   ├── finance/
│   └── docs/
│
├── e2e/
│   ├── cli/
│   └── gui/
│
├── golden/
│   ├── datasets/
│   ├── expected/
│   └── test_golden_portfolios.py
│
├── fixtures/
│   ├── broker/
│   ├── masters/
│   ├── configs/
│   └── snapshots/
│
└── conftest.py
```

Adapt names to existing project conventions.

The separation matters more than the exact folders.

------------------------------------------------------------------------

# 5. Test Data Strategy

Build **synthetic financial datasets designed to expose one behavior at
a time**.

Do not create one giant fake production workbook.

## Dataset A --- Minimal Equity

```text
Instrument: EQ001
Buy 10 @ 100
```

Used for:

-   ingestion,
-   lot creation,
-   holdings,
-   basic Gold outputs.

## Dataset B --- Multi-Lot FIFO

```text
Buy 10 @ 100
Buy 10 @ 120
Sell 15 @ 150
```

Expected:

```text
Lot 1 disposed: 10
Lot 2 disposed: 5
Remaining: 5 @ 120
```

## Dataset C --- Full Liquidation

```text
Buy
Sell all
```

Expected:

```text
active quantity = 0
realized event remains
```

## Dataset D --- Gain/Loss Mix

Include:

```text
STCG
LTCG
STCL
LTCL
```

for set-off testing.

## Dataset E --- Income

Include:

```text
dividend
interest
```

with no capital gains.

Used specifically to catch tax-exposure omissions.

## Dataset F --- Reconciliation

Transaction reconstruction disagrees with broker holdings.

Include:

```text
quantity mismatch
basis mismatch
unknown basis
```

## Dataset G --- Empty Changed Source

Version 1:

```text
10 rows
```

Version 2:

```text
0 rows
```

Used to guarantee stale Bronze is cleared.

## Dataset H --- Rename

Same bytes, new path.

Used to test:

```text
identity migration
payload retention
Bronze ownership
Meta
```

## Dataset I --- Multi-FY

Small 3-4 year lifecycle for:

```text
realized events
loss carry-forward guidance
XIRR
full liquidation
```

------------------------------------------------------------------------

# 6. Golden Expected Data

For important financial fixtures, keep expected outputs in reviewable
files.

Example:

```text
tests/golden/
├── datasets/
│   └── fifo_multi_lot/
│       ├── transactions.csv
│       └── holdings.csv
│
└── expected/
    └── fifo_multi_lot/
        ├── active_lots.csv
        ├── realized_events.csv
        └── portfolio_summary.json
```

Advantages:

-   human-reviewable,
-   easy to diff,
-   CA can inspect the numbers,
-   implementation language does not define truth.

Do not regenerate expected files automatically during normal tests.

Changing expected financial truth should be a deliberate review action.

------------------------------------------------------------------------

# 7. Unit Tests --- Financial Domain

These are mandatory.

## FIFO

Test:

-   single buy,
-   multiple buys,
-   partial sell,
-   multi-lot sell,
-   multiple sells,
-   full liquidation,
-   exact depletion,
-   oversell,
-   zero quantity,
-   malformed transaction ordering where relevant.

Verify:

```text
quantity
basis
proceeds
realized P&L
remaining lots
```

## Holding period

For each supported asset category:

```text
before boundary
exact boundary
after boundary
```

## Tax classification

Test:

```text
listed equity
equity MF
debt MF
gold ETF/MF
unknown
```

Unknown must not silently inherit a valid rate.

## Loss set-off

Test all four relationships:

```text
STCL → STCG
STCL → LTCG
LTCL → LTCG
LTCL ↛ STCG
```

The Income Tax Department describes the same distinction for
capital-loss carry-forward/set-off.
citeturn0search0turn0search1turn0search2

## Carry-forward guidance

Test:

-   opening balance,
-   partial use,
-   full use,
-   multiple FYs,
-   expiry/review status,
-   STCL/LTCL separation.

## Tax exposure

Test:

```text
capital gain only
dividend only
interest only
all three
zero taxable components
```

## XIRR

Test:

```text
positive
negative
valid zero
undefined
invalid sign pattern
non-convergence
```

## Reconciliation

Test:

```text
quantity adjustment
basis adjustment
unknown basis
realized history immutability
```

------------------------------------------------------------------------

# 8. Unit Tests --- Utility / Domain Infrastructure

Test small deterministic helpers:

-   path normalization,
-   file-ID generation,
-   financial-year derivation,
-   hashing,
-   canonical config serialization,
-   date normalization,
-   rule lookup,
-   contract identity,
-   filename normalization.

The path-normalization bug from the hardening sprint should have a
permanent regression test.

------------------------------------------------------------------------

# 9. Control Plane Component Tests

Use a real temporary SQLite database.

## Run lifecycle

Test:

```text
STARTED
RUNNING
COMMITTING
SUCCESS
FAILED
```

Verify legal transitions.

## Stale recovery

Create stale:

```text
STARTED
RUNNING
COMMITTING
```

then reopen/start pipeline.

Verify explicit recovery.

## Artifact registry

Test:

-   new artifact,
-   unchanged artifact,
-   changed artifact,
-   pending artifact,
-   synchronized artifact,
-   rename,
-   delete policy,
-   virtual artifact.

## Payload

Test:

```text
register
→ store bytes
→ retrieve identical bytes
```

## Settings/FinancialRules snapshots

Test deterministic snapshot identity for identical canonical input.

## Failures/logs

Verify:

```text
failure persisted
traceback persisted
execution log persisted
run relationship correct
```

------------------------------------------------------------------------

# 10. DuckDB / Contract Component Tests

Use a real temporary DuckDB database.

## DataContract registry

Test:

-   duplicate contract ID,
-   duplicate physical table,
-   invalid layer,
-   missing grain,
-   missing producer,
-   expected 16/20/17 baseline.

## DDL / publication

For representative contracts:

```text
builder output
→ validate
→ publish
→ read back
```

Verify columns and row counts.

## Orphan cleanup

Create an analytical table not represented by the registry.

Verify intended cleanup behavior.

## Meta

Verify current-run projection is generated from the same contract
authority.

------------------------------------------------------------------------

# 11. Bronze Component Tests

This layer deserves strong coverage because it is the incremental
boundary.

## New artifact

```text
PENDING
→ Bronze insert
→ SYNCED
```

## Unchanged artifact

No duplicate rows.

## Changed historical artifact

Old owned partition removed, new partition inserted.

## Changed source becomes empty

Old partition/table state removed correctly.

## Current/reference replacement

Old current state is replaced, not appended.

## Pending replay

A `PENDING_BRONZE` artifact with unchanged source must replay.

## Replay idempotency

Replay twice.

Same Bronze output.

## Artifact-level healing

Delete one artifact-owned Bronze partition while leaving table present.

Verify:

```text
SYNCED
→ detected inconsistent
→ PENDING
→ replay
→ restored
```

## Rename

Verify:

```text
new identity
payload preserved
old identity removed
Bronze ownership updated
Meta updated
financial rows unchanged
```

------------------------------------------------------------------------

# 12. Silver Component Tests

Test builders individually with tiny DataFrames.

## Data quality

Missing critical:

```text
ISIN
tax category/type
```

must follow the final fail-fast policy.

## Canonicalization

Verify:

-   expected types,
-   required columns,
-   deterministic output,
-   duplicates handled according to contract.

## Financial facts

For investment transaction/holding builders, compare exact expected
rows.

------------------------------------------------------------------------

# 13. Gold Component Tests

Gold tests should focus on analytical semantics rather than
implementation.

Examples:

-   portfolio summary,
-   asset allocation,
-   realized gain summary,
-   tax exposure,
-   XIRR outputs,
-   FIRE inputs,
-   cash-flow reconciliation.

Each builder receives a tiny known Silver state and must produce known
output.

This avoids running the entire pipeline for every analytical
calculation.

------------------------------------------------------------------------

# 14. Pipeline Integration Tests

Now combine layers.

## Happy path

```text
discover
→ raw
→ Bronze
→ Silver
→ Gold
→ Meta
→ SUCCESS
```

Use a tiny synthetic portfolio.

## Unchanged rerun

Run twice.

Assert:

```text
same analytical outputs
no duplicate artifacts
no duplicate Bronze
second run succeeds
```

## Changed source

Modify one source.

Verify only the intended incremental boundary changes and downstream
outputs rebuild deterministically.

## Empty changed source

Catch the v6.5.0 regression permanently.

## Rename

Catch path-identity regression permanently.

## Full liquidation

Verify active state disappears while realized history remains.

------------------------------------------------------------------------

# 15. Failure-Injection Integration Tests

This is where the architecture hardening becomes executable.

Create explicit failure hooks/monkeypatches in tests.

## Fail before Control Plane opens

Verify no lock leak.

## Fail after Control Plane opens

Verify lock released.

## Fail during Bronze

Verify:

```text
run FAILED
artifact pending/recoverable
no false success
```

## Fail during Silver

Verify transaction rollback.

## Fail during Gold

Verify no partial publication.

## Fail during worker

Simulate one ISIN worker exception.

Verify entire investment stage fails.

## Fail during final commit

Exercise both commit-order windows as far as practical.

Verify next-run recovery.

## Fail during log persistence

Primary pipeline outcome must remain primary.

------------------------------------------------------------------------

# 16. Snapshot / Restore Test Suite

This should be comprehensive because restore is now a product feature.

## Snapshot creation

Test:

-   both DBs present,
-   SQLite missing,
-   DuckDB missing,
-   output ZIP contains expected recovery unit.

## Normal restore

Create known state A.

Snapshot.

Mutate to state B.

Restore.

Verify state A returns.

## Invalid snapshot

Test:

-   missing SQLite,
-   missing DuckDB,
-   unexpected nested path,
-   malformed ZIP.

Production DBs must remain untouched.

## Partial replacement failure

Inject failure after first DB replacement.

Verify:

```text
old SQLite restored
old DuckDB restored
old sidecars restored
```

Never mixed state.

## Stale sidecars

Create:

```text
SQLite WAL/SHM
DuckDB WAL
```

then restore.

Verify no stale sidecar contaminates restored state.

## Locking

Attempt restore while pipeline lock is held.

Expected: clean rejection.

------------------------------------------------------------------------

# 17. Logging / Observability Tests

Do not test every log sentence.

Test guarantees.

## Parent logging

Verify run log contains:

```text
run ID/context
major stage
failure traceback
```

## Worker logging

Run multiple synthetic ISINs.

Verify worker start/finish events arrive through the multiprocessing
queue.

## Failure

Worker failure must still reach parent even if worker logging is broken.

## Persistence

Verify compressed execution log round-trips correctly.

## Cleanup

Run pipeline repeatedly in one process.

Verify:

-   no duplicate handlers,
-   no accumulating QueueListeners,
-   Manager shuts down,
-   no repeated duplicate log lines.

## Privacy

Use a fixture containing fake account-sensitive values.

Assert prohibited raw values are not present in persisted logs.

------------------------------------------------------------------------

# 18. Docs Renderer Tests

The docs renderer is now important enough to test.

## Catalog

Test:

-   manifest loads,
-   duplicate/missing paths handled,
-   all declared pages exist.

## Canonical paths

Test:

```text
repo README → docs page
docs README → repo README
docs page → sibling docs page
nested docs → parent docs
```

## Markdown

Fixture containing:

-   headings,
-   tables,
-   fenced code,
-   lists,
-   blockquotes,
-   links,
-   images,
-   Mermaid.

Verify generated HTML contains expected structures.

## TOC

Verify H1/H2/H3 generate expected TOC hierarchy.

## Mermaid

Mock/load the bundled Mermaid asset.

Verify generated HTML includes bundled runtime and no CDN dependency.

## Missing Mermaid asset

Renderer should still return usable HTML with source fallback.

## Packaging smoke

After wheel build, verify the Mermaid asset is present.

------------------------------------------------------------------------

# 19. CLI Tests

Test CLI behavior without requiring interactive manual input.

Use the CLI runner/testing facility appropriate to the CLI framework.

Cover:

-   help,
-   version,
-   run command,
-   docs command,
-   snapshot create,
-   snapshot restore,
-   invalid paths,
-   lock contention,
-   expected exit codes.

Mock:

```text
file picker
browser/webview launch
```

where necessary.

Do not mock the underlying snapshot manager when testing CLI-to-backend
integration.

------------------------------------------------------------------------

# 20. GUI Tests

Keep GUI automation small.

The GUI should not dominate the suite.

Test controller/facade behavior:

-   run button calls correct backend command,
-   snapshot restore validates selection,
-   docs opens renderer,
-   errors surface to user.

Mock actual native dialogs/webview where needed.

Then keep one or two manual/E2E GUI smoke tests for release validation.

------------------------------------------------------------------------

# 21. Configuration Tests

Test:

-   valid default config,
-   missing required field,
-   invalid enum/category,
-   invalid financial threshold,
-   deterministic canonical serialization,
-   path normalization,
-   config override behavior.

FinancialRules tests should assert that changing a financial parameter
changes the financial-rules snapshot identity.

Non-financial path changes should not accidentally imply a methodology
change if the current provenance model separates them.

------------------------------------------------------------------------

# 22. Mocking Strategy

## Mock these

### Provider/API boundary

Return deterministic fake payloads.

Test:

```text
success
empty response
timeout/error
malformed payload
```

### Time

Freeze time only where run timestamps or FY derivation require it.

### Filesystem failure

Monkeypatch:

```text
replace
remove
copy
```

to inject restore/backup failures.

### Worker failure

Patch worker function to:

```text
raise
return structured error
terminate unexpectedly where practical
```

### GUI/native boundary

Mock:

```text
file dialogs
message boxes
pywebview
OS browser
```

## Do not mock these when testing their behavior

```text
SQLite
DuckDB
Bronze upsert
DataContract validation
FIFO
tax set-off
XIRR
snapshot file replacement
```

Use temporary real resources.

------------------------------------------------------------------------

# 23. Temporary Database Fixtures

Use pytest temporary directories.

Conceptually:

``` python
@pytest.fixture
def temp_system(tmp_path):
    sqlite_path = tmp_path / "Raw_Documents.sqlite"
    duckdb_path = tmp_path / "Personal_Finance_DB.duckdb"

    return TestSystem(
        sqlite_path=sqlite_path,
        duckdb_path=duckdb_path,
    )
```

Each test gets isolated state.

Never point automated tests at the real personal databases.

------------------------------------------------------------------------

# 24. Financial Dataset Builders

Avoid hand-writing giant CSVs repeatedly.

Create fixture builders.

Conceptually:

``` python
portfolio = (
    PortfolioFixture()
    .instrument("EQ001", category="LISTED_EQUITY")
    .buy("2025-01-01", qty=10, price=100)
    .buy("2025-03-01", qty=10, price=120)
    .sell("2025-08-01", qty=15, price=150)
    .build()
)
```

The builder should produce the same input shape the pipeline expects.

This makes financial tests readable.

Important:

> The builder creates **source evidence**, not expected output.

Expected output remains independently specified.

------------------------------------------------------------------------

# 25. Property-Based Testing

Optional but valuable for pure financial invariants.

Use a property-based tool such as Hypothesis if you are comfortable
adding it to test dependencies.

Good candidates:

## FIFO

Generate valid sequences where sells never exceed inventory.

Assert:

```text
closing quantity
=
buys - sells
```

## Set-off

Generate non-negative STCG/LTCG/STCL/LTCL.

Assert:

```text
LTCL_to_STCG = 0
used losses <= available losses
net gains >= 0
```

## Reconciliation

Generate small adjustments and assert accounting identities.

Do not use property tests as the only proof of statutory/domain
examples.

Golden scenarios remain primary for financial meaning.

------------------------------------------------------------------------

# 26. Differential / Metamorphic Tests

These are extremely useful for this project.

## Unchanged rerun

```text
run(source)
run(same source)

outputs equal
```

## File-order independence

If ingestion semantics say source order is irrelevant:

```text
same files in different discovery order
→ same analytical state
```

## Rename invariance

Pure rename with identical bytes:

```text
financial outputs unchanged
```

## Snapshot round trip

```text
state A
→ snapshot
→ mutate
→ restore
→ state A
```

## Clean rebuild equivalence

```text
incremental state
=
clean rebuild state
```

These tests exercise architecture without encoding internal
implementation details.

------------------------------------------------------------------------

# 27. Contract Snapshot Tests

For public analytical tables, freeze the schema contract.

Store expected:

```text
table
column
type
nullable/required where modeled
grain
```

A schema change should produce an intentional test failure.

Do not snapshot entire large data outputs where a small semantic
assertion is clearer.

Use schema snapshots for interface stability.

------------------------------------------------------------------------

# 28. Regression-Test Register

Maintain a simple file:

```text
tests/REGRESSIONS.md
```

Every meaningful production bug gets:

```text
Bug:
Version found:
Failure mode:
Regression test:
Fixed in:
```

Examples:

```text
PENDING_BRONZE replay hole
empty Bronze stale state
rename path identity
restore mixed-pair rollback
stale WAL restore
portfolio XIRR 0% fallback
taxable-interest omission
```

This becomes a history of why seemingly strange tests exist.

------------------------------------------------------------------------

# 29. Test Markers / Execution Tiers

Not every test should run at the same cadence.

Recommended markers:

```text
unit
component
integration
golden
e2e
slow
production_regression
```

## Fast local/default

Run:

```text
unit + component + most integration
```

Target: fast enough to run constantly.

## Pre-commit / PR

Run:

```text
unit
component
integration
golden
```

## Release

Run everything except real production regression first.

Then manually/securely run:

```text
production_regression
```

against the real private dataset.

------------------------------------------------------------------------

# 30. Coverage Targets

Do not chase 100% line coverage.

Use coverage as a blind-spot detector.

Suggested targets:

```text
Pure finance/domain modules        90%+
Control Plane core                 85%+
Bronze synchronization             85%+
Backup/restore                     90%+
Contracts/validation               90%+
Pipeline orchestration             75-85%
GUI rendering code                 lower acceptable
```

More important than percentages:

> every meaningful state transition and known failure mode has a test.

Branch coverage is particularly valuable for:

```text
recovery
classification
tax set-off
restore rollback
XIRR failure semantics
```

------------------------------------------------------------------------

# 31. CI Strategy

Keep CI boring.

Recommended jobs:

## Static

```text
Ruff
mypy
Pyright
```

## Fast tests

```text
unit
component
```

## Integration

```text
integration
golden
```

## Build smoke

```text
uv build
install wheel
import package
CLI --help
verify packaged docs/Mermaid asset
```

Do not put the real personal financial dataset in CI.

Never upload private snapshots as CI artifacts.

------------------------------------------------------------------------

# 32. Release Test Gate

Before a release:

## Static

-   Ruff pass.
-   mypy pass.
-   Pyright pass.

## Unit/component

-   finance tests pass,
-   Control Plane tests pass,
-   Bronze tests pass,
-   contracts pass,
-   backup/restore pass,
-   docs renderer pass.

## Integration

-   happy-path ETL,
-   unchanged rerun,
-   changed source,
-   empty source,
-   rename,
-   worker failure,
-   stale run,
-   snapshot restore.

## Golden

-   all financial golden scenarios pass,
-   invariants pass.

## Package

-   wheel/sdist build,
-   clean-wheel install,
-   Mermaid bundled,
-   docs render offline,
-   CLI starts.

## Private production regression

Run real corpus.

Verify:

```text
expected contracts
Control Plane clean
no duplicate Bronze
financial differences explained
runtime observed
```

------------------------------------------------------------------------

# 33. Test Implementation Order

Do not start by testing every module.

## Phase 1 --- Test infrastructure

Build:

-   pytest configuration,
-   temp DB fixtures,
-   financial source builders,
-   golden-data helpers,
-   markers,
-   coverage configuration.

## Phase 2 --- Pure financial truth

Test:

-   FIFO,
-   holding periods,
-   tax classification,
-   set-off,
-   XIRR,
-   reconciliation.

## Phase 3 --- Control Plane

Test lifecycle, artifacts, payloads, provenance, stale recovery.

## Phase 4 --- Bronze

Test incremental behavior, replay, healing, empty state, rename.

## Phase 5 --- Contracts / Silver / Gold

Test schema and representative builders.

## Phase 6 --- Failure recovery

Test orchestrator failures, workers, commits, locks.

## Phase 7 --- Snapshot/restore

Build the complete recovery suite.

## Phase 8 --- Logging

Test cross-process tracing, persistence, cleanup, privacy.

## Phase 9 --- Docs/CLI/GUI

Test renderer, package resources, public commands/controllers.

## Phase 10 --- Golden lifecycle

Build the multi-FY portfolio golden test.

## Phase 11 --- Production regression

Only after deterministic tests are green.

------------------------------------------------------------------------

# 34. Definition of Done

The Test & QA Sprint is complete when:

-   pure financial rules have deterministic unit tests,
-   financial golden scenarios exist independently of implementation,
-   Control Plane state transitions are tested with real SQLite,
-   DuckDB contracts/publication are tested with real DuckDB,
-   Bronze incremental/replay/healing behavior is covered,
-   every hardening-era bug has a regression test,
-   failure injection proves cleanup/recovery,
-   snapshot/restore is tested as an all-or-old recovery unit,
-   cross-process logging is tested without becoming a correctness
    dependency,
-   docs renderer/navigation/offline Mermaid are tested,
-   CLI/backend integration is covered,
-   GUI controllers have targeted tests,
-   clean rebuild equals incremental state,
-   package build/install smoke tests pass,
-   and the private real-data production regression remains the final
    release check.

> **Target:** production data proves realism; deterministic tests prove
> behavior; golden datasets prove financial truth; failure injection
> proves resilience.
