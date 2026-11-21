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

### Step 8b - Observability Throughput & Telemetry Benchmarking
Benchmark high-frequency telemetry under multi-file ingestion and multi-engine processing:
- Ensure per-file ingestion events (`PresentationKind.PROGRESS`) and per-ticker progress updates do not saturate multiprocessing queues or degrade event dispatching throughput.
- Verify that append-only forensic logging to JSONL (`outputs/logs/`) scales efficiently without blocking pipeline workers.
- Verify that Desktop narrative formatting and UI sink updates run smoothly without freezing the GUI event loop.

### Step 8c - Desktop GUI Pre-Flight Health Indicator & Non-Blocking UI Hardening
Harden Desktop GUI under Phase 0 pre-flight execution and heavy processing:
- Add visual status pill badges (Config status, Sources reachability, Rules validity, Pre-Flight overall health) directly to the top bar of `UnifiedETLTab`.
- Wire the "▶ Run Pipeline" action to execute Phase 0 pre-flight diagnostics automatically; if errors exist, immediately surface the diagnostic table without mutating DuckDB or SQLite and halt.
- Verify that GUI event loop remains fully responsive and non-blocking during streaming execution and status queue fan-out.

### Step 8d - Comprehensive FIRE & Monte Carlo Numerical Kernel Hardening & Test Suite
Author and execute `tests/domain/test_fire_monte_carlo_engine.py` to exhaustively certify PFETL's heaviest analytical engine across 10 statistical, numerical, and performance dimensions:
1. **Deterministic Seeding & Thread Reproducibility:** Verify that identical `root_seed` and monthly offsets produce bit-identical stochastic percentile trajectories across multiple threads (`prange`) and repeated invocations.
2. **Markov Regime Switching (Bull, Bear, Stagflation):** Assert state transitions strictly obey the 3x3 transition matrix ($P_{ij}$); verify empirical state occupancy converges to the theoretical stationary distribution $\pi = \pi P$ over long horizons (e.g. 50,000 simulated months).
3. **Jump-Diffusion & Tail Risk Shocks:** Assert Poisson jump arrival frequencies match `jump_probability_annual` and jump magnitudes properly compound negative drawdowns under asset shock events.
4. **Human Capital Shock Simulation:** Verify stochastic income shock events obey `shock_probability`, durations remain bounded within `[shock_duration_min, shock_duration_max]`, and unemployment benefits accurately offset living expense burn.
5. **Dynamic Glide Path & Debt Allocation:** Assert asset allocation dynamically shifts along the pre-retirement derisking window, holds FI target equity at retirement, and executes post-retirement re-risking with dynamic debt yield adjustments.
6. **Guyton-Klinger Dynamic Guardrails:** Test the Capital Preservation Rule (spending cut by `gk_cut` when withdrawal rate exceeds initial rate by `gk_upper`) and Prosperity Rule (spending raised by `gk_raise` when withdrawal rate falls below `gk_lower`).
7. **Stochastic Inflation Dynamics:** Verify mean-reverting inflation paths (Vasicek/Ornstein-Uhlenbeck drift) with hard boundary clipping to `inf_min` and `inf_max` preventing runaway or negative inflation anomalies.
8. **Sequence of Returns Risk (SORR) Sensitivity:** Compare early-retirement bear market paths against late-retirement bear market paths; prove that early drawdowns significantly reduce portfolio survival probability, validating SORR sensitivity.
9. **Boundary & Degeneracy Invariants:** Test extreme edge conditions ($0 starting net worth, negative monthly savings, 100% equity collapse, zero expense burn, and extreme target lifespan); assert zero NaN, Inf, or unhandled exceptions.
10. **Vectorized Polars Batch UDF & Numba JIT Scale:** Benchmark 10,000 simulation iterations across 120 monthly rows; assert total execution time $< 1.5$ seconds with zero memory leaks and proper parallel scaling.

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
- final thresholds encoded/documented in test/benchmark convention;
- **FIRE & Monte Carlo Numerical Kernel Certification (`tests/domain/test_fire_monte_carlo_engine.py`):**
  - Bit-identical reproducibility across random seeds and parallel threads (`prange`);
  - Markov regime transition frequencies converging to theoretical stationary distribution ($\pi = \pi P$);
  - Jump-diffusion shock distributions and cumulative asset drawdown compounding;
  - Human capital unemployment shock probabilities and expense coverage offsets;
  - Dynamic glide path asset allocation (derisking, target equity, re-risking, debt yields);
  - Guyton-Klinger dynamic guardrail triggers (capital preservation cut vs prosperity raise);
  - Stochastic inflation mean-reverting Vasicek paths with min/max bounding;
  - Sequence of Returns Risk (SORR) early vs late market crash sensitivity;
  - Numerical degeneracy and boundary invariants ($0 net worth, 100% equity crash, negative savings);
  - Vectorized Polars batch UDF scale (10,000 iterations across 120 monthly rows in <1.5s).

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
- [ ] Observability throughput and UI narrative rendering benchmarks satisfied.
- [ ] Durable performance gate exists.
- [ ] Desktop GUI pre-flight health indicator verified and UI event loop non-blocking under full execution load.
- [ ] Comprehensive FIRE & Monte Carlo numerical kernel test suite green across all 10 statistical, regime, and performance dimensions.

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
