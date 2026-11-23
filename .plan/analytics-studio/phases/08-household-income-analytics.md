# Phase 08 — Household Income Analytics

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 07.

## Phase outcome
Expose income composition, trends, resilience and transaction drill using canonical Gold summaries and Silver classifications.

## Inherited state
- Overview and shared semantics exist.
- Household route exists as a placeholder.

## Files in scope
- `analytics/household.py`
- `pages/household.py`
- extend metric/dataset registry
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.cashflow_income_breakdown` 14 cols: monthly category/group + active/passive/dividend/interest/non-cash flags, totals, trailing 3M, YTD.
- `gold.cashflow_efficiency_analytics`: Active_Income, Passive_Income, Dividend_Income, Interest_Income, Passive_Income_Core_Expense_Coverage_Ratio, Active_Income_Dependency_Pct.
- `silver.dim_income_category`, `silver.dim_income_subcategory`.
- `silver.fact_income_transactions`: UID/date/asset/category/currency/description/base/account/local amounts and income flags.

## Required contracts at phase exit
- `HouseholdAnalytics.income_summary(period,filters)` returns KPIs + monthly trend + composition tables.
- `income_transactions(...)` returns bounded/paged transaction rows with joined labels.
- Register safe income metrics: total/active/passive/dividend/interest income are additive; coverage/dependency are latest/native ratios.

## Data and query semantics
- Use Gold for monthly/category summaries; use Silver fact only for drill.
- Base amount is the canonical comparable amount; local/account amounts are detail columns, not re-converted by Studio.
- Income flags come from PFETL dimensions/facts; do not reclassify descriptions.

## UI / interaction specification
- Household page gets sub-navigation/tabs: Income, Expense, Budget & Cashflow, Transactions; this phase fully implements Income only.
- Income KPIs: total, active/passive mix, dividend, interest, passive/core coverage, active dependency.
- Charts: monthly income trend, active/passive stacked, category/group bars, cumulative YTD.
- Clicking category/group opens transaction table filtered to the same period/classification.

## Implementation sequence
1. Implement Gold income query service and Silver drill query.
2. Join category/subcategory labels only at query boundary.
3. Add period/category/group/active-passive filters.
4. Render income tab with Plotly and bounded table.
5. Test exact totals and drill row identities.

## Focused verification
- Sum of grouped income equals Gold total for fixture period.
- Drill rows sum to expected Silver fact amount for chosen category.
- Ratio fields are not aggregated across months.

## Edge cases and failure behaviour
- No income in period: zero-flow charts/empty drill, not failure.
- Null category group displayed as “Unclassified” without modifying source.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add income forecasting or anomaly detection.

## Exit criteria
- [ ] Income tab provides composition, resilience and transaction evidence.
- [ ] Guided metric registry knows income-safe dimensions/aggregation.

## Handoff to next phase
Phase 09 extends the same Household service/page with Expense.
