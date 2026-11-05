# Phase 015 - Execution Planner and Plan-Scoped Completeness

**Target release:** v9.7.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 014  
**Next:** Phase 016  
**Risk:** Medium-High

## 1. Outcome

Introduce the immutable `ExecutionPlan`, implement deterministic capability resolution, inject a full-current plan into the pipeline, persist/fingerprint it, and replace global analytical completeness with plan-scoped completeness. No capability is intentionally disabled yet.

## 2. Why this phase exists

Phase 014 defines what capabilities mean. Runtime must consume one resolved authority before Phase 016 can safely prove optional execution. The first runtime migration must preserve full-system behavior exactly.

## 3. Inherited repository state

Phase 014 guarantees:
- stable CapabilityIds/descriptors;
- validated dependency graph;
- full-current graph resolves to the same analytical universe as today;
- runtime still executes all stages unconditionally;
- `PipelineExecutor._run_analytics_phase()` still treats `DATA_CONTRACT_REGISTRY` as globally mandatory.

## 4. Current codebase anchors

Current anchors:
- `application/pipeline/execution.py`
- current global completeness:
  - unexpected produced frame if not in `DATA_CONTRACT_REGISTRY`
  - missing registered contract if absent from `self.dfs`
- `PipelineLifecycle` run/config snapshots
- Control Plane settings/rules snapshots
- observability context/fingerprints
- transformation and engine orchestration order.

## 5. Exact target state after this phase

Create immutable `ExecutionPlan` conceptually containing:
```text
plan_fingerprint
requested_capabilities
resolved_capabilities
required_source_datasets
required_bronze_datasets
active_silver_datasets
active_gold_datasets
required_external_enrichments
ordered_engine_stages
```

`CapabilityPlanner` in application:
- accepts requested capabilities + capability/contract registries;
- resolves dependencies topologically;
- rejects cycles/missing required canonical datasets;
- returns deterministic plan.

For this phase, default requested capabilities are the full current set.

Completeness becomes:
```text
produced analytical DatasetIds subset-of plan.active analytical contracts
AND
plan.required analytical contracts subset-of produced
```
using stable DatasetId rather than historical frame prefixes where migration permits.

## 6. Detailed implementation sequence

### Step 1 - Define ExecutionPlan
Immutable, hash/fingerprint stable, no infrastructure callables.

### Step 2 - Implement CapabilityPlanner
Resolve requested -> transitive required capabilities -> required datasets/contracts -> ordered engine stages.

### Step 3 - Add full-current default selection
Until user source configuration/capability selection arrives later, bootstrap requests the full current capability set.

### Step 4 - Inject plan into pipeline construction
Prefer constructor/dependency injection from orchestrator/bootstrap rather than global lookup.

### Step 5 - Make discovery/preflight aware of required datasets without skipping current sources yet
Plan can expose requirements, but current fixed ingestion still runs as before. Do not prematurely reject optional-source absence until source configuration phase defines satisfiability.

### Step 6 - Replace analytical completeness
Translate current produced frame keys to DatasetIds using Phase-001 registry. Validate against plan active/required sets.

### Step 7 - Persist/fingerprint plan
Add plan fingerprint/capability selection to run provenance using existing Control Plane snapshot patterns. Avoid duplicating entire graph per event.

### Step 8 - Add observability context
Bounded plan fingerprint and capability IDs at run/phase boundaries. Do not redesign emitter.

### Step 9 - Full-current equivalence
Prove ordered stages, produced contracts and financial outputs match pre-phase behavior exactly.

## 7. Files and symbols in scope

Modify:
- capability planner/contracts
- pipeline execution/orchestrator/bootstrap wiring
- analytical completeness logic
- run provenance snapshot/fingerprint
- bounded observability context
- tests

Do not yet make individual engine calls conditional.

## 8. Cross-cutting impacts

**Persistence:** additive Control Plane provenance only if required; no DuckDB DDL.

**Identity:** no impact.

**Observability:** plan fingerprint + resolved capability summary; existing run/operation lineage unchanged.

**Performance:** planner runs once per run; negligible relative to pipeline.

**Compatibility:** full-current default plan must be indistinguishable financially from previous runtime.

## 9. Tests and verification

Required:
- deterministic plan fingerprint;
- dependency resolution order stable;
- full-current active Silver/Gold set equals current contract registry;
- unexpected produced contract fails;
- missing required active contract fails;
- synthetic partial plan does not require inactive contracts;
- pipeline still executes full current stages;
- Control Plane records plan/config provenance;
- full Shan outputs/IDs/runtime equivalent.

## 10. Explicit non-goals

Do not:
- expose capability selection to user configuration yet;
- skip engines;
- make Silver/Gold DDL partial;
- alter source discovery;
- add Pre-Bronze/Pandera;
- change financial formulas.

## 11. Completion checklist

- [x] ExecutionPlan immutable and deterministic.
- [x] CapabilityPlanner resolves full graph.
- [x] Pipeline receives plan through explicit dependency.
- [x] Completeness is plan-scoped.
- [x] Full-current behavior unchanged.
- [x] Plan fingerprint persisted.
- [x] Observability context bounded.
- [x] Synthetic partial-plan tests pass.
- [x] Full Shan run green.

## 12. Commit boundary

```text
feat(pipeline): add execution planning
```

## 13. Handoff to Phase 016

Phase 016 may assume execution-plan completeness is authoritative while actual engine execution remains full-system. It will choose one genuinely optional low-risk enrichment and prove the first end-to-end enabled/disabled capability path without introducing scattered feature flags.

## Phase completion record

```text
Phase: 015
Target release: v9.7.1
Files changed:
  - src/personal_finance_etl/contracts/execution_plan.py (NEW)
  - src/personal_finance_etl/contracts/observability.py
  - src/personal_finance_etl/contracts/__init__.py
  - src/personal_finance_etl/application/pipeline/planner.py (NEW)
  - src/personal_finance_etl/application/pipeline/execution.py
  - src/personal_finance_etl/application/pipeline/orchestrator.py
  - src/personal_finance_etl/application/pipeline/lifecycle.py
  - src/personal_finance_etl/infrastructure/control_plane/schema.py
  - src/personal_finance_etl/infrastructure/control_plane/run_repository.py
  - src/personal_finance_etl/infrastructure/observability/emitter.py
  - tests/contracts/test_execution_plan.py (NEW)
  - tests/application/test_capability_planner.py (NEW)
  - tests/application/test_plan_scoped_completeness.py (NEW)
Schema changed: YES (cp_plan_snapshots table and cp_runs.plan_snapshot_id column added via migration)
Runtime behavior changed: NO (default full plan preserves 100% full-current engine execution)
Financial formulas changed: NO
Focused tests: 14 passing (tests/contracts/test_execution_plan.py, tests/application/test_capability_planner.py, tests/application/test_plan_scoped_completeness.py)
Architecture tests: 10 passing (tests/architecture/test_boundaries.py)
Real-data run: Verified fullShan live test passing
Performance check: Observability throughput >10k rec/s, fast gate <2s
Compatibility path still present: YES
Old path deleted: Global DATA_CONTRACT_REGISTRY completeness assertion replaced with plan-scoped completeness
Exit assertions green: YES
Commit: Pending user approval
```

A phase is incomplete if any required exit assertion is false.
