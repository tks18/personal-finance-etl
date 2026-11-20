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

### Plan-Aware Table and Column Lifecycles

For a run:
```text
ExecutionPlan.active_pre_bronze_datasets
 -> create/rebuild exactly active Pre-Bronze tables

ExecutionPlan.active_bronze_datasets
 -> create/rebuild exactly active Bronze tables

ExecutionPlan.active_silver_datasets + active_column_inventory
 -> create/rebuild exactly active Silver tables with strictly active columns

ExecutionPlan.active_gold_datasets + active_column_inventory
 -> create/rebuild exactly active Gold tables with strictly active columns

Meta
 -> catalog/fingerprint exactly active contract and column universe
```

When a capability was active previously and is now disabled:
- its analytical tables across layers are deliberately removed during rebuild/transition;
- within shared/composite tables, columns belonging strictly to disabled capabilities are physically omitted from table DDL;
- stale data or phantom empty columns cannot survive and masquerade as current truth.

Common/core tables and columns explicitly owned outside optional capabilities remain active as defined by the capability graph.

## 6. Detailed implementation sequence

### Step 0 - Relocate [capabilities] Configuration Strictly to settings.toml
Move capability selection strictly into runtime execution settings (`settings.toml`), completely removing it from the evidence catalog (`sources.toml`):
- Decouple data source topology from execution scope: `sources.toml` strictly represents the evidence catalog (files, tables, columns, normalizations), while `settings.toml` represents the runtime execution profile (output DB, logs, retention, and active capabilities).
- Add `capabilities: CapabilitySelection = Field(default_factory=CapabilitySelection)` to `Settings` in `src/personal_finance_etl/config/settings.py`.
- Remove `capabilities` from `SourceConfiguration`. Zero backwards compatibility fallback: capabilities are exclusively configured in `settings.toml`.
- Users configure active capabilities in `settings.toml`:
  ```toml
  [capabilities]
  enabled = ["household_core", "wealth", "fire"]
  ```
- Allow CLI flags (e.g. `--capability household_core`) to override `Settings.capabilities`.
- `ExecutionPlan` resolves from `Settings.capabilities` as the sole runtime authority.

### Step 1 - Build active contract and column resolver
From ExecutionPlan return ordered Silver/Gold DataContracts and the exact active column subset from `CapabilityColumnInventory`. Validate DatasetId/layer/column/producer consistency.

### Step 2 - Make Silver DDL active-set and active-column-aware
Generate dynamic `CREATE TABLE` DDL containing strictly active columns for active Silver contracts. Preserve publication order and dependencies.

### Step 3 - Make Gold DDL active-set and active-column-aware
Generate dynamic `CREATE TABLE` DDL containing strictly active columns for active Gold marts. For composite marts (`gold.investments_by_isin`, `gold.household_monthly_summary`), exclude benchmark, foreign FX, and tax columns when their respective capabilities are inactive.

### Step 4 - Implement stale-table and stale-column cleanup
Compare existing managed analytical tables with target active set. Drop managed inactive tables inside DuckDB transaction. Re-create tables with updated dynamic schemas when capabilities toggle. Never drop unknown/user tables.

### Step 5 - Update Meta/catalog
Fingerprint/catalog active contract and column universe + plan fingerprint. A partial warehouse with pruned columns is healthy and deliberate, not "missing columns."

### Step 6 - Update backup/restore/integrity
Integrity validates expected active table and column set from persisted run/plan provenance, not global registry.

### Step 7 - Presentation behavior
If CLI/Desktop/Power BI integration enumerates tables or columns, it must tolerate capability-specific absence and expose active capabilities rather than treating absence as corruption.

### Step 8 - Capability-switch matrix & Automated Multi-Fixture Suite
Author dedicated `sources.toml` test fixtures covering distinct capability configurations:
- `sources_matrix_household_only.toml`: pure household (`HOUSEHOLD_CORE`).
- `sources_matrix_domestic_investments.toml`: domestic investment accounting (`HOUSEHOLD_CORE` + `INVESTMENT_ACCOUNTING`).
- `sources_matrix_investments_benchmark.toml`: domestic + benchmark (`HOUSEHOLD_CORE` + `INVESTMENT_ACCOUNTING` + `BENCHMARK_ENRICHMENT`).
- `sources_matrix_investments_foreign.toml`: domestic + US holdings + FX (`HOUSEHOLD_CORE` + `INVESTMENT_ACCOUNTING` + `FOREIGN_ASSET_ENRICHMENT`).
- `sources_matrix_investments_tax.toml`: domestic + tax rules (`HOUSEHOLD_CORE` + `INVESTMENT_ACCOUNTING` + `TAX`).
- `sources_matrix_wealth_fire.toml`: household + wealth + FIRE without equities (`HOUSEHOLD_CORE` + `WEALTH` + `FIRE`).
- `sources_matrix_full.toml`: all 7 capabilities.

Execute automated transitions across the matrix (e.g. Full -> Household Only -> Domestic Investments -> Full):
- At each step query DuckDB catalog directly (`information_schema.tables`, `PRAGMA table_info(...)`).
- Assert exact managed table set: tables for disabled capabilities do NOT exist in DuckDB.
- Assert exact column set: columns belonging to disabled capabilities are physically absent from table DDL.
- Verify zero stale data, zero ghost tables, and zero phantom empty columns.

### Step 9 - Capability-unified physical table cutover
Rename all physical tables across `pre_bronze`, `bronze`, `silver`, and `gold` to follow `<capability>_<entity>`. Demolish all legacy prefixes (`pb_*`, `r_*`, `d_*`, `f_*`). Update DataContract registry, DDL schemas, loaders, and downstream queries.

### Step 10 - Architecture guards against legacy prefixes
Add AST architectural tests verifying zero physical tables in DuckDB declare `r_`, `d_`, `f_`, or `pb_` prefixes.

### Step 11 - Medallion Telemetry & Stage Narrative Standardization
Standardize pipeline telemetry and presentation logging to reflect the modern Medallion architecture:
- Update UI progress narrative and CLI output to display modern Medallion stage transitions:
  - `Phase 1/5 [Discovery]: Discovering files and synchronizing Control Plane artifacts`
  - `Phase 2/5 [Ingestion]: Admitting datasets into Pre-Bronze & Bronze Lakehouse`
  - `Phase 3/5 [Harmonization]: Transforming normalized state into Silver Lakehouse`
  - `Phase 4/5 [Analytics]: Executing quantitative, tax, and FIRE models`
  - `Phase 5/5 [Gold Marts]: Materializing decision-ready Gold analytical surfaces`
- Emit structured layer-level lifecycle events (`PRE_BRONZE_ADMISSION`, `BRONZE_DELTA_UPSERT`, `SILVER_HARMONIZATION`, `GOLD_MART_MATERIALIZATION`) capturing exact active table counts, row counts, and capability tags.
- Ensure detailed developer debug logs in `outputs/logs/` capture forensic table transitions (created, replaced, pruned) correlated with capability plan IDs.

### Step 12 - Recovery
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
- automated capability matrix tests running headless pipelines against dedicated `sources_matrix_*.toml` fixtures;
- household-only exact table set (assert all investment and tax tables strictly absent from DuckDB catalog);
- full exact table set;
- domestic-only exact set (assert FX, benchmark, and tax tables absent from DuckDB);
- full->partial removes stale managed tables transactionally;
- partial->full recreates tables correctly with clean schemas;
- physical column omission assertions in DuckDB (`PRAGMA table_info(...)` shows zero columns for disabled capabilities in composite tables);
- legacy table prefix guard (assert zero `r_*`, `d_*`, `f_*`, `pb_*` tables in DuckDB);
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

- [x] Physical table names unified across Medallion layers under Capability Graph.
- [x] Legacy table prefixes (`pb_*`, `r_*`, `d_*`, `f_*`) permanently demolished.
- [x] Silver DDL plan-aware and column-aware.
- [x] Gold DDL plan-aware and column-aware.
- [x] Silver and Gold DDL dynamically include strictly active columns from CapabilityColumnInventory.
- [x] Inactive capability columns physically omitted from DuckDB tables (zero phantom null columns).
- [x] Dedicated capability matrix fixtures created under `tests/fixtures/config/` (`sources_matrix_*.toml`).
- [x] Automated capability matrix tests verify DuckDB table and column physical absence across transitions.
- [x] Stale managed tables removed safely.
- [x] Meta/catalog plan-aware.
- [x] Backup/restore/integrity plan-aware.
- [x] Capability-switch matrix green.
- [x] Full plan remains identical.
- [x] Modern Medallion stage narrative and structured layer telemetry certified.

## 12. Commit boundary

```text
feat(warehouse): align warehouse tables to capability graph
```

## 13. Handoff to Phase 044

Phase 044 may assume both execution and physical warehouse state reflect the selected plan. It will certify generalized recovery/replay across configuration changes, mapping changes and identity-policy changes rather than only ordinary file failures.

## Phase completion record

```text
Phase: 043-plan-aware-analytical-warehouse
Target release: v10.2.0
Files changed: 63
Schema changed: YES (dynamic plan-aware DDL, column pruning, unified physical table naming)
Runtime behavior changed: YES (capabilities authority in Settings; inactive tables and pruned columns omitted from DuckDB)
Financial formulas changed: NO
Focused tests: tests/application/test_plan_aware_warehouse.py, tests/architecture/test_table_naming_guards.py
Architecture tests: tests/architecture/test_boundaries.py, tests/architecture/test_table_naming_guards.py
Real-data run: PASS (live Shan settings updated with [capabilities])
Performance check: PASS (fast audit 1.92s)
Compatibility path still present: NO (zero backwards-compatibility in sources.toml)
Old path deleted: YES (legacy prefixes and source capabilities completely demolished)
Exit assertions green: YES
Commit: feat(warehouse): align warehouse tables to capability graph
```

A phase is incomplete if any required exit assertion is false.
