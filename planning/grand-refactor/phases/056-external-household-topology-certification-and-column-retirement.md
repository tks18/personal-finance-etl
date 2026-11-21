# Phase 056 - External Household Topology Certification and Column Retirement

**Target release:** v10.5.2  
**Expected effort:** 4-6 hours  
**Previous:** Phase 055  
**Next:** Phase 057  
**Risk:** High

## 1. Outcome

Certify the completed canonical source-binding architecture against household evidence topologies that do not resemble Shan's production sources, and perform the final consumer-backed household Bronze/Silver column-retirement archaeology before contract freeze.

This phase does **not** invent or finish architecture. Phase 055 already guarantees one production path:

```text
SourceBindingId
  -> SourceBindingPlan
  -> Gate 1
  -> Pre-Bronze
  -> bounded semantic interpretation
  -> CanonicalRoute
  -> CanonicalFragment
  -> CanonicalProductionPlan
  -> canonical identity / Gate 2
  -> canonical Bronze
  -> CanonicalIntegrityValidator
  -> Silver / Gold
```

Phase 056 challenges that finished path with external household layouts and removes any household canonical columns that survive only because of historical Shan/vendor assumptions.

## 2. Why this phase exists

The new architecture is only credible if source topology can vary while canonical financial evidence remains stable. Household data provides the cleanest topology stress test because the same financial concepts may arrive as:

- one SQLite container with many tables;
- separate CSV files;
- multiple Excel sheets;
- separate income and expense streams converging into one transaction contract;
- one combined source fanning out into categories, assets and transactions;
- transaction evidence from which a supported canonical dimension can be derived.

Certification must also prove that canonical Bronze is genuinely minimal financial evidence. Pre-Bronze may remain source-shaped; Bronze and Silver may not keep historical vendor columns merely because they once existed.

## 3. Inherited repository state

Phase 055 guarantees:

- `SourceBindingId` is the only physical tabular binding identity;
- Pre-Bronze is binding-keyed, not DatasetId-keyed;
- bounded semantic rules and `CanonicalRoute` execution are authoritative;
- `CanonicalProductionPlan` supports direct, union, provider and PFETL-owned derived production;
- satisfiability planning resolves exactly one producer per required canonical DatasetId;
- household and investment consumers use canonical Bronze only;
- old source-container DatasetIds and the migration compatibility compiler are gone;
- protected investment identities are unchanged;
- Phase 056 inherits no migration-only runtime branch.

## 4. Current codebase anchors

Use the post-055 equivalents of these v10.3.0 anchors:

- `config/sources/model.py`, `selectors.py`, `mapping.py`, `normalization.py`, `identity.py`, `validation.py`;
- `application/pipeline/source_planner.py` plus canonical production/satisfiability planners introduced in 046-051;
- `application/diagnostics/service.py` and `presentation/cli/diagnostics.py`;
- `infrastructure/warehouse/pre_bronze.py`, `bronze.py`, `silver.py`, `gold.py`;
- `infrastructure/validation/canonical_schemas.py` or its post-055 adapter;
- `contracts/datasets.py`, `semantic_inventory.py`, `capabilities.py`, canonical household contracts;
- household Silver transforms and Gold household/wealth outputs;
- replay/recovery and plan-aware warehouse code from Phases 043-044.

Build new fixtures under the existing static-evidence convention. Do not use Shan's real files as external-fixture input.

## 5. Exact target state after this phase

The following independent household topologies can produce the same canonical financial evidence without Python source changes.

### Topology A - single-container fan-out

A non-Shan SQLite database with unrelated table names provides categories, accounts/assets, currencies, opening balances and transactions. One `SourceId` owns multiple `SourceBindingId` values; each binding routes to canonical household evidence without hard-coded table names.

### Topology B - multi-source convergence

Separate income and expense CSV/Excel bindings converge through explicit `UNION` into `HOUSEHOLD_TRANSACTIONS`. Source constants establish `HouseholdTransactionKind`; assembly does not infer finance.

### Topology C - one binding, multiple canonical routes

A combined household source emits multiple canonical fragments through explicit routes. Each route is statically valid against its target contract and carries independent route provenance.

### Topology D - source and derived producer choice

Where a supported PFETL-owned derivation recipe exists, prove both a direct source producer and a derived producer can satisfy the canonical dataset, but ambiguous availability fails until configuration chooses one.

### Topology E - valid-empty evidence

A configured active binding may yield a valid zero-row canonical dataset where the target contract permits emptiness. Empty, missing, disabled and malformed remain distinct.

### Household column-retirement result

Every household Bronze and Silver column has an explicit disposition supported by consumers:

| Disposition | Meaning |
|---|---|
| KEEP | required canonical evidence/state |
| RENAME | same financial meaning, canonical name improved before freeze |
| MOVE_TO_PRE_BRONZE | source/vendor field needed only for source interpretation |
| MOVE_TO_PROVENANCE | operational lineage, not financial evidence |
| DERIVE_DOWNSTREAM | reconstructible Silver/Gold state, not Bronze evidence |
| DELETE | no supported consumer/invariant |

No household column survives solely because it appeared in MoneyManager or another historical source.

## 6. Detailed implementation sequence

### Step 1 - Freeze the external household scenario matrix

Define at least two financially equivalent scenarios represented through materially different physical topologies. Record expected canonical grains, identities and key Silver/Gold values before running the pipeline.

The matrix must cover direct production, explicit union, fan-out and at least one supported derivation/ambiguity case if the final recipe registry exposes one.

### Step 2 - Build static external evidence

Create small but relationally meaningful fixtures for:

- categories/subcategories;
- assets/accounts;
- currencies;
- opening balances;
- income/expense/transfer transactions;
- optional wealth evidence where useful.

Use deliberately different column names, date formats, table/sheet names and source IDs from Shan.

### Step 3 - Author configurations only

Each topology must be expressible using the public post-055 configuration model:

- `SourceConfig`;
- `SourceBindingConfig`;
- selectors/source schema;
- normalization and bounded semantic rules;
- `CanonicalRouteConfig`;
- canonical production selection;
- identity strategy;
- capability selection.

No test-specific source provider or fixture-specific production branch is allowed.

### Step 4 - Run diagnostics before execution

For every topology run the supported diagnostic path:

```text
validate-config
check-sources
preview-mapping
preview-identity
preview-plan
dry-run-admission
```

The plan preview must show binding -> route -> canonical producer resolution, not the old SourceDatasetConfig mental model.

### Step 5 - Prove canonical equivalence

Where two fixtures represent the same financial scenario, compare canonical household Bronze after normalizing provenance differences. Verify:

- same canonical row grain;
- same canonical transaction/category/asset meaning;
- deterministic identity according to the configured strategy;
- equivalent household Silver and Gold financial values.

### Step 6 - Prove N:M topology behavior

Add targeted assertions for:

- one SourceId -> several bindings;
- one binding -> several routes;
- several routes -> one DatasetId through explicit union;
- ambiguous source-vs-derived producer rejection;
- deterministic producer selection after explicit resolution.

### Step 7 - Certify failure semantics

Exercise:

- missing required canonical producer;
- malformed Gate-1 source schema;
- unmapped canonical enum value;
- invalid route projection;
- canonical identity collision;
- cross-dataset reference violation;
- valid-empty input.

Failures must occur at the owning boundary with actionable diagnostics and no partial publication.

### Step 8 - Household Bronze column archaeology

For every household Bronze column, trace actual production and consumers. Build a disposition ledger using repository search, DatasetContracts, transformation code and tests.

Fields such as historical `IS_DEL`, sync flags, app-package metadata, source row internals and provider/vendor artifacts must not survive Bronze unless a genuine canonical invariant proves otherwise.

### Step 9 - Household Silver column archaeology

Repeat for household Silver. Distinguish:

- canonical reconstructed state required by Gold/wealth/Tax;
- capability-owned columns;
- compatibility leftovers;
- duplicated evidence available elsewhere;
- dead columns.

Do not delete a Silver field merely because current Gold does not consume it if it is an intentional advanced analytical contract. The disposition must be explicit.

### Step 10 - Apply safe household retirement

Make only retirements proven by the ledger. Update contracts, DDL/adapters, transforms, tests and Meta/catalog together. If a proposed deletion changes financial output or removes an intentional analytical contract, stop and classify it instead of forcing the cleanup.

### Step 11 - Replay/recovery certification

Change one binding mapping and one piece of source evidence. Verify the canonical dependency graph rebuilds only affected household canonical datasets and downstream state. Exercise rollback around one failed canonical rebuild.

### Step 12 - Shan household regression

Run Shan's accepted household path and compare financial outputs against the post-055 oracle. The external fixtures must not introduce special-case code that changes Shan semantics.

## 7. Files and symbols in scope

Expected work:

- `tests/fixtures/evidence/` external household assets/configurations;
- external household certification tests;
- household canonical DatasetContracts and column metadata where retirement is proven;
- household Bronze/Silver transforms and physical schema adapters;
- diagnostics expectations for route/production plans;
- architecture guards preventing reintroduction of vendor/source fields.

Production architecture changes are out of scope unless the external fixtures expose a genuine generic defect. Any such defect must be fixed at the generic owner, not patched for the fixture.

## 8. Cross-cutting impacts

**Configuration:** proves the public shape can express different topologies without source-code edits.

**Canonical evidence:** household Bronze becomes consumer-proven rather than historically inherited.

**Identity:** derived/trusted identity semantics remain deterministic; row order and physical file naming are irrelevant.

**Replay:** binding/route changes map through canonical production dependencies.

**Warehouse:** retired columns disappear coherently from contracts and physical state.

**Observability:** lineage includes SourceId -> SourceBindingId -> route -> DatasetId -> canonical row/run context.

## 9. Tests and verification

Mandatory evidence:

- non-Shan SQLite single-container fan-out;
- CSV/Excel multi-source convergence into household transactions;
- one-binding multi-route fan-out;
- producer ambiguity and explicit resolution;
- valid-empty distinction;
- Gate-1, semantic, Gate-2 and canonical-integrity failures;
- deterministic rerun and source-row reorder;
- replay after mapping/evidence change;
- rollback/recovery smoke;
- household Bronze/Silver disposition ledger complete;
- all applied retirements covered by contract/physical parity tests;
- Shan household financial regression green.

## 10. Explicit non-goals

Do not:

- add a new transformation language;
- add arbitrary joins/aggregations to semantic mapping;
- change household financial methodology;
- build Config Studio;
- broaden investment certification into this phase;
- freeze the complete public contract universe yet;
- retain vendor columns merely to make migration easier.

## 11. Completion checklist

- [ ] At least three materially different household source topologies satisfy the same canonical household contracts without source-code changes.
- [ ] Explicit union, fan-out and producer-resolution paths are proven through real static evidence, not only planner unit tests.
- [ ] Empty, missing, disabled and malformed household evidence remain observably distinct.
- [ ] Every household Bronze column has a consumer-backed disposition and all approved retirements are applied.
- [ ] Every household Silver column has an explicit contract disposition; dead/vendor-derived fields are removed without narrowing intentional analytical contracts.
- [ ] Diagnostics expose SourceBindingId, route and canonical producer reasoning for the external fixtures.
- [ ] Replay/recovery after household binding or mapping change converges without stale canonical state.
- [ ] Shan household Silver/Gold financial outputs remain equivalent after the retirement pass.

## 12. Commit boundary

Use `pfetl-conventional-commits`. Keep external fixture/certification work and proven household contract/schema retirement in reviewable semantic groups; let the skill own staging and messages. Do not mix unrelated investment work into these commits.

## 13. Handoff to Phase 057

Phase 057 may assume household topology generalization is externally proven and the household Bronze/Silver contract surface has completed its final consumer-backed retirement pass. It must apply the same standard to domestic/foreign investment, reference and provider evidence while preserving all protected financial identities established in Phase 055.

## Phase completion record

```text
Phase:
Target release:
External topologies certified:
Column ledger closed:
Files changed:
Schema changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Shan regression:
Recovery/replay verification:
Observability verification:
Compatibility path remaining: NONE
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
