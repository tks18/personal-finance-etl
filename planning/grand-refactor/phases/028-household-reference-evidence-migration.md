# Phase 028 - Household Reference Evidence Migration

**Target release:** v10.0.0-rc1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 027  
**Next:** Phase 029  
**Risk:** High

## 1. Outcome

Migrate the five current household SQLite reference/dimension evidence streams (`zcategory`, `assetgroup`, `assets`, `currency`, `inoutcome`) through the proven generalized Raw -> Pre-Bronze -> canonical Bronze path, removing each stream's legacy extraction/Bronze route after equivalence.

This phase uses one repeated procedure with a dataset-specific parameter table; it does not redesign the migration architecture.

## 2. Why this phase exists

These five datasets share one SQLite source/provider, full-replace semantics and stable source identities, making them the safest family-scale migration after the Phase-025 proof and DatasetCollection demolition.

## 3. Inherited repository state

Phase 027 guarantees DatasetCollection is authoritative. Phase 025 provides the mandatory vertical-slice template. Pre-Bronze/Pandera/configuration/identity/recovery are production-proven on one dataset.

The five household streams still use the legacy SQLite extractor path unless one was chosen as Phase-025's first dataset. If so, mark it already migrated and execute this phase for the remaining four while re-running family certification.

## 4. Current codebase anchors

Current historical streams:
- `zcategory` -> category `sqlite_source` -> `bronze.r_SQLite_ZCategory`
- `assetgroup` -> `sqlite_source` -> `bronze.r_SQLite_AssetGroup`
- `assets` -> `sqlite_source` -> `bronze.r_SQLite_Assets`
- `currency` -> `sqlite_source` -> `bronze.r_SQLite_Currency`
- `inoutcome` -> `sqlite_source` -> `bronze.r_SQLite_InOutCome`

Current `SQLiteExtractor.extract_base_tables()` knows this fixed five-table universe. Current coordinator unpacks them explicitly.

At phase start, replace historical names with actual post-Phase-027 symbols if prior phases renamed them; DatasetIds are authoritative.

## 5. Exact target state after this phase

For each dataset, define/freeze a row in the phase parameter table:
```text
DatasetId
SourceId = household SQLite source
SqliteSelector.table_name
source schema
mapping/normalization
trusted source identity field(s) if REQUIRED
Pre-Bronze physical table
canonical Bronze physical table
sync = FULL_REPLACE
downstream Transformer consumer
```

All five production routes are configuration-driven. `SQLiteExtractor` becomes generic enough to extract a configured table selector; it no longer owns the list of household tables.

Trusted current SQLite IDs are preserved exactly.

## 6. Detailed implementation sequence

### Step 1 - Build the five-row migration parameter table
Use SourceConfiguration and Bronze contracts. If Phase-025 already migrated one, mark it `ALREADY_GENERALIZED`.

### Step 2 - Generalize SQLite provider
Expose physical `bytes/db + SqliteSelector(table)` extraction. Keep backup-file discovery/Raw payload concerns outside the provider where architecture already places them.

### Step 3 - Migrate one remaining dataset at a time
For each row execute Phase-025 template:
source plan -> sync -> provider -> source validation -> Pre-Bronze -> normalization -> identity -> Bronze validation -> Bronze -> DatasetCollection -> downstream equivalence.

### Step 4 - Preserve trusted source UIDs
Where Bronze identity REQUIRED, configure source-field identity. Assert IDs equal pre-migration values exactly.

### Step 5 - Full-replace family semantics
One SQLite artifact may supply multiple datasets. Ensure full-replace sync does not duplicate Raw artifact ingestion or create contradictory artifact identities. Each dataset gets its own Pre-Bronze/Bronze state linked to the same source artifact.

### Step 6 - Remove fixed-table unpacking
After all five migrate, `SQLiteExtractor`/coordinator no longer hard-code `zcategory`, `assetgroup`, etc.

### Step 7 - Delete family legacy routes
Remove direct legacy extraction-to-Bronze branches for migrated streams.

### Step 8 - Family certification
Change/replace SQLite backup, rerun, rollback, restore, downstream dimensions/facts and full financial outputs.

## 7. Files and symbols in scope

Modify:
- SQLite provider/extractor;
- source plan/config for five datasets;
- source/Bronze contracts;
- ingestion coordinator fixed SQLite branch;
- tests/fixtures.

Do not migrate household transaction/opening-balance evidence assigned to Phase 029.

## 8. Cross-cutting impacts

**Persistence:** five source-shaped Pre-Bronze tables/states; canonical Bronze tables remain financial evidence.

**Identity:** trusted SQLite UIDs preserved byte-for-byte.

**Provenance:** one artifact can feed multiple DatasetIds; lineage must remain unambiguous.

**Observability:** dataset-level events distinguish five datasets under one source/artifact.

**Performance:** SQLite payload should not be reopened/copied wastefully five times if provider can safely share a read session. Optimize only without violating provider abstraction.

## 9. Tests and verification

For each dataset:
- source validation happy/failure;
- Pre-Bronze row count;
- Bronze row count/schema;
- trusted IDs identical;
- downstream output identical;
- legacy route not called.

Family:
- one artifact -> five dataset provenance;
- full-replace changed backup;
- rollback after partial family processing;
- backup/restore;
- full Shan financial regression;
- no fixed five-table extractor list remains.

## 10. Explicit non-goals

Do not:
- derive new IDs for already stable source IDs;
- migrate transaction evidence;
- remove source DB Settings compatibility globally if other paths still need it;
- change household financial formulas;
- begin fixed discovery demolition.

## 11. Completion checklist

- [x] All applicable five reference streams generalized.
- [x] Generic SQLite selector path is production-used.
- [x] Stable IDs preserved.
- [x] Multi-dataset artifact provenance correct.
- [x] Fixed household-table unpacking removed.
- [x] Legacy routes removed.
- [x] Family recovery/full-replace proven.
- [x] Full Shan run green.

## 12. Commit boundary

```text
feat(ingestion): generalize household reference evidence
```

## 13. Handoff to Phase 029

Phase 029 may assume household reference dimensions are fully configuration-driven and the SQLite provider can extract arbitrary configured tables. It will migrate household transactional/opening evidence and prove that a non-Shan source without stable UIDs can satisfy the same canonical Bronze identity contracts.

## Phase completion record

```text
Phase: 028
Target release: v10.0.0-rc1
Files changed:
- src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
- src/personal_finance_etl/infrastructure/validation/__init__.py
- src/personal_finance_etl/config/sources/loader.py
- src/personal_finance_etl/domain/household/transforms/asset_dimensions.py
- src/personal_finance_etl/domain/household/transforms/reference_dimensions.py
- src/personal_finance_etl/domain/household/transforms/transactions.py
- src/personal_finance_etl/infrastructure/warehouse/bronze.py
- src/personal_finance_etl/application/pipeline/execution.py
- src/personal_finance_etl/infrastructure/providers/files/sqlite.py
- src/personal_finance_etl/application/ingestion/coordinator.py
- src/personal_finance_etl/application/ingestion/slice_runner.py
- tests/application/test_ingestion.py
- tests/application/test_generalized_vertical_slice.py
Schema changed: NO
Runtime behavior changed: YES
Financial formulas changed: NO
Focused tests: tests/application/test_generalized_vertical_slice.py, tests/application/test_ingestion.py
Architecture tests: tests/architecture/test_boundaries.py, tests/architecture/test_constitutional_certification.py, tests/architecture/test_legacy_demolition.py
Real-data run: PASS
Performance check: PASS (<1s fast gate)
Compatibility path still present: NO
Old path deleted: YES
Exit assertions green: YES
Commit: pending user confirmation
```

A phase is incomplete if any required exit assertion is false.
