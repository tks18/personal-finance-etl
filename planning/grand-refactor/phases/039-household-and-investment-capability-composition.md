# Phase 039 - Household and Investment Capability Composition

**Target release:** v10.1.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 038  
**Next:** Phase 040  
**Risk:** High

## 1. Outcome

Make household core and investment accounting independently composable through `ExecutionPlan`, including their required/optional cross-contributions, and prove a household-only user can run PFETL with no investment evidence while the full Shan plan remains identical.

This phase does not yet separate benchmark or foreign/FX enrichments; those are Phase 040.

## 2. Why this phase exists

Phase 016 proved one low-risk optional capability. After v10.0 generalized ingestion, the major product requirement is now real: users may have household evidence without investments. This requires more than skipping Quant; the base transformation/calendar/budget pipeline currently contains investment coupling.

## 3. Inherited repository state

Phase 038 certifies generalized ingestion. Capability graph/planner from Phases 014-016 is runtime authority.

Current historical coupling to re-trace on post-v10 branch:
- TransformationDAG builds household + MF + Indian + US investment state;
- master calendar spans household and investment dates;
- household budget/cashflow may include investment purchase/sale flows;
- wealth/Tax/FIRE dependencies exist but remain enabled in full plan.

Phase 039 focuses only household core vs investment accounting boundary.

## 4. Current codebase anchors

Re-trace post-v10:
- Transformer / transformation DAG
- household dimensions/facts
- investment transform stages
- master calendar construction
- household budget/cashflow producers
- capability descriptors and ExecutionPlan
- current Silver/Gold ownership.

Use the post-v10 code as authority because earlier phases may have moved symbols.

## 5. Exact target state after this phase

Define/finalize two capability responsibilities:

```text
HOUSEHOLD_CORE
 required household Bronze datasets
 produced household Silver/core Gold where applicable
 optional contribution: investment cash movements when INVESTMENT_ACCOUNTING active

INVESTMENT_ACCOUNTING
 required investment Bronze/reference datasets
 produced investment master/purchases/sales/lots/reconciliation state
 no mandatory benchmark/foreign enrichment in this phase
```

Household-only plan:
- does not require investment source datasets;
- does not execute investment transforms/FIFO/reconciliation;
- calendar derives from household dates only;
- budget/cashflow remains financially valid without investment contribution;
- no missing-contract failure for investment outputs.

Full Shan plan remains identical.

## 6. Detailed implementation sequence

### Step 1 - Re-trace base transformation dependencies
Map current Transformer/DAG nodes to HOUSEHOLD_CORE vs INVESTMENT_ACCOUNTING vs shared/common.

### Step 2 - Split orchestration, not formulas
Make transformation stages plan-aware. Reuse existing transform functions; do not fork household/investment algorithms.

### Step 3 - Calendar composition
Define required household date sources and optional investment date contribution. Test household-only date range and full-plan equivalence.

### Step 4 - Cashflow/budget optional contribution
Where investment purchases/sales affect household views, model them as optional inputs when investment capability active. Absence must not fabricate zero-valued investment frames unless contract explicitly models empty contribution.

### Step 5 - Source requirement resolution
Household-only ExecutionPlan must not require MF/stock/US source datasets or market-provider evidence.

### Step 6 - Analytical completeness
Active Silver/Gold sets exclude investment-accounting outputs. Physical DDL remains full until Phase 043.

### Step 7 - Household-only fixture
Use generalized external household fixture from Phase 029/038. Run end-to-end with no investment files/config.

### Step 8 - Full Shan regression
Full capability plan must produce identical household + investment outputs and protected IDs.

## 7. Files and symbols in scope

Modify:
- capability descriptors;
- Transformer/DAG orchestration boundaries;
- calendar input composition;
- household cashflow/budget input composition;
- source requirement resolution;
- focused fixtures/tests.

Read but do not independently compose yet:
- Tax;
- wealth;
- FIRE;
- benchmark/FX/foreign enrichment.

Do not change physical analytical DDL.

## 8. Cross-cutting impacts

**Persistence:** inactive investment outputs not required/populated; DDL may still exist.

**Identity:** no investment IDs in household-only run; full Shan IDs unchanged.

**Observability:** stages reflect actual executed capabilities; no fake investment events.

**Performance:** household-only should avoid investment parsing/transforms and be measurably lighter.

**Financial correctness:** absence of investments is a valid model state, not an error/defaulted fake data state.

## 9. Tests and verification

Required:
- household-only SourceConfiguration validates without investment datasets;
- no investment provider/file access;
- no investment transforms/FIFO/reconciliation calls;
- household calendar valid;
- budget/cashflow valid;
- active contract set excludes investment accounting outputs;
- full Shan outputs/IDs identical;
- household-only runtime demonstrates skipped work.

## 10. Explicit non-goals

Do not:
- make benchmark/FX/US enrichment independently selectable yet;
- change Tax/wealth/FIRE methodology;
- make DDL partial;
- introduce fake empty investment datasets.

## 11. Completion checklist

- [ ] Household-only plan resolves.
- [ ] Investment evidence not required/accessed.
- [ ] Household transforms execute independently.
- [ ] Optional investment contributions modeled explicitly.
- [ ] Investment accounting remains correct when enabled.
- [ ] Full Shan regression green.

## 12. Commit boundary

```text
feat(pipeline): compose household and investment capabilities
```

## 13. Handoff to Phase 040

Phase 040 may assume household and investment accounting are separable. It will split benchmark enrichment and foreign-assets/FX/US-market enrichment from core investment accounting so domestic-only investment users do not require those external data paths.

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
