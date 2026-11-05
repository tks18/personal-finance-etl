# Phase 013 - Canonical Silver Vocabulary Cutover

**Target release:** v9.6.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 012  
**Next:** Phase 014  
**Risk:** High

## 1. Outcome

Close the Phase-008 Silver migration manifest: migrate all remaining approved canonical renames/removals across household, investment, Tax and wealth-related state, adapt Gold consumers, and establish the generalized Silver vocabulary as the sole canonical financial-state contract.

## 2. Why this phase exists

After Phases 009-012, the difficult semantic leaks are isolated. Remaining vocabulary cleanup must be completed before capability planning and configurable Bronze are allowed to depend on Silver requirements, otherwise future contracts would encode historical source naming.

## 3. Inherited repository state

Phase 012 guarantees:
- canonical provenance;
- source-independent financial classification;
- provider-neutral market vocabulary;
- Phase-008 manifest remains authoritative;
- Gold dependency manifest identifies downstream consumers.

No financial methodology has changed.

## 4. Current codebase anchors

Primary anchors:
- Phase-008 533-column disposition manifest
- `infrastructure/warehouse/schema/silver.py`
- all producers named by Silver `DataContract`
- Gold dependency manifest
- Gold producers and presentation compatibility tests
- registry/meta fingerprint tests.

## 5. Exact target state after this phase

The Phase-008 manifest has no open migration action for canonical vocabulary except fields intentionally retained.

For every `RENAME`:
- canonical name is sole Silver name;
- all producers/consumers use it.

For every `REMOVE_AFTER_CONSUMER_MIGRATION`:
- zero consumers;
- field absent from DDL.

For every `RETAIN`:
- reason remains valid.

Gold continues to expose its existing externally required names where compatibility is deliberate; compatibility aliases belong at Gold/presentation boundary, never back in Silver.

## 6. Detailed implementation sequence

### Step 1 - Partition manifest by financial family
Create deterministic work order: household dimensions/facts, investment dimensions/facts, Tax/reconciliation state, common/reference.

### Step 2 - Apply canonical renames additively family-by-family
For each rename, first update producer to emit canonical field and add equality regression where old/new coexist briefly.

### Step 3 - Migrate domain/application consumers
Move all Silver consumers to canonical names. Search repository for old names after each family.

### Step 4 - Migrate Gold producers using dependency manifest
Gold values must remain identical. Preserve externally required Gold vocabulary explicitly.

### Step 5 - Remove aliases/residue
After zero-consumer proof, remove old Silver names from producer and DDL.

### Step 6 - Close manifest
Every row must be in a terminal state. `REVIEW_REQUIRED` count must be zero or each remaining row must be intentionally retained with documented canonical reason.

### Step 7 - Freeze architecture
Add tests that Silver DDL and manifest remain synchronized and prohibited source/provider vocabulary cannot return.

### Step 8 - Full financial oracle
Run complete Shan pipeline and compare all Silver/Gold financial outputs and protected IDs.

## 7. Files and symbols in scope

Modify Silver DDL/producers, affected domain/application consumers, Gold producers, manifest and tests.

Do not rename physical Silver table names unless the manifest/target model explicitly requires it; this phase is primarily column vocabulary. Avoid multiplying migration surface.

## 8. Cross-cutting impacts

**Persistence:** Silver rebuild uses new canonical schema. Meta fingerprint changes are intentional.

**Identity:** no identity algorithm changes. If a renamed field participates in an identity hash, preserve the value and input ordering exactly.

**Observability:** event payload field names may change only if they were canonical financial names; preserve compatibility where observability contracts are external/stable.

**Performance:** renames/projections should not add materialization.

**Compatibility:** Power BI/presentation compatibility belongs at Gold/presentation boundary.

## 9. Tests and verification

Required:
- manifest coverage still 533/533 against starting schema and terminal mapping to final schema;
- zero unresolved source/provider residue;
- repository search for deprecated names;
- Gold dependency tests;
- all protected ID fixtures unchanged;
- full Shan Silver/Gold equivalence;
- schema/registry fingerprint tests deliberately updated;
- quality gate.

## 10. Explicit non-goals

Do not:
- change table grains;
- change formulas;
- redesign Gold methodology;
- introduce capability skipping;
- introduce source mapping runtime;
- touch Bronze schemas.

## 11. Completion checklist

- [x] Every Silver manifest row has terminal disposition.
- [x] Deprecated canonical names have zero production references.
- [x] Gold producers consume canonical Silver.
- [x] External compatibility is isolated outside Silver.
- [x] Protected IDs unchanged.
- [x] Financial outputs unchanged.
- [x] Silver canonical model is frozen for later phases.

## 12. Commit boundary

```text
refactor(silver): complete canonical vocabulary cutover
```

## 13. Handoff to Phase 014

Phase 014 may treat Silver as the stable canonical financial-state model. Capability ownership can now be derived against final canonical datasets rather than historical/source-shaped contracts.

## Phase completion record

```text
Phase: 013
Target release: v9.6.4
Files changed:
- src/personal_finance_etl/infrastructure/warehouse/schema/silver.py
- src/personal_finance_etl/domain/household/transforms/asset_dimensions.py
- src/personal_finance_etl/domain/household/transforms/expense_dimensions.py
- src/personal_finance_etl/domain/household/transforms/income_dimensions.py
- src/personal_finance_etl/domain/household/transforms/reference_dimensions.py
- src/personal_finance_etl/domain/household/transforms/transactions.py
- src/personal_finance_etl/domain/household/transforms/calendar.py
- src/personal_finance_etl/domain/household/ledger.py
- src/personal_finance_etl/domain/fire/inflation.py
- src/personal_finance_etl/domain/investments/transforms/common.py
- src/personal_finance_etl/domain/investments/transforms/indian_equity.py
- src/personal_finance_etl/domain/investments/transforms/mutual_funds.py
- src/personal_finance_etl/domain/investments/transforms/us_equity.py
- src/personal_finance_etl/domain/investments/valuation/market_state.py
- src/personal_finance_etl/domain/market/benchmarks.py
- src/personal_finance_etl/domain/market/fx.py
- src/personal_finance_etl/contracts/semantic_inventory.py
- src/personal_finance_etl/contracts/silver_column_dispositions.json
- tests/contracts/test_semantic_inventory.py
- tests/architecture/test_boundaries.py
Schema changed: YES (89 legacy residue/provenance columns dropped across 16 Silver tables; f_Opening_Balances canonicalized)
Runtime behavior changed: NO (0 downstream financial impacts; 100% canonical state)
Financial formulas changed: NO
Focused tests: tests/contracts/test_semantic_inventory.py, tests/architecture/test_boundaries.py, tests/domain/test_household_wealth_fire.py
Architecture tests: PASS (tests/architecture/test_boundaries.py)
Real-data run: PASS (clean rebuild with 428 active Silver columns)
Performance check: PASS (no change in materialization)
Compatibility path still present: NO (deprecated residue removed from Silver)
Old path deleted: YES
Exit assertions green: YES (100% active Silver columns reach RETAIN terminal disposition)
Commit: pending
```

A phase is incomplete if any required exit assertion is false.
