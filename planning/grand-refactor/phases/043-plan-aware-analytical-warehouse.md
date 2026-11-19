# Phase 043 - Plan-Aware Analytical Warehouse

**Target release:** v10.2.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 042  
**Next:** Phase 044  
**Risk:** High

## 1. Outcome

Make Silver/Gold DDL creation, publication, Meta/catalog and cleanup derive from the active `ExecutionPlan` contract set. Disabled capabilities must not leave stale analytical tables masquerading as current truth.

Standardize and unify physical table names across all Medallion layers (`pre_bronze`, `bronze`, `silver`, `gold`) strictly following the **Capability Graph** (`<schema>.<capability>_<entity>`), completely demolishing legacy technical prefixes (`pb_*`, `r_*`, `d_*`, `f_*`).

At phase end the physical analytical warehouse matches the selected financial capabilities with a unified, professional naming hierarchy from Pre-Bronze to Gold.

## 2. Why this phase exists

Until now PFETL intentionally retained the full Silver/Gold schema while proving logical capability composition. That compatibility bridge is now harmful: a user can disable a capability yet still see an old table from a previous run. Physical state must become plan-aware.

Furthermore, table naming historically accumulated disparate technical conventions:
- Pre-Bronze used hybrid prefixes (`pb_household_*`, `pb_market_*`, `pb_investment_*`);
- Bronze used legacy raw prefixes from v9 (`r_Category`, `r_Stock_Transactions`, `r_Currency_Rates`);
- Silver used Kimball dimensional prefixes (`d_*`, `f_*`);
- Gold used freeform PascalCase (`Core_Monthly_Fact`, `Wealth_FIRE_Analytics`).

With generalized ingestion certified and capabilities composed (Phases 039–042), Phase 043 unifies physical naming across all layers under the Capability Graph, creating a cohesive, professional analytical data model.

## 3. Inherited repository state

Phase 042 guarantees every major engine is plan-driven and active Silver/Gold DatasetIds are correct. v10 ingestion/recovery is stable. Current Silver/Gold loaders likely still create/rebuild all registry tables.

## 4. Current codebase anchors

Inspect current:
- Pre-Bronze physical table catalog (`contracts/pre_bronze.py`);
- Bronze DDL and schema builder (`infrastructure/warehouse/schema/bronze.py`);
- Silver DDL and schema builder (`infrastructure/warehouse/schema/silver.py`);
- Gold DDL and schema builder (`infrastructure/warehouse/schema/gold.py`);
- Silver/Gold loaders and publication order;
- `DATA_CONTRACT_REGISTRY` and semantic inventory (`contracts/semantic_inventory.py`);
- Meta catalog/fingerprint;
- presentation/Power BI and export sinks;
- tests for schema completeness and boundaries.

Trace physical table dependencies such as views/foreign keys/indexes before conditional creation and renaming.

## 5. Exact target state after this phase

### Unified Capability-Linked Table Naming Hierarchy

Every table across all 4 Medallion layers strictly adopts the capability namespace `<capability>_<entity>`:

| Layer | Schema | Canonical Namespace Pattern | Example Table Names |
|---|---|---|---|
| **Pre-Bronze** | `pre_bronze` | `<capability>_<entity>` | `pre_bronze.household_transactions`, `pre_bronze.investments_stock_orders` |
| **Bronze** | `bronze` | `<capability>_<entity>` | `bronze.household_transactions`, `bronze.investments_stock_orders` |
| **Silver** | `silver` | `<capability>_<entity>` | `silver.household_transactions`, `silver.investments_purchases`, `silver.investments_lots` |
| **Gold** | `gold` | `<capability>_<entity>` | `gold.household_monthly_summary`, `gold.investments_portfolio_summary`, `gold.wealth_fire_analytics` |

All legacy prefixes (`pb_*`, `r_*`, `d_*`, `f_*`) are permanently demolished.

### Plan-Aware Table Lifecycles

For a run:
```text
ExecutionPlan.active_pre_bronze_datasets
 -> create/rebuild exactly active Pre-Bronze tables

ExecutionPlan.active_bronze_datasets
 -> create/rebuild exactly active Bronze tables

ExecutionPlan.active_silver_datasets
 -> create/rebuild exactly active Silver tables

ExecutionPlan.active_gold_datasets
 -> create/rebuild exactly active Gold tables

Meta
 -> catalog/fingerprint exactly active contract universe
```

When a capability was active previously and is now disabled:
- its analytical tables across layers are deliberately removed during rebuild/transition;
- stale data cannot survive and look current.

Common/core tables explicitly owned outside optional capabilities remain active as defined by the capability graph.

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

### Step 9 - Capability-unified physical table cutover
Rename all physical tables across `pre_bronze`, `bronze`, `silver`, and `gold` to follow `<capability>_<entity>`. Demolish all legacy prefixes (`pb_*`, `r_*`, `d_*`, `f_*`). Update DataContract registry, DDL schemas, loaders, and downstream queries.

### Step 10 - Architecture guards against legacy prefixes
Add AST architectural tests verifying zero physical tables in DuckDB declare `r_`, `d_`, `f_`, or `pb_` prefixes.

### Step 11 - Recovery
Failure during stale-table cleanup/rebuild rolls back DuckDB transaction completely.

## 7. Files and symbols in scope

Modify:
- Pre-Bronze, Bronze, Silver, Gold schema builders/loaders;
- contract registry and semantic inventory;
- Meta/catalog;
- integrity/backup/restore;
- presentation table enumeration if required;
- tests.

Do not change capability graph or financial formulas.

## 8. Cross-cutting impacts

**Persistence:** major physical-schema behavior change. Managed inactive tables are dropped transactionally, and all tables adopt the `<capability>_<entity>` naming standard.

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
- legacy table prefix guard (assert zero `r_*`, `d_*`, `f_*`, `pb_*` tables);
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

- [ ] Physical table names unified across Medallion layers under Capability Graph.
- [ ] Legacy table prefixes (`pb_*`, `r_*`, `d_*`, `f_*`) permanently demolished.
- [ ] Silver DDL plan-aware.
- [ ] Gold DDL plan-aware.
- [ ] Stale managed tables removed safely.
- [ ] Meta/catalog plan-aware.
- [ ] Backup/restore/integrity plan-aware.
- [ ] Capability-switch matrix green.
- [ ] Full plan remains identical.

## 12. Commit boundary

```text
feat(warehouse): align warehouse tables to capability graph
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
