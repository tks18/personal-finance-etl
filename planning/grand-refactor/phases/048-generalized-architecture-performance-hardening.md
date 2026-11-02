# Phase 048 - Generalized Architecture Performance Hardening

**Target release:** v10.3.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 047  
**Next:** Phase 049  
**Risk:** High

## 1. Outcome

Profile the completed generalized architecture, quantify overhead introduced by Pre-Bronze, Pandera, normalization, identity, planning and plan-aware publication, then optimize only measured bottlenecks while preserving all correctness/recovery/observability guarantees.

At phase end PFETL has an explicit approved performance envelope for full and cached Shan runs plus representative external workloads.

## 2. Why this phase exists

The architecture deliberately prioritized correctness and safe migration. Performance should be tuned only after all paths are stable; otherwise optimization risks baking in transitional compatibility behavior. The historical ~27-second Shan workload is a useful reference, not an unconditional target if evidence volume/environment differs.

## 3. Inherited repository state

Phase 047 proves functional correctness across topologies. All major architectural layers are final. Existing observability can provide stage timing/lineage.

## 4. Current codebase anchors

Profile current branch using:
- Shan full/fresh run;
- Shan cached/no-change run;
- external household fixture at scaled representative size if useful;
- external investment fixture;
- provider cached path.

Break timing by:
- discovery/sync;
- source extraction;
- source validation;
- Pre-Bronze write/read;
- normalization;
- identity;
- Bronze validation/write;
- transformation;
- analytical engines;
- Silver/Gold/Meta publication.

Also inspect memory/materialization counts where tooling already exists.

## 5. Exact target state after this phase

Produce a performance baseline table and approved thresholds/ranges.

Optimization principles:
- eliminate accidental repeated collection;
- avoid repeated parsing of same workbook/database;
- avoid N+1 Control Plane/provenance lookups;
- compile configuration/validation plans once per dataset/run;
- reuse source/provider reads safely;
- batch DuckDB writes;
- retain lazy Polars execution where validation boundary permits;
- never skip validation/recovery/observability to gain speed.

No speculative rewrite without measured evidence.

## 6. Detailed implementation sequence

### Step 1 - Capture reproducible baseline
Record environment/data artifact count/config fingerprint and run modes.

### Step 2 - Instrument/inspect stage timing
Use existing observability rather than adding a parallel profiler architecture. Temporary profiling hooks may be used locally but removed unless generally useful.

### Step 3 - Rank bottlenecks
Document top contributors and regression vs accepted pre-refactor baseline.

### Step 4 - Fix repeated materialization
Search for `.collect()`, dataframe copies and Pandera conversions introduced by new architecture. Consolidate at frozen validation boundary.

### Step 5 - Fix repeated source/provider I/O
Share safe workbook/SQLite/provider response parsing where multiple DatasetPlans use same artifact.

### Step 6 - Optimize Pre-Bronze/Bronze writes
Bulk operations, transaction reuse, projection before persistence where semantically valid.

### Step 7 - Optimize plan/config compilation
Cache immutable compiled mapping/validation/identity plans per config fingerprint/run.

### Step 8 - Re-profile after each meaningful fix
Keep only improvements with measurable benefit and green correctness suite.

### Step 9 - Define performance gates
Set thresholds for full/cached runs as relative/absolute ranges appropriate to environment. Document noise methodology.

### Step 10 - Final full regression
All financial, recovery, validation, observability and external fixture tests.

## 7. Files and symbols in scope

Modify measured hot paths only.

Potential modules:
- validation adapter;
- normalization/identity compiler/executor;
- Pre-Bronze/Bronze persistence;
- provider read/session handling;
- Control Plane lookup batching;
- pipeline plan caching.

Do not perform unrelated code-quality refactors.

## 8. Cross-cutting impacts

**Persistence:** semantics unchanged.

**Identity:** outputs unchanged.

**Observability:** retain event fidelity; stage timings may improve.

**Memory:** include peak/large-frame behavior where measurable.

**Correctness:** no optimization may weaken a gate.

**Performance:** this phase creates the durable benchmark/gate used by Phase 050.

## 9. Tests and verification

Required:
- reproducible before/after timing table;
- full and cached Shan runs;
- representative external runs;
- no new eager-collection regression;
- no repeated source I/O where avoidable;
- financial outputs/IDs identical;
- recovery/validation suites green;
- JSONL event lineage retained;
- final thresholds encoded/documented in test/benchmark convention.

## 10. Explicit non-goals

Do not:
- remove Pandera validation for speed;
- bypass Pre-Bronze;
- weaken hashing/change detection;
- suppress observability;
- rewrite financial algorithms;
- optimize synthetic microbenchmarks at expense of real workload.

## 11. Completion checklist

- [ ] Baseline captured.
- [ ] Bottlenecks measured/ranked.
- [ ] Only evidence-backed optimizations applied.
- [ ] Full/cached runtime accepted.
- [ ] External workload accepted.
- [ ] Memory/materialization acceptable.
- [ ] Correctness/recovery/observability unchanged.
- [ ] Durable performance gate exists.

## 12. Commit boundary

```text
perf(pipeline): harden generalized runtime
```

## 13. Handoff to Phase 049

Phase 049 may assume the implementation is functionally and operationally mature across multiple topologies with accepted performance. It will freeze the public configuration contract only now, after real usage has validated the model.

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
