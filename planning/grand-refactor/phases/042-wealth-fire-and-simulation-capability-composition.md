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

### Capability Specification & Gold Mart Ownership

```text
HOUSEHOLD_CORE
  produces Silver: 10 household ledger tables + d_Calendar + d_Currency
  produces Gold (Household Budget & Cashflow Decision Marts):
    - gold.Cashflow_Expense_Breakdown
    - gold.Cashflow_Income_Breakdown
    - gold.Forecast_Budget_Variance
    - gold.Cashflow_Efficiency_Analytics
    - gold.Cashflow_Activity_Summary
    - base monthly cashflow/savings in gold.Core_Monthly_Fact

WEALTH
  requires HOUSEHOLD_CORE
  optional investment contribution (PORTFOLIO_VALUATION)
  produces Gold (Wealth & Balance Sheet Marts):
    - gold.Wealth_Asset_Breakdown
    - gold.Wealth_FIRE_Analytics (deterministic milestones, SWR, linear runway, expense coverage)
    - enriches gold.Core_Monthly_Fact with Net Worth, asset allocation, and liquid vs illiquid breakdown

FIRE (Enrichment Capability)
  requires HOUSEHOLD_CORE, WEALTH
  optional investment portfolio contribution explicit
  enriches Gold at Column Level (CAPABILITY_COLUMN_INVENTORY):
    - enriches gold.Wealth_FIRE_Analytics with Monte Carlo stochastic simulation columns (P10, P50, P90 percentile paths, probability of success, stressed runway, terminal wealth)
  when inactive: Monte Carlo simulation loop (1,000+ stochastic iterations) is completely uninvoked at source, and simulation columns are emitted as null.
```

> [!NOTE]
> **Column Master Retirement Clarification:**  
> `Column_Master.csv` is completely retired from runtime mapping (all column mappings are owned 100% by `sources.toml`). `DatasetId.COMMON_COLUMN_MASTER` remains purely as an inert transitional enum placeholder, which will be completely demolished in Phase 049 (Step 7b). Users do not need or configure `Column_Master.csv`.

If simulation is inseparable from FIRE in current methodology, do not manufacture a capability merely for symmetry. Record it as an internal FIRE stage.

### Permanent Invariant: Source-of-Calculation Gating (Zero-Waste Compute)

- **No Cosmetic Late Pruning:** Do not calculate investment deltas or simulation trajectories only to drop them via `.select()` prior to publication.
- **Confluence Mart Gating (`gold.Core_Monthly_Fact`):**
  - **Household-Only Run (`HOUSEHOLD_CORE`):** The monthly aggregation kernel computes solely income, expense, cashflow, and liquid balance metrics (`Total_Income`, `Total_Cash_Income`, `Total_Expense`, `Net_Cashflow_Month`, `Opening_Balance_Asset`, `Liquid_Assets`, `Total_Liabilities`, `Total_Net_Worth`).
    - The 5 household cashflow & budget marts (`Cashflow_Expense_Breakdown`, `Cashflow_Income_Breakdown`, `Forecast_Budget_Variance`, `Cashflow_Efficiency_Analytics`, `Cashflow_Activity_Summary`) are fully populated.
    - Investment-dependent calculations (`Opening_Investment_Book_Value`, `Closing_Investment_Market_Value`, `Investment_Market_Value_Delta`, `Total_Assets_Market`, `Opening_Unrealized_PL`, `Closing_Unrealized_PL`, `Opening_Investment_XIRR`, `Closing_Investment_XIRR`) are completely skipped at the aggregation kernel level.
    - Foreign exposure calculations (`Total_Foreign_Currency_Exposure`, `Foreign_Exposure_Pct`, `Closing_Forex_PnL`) are skipped when foreign asset enrichment is inactive.
    - Macro parameters (`CPI_INDEX`, `INFLATION_YOY_PCT`) are skipped when macro enrichment is inactive.
  - **Wealth Active Run (`WEALTH`):** Net worth evolution, balance sheet growth, and asset class allocation are calculated and injected into `Core_Monthly_Fact` and `Wealth_Asset_Breakdown`.
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

### Step 7 - Disabled-path proofs & Declarative Configuration Fixtures

Author declarative `sources.toml` test fixtures under `tests/fixtures/config/` modeling isolated household and wealth archetypes:

1. `sources_household_only.toml`: configures purely household evidence (opening balances, bank accounts, expenses, income) with zero investment, brokerage, or market data sources.
2. `sources_household_wealth.toml`: configures household evidence plus physical assets and cash balance sheet tracking (`HOUSEHOLD_CORE` + `WEALTH`), with zero equity brokerages.
3. `sources_household_wealth_fire.toml`: configures household evidence, wealth tracking, and FIRE target parameters (`HOUSEHOLD_CORE` + `WEALTH` + `FIRE`) without equity investments.

Execute headless pipeline runs against each fixture and assert:

- Wealth/FIRE disabled => zero service calls, zero produced wealth/FIRE contracts, and zero simulation matrix generation.
- Confluence mart `gold.Core_Monthly_Fact` skips investment market values, unrealized P&L, XIRR calculations, and foreign currency exposure joins directly at the aggregation kernel level.

### Step 8 - Full Shan regression & End-to-End Analytical Assertions

Execute full headless pipeline run under the comprehensive plan. Assert:

- Net worth, wealth, FIRE, simulation outputs, and all upstream financial IDs unchanged under the full plan down to the penny.
- Assertive analytical outputs for each capability fixture:
  - In `sources_household_only.toml`: the 5 Gold household decision marts (`Cashflow_Expense_Breakdown`, `Cashflow_Income_Breakdown`, `Forecast_Budget_Variance`, `Cashflow_Efficiency_Analytics`, `Cashflow_Activity_Summary`) and the monthly savings/cashflow metrics in `gold.Core_Monthly_Fact` are populated accurately, while all investment/tax columns are strictly null.
  - In `sources_household_wealth.toml`: `gold.Wealth_Asset_Breakdown` and `gold.Wealth_FIRE_Analytics` (with deterministic milestones, SWR, linear runway) are populated using solely household accounts, while all Monte Carlo simulation columns are strictly null.
  - In `sources_household_wealth_fire.toml`: `gold.Wealth_FIRE_Analytics` executes the Monte Carlo simulation engine and populates all 10 stochastic percentile columns (P10, P50, P90, probability of success).

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
  - Meticulously test and assert Monte Carlo simulation engines across 1,000+ stochastic runs, verifying percentile trajectory convergence (p10, p25, median p50, p75, p90 portfolio survival paths), sequence-of-returns risk modeling, seed reproducibility for identical runs, distribution parameter logging, and simulation run provenance recording;
- **Declarative `sources.toml` Configuration Fixture Tests:**
  - Execute headless pipeline runs against `sources_household_only.toml`, `sources_household_wealth.toml`, and `sources_household_wealth_fire.toml`;
  - Assert that in `sources_household_only.toml`:
    - All 5 Gold cashflow/budget marts (`Cashflow_Expense_Breakdown`, `Cashflow_Income_Breakdown`, `Forecast_Budget_Variance`, `Cashflow_Efficiency_Analytics`, `Cashflow_Activity_Summary`) and baseline cashflow in `Core_Monthly_Fact` are populated accurately.
    - All investment, tax, and foreign currency columns in `Core_Monthly_Fact` are strictly null/uncalculated.
  - Assert that in `sources_household_wealth.toml`, net worth and asset class allocations are calculated purely from household banking/property assets with zero equity broker dependencies.
  - Assert that in `sources_household_wealth_fire.toml`, FIRE targets and SWR calculations are produced strictly from cashflow and household wealth.

## 10. Explicit non-goals

Do not:

- alter FIRE assumptions;
- alter net-worth methodology;
- add new simulation algorithms;
- make DDL partial yet (deferred to Phase 043);
- change ingestion.

## 11. Completion checklist

- [x] Wealth capability explicit.
- [x] FIRE capability explicit.
- [x] Simulation boundary justified.
- [x] Confluence mart column attribution established.
- [x] Source-of-calculation gating implemented for confluence aggregations.
- [x] Declarative `sources.toml` fixtures authored (`sources_household_only.toml`, `sources_household_wealth.toml`, `sources_household_wealth_fire.toml`).
- [x] End-to-end analytical output assertions verified across all three fixtures.
- [x] Optional investment contributions correct.
- [x] Disabled engines perform zero work.
- [x] Full Shan outputs unchanged.
- [x] All major financial engines now plan-driven.

## 12. Commit boundary

```text
feat(pipeline): compose wealth and fire capabilities with source calculation gating
```

## 13. Handoff to Phase 043

Phase 043 may assume the logical active Silver/Gold contract set and column attribution are correct for every supported capability combination. It will make the physical analytical warehouse DDL and Meta/catalog reflect that active set dynamically rather than always creating the full universe.

## Phase completion record

```text
Phase: 042
Target release: v10.1.3
Files changed: src/personal_finance_etl/contracts/capabilities.py, src/personal_finance_etl/domain/fire/inflation.py, src/personal_finance_etl/domain/wealth/market_valuation.py, src/personal_finance_etl/domain/wealth/net_worth.py, src/personal_finance_etl/domain/fire/deterministic.py, src/personal_finance_etl/application/wealth/wealth_service.py, src/personal_finance_etl/application/pipeline/execution.py, tests/fixtures/sources_household_wealth.toml, tests/fixtures/sources_household_wealth_fire.toml, tests/domain/test_wealth_fire_source_gating.py, tests/application/test_wealth_fire_composition.py
Schema changed: NO (Column inventory & gating aligned with existing 22 Gold contracts)
Runtime behavior changed: YES (Source calculation gating for Wealth and FIRE simulation skips Monte Carlo and uncalculated columns)
Financial formulas changed: NO
Focused tests: tests/domain/test_wealth_fire_source_gating.py, tests/application/test_wealth_fire_composition.py, tests/contracts/test_capabilities.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: tests/application/test_capability_composition.py
Performance check: Full Quality Gate <200s, Fast Quality Gate <1s
Compatibility path still present: YES
Old path deleted: NO
Exit assertions green: YES
Commit: Pending user approval
```

A phase is incomplete if any required exit assertion is false.
