# Phase 058 - Generalized Architecture Performance Hardening

**Target release:** v10.5.4  
**Expected effort:** profiling-driven; target 3-5 hours, extend only to finish green  
**Previous:** Phase 057  
**Next:** Phase 059  
**Risk:** High

## 1. Outcome

Profile and harden the final generalized canonical architecture after external household/investment certification, quantify the cost of each new trust/composition boundary, and establish durable performance gates without weakening correctness, validation, recovery or observability.

This phase optimizes the architecture that will be frozen in Phase 059. It must not optimize transitional code because Phase 055 already removed it.

## 2. Why this phase exists

Performance tuning before topology and contract stabilization risks preserving the wrong abstractions. By Phase 058, the final runtime path includes more than the old Pre-Bronze/Pandera architecture:

```text
Source planning
-> Gate 1
-> Pre-Bronze
-> normalization
-> semantic interpretation
-> route/fragment production
-> canonical assembly
-> canonical identity
-> Gate 2
-> canonical integrity
-> Silver/Gold engines
```

It also includes satisfiability planning, production fingerprints, replay dependency graphs and plan-aware physical publication. The cost of those boundaries must be measured directly.

## 3. Inherited repository state

Phase 057 guarantees:

- household/investment external source topologies are certified;
- protected financial identities and values are stable across equivalent source representations;
- consumer-backed Bronze/Silver retirement is complete;
- no migration/compatibility runtime path remains;
- representative external static fixtures exist for performance sampling;
- Phase 059 can freeze contracts after this performance pass.

## 4. Current codebase anchors

Profile the post-057 equivalents of:

- source/binding planner compilation;
- satisfiability and canonical production planning;
- file/SQLite/Excel source providers;
- Gate-1 validation;
- Pre-Bronze persistence;
- normalization and semantic rule execution;
- route fragment creation and union assembly;
- canonical identity and duplicate/grain checks;
- Gate-2 Pandera adapter;
- `CanonicalIntegrityValidator`;
- provider-generated FX/benchmark/instrument price evidence;
- Control Plane/replay lookups;
- Silver/Gold/Meta publication;
- observability emitter/consumers.

Use existing observability stage timings first. Temporary local profiling instrumentation must not become a second observability system.

## 5. Exact target state after this phase

PFETL has a reproducible performance baseline and explicit accepted envelope for:

- Shan fresh/full run;
- Shan cached/no-change run;
- external household run;
- external domestic investment run;
- external foreign/provider-assisted run;
- at least one replay/rebuild scenario.

The baseline must identify cost for:

| Area | Required measurement |
|---|---|
| planning | source + satisfiability + production plan compilation |
| Gate 1 | source schema validation |
| Pre-Bronze | write/read/materialization |
| semantic | normalization + include/exclude + value mapping + constants |
| assembly | fragment alignment + direct/union |
| identity | canonical identity + duplicate/grain checks |
| Gate 2 | canonical Pandera validation |
| integrity | cross-dataset reference checks |
| provider | cached/provider evidence planning and loading |
| analytical | Silver/financial engines/Gold publication |
| observability | event/JSONL overhead as part of real run |

No optimization may alter financial outputs, protected identities, validation coverage or recovery semantics.

## 6. Detailed implementation sequence

### Step 1 - Freeze benchmark inputs

Record environment assumptions, artifact counts, config/production-plan fingerprints, capability set and run mode for each benchmark. Do not compare timings from materially different datasets as if they were regressions.

### Step 2 - Capture pre-optimization baseline

Collect multiple samples where practical. Record median/range rather than a single lucky run. Preserve stage-level timings and peak-memory/materialization observations available through current tooling.

### Step 3 - Rank measured bottlenecks

Classify each hotspot as:

- CPU/dataframe work;
- repeated I/O;
- repeated plan/schema compilation;
- unnecessary eager materialization;
- persistence/transaction overhead;
- provider/cache overhead;
- observability overhead.

Do not change code before a hotspot is measurable.

### Step 4 - Inspect plan/schema compilation reuse

Ensure immutable SourceBinding, semantic rule, satisfiability, canonical production and validation plans are not recompiled repeatedly within one run when fingerprints are unchanged.

Any cache must be run/config scoped and deterministic; it must not hide configuration changes.

### Step 5 - Inspect semantic and fragment materialization

Look for repeated Polars collection, copies, per-rule scans or redundant projections introduced by semantic interpretation/route generation. Preserve the deterministic rule order and canonical projection firewall.

### Step 6 - Inspect union/identity/integrity paths

Measure schema alignment, union, canonical identity and cross-dataset integrity separately. Optimize only where contract semantics remain obvious and tests prove equivalence.

### Step 7 - Inspect source/provider I/O reuse

Avoid reopening the same workbook/database/provider payload unnecessarily when several bindings/routes consume one physical source. Reuse must not collapse SourceBindingId provenance or change change-detection behavior.

### Step 8 - Inspect warehouse writes and Meta/catalog updates

Batch safe persistence operations, reuse transactions and avoid redundant schema/catalog work while preserving Phase-043 plan-aware cleanup and Phase-044 recovery semantics.

### Step 9 - Re-profile after each semantic optimization group

Keep only changes with measurable benefit or clear memory reduction. Revert speculative changes that increase complexity without material improvement.

### Step 10 - Encode durable performance gates

Define environment-tolerant thresholds/ranges in the repository's benchmark/test convention. Prefer ratios/stage budgets where absolute timings are noisy. Include a documented procedure for interpreting legitimate variance.

### Step 11 - Run correctness and recovery regression

For every retained optimization, run protected-ID comparison, household/investment financial regression, validation failures, replay/recovery and observability lineage checks.

### Step 12 - Publish the final performance evidence

Record before/after table, accepted thresholds and remaining known hotspots. Phase 059 may freeze contracts only after this evidence is green.

## 7. Files and symbols in scope

Change only measured hot paths and benchmark/test infrastructure. Likely owners include:

- planners/compilers;
- semantic rule executor;
- canonical production/identity/integrity services;
- Pre-Bronze/Bronze persistence;
- provider read/cache paths;
- Control Plane lookup batching;
- warehouse publication.

Do not perform general code-quality refactors merely because a profiler exposed a large function.

## 8. Cross-cutting impacts

**Correctness:** zero methodology/identity change permitted.

**Validation:** both trust gates and canonical integrity remain mandatory.

**Recovery:** transaction and replay behavior must remain identical.

**Observability:** one emitter/three consumers stays intact; no event class is removed solely for speed.

**Memory:** materialization/peak-memory improvements count as legitimate wins even where wall-clock change is modest.

**Contract freeze:** the measured architecture is exactly what Phase 059 will freeze.

## 9. Tests and verification

Required:

- reproducible pre/post benchmark table;
- Shan fresh/full and cached/no-change runs;
- external household/domestic/foreign representative runs;
- replay/rebuild performance sample;
- no repeated compilation/I/O/materialization regression without justification;
- exact protected IDs and financial outputs after optimizations;
- validation/integrity failure suites unchanged;
- recovery/rollback green;
- JSONL/multiprocessing lineage green;
- durable performance thresholds encoded or documented in repository-standard form.

## 10. Explicit non-goals

Do not:

- bypass Gate 1, Gate 2 or canonical integrity;
- suppress observability;
- weaken hashing/change detection;
- change financial algorithms;
- invent asynchronous/distributed execution;
- micro-optimize tiny fixtures at the expense of real workloads;
- begin contract extraction or package split.

## 11. Completion checklist

- [ ] Stage-level cost is measured for planning, semantic interpretation, production assembly, identity, Gate 2 and canonical integrity rather than treating the pipeline as one opaque timer.
- [ ] Shan fresh/cached and representative external workloads have reproducible accepted baselines.
- [ ] Every retained optimization has measured benefit or justified memory reduction and preserves deterministic output.
- [ ] No optimization weakens validation, provenance, observability, replay or recovery semantics.
- [ ] Protected financial IDs and household/investment/Tax/Gold outputs remain exact after all performance changes.
- [ ] Durable benchmark thresholds and interpretation guidance exist for Phase 060 acceptance.
- [ ] No known performance blocker remains that would force a contract/API redesign after Phase 059 freeze.

## 12. Commit boundary

Use `pfetl-conventional-commits`. Group optimizations by measured subsystem or coherent performance cause, with benchmark evidence alongside the relevant change. Do not collapse unrelated hot-path changes into one `perf` commit.

## 13. Handoff to Phase 059

Phase 059 may assume the final canonical architecture is externally certified, consumer-pruned and performance-approved. It can now freeze the complete PFETL contract universe without knowingly fossilizing transitional schema, vendor residue or a performance architecture that still needs structural redesign.

## Phase completion record

```text
Phase:
Target release:
Benchmark environments/scenarios:
Baseline evidence:
Optimizations retained:
Files changed:
Financial formulas changed: NO
Protected IDs changed: NO
Validation/recovery impact:
Observability impact:
Performance gates encoded:
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
