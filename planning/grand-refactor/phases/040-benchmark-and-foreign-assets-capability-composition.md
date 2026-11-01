# Phase 040 - Benchmark and Foreign-Assets Capability Composition

**Target release:** v10.1.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 039  
**Next:** Phase 041  
**Risk:** High

## 1. Outcome

Separate benchmark enrichment and foreign-assets/FX/US-market enrichment from core investment accounting, making both explicit optional capabilities with correct source/provider requirements and active outputs.

At phase end PFETL supports household-only, domestic investment accounting without foreign-data requirements, optional benchmark analytics, foreign-asset valuation with FX/US-market evidence, and the unchanged full Shan plan.

## 2. Why this phase exists

Investment accounting and market enrichments have different correctness roles. A domestic-investment user should not need US market/FX evidence, and benchmark comparison should not be a hidden prerequisite for accounting truth.

## 3. Inherited repository state

Phase 039 guarantees HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING composition. Phase 034 generalized provider evidence and Phase 016 proved optional provider skipping. Canonical financial classification and provider-neutral symbols are stable.

## 4. Current codebase anchors

Re-trace the post-v10 implementation:
- market sync/application orchestration;
- benchmark history/mapping/master consumers;
- currency FX consumers;
- US market consumers;
- investment Quant/valuation;
- Gold benchmark/portfolio outputs;
- capability descriptors.

Classify every market input as core-accounting required, current-valuation required, benchmark enrichment, or foreign-asset-only.

## 5. Exact target state after this phase

Capability graph explicitly owns benchmark and foreign/FX enrichment.

Conceptually:
```text
BENCHMARK_ENRICHMENT
 -> requires INVESTMENT_ACCOUNTING
 -> benchmark mapping/master/history
 -> benchmark comparison outputs

FOREIGN_ASSET_ENRICHMENT
 -> requires INVESTMENT_ACCOUNTING
 -> required only for configured foreign instruments
 -> FX + foreign/US market evidence
 -> foreign valuation outputs
```

If domestic current valuation requires a separate market-price capability, encode that real dependency rather than misclassifying it.

ProviderDatasetPlans exist only for active requirements.

## 6. Detailed implementation sequence

### Step 1 - Freeze market dependency table
Map each provider dataset to consumer, financial necessity and capability owner.

### Step 2 - Update capability graph
Add/finalize benchmark and foreign/FX descriptors and exact dependencies.

### Step 3 - Make market sync plan-aware
Generate provider requests only for active capabilities and actual required instruments/date ranges.

### Step 4 - Domestic-only proof
Run household + domestic investments:
- no US transaction requirement;
- no US market request;
- no foreign FX request except any universally required base-currency evidence explicitly justified;
- accounting outputs valid.

### Step 5 - Benchmark-disabled proof
Core accounting remains valid; benchmark-specific outputs inactive and not required.

### Step 6 - Foreign-enabled proof
US/foreign fixture resolves FX/market requirements and matches full-plan valuation.

### Step 7 - Full Shan equivalence
Provider request ranges/counts, valuations, benchmark analytics and Gold outputs identical.

### Step 8 - Architecture guard
Provider requests derive from ExecutionPlan + canonical financial state, never legacy source categories.

## 7. Files and symbols in scope

Modify:
- capability descriptors/graph;
- market sync/source-plan resolution;
- Quant/valuation orchestration boundaries;
- active contract metadata;
- tests.

Do not compose Tax, wealth or FIRE yet.
Do not make analytical DDL partial yet.

## 8. Cross-cutting impacts

**Persistence:** inactive enrichment datasets/contracts not required; physical full DDL remains until Phase 043.

**Identity:** enrichment toggles must not alter PURCHASE/SALE/LOT/RECON identities.

**Observability:** provider events occur only for active requests and include capability context.

**Performance:** domestic-only/benchmark-disabled plans skip unnecessary network/cache work.

**Financial correctness:** accounting truth and analytical/valuation enrichments remain explicitly distinguished.

## 9. Tests and verification

Required:
- complete dependency classification table;
- domestic-only investment plan;
- zero inappropriate US/FX calls;
- benchmark-disabled accounting validity;
- foreign-enabled valuation equivalence;
- full Shan provider request/output equivalence;
- protected IDs identical across enrichment toggles;
- architecture guard.

## 10. Explicit non-goals

Do not:
- make Tax optional;
- make wealth/FIRE optional;
- change valuation methodology;
- change benchmark methodology;
- make Silver/Gold DDL partial.

## 11. Completion checklist

- [ ] Benchmark enrichment explicit.
- [ ] Foreign/FX enrichment explicit.
- [ ] Domestic-only investments supported.
- [ ] Provider calls match active requirements.
- [ ] Accounting identities unaffected.
- [ ] Full Shan outputs unchanged.

## 12. Commit boundary

```text
feat(pipeline): compose investment enrichments
```

## 13. Handoff to Phase 041

Phase 041 may assume household, investment accounting, benchmark and foreign/FX capabilities are independently resolved. The next batch composes Tax and wealth/FIRE, then makes the physical analytical warehouse match the active plan.

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
