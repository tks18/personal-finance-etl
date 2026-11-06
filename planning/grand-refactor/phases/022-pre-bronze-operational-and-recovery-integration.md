# Phase 022 - Pre-Bronze Operational and Recovery Integration

**Target release:** v9.9.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 021  
**Next:** Phase 023  
**Risk:** High

## 1. Outcome

Integrate Pre-Bronze into PFETL's operational truth: Meta/catalog visibility, integrity/healing expectations, backup/restore, rollback and split-commit recovery. At phase end Pre-Bronze is as operationally trustworthy as the existing warehouse layers, although no production source uses it yet.

## 2. Why this phase exists

A new persistence layer is dangerous if normal writes work but recovery tooling ignores it. PFETL's existing enterprise-grade local recovery semantics are part of the financial correctness boundary. Production migration is forbidden until Pre-Bronze participates in them.

## 3. Inherited repository state

Phase 021 guarantees transactional Pre-Bronze persistence with artifact-key provenance. Existing lifecycle still commits DuckDB first and SQLite second and uses `RECOVERY_REQUIRED` on split commit.

No production source uses Pre-Bronze.

## 4. Current codebase anchors

Anchors:
- Meta schema/catalog/layer and healing code
- warehouse backup/restore services
- integrity validation
- stale-run/split-commit recovery
- `PipelineLifecycle.commit()` / failure handling
- tests for backup, restore, Meta healing, recovery
- current list of managed DuckDB schemas/tables.

## 5. Exact target state after this phase

Operational model after phase:
```text
DuckDB transaction
  pre_bronze
  bronze
  silver
  gold
  meta
COMMIT DuckDB
COMMIT SQLite Control Plane
```

Meta/catalog can describe Pre-Bronze datasets/tables where appropriate without pretending source-shaped columns are canonical contracts.

Backup includes Pre-Bronze.
Restore validates/reconstructs it.
Rollback/recovery never leaves Pre-Bronze outside the warehouse consistency model.

Meta healing uses explicit artifact/source provenance, not new filename assumptions.

## 6. Detailed implementation sequence

### Step 1 - Inventory every warehouse-management path
Search for hard-coded schema lists and table enumeration in backup, restore, integrity, Meta and recovery.

### Step 2 - Add Pre-Bronze catalog semantics
Decide what Meta records: dataset/table/provenance/persistence metadata, not a canonical financial schema fingerprint unless justified.

### Step 3 - Backup inclusion
Create fixture with Pre-Bronze + Bronze state, backup, inspect backup/restore target contains both.

### Step 4 - Restore inclusion
Restore into clean temporary DB. Assert Pre-Bronze rows/provenance equal source.

### Step 5 - Rollback/failure tests
Inject failure after Pre-Bronze write before Bronze. DuckDB rollback removes Pre-Bronze mutation.

### Step 6 - Split-commit recovery test
Simulate DuckDB commit including Pre-Bronze followed by SQLite commit failure. Existing `RECOVERY_REQUIRED` path must converge on next successful run without inventing a Pre-Bronze-specific recovery protocol.

### Step 7 - Meta healing
Where healing reconstructs warehouse metadata from Control Plane, include Pre-Bronze state only when enough authoritative information exists. Never synthesize source-shaped columns from filenames.

### Step 8 - Architecture guard
Any future managed warehouse schema enumeration must include Pre-Bronze or use a centralized registry rather than duplicated hard-coded lists.

## 7. Files and symbols in scope

Modify operational warehouse/Meta/backup/restore/recovery modules and tests.

Do not modify source providers, mapping engine, financial engines or production discovery.

## 8. Cross-cutting impacts

**Persistence:** operational tooling now includes Pre-Bronze.

**Identity:** artifact/source provenance only; no canonical row IDs generated.

**Observability:** existing recovery/backup events should naturally include Pre-Bronze operation context; add schema/layer context only if bounded.

**Performance:** backup size increases by source-shaped data. Record expected size/time on fixture; no production benchmark yet.

**Compatibility:** existing DBs without Pre-Bronze initialize/restore safely.

## 9. Tests and verification

Required:
- backup/restore round trip with Pre-Bronze;
- failure after Pre-Bronze write rolls back;
- split-commit `RECOVERY_REQUIRED` scenario converges;
- Meta/catalog sees layer correctly;
- old DB initializes additively;
- no hard-coded managed-schema path silently excludes Pre-Bronze;
- current pipeline unaffected.

## 10. Explicit non-goals

Do not:
- migrate production data;
- add validation;
- alter commit order;
- create separate recovery state;
- change Control Plane artifact identity.

## 11. Completion checklist

- [x] Meta/catalog integration complete.
- [x] Backup includes Pre-Bronze.
- [x] Restore reproduces Pre-Bronze.
- [x] Rollback proven.
- [x] Split-commit recovery proven.
- [x] Existing DB compatibility proven.
- [x] No production source depends on layer yet.

## 12. Commit boundary

```text
feat(recovery): integrate pre-bronze operations
```

## 13. Handoff to Phase 023

Phase 023 may assume Pre-Bronze is persistence/recovery-safe. It can introduce Pandera validation without worrying that a successfully admitted source-shaped dataset lives outside backup/recovery semantics.

## Phase completion record

```text
Phase: 022
Target release: v9.9.1
Files changed:
  src/personal_finance_etl/infrastructure/warehouse/__init__.py
  src/personal_finance_etl/infrastructure/warehouse/contracts.py
  src/personal_finance_etl/infrastructure/warehouse/meta/healing.py
  src/personal_finance_etl/infrastructure/warehouse/meta/layer.py
  src/personal_finance_etl/infrastructure/warehouse/registry.py
  tests/infrastructure/test_pre_bronze_operational.py
Schema changed: YES (meta.m_Data_Contracts and meta.m_Table_Row_Counts record Pre-Bronze; pre_bronze schema participating in centralized warehouse lifecycle)
Runtime behavior changed: NO (No production sources use Pre-Bronze; Pre-Bronze operations integrated into warehouse metadata, backup, restore, pruning, and healing)
Financial formulas changed: NO
Focused tests: tests/infrastructure/test_pre_bronze_operational.py, tests/infrastructure/test_pre_bronze_persistence.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: N/A (no production source uses Pre-Bronze yet)
Performance check: PASS (backup and restore include pre_bronze with negligible overhead)
Compatibility path still present: YES (databases without pre_bronze schema or tables operate and restore without failure)
Old path deleted: N/A (additive integration)
Exit assertions green: YES
Commit: feat(recovery): integrate pre-bronze operations
```

A phase is incomplete if any required exit assertion is false.
