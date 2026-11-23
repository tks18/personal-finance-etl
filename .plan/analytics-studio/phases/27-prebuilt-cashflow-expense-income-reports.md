# Phase 27 — Prebuilt Cashflow, Expense and Income Reports

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 26.

## Phase outcome
Implement Cashflow & Budget Review, Expense & Lifestyle Review, and Income Resilience Review for recurring monthly/FY household review.

## Inherited state
- First three built-ins certified.

## Files in scope
- `reports/templates/cashflow.py`
- `reports/templates/expense.py`
- `reports/templates/income.py`
- registry/tests

## Grounded PFETL / Studio inputs
- Household analytics from Phases 08–11.
- Gold forecast_budget_variance, cashflow_activity_summary, expense/income breakdown, efficiency metrics.

## Required contracts at phase exit
- Stable IDs: `cashflow_budget_review`, `expense_lifestyle_review`, `income_resilience_review`.

## Data and query semantics
- Cashflow default selected month/FYTD; Expense/Income rolling 12M.
- Transaction appendices are bounded and optional; large full transaction exports belong XLSX/CSV, not huge PDF tables.

## UI / interaction specification
- Built-in cards with supported household filters and custom period controls.

## Implementation sequence
1. Define block order/content for all three.
2. Include budget health/reconciliation in Cashflow; core/non-core + real growth in Expense; active/passive/coverage/dependency in Income.
3. Test filter propagation and exported provenance.

## Focused verification
- Report values equal corresponding analytics service outputs.
- No report template recomputes classifications.

## Edge cases and failure behaviour
- No transactions: appendix empty but summary report renders.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No new household metrics.

## Exit criteria
- [ ] Six total built-in reports are certified.

## Exact report composition
### Cashflow & Budget Review
- **Default period:** selected month; allow FYTD and custom multi-month periods.
- **Blocks:** provenance; budget-health flags; target-vs-actual income/core/non-core/investment; savings/investment-rate cards; operating/investing/financing/internal-transfer statement; opening/closing cash; calculated vs actual net cash movement; unreconciled-difference warning; emergency-fund gap/runway.
- **Filters:** category/asset only where the underlying Household service supports them; do not apply a filter to an incompatible Gold mart and pretend it was respected.
- **Acceptance:** report fields equal `forecast_budget_variance` and `cashflow_activity_summary` service outputs exactly.

### Expense & Lifestyle Review
- **Default period:** rolling 12 months; allow selected FY/custom range.
- **Blocks:** total/core/non-core expense KPIs; cash/non-cash split; nominal vs inflation-adjusted core-expense trend; real core-expense growth; category/group contribution; discretionary/investment/fixed grouping; trailing spend; expense-to-NW; bounded top-transaction appendix.
- **Filters:** category/group, core flag, discretionary/investment/spend type, asset/account.
- **Acceptance:** all classification comes from PFETL Gold/Silver flags; report code contains no description regex or category inference.

### Income Resilience Review
- **Default period:** rolling 12 months; allow FY/custom range.
- **Blocks:** total/active/passive/dividend/interest KPIs; active-vs-passive trend; category/group composition; passive-income share; passive-income/core-expense coverage; active-income dependency; trailing income; bounded source transaction appendix.
- **Filters:** category/group, active/passive classification, asset/account.
- **Acceptance:** coverage/dependency are native PFETL metrics, never averaged across periods.

## Handoff to next phase
Phase 28 adds investment reports.
