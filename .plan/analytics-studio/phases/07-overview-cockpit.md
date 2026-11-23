# Phase 07 — Overview Cockpit

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 06.

## Phase outcome
Create Shan’s default monthly cockpit using existing Gold/Control Plane truth, with concise KPI health and drill links into later domain pages.

## Inherited state
- Semantic periods/metrics and UI shell exist.
- Domain pages beyond Overview remain placeholders.

## Files in scope
- `analytics/overview.py`
- `pages/overview.py`
- extend `semantic/metrics.py` with overview-only metrics
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.core_monthly_fact`: net worth, income, expense, net cashflow, attribution, inflation-adjusted core expense.
- `gold.cashflow_efficiency_analytics`: savings/investment rates, passive coverage, active dependency, liquidity, debt/asset, real NW growth.
- `gold.investment_by_portfolio`: value, XIRR, benchmark, active return, concentration, LTCG ladder.
- `gold.wealth_fire_analytics`: FI coverage/gap/P50/probability/savings rates.
- `gold.tax_financial_year_summary`: indicative tax exposure and estimate completeness.
- `cp_runs` + `meta.m_Table_Row_Counts`: latest run/data-health context.

## Required contracts at phase exit
- `OverviewService.get_snapshot(profile,period,run)` returns a typed `OverviewSnapshot` containing KPI groups and small chart frames.
- Each KPI records value, format, source dataset/as-of date and optional drill route.
- No KPI is recomputed from lower-level transactions when an authoritative Gold field exists.

## Data and query semantics
- Monthly snapshot selects the latest row in period for stock metrics and sums only additive flow fields across multi-month custom periods.
- Portfolio return/XIRR/ratios remain native/latest values; never sum/average.
- Tax exposure uses selected FY associated with the period; label incomplete estimates explicitly.

## UI / interaction specification
- Top row: market net worth, monthly net cashflow, savings rate, portfolio value, indicative tax exposure, FI coverage.
- Secondary cards: passive coverage, active dependency, liquidity/runway, XIRR/active return, HHI/effective holdings, latest PFETL run health.
- Charts: net-worth trend with attribution, income vs expense/net cashflow, portfolio value/return, FIRE coverage/probability.
- Every card/chart has source/as-of tooltip and drill navigation target.

## Implementation sequence
1. Implement typed overview queries using Gold first.
2. Register only the metrics used here with correct aggregation.
3. Build compact snapshot DTOs; keep Plotly construction in `pages/overview.py` or reusable `ui/charts.py` if needed by two+ pages.
4. Render cards/charts and data-health banner.
5. Add numerical fixture assertions for latest-month and rolling-period behavior.

## Focused verification
- Fixture card values exactly equal Gold fixture fields.
- Custom 3-month period sums flows but returns latest stock/ratio metrics.
- No overview query touches Bronze.

## Edge cases and failure behaviour
- Missing Tax/FIRE row: show unavailable card, not zero.
- Locked DuckDB: preserve profile/run status and show analytical locked state.
- No completed PFETL run: no headline finance values.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add custom dashboard composition.
- Do not create new financial scores.

## Exit criteria
- [ ] Overview is useful as the normal monthly landing page.
- [ ] All displayed values have correct source/as-of semantics.
- [ ] Drill links target the fixed domain routes.

## Handoff to next phase
Phase 08 may build Household income analytics independently.
