# Phase 025 - First Generalized Dataset Vertical Slice

**Target release:** v9.9.4  
**Expected effort:** 3-4 hours  
**Previous:** Phase 024  
**Next:** Phase 026  
**Risk:** High

## 1. Outcome

Migrate the Phase-024 selected production dataset completely through the final architecture:
`configured source -> Control Plane/Raw -> provider -> source validation -> Pre-Bronze -> normalization -> identity if required -> Bronze validation -> canonical Bronze -> existing downstream consumer`.

Prove financial/operational equivalence, recovery and rename/change semantics, then delete the legacy extraction-to-Bronze route for this dataset only.

This phase becomes the mandatory template for every v10 source migration.

## 2. Why this phase exists

All architecture pieces have been built additively. A real vertical slice is required before multiplying the design across 19 remaining Bronze streams. The purpose is to discover integration defects while blast radius is deliberately small.

## 3. Inherited repository state

Phase 024 freezes the exact selected dataset and both validation contracts.

Available and tested independently:
- runtime SourceConfiguration;
- ExecutionPlan;
- resolved change policy;
- provider selector;
- Pre-Bronze persistence/recovery;
- mapping/normalization;
- identity planning;
- Pandera adapter;
- source and canonical Bronze schemas;
- canonical provenance.

Current selected dataset still uses its legacy `ExtractionResult`/Bronze route.

## 4. Current codebase anchors

Re-open the exact route frozen in Phase 024.

Also inspect:
- `PipelineExecutor._run_discovery_phase`
- `ExtractionCoordinator`
- selected provider function
- `BronzeLayer` current contract/write path
- downstream transformer/service consuming selected Bronze frame
- Control Plane file sync/artifact repository
- recovery/backup tests.

Do not generalize other datasets opportunistically.

## 5. Exact target state after this phase

For the selected DatasetId, the only production path is:

```text
SourceConfiguration
  -> SourcePlan/DatasetPlan
  -> discovery/Control Plane sync using resolved policy
  -> Raw payload/artifact
  -> generic/current physical provider + typed selector
  -> source-shaped frame
  -> SOURCE Pandera validation
  -> Pre-Bronze persistence
  -> normalization plan
  -> identity plan if REQUIRED
  -> BRONZE Pandera validation
  -> canonical Bronze persistence
  -> full/current downstream financial consumer
```

The selected dataset no longer needs:
- its fixed `ExtractionResult` field as ingestion transport;
- category-specific extraction branch for its production path;
- old direct provider->Bronze path.

Other datasets remain legacy.

## 6. Detailed implementation sequence

### Step 1 - Build DatasetPlan for selected dataset
Resolve SourceConfig, selector, change policy, mapping, identity and contracts before I/O.

### Step 2 - Discovery/Raw integration
Use current Control Plane artifact machinery. Do not create a second raw registry. Ensure policy from Phase 006 is resolved from production SourceConfiguration for this dataset, with compatibility fallback removed for this dataset only.

### Step 3 - Provider extraction
Invoke provider using typed selector. Separate physical parsing from normalization. Any dataset-specific cleanup already represented in Phase-018 plan moves out of provider for this path.

### Step 4 - Source validation
Validate before accepting source-shaped state. On failure:
- no canonical Bronze mutation;
- run fails through normal lifecycle;
- bounded validation event/error emitted.

### Step 5 - Pre-Bronze persistence
Write validated source-shaped frame with artifact/source/dataset provenance inside DuckDB transaction.

### Step 6 - Normalize and resolve identity
Read/use Pre-Bronze frame, compile/run normalization, preserve/derive identity according to Phase-024 contract.

### Step 7 - Bronze validation
Reject canonical violations before Bronze write.

### Step 8 - Canonical Bronze persistence
Use existing Bronze physical table if canonical target remains compatible, or migrate table schema deliberately. Bronze must not dynamically absorb unexpected source fields.

### Step 9 - Downstream equivalence
Feed existing downstream transformer/service without changing financial methodology. Compare output to pre-phase baseline.

### Step 10 - Changed-file and rename scenarios
Run:
- unchanged rerun;
- changed artifact;
- renamed artifact where policy supports rename;
- removed/full-replace semantics as applicable.
Assert Pre-Bronze/Bronze/Control Plane convergence.

### Step 11 - Failure/recovery scenarios
Inject failure:
- after Pre-Bronze before Bronze;
- after Bronze before downstream commit.
Verify rollback/recovery.

### Step 12 - Delete selected legacy route
Remove selected dataset's fixed extraction branch/field usage/direct Bronze path only after all equivalence tests pass.
If `ExtractionResult` field cannot yet be physically deleted because type construction requires it, mark it deprecated/unused and assert production path does not populate/consume it. Phase 027 performs global DTO demolition.

### Step 13 - Freeze migration-template test
Create reusable checklist/helper fixture capturing A-L migration obligations for later dataset phases.

## 7. Files and symbols in scope

Modify only the selected dataset's:
- source-plan resolution;
- provider route;
- ingestion orchestration;
- validation/persistence wiring;
- Bronze contract/schema;
- downstream transport adapter if necessary;
- tests.

Shared infrastructure may receive generic hooks required by the slice, but do not migrate a second dataset.

## 8. Cross-cutting impacts

**Persistence:** first production Pre-Bronze data; selected Bronze becomes strict canonical admission.

**Transactions/recovery:** existing DuckDB/SQLite lifecycle unchanged.

**Identity:** exact Phase-024 policy; protected downstream IDs unchanged.

**Provenance:** artifact/source/dataset identity must trace end-to-end.

**Observability:** source validation, Pre-Bronze, normalization/identity, Bronze validation events correlated under run/operation lineage.

**Performance:** measure selected dataset old vs new path. Validation/persistence overhead recorded; no pathological eager collection.

**Compatibility:** all other 19 Bronze streams remain legacy and fully functional.

## 9. Tests and verification

Required end-to-end matrix:
1. happy path first run;
2. unchanged rerun;
3. changed artifact;
4. rename if supported;
5. malformed source schema;
6. normalization failure;
7. identity collision if applicable;
8. Bronze contract violation;
9. failure after Pre-Bronze;
10. failure after Bronze;
11. backup/restore including selected Pre-Bronze;
12. downstream output equivalence;
13. full Shan pipeline financial equivalence;
14. protected IDs unchanged;
15. selected legacy route not invoked (mock/call assertion);
16. all other dataset paths unchanged.

## 10. Explicit non-goals

Do not:
- migrate another dataset;
- delete `ExtractionResult` globally;
- remove fixed discovery globally;
- make Bronze strict for unmigrated datasets;
- alter financial formulas;
- redesign recovery/observability;
- begin capability composition.

## 11. Completion checklist

- [x] DatasetPlan drives selected production dataset.
- [x] Source validation runs.
- [x] Pre-Bronze persists source shape.
- [x] Normalization/identity runs.
- [x] Bronze validation runs.
- [x] Canonical Bronze persists.
- [x] Downstream output is equivalent.
- [x] Change/rename/rerun semantics proven.
- [x] Failure/recovery proven.
- [x] Provenance traces end-to-end.
- [x] Selected legacy route is deleted or provably dormant pending DTO removal.
- [x] Other datasets remain unchanged.
- [x] Full Shan run green.
- [x] Reusable migration template frozen.

## 12. Commit boundary

```text
feat(ingestion): generalize first dataset end to end
```

## 13. Handoff to Phase 026

Phase 026 may assume the final ingestion architecture is proven on one real production dataset. The next problem is transport: replace the fixed `ExtractionResult` universe with `DatasetCollection` additively so subsequent dataset migrations do not keep expanding a legacy DTO.

Phase 025's vertical-slice procedure is now the mandatory migration template for Phases 028-034.

## Phase completion record

```text
Phase: 025 - First Generalized Dataset Vertical Slice
Target release: v9.9.4
Files changed:
  - src/personal_finance_etl/application/ingestion/__init__.py
  - src/personal_finance_etl/application/ingestion/coordinator.py
  - src/personal_finance_etl/application/ingestion/slice_runner.py
  - src/personal_finance_etl/application/pipeline/execution.py
  - src/personal_finance_etl/application/pipeline/orchestrator.py
  - src/personal_finance_etl/config/sources/loader.py
  - src/personal_finance_etl/domain/household/transforms/expense_dimensions.py
  - src/personal_finance_etl/domain/household/transforms/income_dimensions.py
  - src/personal_finance_etl/infrastructure/providers/files/sqlite.py
  - src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
  - src/personal_finance_etl/infrastructure/warehouse/bronze.py
  - tests/application/test_generalized_vertical_slice.py
  - tests/infrastructure/test_admission_contracts.py
Schema changed: Pre-Bronze DuckDB table 'pre_bronze.pb_household_zcategory' created and populated; 'bronze.r_SQLite_ZCategory' populated with canonical schema.
Runtime behavior changed: DatasetId.HOUSEHOLD_ZCATEGORY is ingested through generalized vertical slice (DatasetIngestionService) coordinating Gate 1, Pre-Bronze, admission, Gate 2, canonical Bronze, and artifact sync. Legacy extraction bypassed for zcategory.
Financial formulas changed: NO
Focused tests: tests/application/test_generalized_vertical_slice.py (17 passed)
Architecture tests: tests/architecture/test_boundaries.py (12 passed)
Real-data run: Shan baseline integration tests pass 100% with identical outputs
Performance check: < 2.5s for fast audit, 0.3s for vertical slice execution
Compatibility path still present: YES (all other 19 Bronze datasets continue through legacy path)
Old path deleted: Bypassed/dormant for HOUSEHOLD_ZCATEGORY (empty LazyFrame in extraction, skipped in BronzeLayer.load); global DTO removal scheduled for Phase 027
Exit assertions green: YES
Commit: (Pending user approval via .commit_overrides.json)
```

A phase is incomplete if any required exit assertion is false.
