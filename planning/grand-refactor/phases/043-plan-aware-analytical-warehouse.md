# Phase 043 - Plan-Aware Analytical Warehouse

**Target release:** v10.2.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 042  
**Next:** Phase 044  
**Risk:** High

## 1. Outcome

Make Silver/Gold DDL creation, publication, Meta/catalog and cleanup derive from the active `ExecutionPlan` contract set. Disabled capabilities must not leave stale analytical tables masquerading as current truth.

At phase end the physical analytical warehouse matches the selected financial capabilities.

## 2. Why this phase exists

Until now PFETL intentionally retained the full Silver/Gold schema while proving logical capability composition. That compatibility bridge is now harmful: a user can disable a capability yet still see an old table from a previous run. Physical state must become plan-aware.

## 3. Inherited repository state

Phase 042 guarantees every major engine is plan-driven and active Silver/Gold DatasetIds are correct. v10 ingestion/recovery is stable. Current Silver/Gold loaders likely still create/rebuild all registry tables.

## 4. Current codebase anchors

Inspect current:
- Silver DDL/schema builder;
- Gold DDL/schema builder;
- Silver/Gold loaders/publication order;
- `DATA_CONTRACT_REGISTRY`;
- Meta catalog/fingerprint;
- backup/restore;
- any presentation/Power BI code assuming all tables exist;
- tests for schema completeness.

Trace physical table dependencies such as views/foreign keys/indexes before conditional creation.

## 5. Exact target state after this phase

For a run:
```text
ExecutionPlan.active_silver_datasets
 -> create/rebuild exactly active Silver tables

ExecutionPlan.active_gold_datasets
 -> create/rebuild exactly active Gold tables

Meta
 -> catalog/fingerprint exactly active contract universe
```

When a capability was active previously and is now disabled:
- its Silver/Gold tables are deliberately removed during rebuild/transition;
- stale data cannot survive and look current.

Common/core tables explicitly owned outside optional capabilities remain active as defined by capability graph.

## 6. Detailed implementation sequence

### Step 1 - Build active contract resolver
From ExecutionPlan return ordered Silver/Gold DataContracts. Validate DatasetId/layer/producer consistency.

### Step 2 - Make Silver DDL active-set-aware
Create/rebuild only active tables. Preserve publication order/dependencies.

### Step 3 - Make Gold DDL active-set-aware
Same discipline.

### Step 4 - Implement stale-table cleanup
Compare existing managed analytical tables with target active set. Drop managed inactive tables inside DuckDB transaction. Never drop unknown/user tables.

### Step 5 - Update Meta/catalog
Fingerprint/catalog active contract set + plan fingerprint. A partial warehouse is healthy, not "missing tables."

### Step 6 - Update backup/restore/integrity
Integrity validates expected active set from persisted run/plan provenance, not global registry.

### Step 7 - Presentation behavior
If CLI/Desktop/Power BI integration enumerates tables, it must tolerate capability-specific absence and expose active capabilities rather than treating absence as corruption.

### Step 8 - Capability-switch matrix
Run full -> household-only -> domestic investments -> full. At each step assert exact managed table set and no stale data.

### Step 9 - Recovery
Failure during stale-table cleanup/rebuild rolls back DuckDB transaction completely.

## 7. Files and symbols in scope

Modify:
- Silver/Gold schema builders/loaders;
- contract registry helpers;
- Meta/catalog;
- integrity/backup/restore;
- presentation table enumeration if required;
- tests.

Do not change capability graph or financial formulas.

## 8. Cross-cutting impacts

**Persistence:** major physical-schema behavior change. Managed inactive tables are dropped transactionally.

**Identity:** unaffected.

**Provenance:** Meta links active contract universe to plan/config fingerprints.

**Observability:** publication/schema events include active counts/plan fingerprint, not giant table lists unless diagnostic.

**Performance:** partial plans should reduce DDL/publication work. Full plan within baseline.

## 9. Tests and verification

Required:
- household-only exact table set;
- full exact table set;
- domestic-only exact set;
- full->partial removes stale managed tables;
- partial->full recreates correctly;
- unknown/user table not dropped;
- Meta considers partial state healthy;
- backup/restore partial warehouse;
- failure rollback during cleanup;
- full Shan outputs unchanged.

## 10. Explicit non-goals

Do not:
- delete Bronze/Pre-Bronze based on analytical capabilities unless source plan explicitly owns that behavior;
- drop unknown tables;
- change financial contracts;
- alter capability dependencies.

## 11. Completion checklist

- [ ] Silver DDL plan-aware.
- [ ] Gold DDL plan-aware.
- [ ] Stale managed tables removed safely.
- [ ] Meta/catalog plan-aware.
- [ ] Backup/restore/integrity plan-aware.
- [ ] Capability-switch matrix green.
- [ ] Full plan remains identical.

## 12. Commit boundary

```text
feat(warehouse): make analytics plan-aware
```

## 13. Handoff to Phase 044

Phase 044 may assume both execution and physical warehouse state reflect the selected plan. It will certify generalized recovery/replay across configuration changes, mapping changes and identity-policy changes rather than only ordinary file failures.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commit:
```

A phase is incomplete if any required exit assertion is false.
