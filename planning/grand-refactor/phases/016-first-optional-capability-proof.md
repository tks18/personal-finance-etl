# Phase 016 - First Optional Capability Proof

**Target release:** v9.7.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 015  
**Next:** Phase 017  
**Risk:** Medium-High

## 1. Outcome

Prove the capability architecture end-to-end by selecting one genuinely optional, low-risk enrichment and disabling it through `ExecutionPlan`, orchestration, completeness validation and publication without affecting unrelated financial outputs.

This phase establishes the one approved pattern all later capability composition must follow. No scattered `ENABLE_X` booleans are allowed.

## 2. Why this phase exists

Phase 015 made the execution plan authoritative for completeness while deliberately leaving all engines active. Until one capability is actually disabled, the graph/planner remains structurally correct but operationally unproven.

## 3. Inherited repository state

Phase 015 guarantees:
- `ExecutionPlan` is immutable and deterministic;
- pipeline receives a full-current plan;
- analytical completeness is plan-scoped;
- full-current execution remains identical to the pre-plan runtime;
- plan fingerprint/capability selection are persisted and observable.

Phase 016 must consume that API rather than inventing a second conditional-execution mechanism.

## 4. Current codebase anchors

Re-open the Phase-014 capability graph and current engine orchestration:
- `application/pipeline/execution.py`
- market/benchmark/FX synchronization
- `InvestmentQuantEngine`
- Tax/wealth/FIRE services
- current Silver/Gold loaders
- `DATA_CONTRACT_REGISTRY`

Choose the optional proof capability from the actual graph. Preferred candidate is an enrichment whose absence does not alter accounting truth, identity, household core, Tax basis or required valuation semantics. Do not select investment accounting, household core, FIFO, reconciliation or Tax as the first proof.

## 5. Exact target state after this phase

For the selected capability:
```text
requested capability absent
  -> planner excludes it
  -> ordered engine stages exclude its stage
  -> its produced contracts are inactive
  -> orchestration does not call its service/provider
  -> completeness does not demand its outputs
  -> publication does not treat its outputs as required
  -> unrelated active outputs are identical
```

The conditional must live at the orchestration boundary using plan membership/stages. Domain code must not inspect capability configuration.

## 6. Detailed implementation sequence

### Step 1 - Select and freeze the proof capability
Document why it is optional, exact dependencies, produced DatasetIds and any provider calls it owns. Add/adjust its Phase-014 descriptor if archaeology exposes a missing edge.

### Step 2 - Add orchestration-stage predicate
Use `ExecutionPlan` ordered stages/resolved capabilities. Do not read user config directly in the engine.

### Step 3 - Skip provider/enrichment work
If the capability owns market/provider synchronization, ensure the provider is not called when inactive.

### Step 4 - Align produced-frame validation
Inactive capability outputs must not appear. If an inactive producer still emits a frame, fail rather than silently publish it.

### Step 5 - Align publication
Current Silver/Gold DDL may still be full-universe, but loader/completeness must not require inactive output. Do not implement partial DDL yet; that is Phase 043.

### Step 6 - Enabled-path equivalence
With full-current plan, calls, outputs, IDs and provider requests must remain identical.

### Step 7 - Disabled-path proof
Run a focused fixture with capability omitted. Assert service/provider call count zero, inactive outputs absent, active outputs unchanged.

### Step 8 - Add architecture guard
Capability execution decisions may occur only in planner/orchestration-approved modules. Prevent domain-level direct feature-flag branching.

## 7. Files and symbols in scope

Modify:
- selected capability descriptor if needed;
- `PipelineExecutor`/orchestration stage dispatch;
- selected service/provider call boundary;
- publication/completeness tests;
- architecture tests.

Do not make all capabilities optional today.

## 8. Cross-cutting impacts

**Persistence:** no DDL change. Inactive tables may still physically exist under current full schema; they must not be populated/required. Phase 043 later makes DDL active-set-aware.

**Identity:** protected IDs for active capabilities unchanged.

**Observability:** skipped capability should have a bounded plan/skip diagnostic if existing event vocabulary supports it. Do not emit fake start/end events for work not executed.

**Performance:** disabled path should be faster or equal; enabled path within noise.

## 9. Tests and verification

Required:
- full-current enabled run identical;
- disabled capability service/provider not called;
- inactive produced contracts absent;
- completeness accepts their absence;
- unrelated active Silver/Gold values identical;
- protected IDs identical;
- plan fingerprint differs between enabled/disabled selections;
- architecture test prevents direct domain feature flags;
- full quality gate.

## 10. Explicit non-goals

Do not:
- expose capability selection in source configuration yet;
- implement household-only;
- make DDL partial;
- alter financial formulas;
- refactor unrelated engine orchestration.

## 11. Completion checklist

- [x] One optional capability is explicitly selected and justified (`CapabilityId.BENCHMARK_ENRICHMENT`).
- [x] Execution is controlled only by ExecutionPlan.
- [x] Provider/service work is skipped when inactive (`BenchmarkPipeline.sync_and_calculate` not invoked, `SKIP` event emitted).
- [x] Inactive outputs are not required/published (`df_d_benchmark_master` & `df_f_benchmark_prices` omitted from DAG and plan completeness; spurious output rejected).
- [x] Enabled path is identical (full-current plan executes all 46 tables and syncs prices).
- [x] Disabled path leaves unrelated outputs identical (core 73 lot accounting columns, realized PnL, reconciliation events 100% byte-identical).
- [x] No scattered feature flag introduced (conditional branching confined to `PipelineExecutor` & `TransformationDAG`; `domain/` free of capability plan branching).

## 12. Commit boundary

```text
feat(pipeline): prove optional capability execution
```

## 13. Handoff to Phase 017

Phase 017 may assume capability selection is operationally meaningful and `ExecutionPlan` is the only runtime authority for enabled work. Phase 017 will expose the already-defined source/capability configuration as a production-loaded contract without changing ingestion topology yet.

## Phase completion record

```text
Phase: 016
Target release: v9.7.2
Files changed:
  - src/personal_finance_etl/application/pipeline/transformer.py
  - src/personal_finance_etl/application/pipeline/execution.py
  - tests/architecture/test_boundaries.py
  - tests/application/test_optional_capability_benchmark.py
  - planning/grand-refactor/phases/016-first-optional-capability-proof.md
  - planning/grand-refactor/README.md
Schema changed: NO (analytical completeness scoped to active contracts; DuckDB full schema unchanged)
Runtime behavior changed: YES (when BENCHMARK_ENRICHMENT is disabled in ExecutionPlan, benchmark master transform and benchmark price provider sync are skipped, emitting PresentationKind.SKIP; plan-scoped completeness requires exactly 44 analytical tables instead of 46)
Financial formulas changed: NO
Focused tests: tests/application/test_optional_capability_benchmark.py (7 passed)
Architecture tests: tests/architecture/test_boundaries.py::test_domain_has_no_capability_plan_inspection (11 passed)
Real-data run: YES (live pipeline E2E passed with full plan)
Performance check: PASS (audit-fast in 1.04s; full audit across 6 engines in 80.25s)
Compatibility path still present: NO (default ExecutionPlan is full-universe backward compatible)
Old path deleted: N/A
Exit assertions green: YES (all 350 tests passing; 6/6 quality engines green)
Commit: pending user confirmation
```

A phase is incomplete if any required exit assertion is false.
