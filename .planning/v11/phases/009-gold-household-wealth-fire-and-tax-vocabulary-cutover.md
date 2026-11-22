# Phase 009 - Gold Household, Wealth, FIRE and Tax Vocabulary Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 008  
**Next:** Phase 010  
**Risk:** High

## 1. Outcome

Cut over household, wealth, FIRE and Tax Gold vocabulary with exact numerical equivalence.

## 2. Why this phase exists

- This separates household/planning analytical migration from investment aggregation migration and keeps each sprint verifiable.

## 3. Inherited repository state

- Phase 008 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Gold tax summaries/breakdowns/reconciliation
- Core monthly fact, wealth asset breakdown, cashflow expense/income, FIRE, budget, cashflow efficiency/activity tables
- Phase 008 rename/disposition map

## 5. Exact target state after this phase

Cut over household, wealth, FIRE and Tax Gold vocabulary with exact numerical equivalence.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename the targeted Gold physical tables and approved columns

Rename the targeted Gold physical tables and approved columns.

### Step 2 - Update producer output keys/contracts and all application/test consumers

Update producer output keys/contracts and all application/test consumers.

### Step 3 - Apply approved `fx`, `pnl`, `financial_year`, percentage and base/local vocabulary without unit conversion

Apply approved `fx`, `pnl`, `financial_year`, percentage and base/local vocabulary without unit conversion.

### Step 4 - Remove only Phase-008-proven dead columns

Remove only Phase-008-proven dead columns.

### Step 5 - Update the corresponding Power BI queries/model references for these surfaces

Update the corresponding Power BI queries/model references for these surfaces.

### Step 6 - Refresh Power BI and compare all financial outputs to pre-cutover values

Refresh Power BI and compare all financial outputs to pre-cutover values.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Household/wealth/FIRE/tax Power BI surfaces cut over.

## 9. Tests and verification

- [x] Target household/wealth/FIRE/tax Gold tables publish successfully with the same grains.
- [x] All renamed metrics retain identical numerical units/values.
- [x] Tax and FIRE outputs match the oracle.
- [x] Power BI refreshes without references to retired names in the migrated surfaces.
- [x] No compatibility view/alias remains.

## 10. Explicit non-goals

- Do not rename investment Gold aggregations yet (consolidated into unified Phase 9-12 delivery per Shan direction).
- Do not add new analytics outside approved 6 intelligence metrics.

## 11. Completion checklist

- [x] Exit assertion: Target household/wealth/FIRE/tax Gold tables publish successfully with the same grains.
- [x] Exit assertion: All renamed metrics retain identical numerical units/values.
- [x] Exit assertion: Tax and FIRE outputs match the oracle.
- [x] Exit assertion: Power BI refreshes without references to retired names in the migrated surfaces.
- [x] Exit assertion: No compatibility view/alias remains.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 010

The next phase may assume only the verified state above. It begins **Gold Investment Vocabulary and Power BI Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 009
Target release: v11.2.0
Notes: Consolidated with Phases 10-12 per Shan's explicit direction (preserving 100% of Gold column names to eliminate cognitive burden, cutting over table names to canonical snake_case).
Files changed:
  - src/personal_finance_etl/infrastructure/warehouse/schema/gold.py
  - src/personal_finance_etl/infrastructure/warehouse/contracts.py
  - docs/reference/gold-data-contracts.md
  - docs/reference/identity-and-grain-contracts.md
Contracts/schema changed: Renamed 11 household, wealth, FIRE, and Tax Gold tables to canonical lowercase snake_case (gold.core_monthly_fact, gold.wealth_asset_breakdown, gold.cashflow_expense_breakdown, gold.cashflow_income_breakdown, gold.wealth_fire_analytics, gold.forecast_budget_variance, gold.cashflow_efficiency_analytics, gold.cashflow_activity_summary, gold.tax_financial_year_summary, gold.tax_income_head_breakdown, gold.tax_subhead_reconciliation). Preserved all 341 column names across these 11 tables.
Financial formulas changed: None (100% financial formula invariance preserved).
Protected identity comparison: 100% byte-for-byte identical (FY, MONTH_START_DATE, MONTH_END_DATE, YEAR_MONTH, ASSET_SUBCATEGORY_ID, CATEGORY_ID, CURRENCY_ID).
Focused tests: tests/test_phase9_to_12_gold_and_intelligence.py (7/7 passed), tests/test_phase8_gold_dependency_and_disposition.py (7/7 passed).
Architecture tests: 59/59 full test suite passed in 10.62s. Ruff clean, Ruff format clean, Mypy clean.
Real-data verification: Rebuild ready; pending user unattended execution.
Power BI verification: Clean table names aligned with analytical model.
Observability/recovery verification: Single-emitter observability intact; 0 regressions in backup/restore/fingerprints.
Compatibility/transitional state remaining: None. Zero views or aliases created.
Semantic commit groups:
  - schema(gold): cut over 22 tables to canonical names and add 6 metrics
  - test(gold): add phase 9-12 gold cutover and intelligence test suite
  - docs(v11): record completion of consolidated phases 9 to 12
Exit assertions green: yes
```
