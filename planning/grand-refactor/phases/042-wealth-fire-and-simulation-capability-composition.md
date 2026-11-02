# Phase 042 - Wealth, FIRE and Simulation Capability Composition

**Target release:** v10.1.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 041  
**Next:** Phase 043  
**Risk:** High

## 1. Outcome

Make Wealth and FIRE plan-driven capabilities with explicit required and optional investment contributions, and isolate simulation as a distinct capability if the current implementation supports meaningful independent execution.

At phase end every major PFETL financial engine is governed by `ExecutionPlan`; no engine is implicitly mandatory merely because the old pipeline always ran it.

## 2. Why this phase exists

Wealth and FIRE are downstream aggregations with cross-domain inputs. Their optionality cannot be modeled by simply skipping a function: the planner must know which household state is required, when investments contribute, and whether simulation is a separate computational responsibility.

## 3. Inherited repository state

Phase 041 guarantees Tax composition. Household/investment/enrichment composition is already operational. Gold contracts remain full-DDL physically but active-set metadata is accurate.

## 4. Current codebase anchors

Re-trace post-v10:
- wealth service/presentation engine;
- net-worth producers;
- FIRE producers;
- simulation engine/provenance;
- household balance/cashflow inputs;
- investment portfolio analytics inputs;
- current 9-ish WealthPresentationEngine Gold contracts from original registry, updated for current code;
- capability graph.

Create exact contract/input table before edits.

## 5. Exact target state after this phase

Conceptually:
```text
WEALTH
  requires HOUSEHOLD_CORE
  optional/required investment contribution according to current methodology
  produces net-worth/wealth Gold contracts

FIRE
  requires exact household/wealth state defined by methodology
  investment portfolio contribution explicit
  produces FIRE analytical contracts

SIMULATION (only if independently meaningful)
  requires FIRE/wealth inputs as actually implemented
  produces simulation-specific output/provenance
```

If simulation is inseparable from FIRE in current methodology, do not manufacture a capability merely for symmetry. Record it as an internal FIRE stage.

## 6. Detailed implementation sequence

### Step 1 - Freeze Wealth/FIRE dependency table
Map every input DatasetId and produced Gold contract.

### Step 2 - Decide simulation boundary from code
Document whether simulation earns its own capability. Decision must follow current ownership and output semantics.

### Step 3 - Update capability graph
Encode required/optional edges and active outputs.

### Step 4 - Make Wealth orchestration plan-driven
Household-only wealth path must be valid if methodology supports it; investment contribution is absent, not fabricated.

### Step 5 - Make FIRE orchestration plan-driven
Missing mandatory FIRE evidence fails at planner/preflight. Optional investment contribution handled explicitly.

### Step 6 - Simulation orchestration
Conditional only if capability is separately modeled; otherwise remains an internal FIRE stage with plan-aware FIRE execution.

### Step 7 - Disabled-path proofs
Wealth/FIRE disabled => zero service calls and no produced contracts.

### Step 8 - Full Shan regression
Net worth, wealth, FIRE, simulation outputs and all upstream financial IDs unchanged.

## 7. Files and symbols in scope

Modify:
- wealth/FIRE/simulation capability descriptors;
- planner;
- orchestration;
- active Gold contract metadata;
- tests.

Do not change formulas/assumptions in FinancialRules or domain engines.

## 8. Cross-cutting impacts

**Persistence:** active Gold set changes logically; physical DDL waits Phase 043.

**Identity:** no upstream identity change.

**Observability:** stages/events reflect only executed capabilities; simulation provenance retained when active.

**Performance:** disabled downstream capabilities skip their computations.

**Financial correctness:** optional contributions modeled explicitly; no zero-fill hacks.

## 9. Tests and verification

Required:
- exact dependency/output table;
- household-only wealth case according to methodology;
- investment contribution enabled/disabled tests;
- FIRE missing-mandatory-input failure;
- disabled service call counts zero;
- simulation boundary test/documented decision;
- full Shan wealth/FIRE/simulation equivalence.

## 10. Explicit non-goals

Do not:
- alter FIRE assumptions;
- alter net-worth methodology;
- add new simulation algorithms;
- make DDL partial yet;
- change ingestion.

## 11. Completion checklist

- [ ] Wealth capability explicit.
- [ ] FIRE capability explicit.
- [ ] Simulation boundary justified.
- [ ] Optional investment contributions correct.
- [ ] Disabled engines perform zero work.
- [ ] Full Shan outputs unchanged.
- [ ] All major financial engines now plan-driven.

## 12. Commit boundary

```text
feat(pipeline): compose wealth and fire capabilities
```

## 13. Handoff to Phase 043

Phase 043 may assume the logical active Silver/Gold contract set is correct for every supported capability combination. It will make the physical analytical warehouse and Meta/catalog reflect that active set rather than always creating the full universe.

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
