# Phase 041 - Tax Capability Composition

**Target release:** v10.1.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 040  
**Next:** Phase 042  
**Risk:** High

## 1. Outcome

Make Tax a fully plan-driven financial capability with explicit household/investment input requirements, active Silver/Gold ownership, **source-of-calculation column gating**, and preflight failure semantics. Tax must execute only when requested and satisfiable, while the full Shan plan remains byte-for-byte equivalent in Tax events, liabilities, and outputs.

Crucially, when the `TAX` capability is disabled, zero compute is expended on tax calculations: tax holding period classifications, slab lookups, unrealized tax estimations, and tax-loss harvesting priority algorithms are completely skipped at the calculation kernel level.

## 2. Why this phase exists

Phases 039-040 made household, investment accounting and market enrichments independently composable. Tax still historically assumes the full investment/household universe exists. External users need a capability model that states exactly which Tax evidence is mandatory rather than discovering missing frames deep inside the Tax engine.

Furthermore, investment lot kernels (`f_Investment_Analytics_Lot`) and realized event kernels currently embed extensive tax logic (holding periods, Section 112A grandfathering, unrealized capital gains tax if sold, and harvesting priority scoring). When a user does not require tax analytics, calculating these fields wastes significant CPU cycles and litters analytical tables with empty/zero tax metrics.

## 3. Inherited repository state

Phase 040 guarantees:
- HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING are independently resolved;
- benchmark and foreign/FX enrichments are optional with source-of-calculation column gating;
- ExecutionPlan owns active work and active column attribution;
- generalized ingestion is stable.

Tax methodology, `TAX` deterministic identity and current Tax Gold outputs remain unchanged.

## 4. Current codebase anchors

Re-trace the post-v10 Tax path:
- Tax service/application entry point;
- domain Tax event classification/hashing;
- realized investment event inputs;
- household income/expense inputs used by Tax;
- `f_Tax_Events` Silver contract;
- Tax Gold contracts (`Tax_Year_Summary`, `Tax_Income_Breakdown`, `Tax_Reconciliation`);
- Tax columns embedded in `f_Investment_Analytics_Lot` and `f_Investment_Realized_Events`;
- Tax-related FinancialRules;
- `PipelineExecutor` engine ordering;
- capability graph.

Build an exact input table before coding: DatasetId, required/optional, reason, producer capability, Tax consumer.

## 5. Exact target state after this phase

### Capability Specification

```text
TAX
  required capabilities: exact graph-derived set (e.g. HOUSEHOLD_CORE or INVESTMENT_ACCOUNTING)
  required inputs: exact canonical household/investment datasets
  optional inputs: only where methodology genuinely permits absence
  produced Silver: Tax event state (f_Tax_Events)
  produced Gold: Tax analytical contracts (Tax_Year_Summary, Tax_Income_Breakdown, Tax_Reconciliation)
```

### Permanent Invariant: Source-of-Calculation Gating (Zero-Waste Compute)

- **No Cosmetic Late Pruning:** Tax columns must never be calculated inside investment or household kernels only to be dropped via `.select()` later.
- **Kernel-Level Execution Gating:**
  - If `TAX` is disabled:
    - In lot analytics (`f_Investment_Analytics_Lot`): completely skip tax slab evaluations, holding duration tax flags, unrealized tax liabilities if sold, and harvesting recommendation loops (`TAX_TYPE`, `TAX_SUBTYPE`, `Tax_Rate`, `LTCG_Threshold_Days`, `Days_To_LTCG`, `Unrealized_LTCG`, `Unrealized_STCG`, `Unrealized_Gain`, `Unrealized_LTCL`, `Unrealized_STCL`, `Unrealized_Loss`, `LTCG_Tax_If_Sold`, `STCG_Tax_If_Sold`, `After_Tax_PL`, `After_Tax_Close_Value`, `After_Tax_XIRR`, `FY_Realized_LTCG`, `FY_Realized_STCG`, `FY_Realized_Gain`, `FY_Realized_LTCL`, `FY_Realized_STCL`, `FY_Realized_Loss`, `FY_Realized_Net_PnL`, `Equity_LTCG_Exemption`, `Stepup_Eligible`, `Can_Harvest_Loss`, `Harvest_Recommendation`).
    - In realized events (`f_Investment_Realized_Events`): completely skip `Applied_Rate` and `Estimated_Tax`.
    - In portfolio marts (`gold.Investment_Portfolio_Summary`): completely skip `ISIN_Harvestable_Loss` and `Tax_Harvesting_Priority_Score`.
    - Pipeline skips the entire `TaxService` / `TaxEngine` execution and emits a `SKIP` event.

## 6. Detailed implementation sequence

### Step 1 - Freeze Tax dependency and column attribution table
Trace every dataframe and column read or written by Tax. Distinguish accounting evidence from tax estimations.

### Step 2 - Update capability descriptor
Encode exact required/optional dependencies, produced contracts, and active tax column definitions.

### Step 3 - Add planner/preflight satisfiability
Requested Tax with missing mandatory input fails with actionable DatasetId/capability remediation before engine execution.

### Step 4 - Make Tax orchestration and domain calculation conditional
Pipeline calls Tax service only when `TAX` active. Decouple tax calculation routines from base investment lots; base lots emit strictly accounting columns when `TAX` is inactive.

### Step 5 - Align completeness/publication
Tax Silver/Gold contracts active only when Tax requested. Inactive tax columns are not emitted by domain kernels. Physical DDL remains full until Phase 043.

### Step 6 - Tax-disabled proof
Run household/investment plan without Tax. Assert zero Tax service calls/events/outputs, zero tax computation in lots, and unrelated outputs identical.

### Step 7 - Household-only Tax decision
Based on actual methodology, either support household-only Tax with explicitly reduced inputs or reject it as an invalid capability combination. Do not invent support by zero-filling missing investment evidence.

### Step 8 - Full Shan Tax regression
Compare Tax event count, classifications, taxable amounts, sub-heads, Gold outputs, and `TAX` IDs byte-for-byte.

## 7. Files and symbols in scope

Modify:
- Tax capability descriptor (`contracts/capabilities.py`, `contracts/execution_plan.py`);
- planner/preflight (`application/pipeline/planner.py`, `application/pipeline/source_planner.py`);
- pipeline Tax orchestration (`application/pipeline/execution.py`);
- domain investment lot analytics kernels (`domain/investments/lots/`);
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

**Performance:** Tax-disabled plan skips Tax computation and eliminates tax slab lookup and harvesting scoring overhead in investment lots.

**Financial correctness:** missing mandatory evidence fails; never silently zero-fill or exception-default.

## 9. Tests and verification

Required:
- exact Tax dependency and column attribution table;
- requested+satisfiable Tax runs;
- requested+missing mandatory input fails pre-engine;
- Tax-disabled service call count zero;
- verification that lot analytics emit clean frames without tax metrics when Tax is inactive;
- inactive Tax outputs absent from produced set;
- full Shan Tax events/amounts/IDs identical;
- unrelated outputs identical when Tax disabled;
- architecture guard against direct Tax feature flags;
- deterministic financial test cases using `tests/fixtures/evidence/` for capital gains tax calculations (LTCG / STCG, grandfathering rules, tax slabs, dividend withholding) against predictable real-world trades;
- **Exhaustive Deep Domain Tax Assertions (Silver & Gold):**
  - Meticulously test and assert Silver tax events (`f_Tax_Events`), validating deterministic `TAX` identity stability, event classification (LTCG, STCG, dividend, interest), Section 112A grandfathering fair market value (FMV) price lookups as of 31-Jan-2018, indexation calculations, and withholding tax amounts;
  - Meticulously test and assert Gold tax summary marts (`Tax_Year_Summary`), validating annual aggregate taxable income, statutory exemptions (e.g. Section 112A ₹1L exemption), applicable slab brackets, cess percentages, and gross vs net tax liabilities;
  - Meticulously test and assert Gold income breakdown marts (`Tax_Income_Breakdown`), verifying exact head-wise attribution across salary, capital gains, dividend income, and other sources;
  - Meticulously test and assert Gold tax reconciliation marts (`Tax_Reconciliation`), asserting exact balance reconciliation between commercial book profit and statutory tax profit.

## 10. Explicit non-goals

Do not:
- change Tax methodology;
- change Tax rules/sub-heads;
- make missing investment evidence zero;
- make DDL partial (deferred to Phase 043);
- compose wealth/FIRE in this phase.

## 11. Completion checklist

- [ ] Tax dependencies explicit.
- [ ] Tax column attribution established across lots, realized events, and marts.
- [ ] Source-of-calculation gating implemented (zero tax compute when Tax disabled).
- [ ] Planner validates Tax satisfiability.
- [ ] Tax execution is plan-driven.
- [ ] Disabled Tax performs zero work.
- [ ] Missing mandatory evidence fails early.
- [ ] Tax values and IDs unchanged under full plan.

## 12. Commit boundary

```text
feat(pipeline): compose tax capability with source calculation gating
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
