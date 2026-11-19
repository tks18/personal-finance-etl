# Phase 042 - Wealth, FIRE and Simulation Capability Composition

**Target release:** v10.1.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 041  
**Next:** Phase 043  
**Risk:** High

## 1. Outcome

Make Wealth and FIRE plan-driven capabilities with explicit required and optional investment contributions, **source-of-calculation column gating across confluence marts**, and isolate simulation as a distinct capability if the current implementation supports meaningful independent execution.

At phase end every major PFETL financial engine is governed by `ExecutionPlan`; no engine is implicitly mandatory merely because the old pipeline always ran it. Furthermore, composite confluence marts such as `gold.Core_Monthly_Fact` and `gold.Wealth_FIRE_Analytics` calculate and populate only the columns belonging to active capabilities, saving significant compute.

## 2. Why this phase exists

Wealth and FIRE are downstream aggregations with cross-domain inputs. Their optionality cannot be modeled by simply skipping a function: the planner must know which household state is required, when investments contribute, and whether simulation is a separate computational responsibility.

Additionally, central confluence tables like `gold.Core_Monthly_Fact` (39 columns) combine household cashflow, investment book/market values, foreign currency exposures (`Total_Foreign_Currency_Exposure`, `Foreign_Exposure_Pct`), and macro inflation indices (`CPI_INDEX`, `INFLATION_YOY_PCT`). In a household-only run, running joins or calculations for investment market values, XIRRs, and foreign exposures is a complete waste of CPU and memory.

## 3. Inherited repository state

Phase 041 guarantees Tax composition with source-of-calculation column gating. Household/investment/enrichment composition is already operational. Gold contracts remain full-DDL physically but active-set metadata and active column inventories are accurate.

## 4. Current codebase anchors

Re-trace post-v10:
- wealth service/presentation engine;
- net-worth producers;
- FIRE producers;
- simulation engine/provenance;
- household balance/cashflow inputs;
- investment portfolio analytics inputs;
- composite confluence marts (`gold.Core_Monthly_Fact`, `gold.Wealth_FIRE_Analytics`, `gold.Wealth_Asset_Breakdown`);
- capability graph.

Create exact contract, input, and column attribution table before edits.

## 5. Exact target state after this phase

### Capability Specification

```text
WEALTH
  requires HOUSEHOLD_CORE
  optional investment contribution according to current methodology
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

### Permanent Invariant: Source-of-Calculation Gating (Zero-Waste Compute)

- **No Cosmetic Late Pruning:** Do not calculate investment deltas or simulation trajectories only to drop them via `.select()` prior to publication.
- **Confluence Mart Gating (`gold.Core_Monthly_Fact`):**
  - **Household-Only Run:** The monthly aggregation kernel computes solely income, expense, cashflow, and liquid balance metrics (`Total_Income`, `Total_Cash_Income`, `Total_Expense`, `Net_Cashflow_Month`, `Opening_Balance_Asset`, `Liquid_Assets`, `Total_Liabilities`, `Total_Net_Worth`).
  - Investment-dependent calculations (`Opening_Investment_Book_Value`, `Closing_Investment_Market_Value`, `Investment_Market_Value_Delta`, `Total_Assets_Market`, `Opening_Unrealized_PL`, `Closing_Unrealized_PL`, `Opening_Investment_XIRR`, `Closing_Investment_XIRR`) are completely skipped at the aggregation kernel level.
  - Foreign exposure calculations (`Total_Foreign_Currency_Exposure`, `Foreign_Exposure_Pct`, `Closing_Forex_PnL`) are skipped when foreign asset enrichment is inactive.
  - Macro parameters (`CPI_INDEX`, `INFLATION_YOY_PCT`) are skipped when macro enrichment is inactive.
- **Simulation Gating:**
  - When simulation is disabled, the Monte Carlo loop (1,000+ stochastic iterations, percentile path calculations, and seed tracking) is **completely uninvoked**.

## 6. Detailed implementation sequence

### Step 1 - Freeze Wealth/FIRE dependency and confluence column table
Map every input DatasetId, produced Gold contract, and column attribution in composite marts.

### Step 2 - Decide simulation boundary from code
Document whether simulation earns its own capability. Decision must follow current ownership and output semantics.

### Step 3 - Update capability graph
Encode required/optional edges, active outputs, and column attribution rules.

### Step 4 - Make Wealth orchestration and confluence aggregation plan-driven
Household-only wealth path must be valid if methodology supports it; investment contribution is absent and uncalculated, not fabricated with zeros.

### Step 5 - Make FIRE orchestration plan-driven
Missing mandatory FIRE evidence fails at planner/preflight. Optional investment contribution handled explicitly at the calculation kernel.

### Step 6 - Simulation orchestration
Conditional only if capability is separately modeled; otherwise remains an internal FIRE stage with plan-aware FIRE execution skipping Monte Carlo loops when disabled.

### Step 7 - Disabled-path proofs
Wealth/FIRE disabled => zero service calls, no produced contracts, and zero simulation matrix generation.

### Step 8 - Full Shan regression
Net worth, wealth, FIRE, simulation outputs, and all upstream financial IDs unchanged under the full plan.

## 7. Files and symbols in scope

Modify:
- wealth/FIRE/simulation capability descriptors;
- planner;
- orchestration;
- confluence mart aggregation kernels (`application/wealth/`, `domain/wealth/`);
- active Gold contract metadata;
- tests.

Do not change formulas/assumptions in FinancialRules or domain engines.

## 8. Cross-cutting impacts

**Persistence:** active Gold set changes logically; physical DDL waits Phase 043.

**Identity:** no upstream identity change.

**Observability:** stages/events reflect only executed capabilities; simulation provenance retained when active.

**Performance:** disabled downstream capabilities skip their computations; composite marts avoid heavy joins and XIRR iterations.

**Financial correctness:** optional contributions modeled explicitly; no zero-fill hacks.

## 9. Tests and verification

Required:
- exact dependency/output table and confluence column matrix;
- household-only wealth case according to methodology;
- verification that household-only monthly facts skip investment/forex calculations at source;
- investment contribution enabled/disabled tests;
- FIRE missing-mandatory-input failure;
- disabled service call counts zero;
- simulation boundary test/documented decision;
- full Shan wealth/FIRE/simulation equivalence;
- end-to-end headless wealth and FIRE Monte Carlo simulation tests driven by static sample fixtures from `tests/fixtures/evidence/`;
- **Exhaustive Deep Domain Wealth, FIRE & Monte Carlo Assertions (Gold):**
  - Meticulously test and assert Gold Wealth & FIRE analytics marts (`Wealth_FIRE_Analytics`), verifying point-in-time and historical net worth curves, asset class breakdowns (equity, debt, cash, physical assets), liquid vs illiquid asset separation, savings rates, and expense coverage ratios;
  - Meticulously test and assert FIRE projection engines, verifying Safe Withdrawal Rate (SWR) mechanics, inflation-adjusted annual spending targets, LeanFIRE, FatFIRE, and CoastFIRE target milestones, and projected year of financial independence;
  - Meticulously test and assert Monte Carlo simulation engines across 1,000+ stochastic runs, verifying percentile trajectory convergence (p10, p25, median p50, p75, p90 portfolio survival paths), sequence-of-returns risk modeling, seed reproducibility for identical runs, distribution parameter logging, and simulation run provenance recording.

## 10. Explicit non-goals

Do not:
- alter FIRE assumptions;
- alter net-worth methodology;
- add new simulation algorithms;
- make DDL partial yet (deferred to Phase 043);
- change ingestion.

## 11. Completion checklist

- [ ] Wealth capability explicit.
- [ ] FIRE capability explicit.
- [ ] Simulation boundary justified.
- [ ] Confluence mart column attribution established.
- [ ] Source-of-calculation gating implemented for confluence aggregations.
- [ ] Optional investment contributions correct.
- [ ] Disabled engines perform zero work.
- [ ] Full Shan outputs unchanged.
- [ ] All major financial engines now plan-driven.

## 12. Commit boundary

```text
feat(pipeline): compose wealth and fire capabilities with source calculation gating
```

## 13. Handoff to Phase 043

Phase 043 may assume the logical active Silver/Gold contract set and column attribution are correct for every supported capability combination. It will make the physical analytical warehouse DDL and Meta/catalog reflect that active set dynamically rather than always creating the full universe.

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
