# Phase 047 - External Investment Topology Certification

**Target release:** v10.3.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 046  
**Next:** Phase 048  
**Risk:** High

## 1. Outcome

Certify external investment use cases with at least:
1. household + domestic investments with no foreign/FX requirement;
2. household + foreign investments requiring FX/foreign-market evidence.

Slim down and prune canonical Bronze and Silver investment schemas:
- Prune vendor-specific columns from stock trades, mutual fund orders, and US equity transactions down to the essential financial attributes needed for FIFO lots, realized gains, and portfolio valuation (`ISIN`/`Instrument_Name`, `Date`, `Transaction_Type`, `Quantity`, `Price`, `Amount`, `Fees`/`Brokerage`, `Currency_ID`, `artifact_id`).
- Pre-Bronze preserves full source-shaped brokerage exports, while Bronze and Silver expose clean, minimal investment contracts that any brokerage format can satisfy without carrying legacy vendor columns.
- Permanently demolish `__file_category__`: completely excise the legacy `__file_category__` column from Bronze table DDL, Pandera schemas (`CANONICAL_BRONZE_INVESTMENT_*_SCHEMA`), `CANONICAL_BRONZE_FIELDS`, Excel file readers, and source configurations. Authoritative row provenance is strictly owned by `artifact_id` and the 1-to-1 dataset binding, eliminating legacy folder-derived tags from financial lakehouse contracts.

Both configurations must use source shapes/topologies different from Shan's current vendors and require no source-code changes. Capability dependency failures must be diagnosed before financial execution.

## 2. Why this phase exists

Investment generalization is more demanding than household onboarding because source evidence feeds financial reconstruction, provider enrichments, FIFO/reconciliation, Tax and wealth. The final product claim is not credible until alternate investment sources reach those same canonical engines safely.

## 3. Inherited repository state

Phase 046 proves external household topologies. Phases 039-042 provide capability composition. Provider-generated evidence is generalized. Protected financial identities remain canonical.

## 4. Current codebase anchors

Build fixtures from current canonical investment Bronze contracts, not Shan vendor formats.

Domestic fixture should include enough evidence to exercise:
- investment master/reference resolution;
- purchases and sales;
- FIFO lot/realized reconstruction;
- reconciliation if applicable;
- current valuation if domestic market evidence is required;
- optional Tax/wealth according to selected plan.

Foreign fixture should exercise:
- canonical foreign classification;
- FX requirement;
- foreign/US market provider dataset plan using deterministic test provider/cache fixtures;
- purchase/sale and valuation.

Use Phase-045 diagnostics before full runs.

## 5. Exact target state after this phase

External investment configurations map arbitrary supported source shapes into the same canonical investment evidence.

Domestic-only plan performs zero unnecessary foreign/US provider work.

Foreign plan requests exactly required FX/market evidence.

Financial identities are derived from canonical financial state after Bronze, not vendor/source identity.

Invalid capability combinations fail at planner/preflight with remediation.

## 6. Detailed implementation sequence

### Step 1 - Freeze domestic scenario and Generic External Investment Fixtures
Establish a permanent Generic External Investment Fixture repository at `tests/fixtures/external/investments/`:
- `generic_domestic_trades.csv`: generic brokerage tradebook with column headers `Order_Date`, `Symbol`, `Order_Type`, `Exec_Shares`, `Price_Per_Share`, `Stamp_Duty`, `Brokerage`;
- `generic_mf_transactions.xlsx`: mutual fund statement workbook with columns `Folio`, `Fund_Name`, `ISIN_Code`, `Date_Of_Txn`, `Type`, `Units_Count`, `Purchase_NAV`, `Net_Amount`;
- `generic_us_trades.csv`: foreign equity trade export with columns `Ticker_Symbol`, `Txn_Timestamp`, `Side`, `Unit_Quantity`, `Share_Price`, `Gross_Value`;
- Capability-specific typed source configurations:
  - `sources_external_investments_domestic_only.toml`: domestic stocks + mutual funds without benchmark, foreign FX, or tax (`HOUSEHOLD_CORE` + `INVESTMENT_ACCOUNTING`).
  - `sources_external_investments_benchmark.toml`: domestic trades enriched with benchmark index closing prices (`+ BENCHMARK_ENRICHMENT`).
  - `sources_external_investments_foreign.toml`: domestic + US equities with USD/INR currency exchange rates (`+ FOREIGN_ASSET_ENRICHMENT`).
  - `sources_external_investments_tax.toml`: domestic trades enriched with statutory capital gains tax calculations (`+ TAX`).
- Capability-specific financial rules fixtures:
  - `rules_investments_domestic_only.toml`: rules declaring instrument categories, base currency, and scheme mappings without tax schedules or FIRE parameters.
  - `rules_investments_tax.toml`: pairs accounting rules with statutory capital gains schedules (`[assumptions.tax]`).
- Dedicated runtime execution profiles:
  - `settings_external_investments_domestic_only.toml`: defines `[capabilities] enabled = ["household_core", "investment_accounting"]`.
  - `settings_external_investments_tax.toml`: defines `[capabilities] enabled = ["household_core", "investment_accounting", "tax"]`.

### Step 2 - Configure domestic source
Configure domestic-only pipeline using `sources_external_investments_domestic_only.toml`. Run diagnostics (`validate-config`, `check-sources`, `dry-run-admission`). Assert no hardcoded vendor assumptions.

### Step 3 - Full domestic run & Analytical Output Assertions
Execute pipeline under domestic-only configuration. Assert:
- Zero foreign provider calls; zero benchmark downloads.
- Assertive analytical outputs:
  - FIFO lot depletion, remaining cost basis, realized gains, and portfolio XIRR match expected ground-truth scenario down to the cent.
  - Tax rates, thresholds, and liabilities are strictly null in `silver.investments_lots` and `silver.investments_realized`.
  - Benchmark alpha/beta columns are strictly null in `gold.investments_by_isin`.
  - Foreign currency exposure in `gold.core_monthly_fact` is strictly null/zero.

### Step 4 - Freeze foreign scenario
Include foreign equity fixture `generic_us_trades.csv` and deterministic test provider fixtures for FX and US equity prices using `sources_external_investments_foreign.toml`.

### Step 5 - Full foreign run & Multi-Currency Assertions
Execute combined foreign run. Assert:
- Exact provider requirements and date ranges fetched for USD/INR exchange rates and US prices.
- Multi-currency valuation mart (`gold.investments_by_currency`) accurately computes INR and USD asset splits.
- `gold.core_monthly_fact` correctly reflects `Total_Foreign_Currency_Exposure` and `Foreign_Exposure_Pct` matching transaction-date exchange rates.

### Step 5b - Benchmark & Tax Capability Fixture Runs
Execute runs using `sources_external_investments_benchmark.toml` and `sources_external_investments_tax.toml`:
- Benchmark run asserts Alpha/Beta and shadow market returns populate accurately.
- Tax run asserts realized transactions reflect statutory STCG/LTCG holding period classification and rate calculations.

### Step 6 - Identity stability
Reorder source rows/files and rerun. PURCHASE/SALE/LOT/REALIZED/RECON IDs remain stable for unchanged canonical scenario.

### Step 7 - Capability failure matrix
Examples:
- request foreign valuation with required FX/provider capability disabled;
- request Tax without mandatory accounting evidence;
- request FIRE/wealth with missing required household state.
Failures occur before engine execution and identify missing capability/DatasetId.

### Step 8 - Source failure matrix
Bad transaction type/date/amount/schema, missing instrument mapping, duplicate canonical grain where prohibited.

### Step 9 - Recovery/incremental
Change one transaction; verify affected canonical/financial state and replay behavior.

### Step 10 - Full Shan regression
External fixtures must not introduce special-case code that changes Shan outputs.

### Step 11 - Desktop GUI Tri-Configuration & Diagnostic Actions Integration
Modernize `src/personal_finance_etl/presentation/desktop/app.py` (`UnifiedETLTab`):
- Add file picker inputs and recent history management for `sources.toml` alongside `config.toml` and `rules.toml`.
- Add interactive diagnostic buttons to the control header:
  - `Validate Config` (calls `PersonalFinanceEngine.validate_all_configs` and renders the issue table directly in the GUI log panel).
  - `Check Sources` (calls `PersonalFinanceEngine.check_sources` and renders source reachability status in the GUI log panel).
  - `Dry Run Admission` (runs non-mutating pre-bronze admission test).
- Ensure desktop users can select custom investment topologies and run diagnostics before triggering pipeline execution.

## 7. Files and symbols in scope

Create external investment fixtures/configs/provider test responses and certification tests.

Production changes only for genuine generalized-contract defects; no vendor-specific branches.

## 8. Cross-cutting impacts

**Persistence:** isolated fixture warehouses.

**Identity:** PURCHASE/SALE/LOT/REALIZED/RECON/TAX stability is central.

**Provider provenance:** deterministic test provider/cache responses use same provider-plan contracts.

**Observability:** foreign provider request and financial lineage traceable.

**Performance:** correctness fixtures; Phase 048 handles scale.

## 9. Tests and verification

Mandatory:
- domestic external topology via `sources_external_investments_domestic_only.toml`;
- zero inappropriate foreign provider calls or benchmark downloads;
- foreign external topology via `sources_external_investments_foreign.toml`;
- exact FX/market request requirements;
- benchmark enrichment topology via `sources_external_investments_benchmark.toml`;
- tax enrichment topology via `sources_external_investments_tax.toml`;
- assertive verification of analytical outputs:
  - domestic run asserts FIFO lots, realized gains, remaining cost basis, and portfolio XIRR equal expected ground-truth values down to the cent;
  - domestic run asserts tax liabilities, benchmark shadow prices, and foreign exposures are null;
  - foreign run asserts multi-currency valuation (`gold.investments_by_currency`) and forex P&L match transaction-date FX rates;
- protected IDs stable across reorder/rerun;
- capability failure matrix;
- malformed source/mapping failures;
- incremental change/replay;
- comprehensive FIFO lot matching tests (exhaustive consumption, partial lot depletion, remaining cost basis) using static evidence fixtures;
- full Shan regression.

## 10. Explicit non-goals

Do not:
- add vendor-specific adapters beyond generic supported providers;
- change FIFO/reconciliation/Tax methodology;
- add new market providers;
- weaken capability dependencies.

## 11. Completion checklist

- [ ] Canonical Bronze investment schemas slimmed down to essential financial columns.
- [ ] Declarative investment capability fixtures authored (`sources_external_investments_*.toml`).
- [ ] Domestic external investment topology passes.
- [ ] Foreign external topology passes.
- [ ] Benchmark and Tax enrichment runs pass.
- [ ] End-to-end analytical outputs asserted against expected ground-truth arithmetic.
- [ ] Provider requirements correct.
- [ ] Financial identities stable.
- [ ] Capability failures are early/actionable.
- [ ] No vendor-specific production branch added.
- [ ] Shan regression green.
- [ ] Desktop GUI supports tri-configuration (config.toml, sources.toml, rules.toml) and interactive diagnostic buttons.

## 12. Commit boundary

```text
test(certification): add external investment topologies
```

## 13. Handoff to Phase 048

Phase 048 may assume correctness and configurability are proven across Shan and external topologies. It can now optimize the generalized architecture using representative workloads without hiding correctness defects behind performance work.

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
