# Phase 09 — Household Expense Analytics

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 08.

## Phase outcome
Expose core/non-core, discretionary/investment/fixed grouping, real expense growth and expense transaction drill using PFETL classifications.

## Inherited state
- Household Income is complete.
- `analytics/household.py` and page tab structure exist.

## Files in scope
- `analytics/household.py`
- `pages/household.py`
- semantic registry extensions
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.cashflow_expense_breakdown`: category/group, Spend_Type, core/investment/discretionary flags, monthly/cash/non-cash spend, trailing 3M, YTD.
- `gold.core_monthly_fact`: Inflation_Adjusted_Core_Expense, Real_Core_Expense_Growth_Pct.
- `gold.cashflow_efficiency_analytics`: Core_Expense, NonCore_Expense, shares, expense MoM/trailing averages, Expense_to_NW_Ratio.
- Silver expense dimensions/fact for drill.

## Required contracts at phase exit
- `HouseholdAnalytics.expense_summary(...)`.
- `expense_transactions(...)` joins category/account/currency labels and returns base/account/local amounts.
- Expense metrics are positive analytical outflows as represented by Gold; do not flip signs based on assumptions.

## Data and query semantics
- Use Gold-provided `Is_Core_Expense`, `Is_Investment`, `Is_Discretionary`, `Spend_Type`; Studio does not rerun regex/grouping rules from FinancialRules.
- Real core-expense growth is consumed directly from `core_monthly_fact`.
- Transactions retain source description/paid fields for audit.

## UI / interaction specification
- Expense KPIs: total, core, non-core, cash/non-cash, real core growth, expense/NW.
- Charts: monthly core vs non-core, category/group contribution, trailing spend, nominal vs inflation-adjusted core expense where available.
- Filters: category/group, core, discretionary, investment, spend type, asset/account.
- Category chart drill opens canonical expense transactions.

## Implementation sequence
1. Implement Gold queries and Silver drill.
2. Register additive expense metrics and native ratio/growth metrics.
3. Add expense filters and cross-filter handoff to Transactions tab.
4. Render empty/null labels consistently.
5. Test grouped totals, core split and real-growth passthrough.

## Focused verification
- Core+non-core totals reconcile to fixture total within source rounding.
- Inflation-adjusted values match Gold exactly.
- Transaction drill amount matches selected group.

## Edge cases and failure behaviour
- Investment-like expenses remain whatever PFETL classified; do not reinterpret.
- Negative/correction transactions are displayed as source values and included according to canonical Gold totals.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not build budgeting here; Phase 10 owns budget/cashflow.

## Exit criteria
- [ ] Expense tab is complete with lifestyle/core analysis and evidence drill.

## Handoff to next phase
Phase 10 builds Budget & Cashflow on the existing Household page.
