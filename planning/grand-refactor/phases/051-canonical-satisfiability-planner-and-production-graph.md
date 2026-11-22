# Phase 051 - Canonical Satisfiability Planner and Production Graph

**Target release:** v10.4.0  
**Expected effort:** 4-5 hours  
**Previous:** Phase 050  
**Next:** Phase 052  
**Risk:** Very High

## 1. Outcome

Make canonical evidence producibility a preflight planning concern.

Given the active `ExecutionPlan`, compiled source bindings/routes, provider capabilities and registered derivation recipes, PFETL must resolve a deterministic acyclic `CanonicalProductionPlan` or fail before physical execution with actionable diagnostics.

## 2. Why this phase exists

The production engine in Phase 050 can execute a supplied plan, but source-agnostic operation requires a separate answer to:

> Can this user's configured evidence actually satisfy the canonical financial evidence required by the selected capabilities?

This logic cannot live in `CapabilityPlanner`, SourcePlanner, diagnostics or runtime fallbacks without recreating source topology coupling.

## 3. Inherited repository state

Phase 050 guarantees:
- SourceBindingPlan and canonical routes are executable;
- canonical fragments can be assembled/validated;
- provider and derived producer kinds have typed production metadata;
- canonical production fingerprints can be formed;
- capabilities still primarily reference transitional DatasetIds until domain migration.

## 4. Current codebase anchors

Inspect:
- `contracts/capabilities.py` and `config/capabilities.py`;
- current `CapabilityGraph` / `ExecutionPlan` compiler;
- `application/pipeline/source_planner.py`;
- provider plan metadata;
- derivation recipe descriptors introduced in Phase 050;
- `application/diagnostics/service.py` preview-plan output;
- `application/pipeline/replay.py` affected-dataset logic.

## 5. Exact target state after this phase

Introduce an application planning service with no physical I/O:

```text
ExecutionPlan.required_bronze_datasets
        + SourceBindingPlans/routes
        + provider producer descriptors
        + derivation recipe descriptors
        ↓
CanonicalSatisfiabilityPlanner
        ↓
producer candidate sets
        ↓
resolution + dependency graph
        ↓
CanonicalProductionPlan
```

Resolution rules:
1. explicit valid production selection wins;
2. otherwise exactly one valid candidate may auto-resolve;
3. zero candidates for a required dataset is an error;
4. multiple candidates without explicit selection is an ambiguity error;
5. source UNION members are explicit routes, never inferred from declaration order;
6. derived dependencies must themselves be satisfiable;
7. cycles fail with the concrete dependency cycle;
8. optional unsatisfied datasets remain absent, not fake-empty;
9. stale existing Bronze cannot satisfy a missing current producer.

The result is immutable, deterministic and fingerprinted.

## 6. Detailed implementation sequence

### Step 1 - Build candidate descriptors
Represent source, provider and derived candidates with enough metadata for planning but no executable infrastructure objects.

### Step 2 - Map capability requirements to canonical production requests
Initially support both transitional and newly declared DatasetIds. Keep CapabilityPlanner unaware of physical sources.

### Step 3 - Discover source candidates
Use compiled CanonicalRoutes and explicit production declarations. Validate enabled source/binding/route and target compatibility.

### Step 4 - Discover provider candidates
Ask provider planning metadata whether the target can be produced. Do not perform network I/O.

### Step 5 - Discover derived candidates recursively
Use recipe metadata only. Gather canonical dependencies and reject unsupported/disabled targets.

### Step 6 - Apply producer resolution rules
Implement explicit selection, single-candidate auto-resolution, missing-producer and ambiguity results. Never use list order or existing warehouse state.

### Step 7 - Build and validate dependency DAG
Detect cycles and produce deterministic topological order. Preserve dependency chains for diagnostics and replay.

### Step 8 - Define typed planning diagnostics
Return all relevant unsatisfied/ambiguous requirements for preview instead of stopping at the first issue. Actual run preflight fails when the result is not satisfiable.

### Step 9 - Fingerprint the complete production plan
Include capabilities, resolved producer definitions, route/binding fingerprints, dataset contract versions, identity strategies and recipe versions.

### Step 10 - Integrate replay dependency closure
Changed binding/route/production/recipe should invalidate the target DatasetId and all derived canonical dependents. Keep FinancialRules replay separate.

### Step 11 - Upgrade Phase-045 diagnostics
`preview-plan` shows required canonical evidence, resolved producer, source routes/derived dependencies and satisfiability result. `dry-run-admission` executes the resolved plan in isolation.

### Step 12 - Run generic planner certification
Test direct, union, derived, provider, optional, ambiguous, missing, disabled and cyclic combinations without domain-specific branches.

## 7. Files and symbols in scope

Expected changes:
- new application planning service;
- capability-to-evidence planning helpers;
- production plan/fingerprint contracts;
- replay dependency resolver;
- diagnostics typed results/CLI rendering;
- architecture/planning tests.

Do not rewrite domain capability requirements to the new household/investment DatasetIds until Phases 053/055.

## 8. Cross-cutting impacts

**Planning:** major new preflight boundary. Physical I/O starts only after a satisfiable immutable production plan exists.

**Replay:** canonical dependency closure becomes graph-derived rather than hardcoded where the new model applies.

**Diagnostics:** users can see why a capability is or is not satisfiable before running evidence ingestion.

**Performance:** planner must be cheap and deterministic. No file reads/provider calls.

**Architecture:** CapabilityPlanner remains about financial capability composition; SatisfiabilityPlanner remains about canonical evidence production.

## 9. Tests and verification

Required:
- required dataset with one source producer resolves;
- explicit UNION resolves exactly listed routes;
- no producer produces a typed unsatisfied requirement with capability cause;
- direct source + derived recipe produces an ambiguity unless explicitly selected;
- explicit source/derived selection resolves deterministically;
- derived dependency chain topologically orders correctly;
- cycle diagnostics report the cycle;
- optional missing evidence does not create a fake dataset;
- disabled binding cannot satisfy requirement;
- stale Bronze table cannot satisfy current config;
- equivalent config ordering yields same plan fingerprint/order;
- provider availability is planned without network I/O;
- replay closure includes derived dependents;
- preview-plan is side-effect free and dry-run remains non-mutating;
- transitional full Shan plan remains satisfiable and financially unchanged.

## 10. Explicit non-goals

Do not:
- migrate household/investment capability requirements yet;
- add automatic priority between source and derived producers;
- perform source reachability/network checks in satisfiability planning;
- validate row-level foreign keys before execution;
- optimize concurrent graph execution.

## 11. Completion checklist

- [x] Every active required DatasetId resolves to exactly one producer definition or a typed preflight error.
- [x] Ambiguous source/provider/derived alternatives require explicit resolution and never depend on declaration order.
- [x] Derived dependencies form an acyclic deterministic production graph with actionable cycle/missing diagnostics.
- [x] Optional unsatisfied evidence remains absent rather than materializing fake empty datasets.
- [x] CanonicalProductionPlan fingerprinting is stable and replay dependency closure follows the graph.
- [x] `preview-plan` exposes producer resolution and `dry-run-admission` can execute the resolved plan without mutation.
- [x] Generic topology certification is green while the current Shan plan remains fully satisfiable.

## 12. Commit boundary

Use `pfetl-conventional-commits` for semantic grouping of planner core, replay integration and diagnostics/tests. The commit skill owns staging/message mechanics; this phase only requires each group to be independently coherent and green.

## 13. Handoff to Phase 052

Phase 052 may assume the entire generic architecture works **against transitional contracts**: binding-owned acquisition, semantic routes, N:M production and satisfiability. It now performs the first real financial evidence migration by producing the six canonical household Bronze datasets from Shan's existing source topology while leaving old Silver as the comparison oracle.

## Phase completion record

```text
Phase: 051
Target release: v10.4.0
Files changed:
- src/personal_finance_etl/contracts/canonical_plans.py
- src/personal_finance_etl/contracts/diagnostics.py
- src/personal_finance_etl/contracts/__init__.py
- src/personal_finance_etl/application/ingestion/canonical_recipes.py
- src/personal_finance_etl/application/pipeline/satisfiability.py
- src/personal_finance_etl/application/pipeline/source_planner.py
- src/personal_finance_etl/application/pipeline/replay.py
- src/personal_finance_etl/application/pipeline/__init__.py
- src/personal_finance_etl/application/diagnostics/service.py
- src/personal_finance_etl/presentation/cli/diagnostics.py
- tests/architecture/test_canonical_satisfiability_guards.py
- tests/application/test_canonical_satisfiability_planner.py
- planning/grand-refactor/phases/051-canonical-satisfiability-planner-and-production-graph.md
- planning/grand-refactor/README.md
Schema changed: NO (internal satisfiability graph, topological resolution, and production planning contracts)
Runtime behavior changed: YES (preflight satisfiability planning verifies evidence producers, generates cryptographic plan fingerprints, and builds deterministic production DAG before execution)
Financial formulas changed: NO
Focused tests: tests/application/test_canonical_satisfiability_planner.py
Architecture tests: tests/architecture/test_canonical_satisfiability_guards.py, tests/architecture/test_boundaries.py, tests/architecture/test_constitutional_certification.py
Real-data run: Shan generalized ingestion certification passed (15/15), 10-run multi-fixture state machine passed (7/7)
Performance check: Pure in-memory preflight satisfiability plan and topological sort execute in <0.01s without storage/network I/O
Compatibility path still present: YES (Transitional 1:1 DIRECT route compilation supported through CompatibilitySourceBindingCompiler pending Phase 055 demolition)
Old path deleted: NO (Old direct slice execution preserved under transitional fallback)
Exit assertions green: YES (7/7)
Commits: Pending conventional-commit review and staging
```

A phase is incomplete if any required exit assertion is false.
