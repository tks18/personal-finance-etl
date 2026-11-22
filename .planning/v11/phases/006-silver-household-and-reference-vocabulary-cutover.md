# Phase 006 - Silver Household and Reference Vocabulary Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 005  
**Next:** Phase 007  
**Risk:** High

## 1. Outcome

Apply the approved Silver vocabulary cleanup to household/reference tables only, preserving all existing table grains and values.

## 2. Why this phase exists

- Splitting Silver implementation keeps the 2–3 hour sprint honest and isolates household/reference blast radius from investments.
- This phase converts obvious canonical vocabulary without touching protected investment identities.

## 3. Inherited repository state

- Phase 005 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Silver calendar/income/expense/asset/currency/benchmark/macro/opening-balance/FX DDL and transforms
- household ledger/wealth consumers
- Gold household producers
- Phase 005 disposition manifest

## 5. Exact target state after this phase

Apply the approved Silver vocabulary cleanup to household/reference tables only, preserving all existing table grains and values.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename the household/reference Silver physical tables according to the approved 24-table map

Rename the household/reference Silver physical tables according to the approved 24-table map.

### Step 2 - Apply approved column renames only; preserve units and value semantics exactly

Apply approved column renames only; preserve units and value semantics exactly.

### Step 3 - Remove only Phase-005-proven dead provenance/source columns

Remove only Phase-005-proven dead provenance/source columns.

### Step 4 - Update contract IDs only where the plan explicitly chooses semantic IDs; keep publication order/grain unchanged

Update contract IDs only where the plan explicitly chooses semantic IDs; keep publication order/grain unchanged.

### Step 5 - Migrate ledger/wealth/Gold/test consumers in the same semantic commit groups

Migrate ledger/wealth/Gold/test consumers in the same semantic commit groups.

### Step 6 - Run household monthly totals, balances, net-worth, FX and FIRE regression against the oracle

Run household monthly totals, balances, net-worth, FX and FIRE regression against the oracle.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Household/wealth consumers and tests migrate to new Silver vocabulary.

## 9. Tests and verification

- [ ] All targeted household/reference Silver tables exist under approved names and old names do not.
- [ ] No table grain or row count changes unexpectedly.
- [ ] Income/expense/transfer/opening-balance values are equivalent.
- [ ] Net worth and FIRE outputs remain equivalent.
- [ ] No unapproved source/provenance column was removed.

## 10. Explicit non-goals

- Do not modify investment/event/tax Silver tables.
- Do not add new analytics or change Gold physical names.

## 11. Completion checklist

- [x] Exit assertion: All targeted household/reference Silver tables exist under approved names and old names do not.
- [x] Exit assertion: No table grain or row count changes unexpectedly.
- [x] Exit assertion: Income/expense/transfer/opening-balance values are equivalent.
- [x] Exit assertion: Net worth and FIRE outputs remain equivalent.
- [x] Exit assertion: No unapproved source/provenance column was removed.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 007

The next phase may assume only the verified state above. It begins **Silver Investment, Event and Tax Vocabulary Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 006
Target release: v11.2.0
Files changed:
  - src/personal_finance_etl/infrastructure/warehouse/schema/silver.py
  - src/personal_finance_etl/infrastructure/warehouse/contracts.py
  - src/personal_finance_etl/infrastructure/warehouse/silver.py
  - src/personal_finance_etl/domain/household/transforms/asset_dimensions.py
  - src/personal_finance_etl/domain/household/transforms/expense_dimensions.py
  - src/personal_finance_etl/domain/household/transforms/income_dimensions.py
  - src/personal_finance_etl/domain/household/transforms/reference_dimensions.py
  - src/personal_finance_etl/domain/household/transforms/transactions.py
  - src/personal_finance_etl/config/financial_rules/model.py
  - src/personal_finance_etl/domain/tax/classification.py
  - tests/test_phase6_silver_household_cutover.py
  - tests/test_phase3_infrastructure.py
  - tests/test_phase5_silver_column_disposition.py
  - tests/test_phase7_tax_domain.py
  - docs/reference/silver-data-contracts.md
  - docs/reference/identity-and-grain-contracts.md
  - docs/architecture/data-model.md
  - docs/configuration/financial-rules-reference.md
  - .planning/v11/phases/006-silver-household-and-reference-vocabulary-cutover.md
Contracts/schema changed:
  - 15 household/reference tables cut over to dimensional names: silver.dim_calendar, silver.dim_income_category, silver.dim_income_subcategory, silver.dim_expense_category, silver.dim_expense_subcategory, silver.dim_asset_category, silver.dim_asset_subcategory, silver.dim_currency, silver.fact_currency_fx_rates, silver.fact_income_transactions, silver.fact_expense_transactions, silver.fact_transfer_transactions, silver.fact_opening_balances, silver.dim_benchmark_master, silver.ref_financial_year_parameters
  - 92 proven dead columns dropped from Silver DDL and transform outputs
  - 9 investment/event/tax tables strictly preserved under legacy naming
Financial formulas changed: None (0 formula modifications)
Protected identity comparison: 100% byte-for-byte match (UID, Date, ISIN, etc.)
Focused tests: tests/test_phase6_silver_household_cutover.py (8/8 passed)
Architecture tests: Full test suite 219/219 passed in 15.20s; full quality gate green
Real-data verification: Shan verified live pipeline rebuild and financial equivalence with 0 regressions
Power BI verification: Not in scope for Phase 006 (Phase 008 owns Power BI query audit/migration)
Observability/recovery verification: Single-emitter and event contracts verified green
Compatibility/transitional state remaining: 9 investment/tax tables remain under legacy naming awaiting Phase 007
Semantic commit groups:
  1. refactor(warehouse): cut over 15 household and reference tables to dimensional names
  2. refactor(household): drop dead columns from household and reference transforms
  3. test(silver): add phase 6 household cutover tests and update existing suites
  4. docs(warehouse): update silver contracts and architecture for phase 6 cutover
Exit assertions green: yes
```
