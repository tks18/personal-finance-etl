# Phase 12 — Wealth, Net Worth, Liquidity and Attribution

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 11.

## Phase outcome
Turn PFETL wealth marts into a complete personal balance-sheet, liquidity and net-worth-change analysis with asset-level drill.

## Inherited state
- Household analytics are complete.
- Shared period/filter semantics are stable.

## Files in scope
- `analytics/wealth.py`
- `pages/wealth.py`
- semantic registry extensions
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.core_monthly_fact`: book/market balances, assets/liabilities/net worth, foreign exposure, unrealized P&L, asset/FX P&L, attribution fields.
- `gold.wealth_asset_breakdown`: asset-subcategory opening/closing/market, liquidity, drawdown, contributions, flows, cumulative savings, runway.
- Silver asset dimensions and opening balances for drill/context.
- `gold.cashflow_efficiency_analytics`: liquidity ratio, debt/asset, real NW growth, emergency fund coverage.

## Required contracts at phase exit
- `WealthAnalytics.summary(period,filters)`.
- `asset_breakdown(period, asset filters)` returns monthly/asset grain.
- `net_worth_attribution(period)` exposes `Net_Savings_Flow + Market_Return_Flow + Attribution_Residual = Asset_Market_Delta` exactly as Core produced.

## Data and query semantics
- Use latest row for stock/balance metrics; sum only monthly flow fields over multi-month periods.
- Book and market net worth are separate series.
- Attribution residual is displayed explicitly; Studio never hides/reallocates it.
- Liquidity comes from PFETL asset classifications/Gold fields; do not reclassify accounts.

## UI / interaction specification
- KPIs: book/market NW, assets, liabilities, liquid assets, liquidity ratio, debt/assets, emergency coverage, foreign exposure, real NW growth.
- Charts: book vs market NW, asset group/subcategory composition, net-worth attribution waterfall, P&L/FX trend, drawdown/runway.
- Asset table drills to asset-subcategory metadata and monthly history.

## Implementation sequence
1. Implement wealth summary and asset breakdown queries.
2. Register wealth stock/flow metrics correctly.
3. Build attribution waterfall from canonical Gold components.
4. Join asset labels for drill.
5. Test stock/latest vs flow/sum semantics and attribution identity.

## Focused verification
- Attribution components reconcile to Gold `Asset_Market_Delta` within fixture tolerance.
- Latest net worth equals source row exactly.

## Edge cases and failure behaviour
- Missing market valuation: show book values and mark market unavailable; do not substitute.
- Liabilities may be zero/negative according to Core representation; do not force sign conventions.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add real-estate/manual valuation models.

## Exit criteria
- [ ] Wealth page supports balance sheet, liquidity, attribution and asset drill.

## Handoff to next phase
Phase 13 starts Investments.
