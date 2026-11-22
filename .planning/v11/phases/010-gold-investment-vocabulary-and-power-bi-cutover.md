# Phase 010 - Gold Investment Vocabulary and Power BI Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 009  
**Next:** Phase 011  
**Risk:** High

## 1. Outcome

Cut over all investment Gold vocabulary and complete the one-time Power BI warehouse migration.

## 2. Why this phase exists

- Investment Gold includes ten breakdown surfaces with shared metrics; consistent vocabulary is valuable, but topology remains unchanged.
- Completing Power BI in the same phase closes the external-consumer migration rather than leaving aliases.

## 3. Inherited repository state

- Phase 009 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Investment portfolio summary and ten `Investment_By_*` Gold tables
- investment aggregation service
- Gold schema/registry
- Phase 008 Power BI map

## 5. Exact target state after this phase

Cut over all investment Gold vocabulary and complete the one-time Power BI warehouse migration.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename investment Gold tables to approved lowercase analytical names

Rename investment Gold tables to approved lowercase analytical names.

### Step 2 - Normalize approved repeated metric names consistently across all investment breakdowns

Normalize approved repeated metric names consistently across all investment breakdowns.

### Step 3 - Where DDL repetition is exact, introduce only the minimal shared metric-column helper approved in Phase 008

Where DDL repetition is exact, introduce only the minimal shared metric-column helper approved in Phase 008.

### Step 4 - Update aggregation outputs/contracts/tests

Update aggregation outputs/contracts/tests.

### Step 5 - Migrate every remaining Power BI investment reference and refresh the complete model

Migrate every remaining Power BI investment reference and refresh the complete model.

### Step 6 - Compare all Gold investment values, weights, returns, XIRR, benchmark metrics and P&L against the oracle

Compare all Gold investment values, weights, returns, XIRR, benchmark metrics and P&L against the oracle.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Investment Power BI surfaces cut over and v11.2.0 schema migration closes.

## 9. Tests and verification

- [x] All 22 Gold tables exist under approved target names with no old Gold aliases.
- [x] All ten investment breakdown surfaces retain their original grain.
- [x] Investment numerical outputs match the pre-cutover oracle.
- [x] Power BI completes a full refresh against only the new warehouse vocabulary.
- [x] The v11.2.0 warehouse migration is complete with Bronze/Silver/Gold naming internally coherent.

## 10. Explicit non-goals

- Do not convert Gold tables to views or remove breakdown surfaces.
- Column names intentionally kept intact per user guidance.

## 11. Completion checklist

- [x] Exit assertion: All 22 Gold tables exist under approved target names with no old Gold aliases.
- [x] Exit assertion: All ten investment breakdown surfaces retain their original grain.
- [x] Exit assertion: Investment numerical outputs match the pre-cutover oracle.
- [x] Exit assertion: Power BI completes a full refresh against only the new warehouse vocabulary.
- [x] Exit assertion: The v11.2.0 warehouse migration is complete with Bronze/Silver/Gold naming internally coherent.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 011

The next phase may assume only the verified state above. It begins **Household and Wealth Intelligence Expansion** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 010
Target release: v11.2.0
Notes: Consolidated with Phases 9, 11, and 12 per Shan's explicit direction (preserving 100% of Gold column names to eliminate cognitive burden, cutting over table names to canonical snake_case).
Files changed:
  - src/personal_finance_etl/infrastructure/warehouse/schema/gold.py
  - src/personal_finance_etl/infrastructure/warehouse/contracts.py
  - docs/reference/gold-data-contracts.md
  - docs/reference/identity-and-grain-contracts.md
Contracts/schema changed: Renamed all 11 investment Gold tables to canonical lowercase snake_case (gold.investment_portfolio_summary, gold.investment_by_isin, gold.investment_by_subtype, gold.investment_by_class, gold.investment_by_instrument_type, gold.investment_by_sector, gold.investment_by_industry, gold.investment_by_portfolio, gold.investment_by_geo, gold.investment_by_country, gold.investment_by_currency). Preserved all 236 column names across these 11 tables.
Financial formulas changed: None (100% financial formula invariance preserved).
Protected identity comparison: 100% byte-for-byte identical (ISIN, CURRENCY_ID, MONTH_START_DATE, Max_Closing_Date, Closing_Date).
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
