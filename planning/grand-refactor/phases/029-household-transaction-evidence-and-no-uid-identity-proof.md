# Phase 029 - Household Transaction Evidence and No-UID Identity Proof

**Target release:** v10.0.0-rc2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 028  
**Next:** Phase 030  
**Risk:** High

## 1. Outcome

Migrate the remaining household transactional/opening evidence through generalized ingestion and prove the external-user identity case: a supported Excel/CSV household source with no stable source UID can deterministically generate the Bronze identity required by PFETL.

The production Shan topology must continue preserving its trusted source IDs.

## 2. Why this phase exists

Phase 028 proves generalized household reference evidence with trusted SQLite identity. The architecture is not truly source-agnostic until the same canonical contract can admit evidence from a source that lacks those UIDs.

## 3. Inherited repository state

Phase 028 guarantees generic SQLite selection and household reference migration. Phase 007/019 already proved deterministic derived identity in fixtures, but not yet as part of the family-scale generalized household admission path.

Use the current migration ledger to identify all household transactional/opening Bronze datasets still legacy at phase start. Do not invent dataset names from memory; resolve by DatasetId/registry.

## 4. Current codebase anchors

Anchors include:
- household transaction/opening-balance current Bronze streams;
- `raw_opening_balances`/opening balance CSV where applicable;
- household transaction transforms/facts;
- identity fields used for downstream joins;
- SourceConfiguration mapping definitions;
- current `column_master` compatibility path, which Phase 030 retires.

At phase start generate exact dataset table: current source, selector, sync strategy, identity requirement, downstream consumer.

## 5. Exact target state after this phase

Every remaining household evidence dataset follows final vertical path.

For Shan's current SQLite evidence:
- trusted source identity remains authoritative where configured.

For the external no-UID proof fixture:
- source is supported CSV or Excel;
- mapping produces canonical identity fields;
- `DerivedDeterministicIdentity` creates required Bronze ID;
- repeated runs/order changes produce identical IDs;
- duplicate identity inputs fail before Silver.

Both sources satisfy the same PFETL-owned canonical Bronze contract.

## 6. Detailed implementation sequence

### Step 1 - Freeze remaining household dataset table
List DatasetId, source, selector, mapping, identity, sync, Bronze target, downstream consumer.

### Step 2 - Migrate Shan production datasets
Apply Phase-025 template dataset-by-dataset. Preserve source IDs.

### Step 3 - Build external no-UID fixture
Use realistic source column names different from Shan canonical names. Configure mapping and derived identity; do not hard-code fixture-specific logic.

### Step 4 - Run admission twice with reordered rows/files
Assert generated IDs stable and canonical Bronze rows equivalent after deterministic sorting.

### Step 5 - Collision proof
Create two source rows producing same identity key; admission fails with bounded diagnostics and no Bronze mutation.

### Step 6 - Downstream equivalence
Feed both Shan and external canonical Bronze shape into existing household transforms. External fixture need not reproduce Shan financial values, but must satisfy the same schema/grain contracts.

### Step 7 - Remove migrated legacy branches
No remaining household transactional dataset may depend on fixed extraction fields/category-specific provider cleanup.

### Step 8 - Family recovery/performance
Changed source, rollback, backup/restore, full Shan regression.

## 7. Files and symbols in scope

Modify remaining household source configs/contracts/providers/ingestion paths and external fixture tests.

Do not retire column_master compatibility until Phase 030 verifies all static/reference mappings too.

## 8. Cross-cutting impacts

**Persistence:** additional Pre-Bronze household states.

**Identity:** this phase is the first production-grade proof of alternate identity strategy against same canonical contract. Shan IDs must not change.

**Provenance:** external source SourceId/artifact differs; canonical finance does not.

**Observability:** identity strategy/collision stage identifiable without exposing sensitive row payloads.

**Performance:** derived identity must not create row-wise Python bottleneck.

## 9. Tests and verification

Required:
- all remaining household evidence generalized;
- Shan IDs unchanged;
- external no-UID fixture admitted;
- repeated/reordered external run IDs stable;
- collision rejected atomically;
- same canonical Bronze contract used by both source topologies;
- downstream household transforms accept external canonical shape;
- legacy household paths zero;
- full Shan financial regression.

## 10. Explicit non-goals

Do not:
- customize Silver/Gold per external fixture;
- weaken canonical Bronze contract;
- make identity optional where REQUIRED;
- change financial formulas;
- migrate investment evidence.

## 11. Completion checklist

- [x] Household evidence family fully generalized.
- [x] Shan trusted IDs preserved.
- [x] External derived IDs deterministic.
- [x] Collision failure atomic/actionable.
- [x] Same canonical contract serves both sources.
- [x] No household legacy extraction route remains.
- [x] Full Shan run green.

## 12. Commit boundary

```text
feat(ingestion): generalize household transaction evidence
```

## 13. Handoff to Phase 030

Phase 030 may assume the household side is completely generalized and has proven both trusted-source and derived Bronze identity. It will migrate static/reference/config evidence and remove `column_master` as a special data-plane dataset because its semantics have already moved into SourceConfiguration.

## Phase completion record

```text
Phase: 029
Target release: v10.0.0-rc2
Files changed:
- src/personal_finance_etl/infrastructure/providers/files/csv.py
- src/personal_finance_etl/infrastructure/providers/files/__init__.py
- src/personal_finance_etl/application/ingestion/slice_runner.py
- src/personal_finance_etl/application/ingestion/coordinator.py
- src/personal_finance_etl/application/pipeline/execution.py
- src/personal_finance_etl/config/sources/loader.py
- src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
- src/personal_finance_etl/infrastructure/warehouse/bronze.py
- tests/application/test_generalized_vertical_slice.py
- tests/application/test_household_no_uid_identity_proof.py
Schema changed: NO
Runtime behavior changed: YES
Financial formulas changed: NO
Focused tests: tests/application/test_household_no_uid_identity_proof.py, tests/application/test_generalized_vertical_slice.py
Architecture tests: tests/architecture/test_boundaries.py, tests/architecture/test_constitutional_certification.py, tests/architecture/test_legacy_demolition.py
Real-data run: PASS
Performance check: PASS (2.18s fast audit, 86.87s full 6-engine audit)
Compatibility path still present: NO
Old path deleted: YES
Exit assertions green: YES
Commit: pending user confirmation
```

A phase is incomplete if any required exit assertion is false.
