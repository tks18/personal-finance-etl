# Phase 014 - Capability Graph

**Target release:** v9.7.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 013  
**Next:** Phase 015  
**Risk:** Medium

## 1. Outcome

Derive and encode PFETL's financial capability graph from the actual v9.5.3/current engine and transformation dependencies. The graph is descriptive/validated in this phase; runtime execution remains full-system.

## 2. Why this phase exists

Optional user workflows cannot be implemented safely with scattered feature flags. With canonical Silver stable, PFETL can now state which capabilities require which canonical evidence and which Silver/Gold contracts they produce.

## 3. Inherited repository state

Phase 013 guarantees stable canonical Silver/Gold semantics. DatasetId is stable. Runtime still executes the full transformation DAG and all analytical engines. Global completeness remains in place until Phase 015.

## 4. Current codebase anchors

Trace current:
- `application/pipeline/transformer.py`
- transformation DAG
- `PipelineExecutor.run_engines()` / analytics phase
- investment Quant service
- Tax service
- Wealth/FIRE/presentation service
- market sync/enrichment
- all 24 Silver + 22 Gold contracts
- calendar construction
- household budget/cashflow contributions from investments.

Important current coupling:
- calendar uses household + investment dates;
- household cashflow/budget may consume investment purchase/sale activity;
- wealth can consume investment analytics;
- FIRE consumes wealth/investment state;
- Tax consumes realized investment events in current full topology.

## 5. Exact target state after this phase

Define typed `CapabilityId` and immutable `CapabilityDescriptor`.

Descriptor fields:
```text
capability_id
required_capabilities
required_bronze_datasets
optional_bronze_datasets
produced_silver_datasets
produced_gold_datasets
required_external_enrichments
optional_contributions
```

The exact initial capability set is derived from code. Likely concepts include household core, investment accounting, benchmark enrichment, foreign-assets/FX enrichment, Tax, wealth, FIRE and simulation, but names/edges must reflect actual ownership rather than this illustrative list.

No callables in descriptors.

## 6. Detailed implementation sequence

### Step 1 - Trace engine graph
Build producer/consumer graph from current calls and contract registry.

### Step 2 - Define capability boundaries
A capability must represent a coherent financial execution responsibility, not a UI tab.

### Step 3 - Model required vs optional contributions
Example: household can exist without investments, while investment purchase/sale activity may optionally contribute to cashflow/budget when investments are enabled.

### Step 4 - Define typed descriptors
Place stable IDs/contracts under `contracts`; registry/graph assembly in application or appropriate contract registry.

### Step 5 - Encode all current contracts
Every Silver/Gold DatasetId must have capability/common ownership. Every required Bronze dataset must be represented.

### Step 6 - Add graph validation
- unknown dependency fails;
- cycle fails;
- unknown dataset fails;
- duplicate capability ID fails;
- produced contract cannot have contradictory owners unless explicitly shared/common.

### Step 7 - Resolve full-current graph
Request all current capabilities and prove produced/required analytical contract universe equals current full-system registry.

### Step 8 - Freeze graph tests
No runtime skipping yet.

## 7. Files and symbols in scope

Create capability contracts/registry/planner primitives and tests.

Read engine/application modules extensively but do not condition their execution yet.

Do not modify Silver/Gold DDL.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity/provenance:** none.

**Observability:** none required; graph is not runtime authority yet.

**Performance:** graph resolution is configuration-scale.

**Compatibility:** full-current capability graph must describe exactly today's outputs.

## 9. Tests and verification

Required:
- exact capability set documented in code;
- cycle/unknown dependency tests;
- every current Silver/Gold contract owned;
- required/optional input tests;
- full-current graph contract set equals current registry;
- calendar/cashflow/wealth/Tax cross-capability relationships represented explicitly;
- no runtime behavior change.

## 10. Explicit non-goals

Do not:
- add user capability configuration;
- skip any engine;
- change completeness checks;
- make DDL plan-aware;
- redesign financial algorithms.

## 11. Completion checklist

- [x] Capability IDs derive from real engine ownership.
- [x] Required vs optional dependencies explicit.
- [x] All analytical contracts covered.
- [x] Full graph resolves deterministically.
- [x] Cycles/unknown references fail.
- [x] Runtime remains full-system.

## 12. Commit boundary

```text
feat(pipeline): define financial capability graph
```

## 13. Handoff to Phase 015

Phase 015 may assume the capability graph can resolve the full current system and knows the exact required/optional datasets and produced contracts. Phase 015 turns that descriptive graph into an immutable ExecutionPlan and makes pipeline completeness plan-scoped.

## Phase completion record

```text
Phase: 014
Target release: v9.7.0
Files changed:
  - src/personal_finance_etl/contracts/capabilities.py
  - src/personal_finance_etl/contracts/__init__.py
  - tests/contracts/test_capabilities.py
  - tests/architecture/test_boundaries.py
Schema changed: NO
Runtime behavior changed: NO
Financial formulas changed: NO
Focused tests: tests/contracts/test_capabilities.py (15 passed)
Architecture tests: tests/architecture/test_boundaries.py (10 passed)
Real-data run: N/A (declarative contract and graph resolution phase; runtime remains full-system)
Performance check: Graph validation and topological resolution execute in <1ms
Compatibility path still present: YES (full-system pipeline execution unchanged)
Old path deleted: N/A (first formal capability graph architecture)
Exit assertions green: YES
Commit: feat(contracts): define financial capability graph and registry
```

A phase is incomplete if any required exit assertion is false.
