# Phase 036 - Strict Canonical Bronze Cutover

**Target release:** v10.0.0-rc9  
**Expected effort:** 3-4 hours  
**Previous:** Phase 035  
**Next:** Phase 037  
**Risk:** High

## 1. Outcome

Remove Bronze's legacy source-schema evolution behavior and make PFETL-owned canonical Bronze contracts the sole admission authority for every migrated dataset.

At phase end:
- source drift is contained in Pre-Bronze;
- mapping/normalization is the only route from source vocabulary to canonical vocabulary;
- Bronze tables cannot silently add source columns;
- every one of the current Bronze DatasetIds has an explicit canonical schema/grain/identity contract;
- unexpected canonical output fails before Bronze mutation.

This phase changes Bronze admission semantics, not financial methodology.

## 2. Why this phase exists

Phase 035 removed the final fixed ingestion topology. All current evidence now passes through Source/Provider plans, validation, Pre-Bronze and normalization. Dynamic Bronze evolution is therefore no longer a compatibility necessity; leaving it enabled would defeat the entire trust-boundary design by allowing source drift to leak back into canonical evidence.

## 3. Inherited repository state

Phase 035 guarantees:
- every current Bronze stream has a generalized production route;
- no folder/category/manual-injection topology authority remains;
- SourceConfiguration/ProviderDatasetPlan own evidence topology;
- source validation and Pre-Bronze are operationally proven;
- canonical Bronze validation exists for migrated datasets;
- current Bronze implementation may still contain dynamic schema evolution helpers for historical compatibility.

Phase 036 must not alter operational artifact identity; `__file_name__` replacement belongs to Phase 037.

## 4. Current codebase anchors

Mandatory current-branch archaeology:
- `infrastructure/warehouse/bronze.py`
- Bronze schema creation/evolution helpers, especially `_evolve_schema` or successor
- canonical Bronze schema/contract registry introduced across Phases 024-034
- all 20 DatasetIds and physical Bronze tables
- source validation/normalization/Bronze validation services
- Meta schema fingerprint/catalog behavior
- tests that historically expected new source columns to appear in Bronze.

Generate an exact list of any code path that can execute `ALTER TABLE ... ADD COLUMN` or infer Bronze columns from an incoming frame.

## 5. Exact target state after this phase

For every canonical Bronze DatasetId:

```text
Pre-Bronze source shape
  -> configured normalization
  -> identity resolution if required
  -> canonical frame
  -> PFETL-owned Bronze contract validation
  -> write to fixed canonical Bronze schema
```

Rules:
- canonical Bronze columns are contract-defined;
- unexpected source columns may exist in Pre-Bronze but are ignored/rejected according to mapping policy, never auto-added to Bronze;
- missing canonical required fields fail;
- canonical types/nullability/grain/identity/uniqueness fail before write;
- schema changes require an explicit PFETL contract migration, not runtime inference.

No dynamic Bronze DDL based on input frame remains.

## 6. Detailed implementation sequence

### Step 1 - Enumerate canonical Bronze coverage
Assert all current production DatasetIds have canonical schema metadata. If any still relies on implicit schema, stop and define it before deleting evolution.

### Step 2 - Find all dynamic DDL paths
Repository-search for `ALTER TABLE`, schema-diff/add-column logic and source-frame-driven table creation under Bronze.

### Step 3 - Centralize canonical table creation
Bronze table initialization uses canonical contract/schema registry. Physical DDL is deterministic for a given contract version.

### Step 4 - Remove `_evolve_schema` behavior
Delete runtime add-column behavior. If a helper remains for explicit migrations, rename it to make migration-only ownership unmistakable and require an explicit schema version.

### Step 5 - Enforce projection
Normalization/admission must produce exactly the canonical columns plus deliberately owned operational provenance fields. Unexpected Pre-Bronze columns cannot sneak through `select("*")`.

### Step 6 - Add source-drift proof
Take a configured source fixture and add an extra source column:
- source validation may allow it if config permits;
- Pre-Bronze stores it;
- canonical normalization does not map it;
- Bronze schema remains unchanged.

### Step 7 - Add missing/changed canonical failure proof
Remove a required mapped field or change incompatible type. Assert Bronze mutation does not occur.

### Step 8 - Contract-version/fingerprint handling
Ensure Meta/registry fingerprint changes only when PFETL canonical contract changes, not when source adds an irrelevant field.

### Step 9 - Existing database compatibility
Open current Bronze DB and verify canonical schema matches target. If historical extra columns exist from prior dynamic evolution, define an explicit rebuild/cleanup path rather than silently ignoring schema mismatch.

### Step 10 - Full regression
Rebuild all Bronze/Silver/Gold from Shan evidence and compare financial outputs/IDs.

## 7. Files and symbols in scope

Modify:
- Bronze layer/schema initialization;
- canonical Bronze contract registry/schema definitions;
- Meta/contract fingerprint tests;
- validation/admission projection;
- schema-drift tests.

Delete:
- source-driven Bronze evolution helpers with zero explicit-migration responsibility.

Do not touch Phase-037 operational provenance keys.

## 8. Cross-cutting impacts

**Persistence:** canonical Bronze DDL becomes strict. Existing DB compatibility/rebuild behavior must be explicit.

**Identity:** Phase-007 requirements unchanged; protected financial IDs unchanged.

**Provenance:** operational provenance columns remain deliberately allowed by contract; filename replacement waits.

**Observability:** Bronze validation/schema mismatch errors should name DatasetId/contract version, not dump full schema/frame.

**Performance:** removing schema introspection/evolution should not regress runtime; avoid repeated DDL checks per frame.

## 9. Tests and verification

Required:
- 100% current Bronze DatasetId canonical schema coverage;
- no input-driven `ALTER TABLE ADD COLUMN`;
- extra source field remains Pre-Bronze-only;
- missing canonical field fails atomically;
- incompatible type fails atomically;
- canonical schema fingerprint unaffected by irrelevant source drift;
- historical extra-column DB handled explicitly;
- all Bronze row counts/canonical values match baseline;
- full Shan Silver/Gold and protected IDs identical;
- architecture guard forbids dynamic Bronze evolution.

## 10. Explicit non-goals

Do not:
- remove Pre-Bronze source columns;
- replace artifact/filename operational identity;
- change financial formulas;
- make Silver/Gold DDL plan-aware;
- alter capability composition.

## 11. Completion checklist

- [x] Every Bronze dataset has explicit canonical schema.
- [x] Dynamic Bronze schema evolution is gone.
- [x] Source drift is contained in Pre-Bronze.
- [x] Canonical admission failures are atomic.
- [x] Existing DB compatibility is explicit.
- [x] Meta fingerprint semantics are correct.
- [x] Full financial/ID regression green.

## 12. Commit boundary

```text
refactor(bronze): enforce canonical schemas
```

## 13. Handoff to Phase 037

Phase 037 may assume Bronze schema is now fully canonical and cannot absorb source drift. It can safely migrate the last major operational legacy: changed-file deletion, rename handling and Meta healing currently keyed by filename.

## Phase completion record

```text
Phase: 036
Target release: v10.0.0-rc9
Files changed:
- src/personal_finance_etl/contracts/canonical_fields.py
- src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
- src/personal_finance_etl/infrastructure/warehouse/schema/bronze.py
- src/personal_finance_etl/infrastructure/warehouse/connection.py
- src/personal_finance_etl/infrastructure/warehouse/bronze.py
- src/personal_finance_etl/application/normalization/executor.py
- tests/architecture/test_bronze_canonical_guards.py
- tests/infrastructure/test_bronze_strict_canonical.py
- tests/application/test_generalized_vertical_slice.py
- tests/application/test_mutual_fund_evidence_migration.py
- tests/application/test_reference_evidence_migration.py
- tests/contracts/test_dataset_collection.py
Schema changed: YES (Bronze DDL centralized and deterministically instantiated on schema initialization; dynamic schema evolution permanently removed)
Runtime behavior changed: YES (Bronze validation enforces strict=True schemas rejecting unmapped drift; Bronze table mutation uses deterministic DDL and transactional deletion without dynamic schema mutation)
Financial formulas changed: NO
Focused tests: tests/infrastructure/test_bronze_strict_canonical.py, tests/contracts/test_dataset_collection.py, tests/application/test_generalized_vertical_slice.py
Architecture tests: tests/architecture/test_boundaries.py, tests/architecture/test_bronze_canonical_guards.py
Real-data run: 46/46 nodes successful (30.21s, FULLY_COMMITTED)
Performance check: FAST audit 0.89s, FULL audit passed across all 6 engines (89.37s)
Compatibility path still present: NO (dynamic schema evolution helper deleted)
Old path deleted: YES (_evolve_schema deleted from BronzeLayer)
Exit assertions green: YES (all 7 checklist items satisfied)
Commit: refactor(bronze): enforce canonical schemas
```

A phase is incomplete if any required exit assertion is false.
