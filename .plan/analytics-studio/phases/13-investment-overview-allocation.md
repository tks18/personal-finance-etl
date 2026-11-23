# Phase 13 — Investment Overview and Allocation

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 12.

## Phase outcome
Expose the complete current portfolio state and every Gold allocation lens while preserving native investment grains.

## Inherited state
- Household/Wealth pages complete.

## Files in scope
- `analytics/investments.py`
- `pages/investments.py`
- semantic registry extensions
- `tests/test_investment_queries.py`

## Grounded PFETL / Studio inputs
- `gold.investment_portfolio_summary` ISIN/month grain with instrument/class/type/subtype/sector, values, P&L, weights, drift, harvest score.
- Gold allocation marts: `investment_by_isin`, `by_subtype`, `by_class`, `by_instrument_type`, `by_sector`, `by_industry`, `by_geo`, `by_country`, `by_currency`, plus `by_portfolio`.
- `silver.dim_instrument_master`, `dim_currency` for labels/filter vocabularies.

## Required contracts at phase exit
- `InvestmentAnalytics.portfolio_snapshot(period)` returns latest close current/book values and instrument rows.
- `allocation(dimension,period,filters)` accepts only the nine registered allocation dimensions and selects the corresponding Gold mart.
- Allocation rows carry current value, invested value, weight and P&L; no arbitrary dynamic table names outside whitelist.

## Data and query semantics
- For portfolio snapshots use latest `Closing_Date`/`Max_Closing_Date` inside period.
- Do not sum weights across rows; display native group weights.
- Local/base values remain separate and appear only where source mart provides them.
- Target/drift/rebalance flag are descriptive Core outputs, not trade instructions.

## UI / interaction specification
- Investments page sub-navigation: Overview, Performance, Lots, Realized & Reconciliation, Market Evidence.
- Overview cards: portfolio current/invested value, unrealized P&L, weight count, latest close.
- Allocation selector switches class/type/subtype/sector/industry/geo/country/currency/ISIN charts and table.
- ISIN row click opens instrument context and later links to Lots.

## Implementation sequence
1. Implement mart registry and allocation query dispatch.
2. Implement latest portfolio snapshot.
3. Join instrument/currency labels only where necessary.
4. Render treemap/bar/table views with consistent filters.
5. Test each allocation dimension maps to correct physical table and fixture totals.

## Focused verification
- All ten Gold investment aggregation tables receive a consumer path.
- No SQL table name comes directly from user text.

## Edge cases and failure behaviour
- Empty classification (`NULL sector`) groups as “Unclassified”.
- Different Gold marts may have different local/FX columns; page adapts to registered schema rather than assuming them.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not recompute portfolio weights from Silver in v1.

## Exit criteria
- [ ] Portfolio state and every allocation lens are usable.

## Handoff to next phase
Phase 14 adds performance/benchmark/FX/concentration using the same Investment service.
