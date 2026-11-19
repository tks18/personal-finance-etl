# Phase 040 - Benchmark and Foreign-Assets Capability Composition

**Target release:** v10.1.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 039  
**Next:** Phase 041  
**Risk:** High

## 1. Outcome

Separate benchmark enrichment and foreign-assets/FX/US-market enrichment from core investment accounting, making both explicit optional capabilities with correct source/provider requirements, active outputs, and **source-of-calculation column gating**.

At phase end PFETL supports household-only, domestic investment accounting without foreign-data requirements, optional benchmark analytics, foreign-asset valuation with FX/US-market evidence, and the unchanged full Shan plan.

Crucially, capability gating operates **at the source of calculation**: when a capability is disabled, the pipeline skips the expensive joins, FX conversions, benchmark returns, and matrix math entirely at the kernel level rather than computing them in Python/Polars and cosmetically pruning columns at the tail end.

## 2. Why this phase exists

Investment accounting and market enrichments have different correctness roles. A domestic-investment user should not need US market/FX evidence, and benchmark comparison should not be a hidden prerequisite for accounting truth.

Furthermore, analytical tables such as `silver.f_Investment_Analytics_Lot` (88 columns) and Gold marts like `gold.Investment_By_ISIN` (46 columns) are composite structures containing columns that belong strictly to benchmark comparison (`Active_Return`, `BM_XIRR`, `Lot_Alpha`) or foreign asset valuation (`Forex_PnL`, `Buy_Price_Local`, `Currency_Appreciation_Pct`, `XIRR_Local`). Computing these columns when their governing capabilities are inactive wastes compute, clutters outputs with dummy/null values, and creates fragile external data dependencies.

## 3. Inherited repository state

Phase 039 guarantees HOUSEHOLD_CORE and INVESTMENT_ACCOUNTING composition. Phase 034 generalized provider evidence and Phase 016 proved optional provider skipping. Canonical financial classification and provider-neutral symbols are stable.

## 4. Current codebase anchors

Re-trace the post-v10 implementation:
- market sync/application orchestration;
- benchmark history/mapping/master consumers;
- currency FX consumers;
- US market consumers;
- investment Quant/valuation (`src/personal_finance_etl/domain/investments/`);
- Gold benchmark/portfolio outputs;
- capability descriptors and `ExecutionPlan`;
- `SILVER_COLUMN_DISPOSITIONS` in `src/personal_finance_etl/contracts/semantic_inventory.py`.

Classify every market input and analytical column as core-accounting required, current-valuation required, benchmark enrichment, or foreign-asset-only.

## 5. Exact target state after this phase

### Capability Graph Architecture

```text
BENCHMARK_ENRICHMENT
 -> requires INVESTMENT_ACCOUNTING
 -> required inputs: benchmark mapping/master/history
 -> produced outputs: benchmark comparison marts and benchmark columns

FOREIGN_ASSET_ENRICHMENT
 -> requires INVESTMENT_ACCOUNTING
 -> required only for configured foreign instruments
 -> required inputs: FX rates + foreign/US market evidence
 -> produced outputs: foreign valuation marts and local currency/forex columns
```

If domestic current valuation requires a separate market-price capability, encode that real dependency rather than misclassifying it.

ProviderDatasetPlans exist only for active requirements.

### Permanent Invariant: Source-of-Calculation Gating (Zero-Waste Compute)

- **No Cosmetic Late Pruning:** Under no circumstances should the pipeline compute benchmark or FX columns inside domain transform loops and subsequently filter them out using `.select()` before DuckDB ingestion. This wastes user CPU, memory bandwidth, and execution time.
- **Kernel-Level Execution Gating:**
  - If `BENCHMARK_ENRICHMENT` is disabled, the benchmark join and comparison kernels are **completely skipped**. The resulting lot and portfolio DataFrames are emitted without benchmark metrics.
  - If `FOREIGN_ASSET_ENRICHMENT` is disabled, the currency FX conversion kernels and local currency valuation kernels are **completely skipped**.
- **Capability Column Attribution Matrix (Investments):**
  - **`BENCHMARK_ENRICHMENT` Columns:** `BENCHMARK_ID`, `BM_Buy_Price`, `BM_Market_Price`, `Lot_BM_Return`, `Lot_BM_CAGR`, `Lot_BM_CAGR_Status`, `Lot_BM_CAGR_Local`, `BM_CAGR`, `BM_CAGR_Status`, `BM_XIRR`, `BM_XIRR_Local`, `Active_Return`, `Active_Return_Local`, `Lot_Alpha`, `Is_Lagging_Benchmark`.
  - **`FOREIGN_ASSET_ENRICHMENT` Columns:** `CURRENCY_ID`, `Buy_Value_Local`, `Close_Value_Local`, `Blended_FX_Buy_Rate`, `Buy_Price_Local`, `Market_Price_Local`, `FX_Rate_Buy`, `FX_Rate_Snap`, `Currency_Appreciation_Pct`, `Absolute_Return_Local`, `Asset_PnL`, `Forex_PnL`, `Forex_Contribution_Pct`, `Asset_Return_Pct`, `Forex_Return_Pct`, `Lot_CAGR_Local`, `XIRR_Local`, `FX_XIRR_Impact`.

## 6. Detailed implementation sequence

### Step 1 - Freeze market dependency and column attribution table
Map each provider dataset and analytical column to consumer, financial necessity, and capability owner (`BENCHMARK_ENRICHMENT` vs `FOREIGN_ASSET_ENRICHMENT` vs `INVESTMENT_ACCOUNTING`).

### Step 2 - Update capability graph and ExecutionPlan
Add/finalize benchmark and foreign/FX descriptors, exact dependency edges, and active column resolution methods.

### Step 3 - Make market sync plan-aware
Generate provider requests only for active capabilities and actual required instruments/date ranges. Domestic-only plans issue zero Yahoo Finance / foreign provider requests.

### Step 4 - Implement source-of-calculation gating in domain kernels
Refactor lot analytics and realized gain/loss kernels:
- Decouple the monolithic lot transformation into composable calculation stages:
  1. Base Lot Accounting Kernel (always active with `INVESTMENT_ACCOUNTING`);
  2. Foreign Currency & FX Valuation Kernel (active only when `FOREIGN_ASSET_ENRICHMENT` is present);
  3. Benchmark Comparison Kernel (active only when `BENCHMARK_ENRICHMENT` is present).
- Ensure skipped kernels incur zero join and zero computation cost.

### Step 5 - Domestic-only proof
Run household + domestic investments:
- no US transaction requirement;
- no US market request;
- no foreign FX request except any universally required base-currency evidence explicitly justified;
- accounting outputs valid;
- lot analytics emit clean frames without foreign or benchmark metrics.

### Step 6 - Benchmark-disabled proof
Core accounting remains valid; benchmark-specific outputs and columns inactive and not computed.

### Step 7 - Foreign-enabled proof
US/foreign fixture resolves FX/market requirements and matches full-plan valuation.

### Step 8 - Full Shan equivalence
Provider request ranges/counts, valuations, benchmark analytics, and Gold outputs identical when all capabilities are enabled.

### Step 9 - Architecture guard
Provider requests and domain calculations derive from `ExecutionPlan` + canonical financial state, never legacy source categories or hardcoded table projections.

## 7. Files and symbols in scope

Modify:
- capability descriptors/graph (`contracts/capabilities.py`, `contracts/execution_plan.py`);
- capability column inventory (`contracts/semantic_inventory.py`);
- market sync/source-plan resolution (`application/pipeline/source_planner.py`, `application/market/`);
- domain investment calculation kernels (`domain/investments/lots/`, `domain/investments/performance/`);
- active contract metadata;
- tests.

Do not compose Tax, wealth or FIRE yet.
Physical analytical DDL remains full until Phase 043.

## 8. Cross-cutting impacts

**Persistence:** inactive enrichment datasets/contracts not required; physical full DDL remains until Phase 043.

**Identity:** enrichment toggles must not alter PURCHASE/SALE/LOT/RECON identities.

**Observability:** provider events occur only for active requests and include capability context.

**Performance:** domestic-only and benchmark-disabled plans skip unnecessary network/cache work and eliminate heavy window/join math in domain kernels.

**Financial correctness:** accounting truth and analytical/valuation enrichments remain explicitly distinguished.

## 9. Tests and verification

Required:
- complete dependency and column classification table;
- domestic-only investment plan with zero US/FX calls;
- benchmark-disabled plan with zero benchmark kernel executions;
- verification that disabled capability columns are not computed at the source;
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
- make Silver/Gold DDL partial (deferred to Phase 043).

## 11. Completion checklist

- [ ] Benchmark enrichment explicit.
- [ ] Foreign/FX enrichment explicit.
- [ ] Capability column inventory established for investment tables.
- [ ] Source-of-calculation gating implemented for benchmark and FX kernels (zero compute wasted).
- [ ] Domestic-only investments supported without foreign provider calls.
- [ ] Provider calls match active requirements.
- [ ] Accounting identities unaffected.
- [ ] Full Shan outputs unchanged.

## 12. Commit boundary

```text
feat(pipeline): compose investment enrichments with source calculation gating
```

## 13. Handoff to Phase 041

Phase 041 may assume household, investment accounting, benchmark, and foreign/FX capabilities are independently resolved at both table and column/calculation grains. Phase 041 will compose Tax using the same source-of-calculation principles.

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
