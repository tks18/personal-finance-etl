# Phase 041 - Tax Capability Composition

**Target release:** v10.1.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 040  
**Next:** Phase 042  
**Risk:** High

## 1. Outcome

Make Tax a fully plan-driven financial capability with explicit household/investment input requirements, active Silver/Gold ownership, and preflight failure semantics. Tax must execute only when requested and satisfiable, while the full Shan plan remains byte-for-byte equivalent in Tax events and outputs.

## 2. Why this phase exists

Phases 039-040 made household, investment accounting and market enrichments independently composable. Tax still historically assumes the full investment/household universe exists. External users need a capability model that states exactly which Tax evidence is mandatory rather than discovering missing frames deep inside the Tax engine.

## 3. Inherited repository state

Phase 040 guarantees:
- HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING are independently resolved;
- benchmark and foreign/FX enrichments are optional;
- ExecutionPlan owns active work;
- generalized ingestion is stable.

Tax methodology, `TAX` deterministic identity and current Tax Gold outputs remain unchanged.

## 4. Current codebase anchors

Re-trace the post-v10 Tax path:
- Tax service/application entry point;
- domain Tax event classification/hashing;
- realized investment event inputs;
- household income/expense inputs used by Tax;
- `f_Tax_Events` Silver contract;
- Tax Gold contracts;
- Tax-related FinancialRules;
- `PipelineExecutor` engine ordering;
- capability graph.

Build an exact input table before coding: DatasetId, required/optional, reason, producer capability, Tax consumer.

## 5. Exact target state after this phase

Define/finalize `TAX` capability:

```text
TAX
  required capabilities: exact graph-derived set
  required inputs: exact canonical household/investment datasets
  optional inputs: only where methodology genuinely permits absence
  produced Silver: Tax event state
  produced Gold: Tax analytical contracts
```

Rules:
- if Tax requested and mandatory evidence/capability missing, planner/preflight fails before Tax engine execution;
- if Tax not requested, Tax service is not called and Tax outputs are inactive;
- benchmark/foreign enrichments are dependencies only if Tax methodology actually uses them;
- `TAX` event hashing remains unchanged.

## 6. Detailed implementation sequence

### Step 1 - Freeze Tax dependency table
Trace every dataframe read by Tax. Distinguish accounting evidence from analytical enrichments.

### Step 2 - Update capability descriptor
Encode exact required/optional dependencies and produced contracts.

### Step 3 - Add planner/preflight satisfiability
Requested Tax with missing mandatory input fails with actionable DatasetId/capability remediation before engine execution.

### Step 4 - Make Tax orchestration conditional
Pipeline calls Tax service only when `TAX` active. Domain Tax code never reads feature flags.

### Step 5 - Align completeness/publication
Tax Silver/Gold contracts active only when Tax requested. Physical DDL remains full until Phase 043.

### Step 6 - Tax-disabled proof
Run household/investment plan without Tax. Assert zero Tax service calls/events/outputs and unrelated outputs identical.

### Step 7 - Household-only Tax decision
Based on actual methodology, either support household-only Tax with explicitly reduced inputs or reject it as an invalid capability combination. Do not invent support by zero-filling missing investment evidence.

### Step 8 - Full Shan Tax regression
Compare Tax event count, classifications, taxable amounts, sub-heads, Gold outputs and `TAX` IDs byte-for-byte.

## 7. Files and symbols in scope

Modify:
- Tax capability descriptor;
- planner/preflight;
- pipeline Tax orchestration;
- active contract metadata;
- Tax capability tests.

Read but do not change:
- Tax formulas/classification;
- FinancialRules semantics;
- deterministic Tax hashing algorithm.

## 8. Cross-cutting impacts

**Persistence:** inactive Tax contracts not required/populated; DDL unchanged until Phase 043.

**Identity:** `TAX` IDs are absolute non-regression gate.

**Observability:** no Tax start/end events when inactive; active Tax remains correlated to capability/run.

**Performance:** Tax-disabled plan skips Tax computation.

**Financial correctness:** missing mandatory evidence fails; never silently zero-fill or exception-default.

## 9. Tests and verification

Required:
- exact Tax dependency table;
- requested+satisfiable Tax runs;
- requested+missing mandatory input fails pre-engine;
- Tax-disabled service call count zero;
- inactive Tax outputs absent from produced set;
- full Shan Tax events/amounts/IDs identical;
- unrelated outputs identical when Tax disabled;
- architecture guard against direct Tax feature flags.

## 10. Explicit non-goals

Do not:
- change Tax methodology;
- change Tax rules/sub-heads;
- make missing investment evidence zero;
- make DDL partial;
- compose wealth/FIRE in this phase.

## 11. Completion checklist

- [ ] Tax dependencies explicit.
- [ ] Planner validates Tax satisfiability.
- [ ] Tax execution is plan-driven.
- [ ] Disabled Tax performs zero work.
- [ ] Missing mandatory evidence fails early.
- [ ] Tax values and IDs unchanged under full plan.

## 12. Commit boundary

```text
feat(pipeline): compose tax capability
```

## 13. Handoff to Phase 042

Phase 042 may assume Tax is independently plan-driven. It will complete financial-engine composition by separating Wealth, FIRE and simulation responsibilities while preserving their current financial relationships.

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
