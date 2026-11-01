# Phase 011 - Silver Provenance Cleanup

**Target release:** v9.6.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 010  
**Next:** Phase 012  
**Risk:** Medium-High

## 1. Outcome

Complete the destructive half of the provenance migration begun in Phase 010. Remove legacy source-path fields from canonical Silver wherever Phase 010 proved `ProvenanceRef` replacement, while deliberately leaving Bronze operational filename semantics untouched.

At phase end canonical Silver no longer exposes `__file_name__` or `__folder_path__` merely to preserve source lineage. Any retained source-native field must have an explicit financial/audit justification in the Phase-008 disposition manifest.

## 2. Why this phase exists

Phase 010 established additive canonical provenance and proved that representative Silver rows can resolve their originating artifact through the Control Plane. Keeping both lineage systems indefinitely would turn the temporary compatibility bridge into permanent schema debt.

## 3. Inherited repository state

Phase 010 guarantees:
- `ProvenanceRef` exists and is populated for Silver families carrying path lineage;
- artifact metadata can be resolved through Control Plane without hot-path N+1 lookups;
- financial outputs and protected deterministic IDs are unchanged;
- `__file_name__`/`__folder_path__` still exist for compatibility;
- Bronze delete/rename and Meta healing still depend on operational filename semantics.

Phase 011 must not disturb those Bronze operational uses.

## 4. Current codebase anchors

Primary anchors:
- `infrastructure/warehouse/schema/silver.py` (24 tables / 533-column Phase-008 inventory)
- Phase-008 Silver disposition manifest
- household transforms: `domain/household/transforms/*`
- investment transforms: `domain/investments/transforms/*`
- `domain/market/benchmarks.py`
- Gold producers identified by Phase-008 dependency manifest
- tests asserting Silver schema/registry parity

Known legacy lineage columns include `__file_name__` and `__folder_path__` across household dimensions/facts, opening balances, investment purchase/sale/master/reference frames and macro/reference state.

## 5. Exact target state after this phase

For every Silver column classified `MOVE_TO_PROVENANCE`:
1. zero production consumer reads the legacy path field;
2. producer emits canonical provenance reference only;
3. Silver DDL no longer declares the legacy field;
4. Gold dependency manifest references canonical provenance only where lineage is genuinely exposed;
5. Phase-008 manifest row is marked closed.

Source-native metadata classified separately (`S_NO`, `MODIFY_DATE`, `DEVICE_ID`, etc.) is removed only when its disposition is already `REMOVE_AFTER_CONSUMER_MIGRATION` and consumer tracing proves no canonical/audit use. Do not opportunistically remove `REVIEW_REQUIRED` fields.

## 6. Detailed implementation sequence

### Step 1 - Generate the exact removal set
Query the Phase-008 manifest. Build the list of Silver `(table, column)` rows whose disposition is `MOVE_TO_PROVENANCE` and whose Phase-010 replacement is implemented. Fail the phase if the list is hand-maintained separately.

### Step 2 - Prove zero financial consumers
Repository-search/AST-check each removal candidate. Any remaining consumer must be migrated to `ProvenanceRef` or Control Plane lookup before DDL changes.

### Step 3 - Migrate producers
Remove legacy path columns from household/reference/investment transform selections and projections. Do not remove provider/extraction provenance upstream of Silver.

### Step 4 - Migrate Gold consumers
Use Phase-008 dependency manifest. If Gold does not need lineage, stop projecting it. If Gold exposes lineage, project canonical provenance identifiers rather than paths.

### Step 5 - Modify Silver DDL
Drop only approved columns. Silver is rebuilt, so normal pipeline execution does not require in-place data migration. Update registry/schema fingerprints deliberately.

### Step 6 - Close source-native residue that is already proven removable
For `S_NO`, `MODIFY_DATE`, `DEVICE_ID`, `USE_TIME`, `ADDED_TIME`, `INSERT_TYPE`, `IS_SHOW`: remove only entries whose manifest says removal is safe and whose consumers are zero after producer cleanup. Leave financially/audit-relevant fields untouched.

### Step 7 - Update manifest and architecture guards
Mark closed rows. Add a test preventing `__file_name__`/`__folder_path__` from re-entering canonical Silver DDL.

### Step 8 - Run full financial regression
Compare row counts, financial values and protected IDs with pre-phase baseline.

## 7. Files and symbols in scope

Expected modifications:
- Silver DDL
- relevant household/investment/reference producers
- Gold producers only where they consumed path fields
- Phase-008 manifest
- schema/architecture/regression tests

Explicitly read-only:
- `infrastructure/warehouse/bronze.py` changed-file deletion/rename
- `infrastructure/warehouse/meta/healing.py`
- Control Plane artifact identity
- provider extraction provenance.

## 8. Cross-cutting impacts

**Persistence:** Silver DDL shrinks. No Control Plane or Bronze DDL change.

**Identity:** provenance is not part of PURCHASE/SALE/LOT/REALIZED/RECON/TAX identity. All protected IDs must remain byte-for-byte stable.

**Observability:** diagnostic path rendering may resolve through Control Plane when needed. Do not remove path metadata from Control Plane.

**Performance:** removing path columns should not regress runtime. No row-wise Control Plane lookups may be introduced.

**Compatibility:** if an external presentation currently reads a removed Silver path column, compatibility belongs at a deliberate presentation/Gold boundary, not by retaining the field in canonical Silver.

## 9. Tests and verification

Required:
- manifest-driven removal-set test;
- zero-consumer assertion for every removed column;
- Silver DDL contains no `__file_name__`/`__folder_path__`;
- representative provenance resolves to same artifact metadata as before;
- Gold contract tests pass;
- full Shan financial outputs unchanged;
- protected IDs unchanged;
- Bronze rename/delete/healing tests unchanged;
- full quality gate.

Real-data check: sample household transaction, household dimension, investment purchase/sale and reference rows after rebuild and verify provenance resolution.

## 10. Explicit non-goals

Do not:
- remove Bronze operational filename fields;
- alter Control Plane file/path storage;
- remove `__file_category__` from provenance infrastructure merely because financial use ended;
- change provider symbols (`yF_Ticker`, `YAHOO_TICKER`);
- rename unrelated canonical Silver columns;
- alter formulas.

## 11. Completion checklist

- [ ] Removal set came from the Phase-008 manifest.
- [ ] Every removed field has zero legacy consumers.
- [ ] Canonical provenance remains resolvable.
- [ ] Silver DDL has no legacy path lineage fields.
- [ ] Only proven source-native residue was removed.
- [ ] Gold remains valid.
- [ ] Protected IDs unchanged.
- [ ] Bronze operational provenance untouched.
- [ ] Full Shan run green.

## 12. Commit boundary

```text
refactor(silver): remove legacy source-path lineage
```

## 13. Handoff to Phase 012

Phase 012 may assume Silver lineage is canonical and source paths are no longer part of canonical financial state.

Still intentionally present:
- provider-specific ticker vocabulary;
- Bronze operational filename provenance;
- fixed ingestion topology;
- current provider adapters.

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
