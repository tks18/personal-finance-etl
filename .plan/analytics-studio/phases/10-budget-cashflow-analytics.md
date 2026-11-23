# Phase 10 — Budget and Cashflow Analytics

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 09.

## Phase outcome
Use the entire budget variance and cashflow activity marts to explain monthly financial operation, not just savings rate.

## Inherited state
- Income and Expense tabs are complete.

## Files in scope
- `analytics/household.py`
- `pages/household.py`
- semantic registry extensions
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.forecast_budget_variance` 27 cols including overspend/underfunded/volatility/healthy flags, budget targets, actuals, emergency gap, allocation rules, runway.
- `gold.cashflow_activity_summary` 24 cols: opening/closing cash, operating/investing/financing/internal transfer flows, calculated cashflow and unreconciled difference.
- `silver.fact_transfer_transactions` for transfer drill with `ADJUSTED_DATE_FOR_ANALYSIS` and `TRANSFER_TYPE`.
- FinancialRules budget percentages are context/overlay only; Gold fields remain canonical output.

## Required contracts at phase exit
- `budget_summary(period)` returns monthly budget target vs actual + flags.
- `cashflow_statement(period)` returns operating/investing/financing/internal-transfer flows and reconciliation.
- `transfer_transactions(...)` provides drill evidence.

## Data and query semantics
- Budget target/actual fields are consumed directly; no recomputation of PFETL budgeting rules.
- Cashflow categories use Gold `cashflow_activity_summary`; internal transfers are not treated as income/expense.
- `Unreconciled_Difference` is surfaced as a health signal, never forced to zero.

## UI / interaction specification
- Budget & Cashflow tab sections: budget health flags, target-vs-actual grouped bars, savings/investment outcome, emergency gap/runway, cashflow waterfall/statement, reconciliation card.
- Drill from investing/financing/internal transfer to filtered transfer transactions where mapping exists.

## Implementation sequence
1. Implement two queries and transfer drill.
2. Add warning styling for overspent/underfunded/unreconciled flags.
3. Render rule target percentages from Gold and optionally show selected-run FinancialRules snapshot in tooltip.
4. Test budget/actual passthrough and cashflow identity using fixture.

## Focused verification
- Fixture calculated net cashflow and unreconciled difference match Gold.
- All budget flags render correct status semantics.

## Edge cases and failure behaviour
- Zero-income month: show PFETL runway/flags as provided.
- Missing transfer rows: drill empty without hiding Gold activity.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not create a budgeting editor; Core FinancialRules owns inputs.

## Exit criteria
- [ ] Budget & Cashflow tab uses every meaningful field family in both Gold marts.

## Handoff to next phase
Phase 11 completes Household with a unified transaction/classification explorer.
