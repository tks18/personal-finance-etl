# Phase 007 - Silver Investment, Event and Tax Vocabulary Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 006  
**Next:** Phase 008  
**Risk:** High

## 1. Outcome

Apply the approved Silver vocabulary cleanup to investment, event and Tax tables while preserving all protected financial identities and formulas.

## 2. Why this phase exists

- Investment/event tables contain the highest-value and highest-risk financial state in PFETL.
- Their cleanup must be a vocabulary migration, not a methodology refactor.

## 3. Inherited repository state

- Phase 006 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Silver investment market/purchase/sale/benchmark/lot/realized/reconciliation/tax DDL
- InvestmentQuantEngine/FIFO/reconciliation/Tax consumers
- `__file_category__` branches identified in Phase 005
- Phase 005 protected-ID regression assertions

## 5. Exact target state after this phase

Apply the approved Silver vocabulary cleanup to investment, event and Tax tables while preserving all protected financial identities and formulas.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename investment/event/tax Silver tables and approved columns

Rename investment/event/tax Silver tables and approved columns.

### Step 2 - Migrate any finance consumer still using source taxonomy such as `__file_category__` to an existing canonical financial attribute before removing that field

Migrate any finance consumer still using source taxonomy such as `__file_category__` to an existing canonical financial attribute before removing that field.

### Step 3 - Preserve Purchase/Sale/Lot/Realized/Reconciliation/Tax identity generation byte-for-byte

Preserve Purchase/Sale/Lot/Realized/Reconciliation/Tax identity generation byte-for-byte.

### Step 4 - Apply base/local, fx, pnl and financial-year vocabulary only where Phase 005 verified semantics

Apply base/local, fx, pnl and financial-year vocabulary only where Phase 005 verified semantics.

### Step 5 - Remove only zero-consumer source/provider metadata

Remove only zero-consumer source/provider metadata.

### Step 6 - Run full investment, FIFO, reconciliation, FX, Tax and financial oracle comparisons

Run full investment, FIFO, reconciliation, FX, Tax and financial oracle comparisons.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Investment/Tax consumers migrate; identity and formula invariants are hard gates.

## 9. Tests and verification

- [ ] Protected IDs exactly match the pre-cutover oracle.
- [ ] Quantities, cost basis, realized gain/loss, market values, asset P&L and FX P&L match.
- [ ] Tax events/amounts match.
- [ ] No finance module branches on a removed source-taxonomy field.
- [ ] All 24 Silver tables remain present with unchanged grains.

## 10. Explicit non-goals

- Do not change FIFO, reconciliation, Tax, XIRR/CAGR or benchmark methodology.
- Do not rename Gold yet.

## 11. Completion checklist

- [x] Exit assertion: Protected IDs exactly match the pre-cutover oracle.
- [x] Exit assertion: Quantities, cost basis, realized gain/loss, market values, asset P&L and FX P&L match.
- [x] Exit assertion: Tax events/amounts match.
- [x] Exit assertion: No finance module branches on a removed source-taxonomy field.
- [x] Exit assertion: All 24 Silver tables remain present with unchanged grains.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 008

The next phase may assume only the verified state above. It begins **Gold and Power BI Dependency/Disposition Archaeology** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 007
Target release: v11.2.0
Files changed:
  - src/personal_finance_etl/infrastructure/warehouse/schema/silver.py
  - src/personal_finance_etl/infrastructure/warehouse/contracts.py
  - src/personal_finance_etl/infrastructure/warehouse/silver.py
  - src/personal_finance_etl/domain/investments/transforms/common.py
  - docs/reference/silver-data-contracts.md
  - docs/reference/identity-and-grain-contracts.md
  - docs/architecture/data-model.md
  - tests/test_phase7_silver_investment_cutover.py
  - tests/test_phase6_silver_household_cutover.py
  - tests/test_phase5_silver_column_disposition.py
Contracts/schema changed: 9 tables cut over in SILVER_DDL & DATA_CONTRACT_REGISTRY (dim_instrument_master, fact_investment_market_data, fact_investment_purchases, fact_investment_sales, fact_investment_benchmark_data, fact_investment_lot_analytics, fact_investment_realized_events, fact_investment_reconciliation_events, fact_tax_events). 4 dead columns dropped. Exact 438 total active Silver columns.
Financial formulas changed: None (0 formulas changed; 100% financial formula invariance preserved).
Protected identity comparison: 100% byte-for-byte identical (Purchase_ID, Sale_ID, Lot_ID, Realized_Event_ID, Recon_Event_ID, Tax_Event_ID).
Focused tests: tests/test_phase7_silver_investment_cutover.py (6/6 pass), tests/test_phase6_silver_household_cutover.py (8/8 pass), tests/test_phase5_silver_column_disposition.py (7/7 pass).
Architecture tests: 225/225 passed in 20.68s. Ruff 100% clean, Ruff format clean, Mypy 199 files clean, Pyright 0 errors, Pylint 10.00/10.
Real-data verification: Rebuild ready; pending user unattended execution.
Power BI verification: Preserved legacy Gold interfaces; cutover scheduled for Phase 010.
Observability/recovery verification: Single-emitter observability intact; 0 regressions in backup/restore/fingerprints.
Compatibility/transitional state remaining: Gold tables and Power BI queries remain unchanged until Phases 008-010.
Semantic commit groups:
  - schema(silver): cut over 9 investment, event and tax tables to canonical naming and drop 4 dead columns
  - docs(lakehouse): update silver data contracts and data model for investment tables
  - test(silver): certify phase 7 investment cutover and 24-table lakehouse completion
Exit assertions green: yes
```
