# Phase 038 - Generalized Ingestion Certification

**Target release:** v10.0.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 037  
**Next:** Phase 039  
**Risk:** High

## 1. Outcome

Certify the complete generalized ingestion architecture as the authoritative PFETL v10 data plane. This phase introduces no planned architectural feature; it executes the exhaustive release gate, closes any discovered defects, and proves no legacy ingestion mode remains.

v10.0.0 is released only if every acceptance gate below passes.

## 2. Why this phase exists

Phases 025-037 progressively migrated every evidence family and removed all compatibility topology/schema/provenance mechanisms. A major-version cutover requires a dedicated certification day rather than assuming local phase tests compose perfectly.

## 3. Inherited repository state

Phase 037 guarantees:
- SourceConfiguration/ExecutionPlan are topology authority;
- all current Bronze streams generalized;
- DatasetCollection authoritative;
- Pre-Bronze/Pandera operational;
- strict canonical Bronze;
- artifact-key operational provenance;
- no fixed discovery/extraction mode;
- financial methodologies intentionally unchanged.

No further legacy ingestion fallback is allowed to rescue certification failures.

## 4. Current codebase anchors

Certification must inspect the current branch, not v9.5.3 symbol names.

Baseline oracle remains the accepted v9.5.3 financial outputs/identity semantics for unchanged methodology plus the phase-by-phase approved schema vocabulary migrations.

Use:
- full quality-gate suite;
- current Shan production dataset;
- external no-UID household fixture;
- provider cache/fresh fixtures;
- backup/restore/recovery fixtures;
- observability JSONL lineage.

## 5. Exact target state after this phase

Release state:
```text
Raw/Control Plane
 -> Pre-Bronze source-shaped validated state
 -> normalization + identity
 -> strict canonical Bronze
 -> canonical Silver
 -> Gold
```

All source/provider topology is configuration/plan-driven.

No production legacy mode, fallback locator, fixed extraction DTO, dynamic Bronze evolution, column-master data path or filename operational identity remains.

v10.0.0 must be releasable at phase end.

## 6. Detailed implementation sequence

### Step 1 - Static legacy sweep
Search for all retired architecture symbols/literals from Phases 027/030/035/036/037. Any production reference must be explained or removed.

### Step 2 - Full clean rebuild on Shan data
From empty Control Plane/warehouse, run complete pipeline. Compare accepted financial oracle.

### Step 3 - Cached/incremental rerun
No-change run produces expected skipped/cached behavior and identical outputs.

### Step 4 - Change matrix
Exercise representative CSV/Excel/SQLite changes, full-replace and incremental datasets, rename and removal.

### Step 5 - Identity certification
Verify trusted household IDs, derived external IDs and protected financial namespaces.

### Step 6 - Provider certification
Fresh and cached currency/benchmark/US-market evidence; request ranges/counts and outputs equivalent.

### Step 7 - Validation failure certification
Malformed source, mapping failure, identity collision, canonical Bronze violation. No invalid canonical state committed.

### Step 8 - Recovery certification
Failures after Raw sync, Pre-Bronze, Bronze, analytics; DuckDB-first/SQLite-second split commit; stale run recovery.

### Step 9 - Backup/restore certification
Backup current generalized warehouse including Pre-Bronze; restore and rerun.

### Step 10 - Observability lineage
Select a run and reconstruct source/artifact -> validation -> Pre-Bronze -> normalization/identity -> Bronze -> analytical publication using JSONL lineage/context.

Include at least one multiprocessing/worker path used by the current system (for example the ISIN worker path if it remains current). Prove run ID, worker context, operation ID / parent operation ID and JSONL parent-child lineage survive process boundaries after the new configuration/dataset context was added.

### Step 11 - Performance
Compare full/cached runtime to approved pre-refactor baseline and explain material deltas. Fix regressions caused by accidental eager work/N+1 behavior.

### Step 12 - Release cleanup
Version metadata/changelog/release notes only after all gates green.

## 7. Files and symbols in scope

Modify only defects uncovered by certification plus release metadata/tests.

Any defect requiring architectural redesign stops certification and amends the relevant earlier phase/ARCHITECTURE before proceeding.

## 8. Cross-cutting impacts

**Persistence:** complete generalized model certified.

**Identity:** absolute non-regression gate.

**Observability:** complete lineage gate.

**Performance:** explicit release gate.

**Compatibility:** v10 may intentionally break internal/source configuration contracts documented by plan; financial truth remains equivalent.

## 9. Tests and verification

Mandatory:
- all tests/typing/lint/architecture gates;
- clean Shan run;
- cached Shan run;
- external no-UID fixture;
- change/rename/removal matrix;
- validation failure matrix;
- recovery/split-commit matrix;
- backup/restore;
- provider fresh/cache;
- protected identity snapshot;
- JSONL lineage reconstruction, including a multiprocessing/worker path;
- performance comparison;
- zero legacy ingestion references.

## 10. Explicit non-goals

Do not:
- add new capabilities;
- redesign configuration;
- change financial formulas;
- weaken a gate to ship;
- preserve a legacy fallback because certification exposed a bug.

## 11. Completion checklist

- [ ] Zero legacy ingestion mode.
- [ ] Clean/full/cached runs green.
- [ ] Financial oracle equivalent.
- [ ] All protected IDs stable.
- [ ] Validation/recovery matrices green.
- [ ] Backup/restore green.
- [ ] Provider behavior green.
- [ ] JSONL lineage reconstructable.
- [ ] Multiprocessing/worker lineage remains correlated.
- [ ] Performance accepted.
- [ ] v10.0.0 releasable.

## 12. Commit boundary

```text
chore(release): certify generalized ingestion v10
```

## 13. Handoff to Phase 039

Phase 039 starts after v10.0.0 generalized ingestion is stable. It does not revisit ingestion architecture. It begins capability composition by making household-only and investment-accounting execution genuinely independent through the already-proven ExecutionPlan.

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
