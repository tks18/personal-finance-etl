# Phase 004 - Semantic Bronze Naming and Rebuild Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 003  
**Next:** Phase 005  
**Risk:** Medium-High

## 1. Outcome

Rename all 20 Bronze physical tables and runtime extraction attributes to semantic snake_case while preserving source-oriented content and sync behavior.

## 2. Why this phase exists

- Current names such as `r_SQLite_ZCategory` and `r_MF_Market_Data` expose implementation history rather than evidence meaning.
- Bronze content is intentionally not being canonicalized; only vocabulary and maintainability change.
- DuckDB is rebuildable derived state, so compatibility aliases are unnecessary.

## 3. Inherited repository state

- Phase 003 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- `infrastructure/warehouse/contracts.py::BRONZE_CONTRACT_REGISTRY`
- `infrastructure/warehouse/bronze.py`
- `infrastructure/warehouse/schema/bronze.py`
- `contracts/extraction.py::ExtractionResult`
- ingestion coordinator/market sync output attributes
- Bronze-focused tests and Meta row-count publication

## 5. Exact target state after this phase

Rename all 20 Bronze physical tables and runtime extraction attributes to semantic snake_case while preserving source-oriented content and sync behavior.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Capture a clean pre-cutover Bronze row-count/content oracle

Capture a clean pre-cutover Bronze row-count/content oracle.

### Step 2 - Apply the frozen 20-table old→new semantic map, including household, reference, statement and provider-generated evidence

Apply the frozen 20-table old→new semantic map, including household, reference, statement and provider-generated evidence.

### Step 3 - Rename matching extraction/runtime attributes where this removes historical vocabulary; keep source column content unchanged

Rename matching extraction/runtime attributes where this removes historical vocabulary; keep source column content unchanged.

### Step 4 - Update Bronze registry, upsert/delete logic, Meta row-count/table references and recovery rebuild paths

Update Bronze registry, upsert/delete logic, Meta row-count/table references and recovery rebuild paths.

### Step 5 - Rebuild DuckDB from retained evidence rather than migrating old Bronze tables in place

Rebuild DuckDB from retained evidence rather than migrating old Bronze tables in place.

### Step 6 - Compare row counts, source keys/hashes and representative content across old/new tables

Compare row counts, source keys/hashes and representative content across old/new tables.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- DuckDB is rebuilt; Raw Store and Control Plane must remain intact.

## 9. Tests and verification

- [x] Exactly 20 target Bronze tables are published.
- [x] No `bronze.r_*` physical name remains.
- [x] Full vs incremental behavior for every sync category matches v11.0.0.
- [x] Raw Store and Control Plane histories are preserved.
- [x] Silver/Gold financial oracle remains unchanged after rebuild.

## 10. Explicit non-goals

- Do not rename Silver/Gold yet.
- Do not remove Bronze provenance columns or canonicalize source fields.

## 11. Completion checklist

- [x] Exit assertion: Exactly 20 target Bronze tables are published.
- [x] Exit assertion: No `bronze.r_*` physical name remains.
- [x] Exit assertion: Full vs incremental behavior for every sync category matches v11.0.0.
- [x] Exit assertion: Raw Store and Control Plane histories are preserved.
- [x] Exit assertion: Silver/Gold financial oracle remains unchanged after rebuild.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 005

The next phase may assume only the verified state above. It begins **Silver Column Disposition and Consumer Archaeology** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 004
Target release: v11.2.0
Files changed:
  - src/personal_finance_etl/contracts/extraction.py
  - src/personal_finance_etl/infrastructure/warehouse/contracts.py
  - src/personal_finance_etl/infrastructure/warehouse/bronze.py
  - src/personal_finance_etl/infrastructure/control_plane/artifact_repository.py
  - src/personal_finance_etl/application/ingestion/coordinator.py
  - src/personal_finance_etl/application/ingestion/asset_strategies.py
  - src/personal_finance_etl/application/ingestion/market_sync.py
  - src/personal_finance_etl/application/pipeline/transformer.py
  - docs/reference/bronze-data-contracts.md
  - tests/test_core_pipeline_observability.py
  - tests/test_forensic_debuggability.py
  - tests/test_phase3_reference_data_and_instrument_master.py
  - tests/test_phase4_semantic_bronze_naming_and_rebuild.py
Contracts/schema changed:
  - 20 Bronze physical tables renamed from bronze.r_* to semantic snake_case.
  - ExtractionResult attributes harmonized to 1:1 matching table suffixes.
Financial formulas changed: None (0 formulas touched).
Protected identity comparison: 100% byte-for-byte equivalent (0 identity changes).
Focused tests: tests/test_phase4_semantic_bronze_naming_and_rebuild.py (5 passed).
Full test suite: 204 / 204 passed in 14.43s.
Real-data verification: Rebuilt live DuckDB against Shan's test data (131,287 rows across 20 Bronze tables, 24 Silver tables, 22 Gold tables).
Power BI verification: Gold analytical layer topology preserved (22 tables).
Observability/recovery verification: Single-emitter observability, Control Plane, Raw Store intact.
Compatibility/transitional state remaining: None. Zero permanent compatibility views created.
Semantic commit groups: 5 atomic Conventional Commits staged in .commit_overrides.json.
Exit assertions green: yes
```
